#!/usr/bin/env python3
"""汉字字形硬校验模块 —— agent 校验闭环的"确定性尺子"。

设计原则（对应闭环图的 ③ 自动校验层）：
- 只做能用代码确定的检查：结构合法性、坐标范围、bbox 合理性、近似重复、与现版本 diff。
- 审美/笔顺"好不好"交给上层 VLM/盲评 + 人工 the eye，这里不假装能判。
- 纯标准库，供 server.py import 复用。
"""
import math

CANVAS = 1024          # hanzi-writer-data 坐标轴范围 0..1024
OOB_MARGIN = 60        # 允许笔画略微出界
MIN_SPAN = 80          # 字形有效跨度的下限（过小视为废数据）
GRID = 16              # 近似重复检测的归一化网格边长


def _nums(point):
    """把一个 [x,y] 点转为 float 对，失败返回 None。"""
    try:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            return None
        return float(point[0]), float(point[1])
    except (TypeError, ValueError):
        return None


def validate_glyph(strokes, medians, ref=None, source="manual-fix"):
    """校验单个候选字形，返回结构化报告。

    strokes : list[str]  每笔的 SVG path
    medians : list[list[[x,y],...]]  每笔中轴点
    ref     : dict | None  当前正式版本 {"strokes":..., "medians":...}，用于 diff
    source  : str  候选来源（arphic-reextract / manual-fix / ai-generated）
    """
    errors, warnings = [], []

    if not isinstance(strokes, list) or not strokes:
        errors.append("strokes 为空或不是数组")
        strokes = []
    if not isinstance(medians, list) or not medians:
        errors.append("medians 为空或不是数组")
        medians = []

    if strokes and medians and len(strokes) != len(medians):
        errors.append("轮廓数(%d)与中轴数(%d)不一致" % (len(strokes), len(medians)))

    n = min(len(strokes), len(medians)) if (strokes and medians) else 0
    pts = []
    for i in range(n):
        s, m = strokes[i], medians[i]
        if not isinstance(s, str) or not s.strip():
            errors.append("第%d笔轮廓为空" % (i + 1))
        elif not s.lstrip().upper().startswith("M"):
            warnings.append("第%d笔 SVG 路径未以 M 起始" % (i + 1))
        if not isinstance(m, list) or len(m) < 2:
            errors.append("第%d笔中轴点少于 2 个，无法确定笔尖轨迹" % (i + 1))
            continue
        ok = True
        for p in m:
            xy = _nums(p)
            if xy is None:
                errors.append("第%d笔含非法坐标点" % (i + 1))
                ok = False
                break
            pts.append(xy)
        if not ok:
            continue

    if not pts:
        errors.append("没有任何有效中轴点，字形无法渲染")

    bbox, span = None, 0.0
    if pts:
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)
        span = round(max(xmax - xmin, ymax - ymin), 1)
        bbox = {"xmin": round(xmin, 1), "xmax": round(xmax, 1),
                "ymin": round(ymin, 1), "ymax": round(ymax, 1)}
        oob = sum(1 for x, y in pts
                  if not (-OOB_MARGIN <= x <= CANVAS + OOB_MARGIN
                          and -OOB_MARGIN <= y <= CANVAS + OOB_MARGIN))
        if oob:
            warnings.append("%d 个中轴点超出画布 %d±%d" % (oob, CANVAS // 2, OOB_MARGIN))
        if span < MIN_SPAN:
            errors.append("字形跨度仅 %s，疑似无效或退化数据" % span)
        elif span > CANVAS + 120:
            warnings.append("字形跨度 %s 异常大" % span)

    # 与当前正式版本对比（diff 而非覆盖）
    diff = {}
    if ref is not None:
        ref_s = ref.get("strokes", [])
        diff["refStrokeCount"] = len(ref_s)
        diff["strokeCountDelta"] = n - len(ref_s)
        if n != len(ref_s):
            warnings.append("笔画数相对现版本变化：%d → %d" % (len(ref_s), n))
        try:
            diff["identical"] = (strokes == ref_s and medians == ref.get("medians", []))
            if diff["identical"]:
                warnings.append("候选与当前版本完全相同，无需提交")
        except Exception:
            diff["identical"] = None

    # 来源风险提示
    if source == "ai-generated":
        warnings.append("来源标记为 AI 生成：笔顺/笔画数须经独立评审确认，勿仅凭视觉通过")

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "strokeCount": n,
        "bbox": bbox,
        "span": span,
        "diff": diff,
        "source": source,
    }


def grid_signature(medians, g=GRID):
    """把字形中轴点归一化到 g×g 网格，返回占据格集合，用于粗粒度近似比对。"""
    pts = [xy for m in (medians or []) for xy in (_nums(p) for p in m) if xy]
    if not pts:
        return frozenset()
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)
    sx = (xmax - xmin) or 1.0
    sy = (ymax - ymin) or 1.0
    cells = set()
    for x, y in pts:
        cx = min(g - 1, max(0, int((x - xmin) / sx * g)))
        cy = min(g - 1, max(0, int((y - ymin) / sy * g)))
        cells.add((cx, cy))
    return frozenset(cells)


def iou(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def find_similar(char, medians, library, threshold=0.92, top=3):
    """在字库中查找与候选高度相似的"其它字"，防止把别的字复制成候选。

    library: {字: {"strokes":..., "medians":...}}
    返回按相似度降序的 [{char, iou}]，已排除本字。
    """
    sig = grid_signature(medians)
    if not sig:
        return []
    out = []
    for ch, data in library.items():
        if ch == char:
            continue
        score = iou(sig, grid_signature(data.get("medians", [])))
        if score >= threshold:
            out.append({"char": ch, "iou": round(score, 3)})
    out.sort(key=lambda x: -x["iou"])
    return out[:top]


def summarize(report):
    """把报告压成一行人可读摘要，供 MCP 返回。"""
    tag = "PASS" if report["ok"] else "FAIL"
    bits = ["%s" % tag, "%d 笔" % report["strokeCount"]]
    if report["errors"]:
        bits.append("错误:" + "; ".join(report["errors"]))
    if report["warnings"]:
        bits.append("注意:" + "; ".join(report["warnings"]))
    return " · ".join(bits)
