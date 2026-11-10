#!/usr/bin/env python3
"""Agent 字形自动修复引擎 —— 反馈驱动的重画闭环（GitHub issue 可直接触发）。

角色边界（延续 server.py 的权限设计）：
  agent 只能「上报 / 重画 / 测量」，绝不自动采纳、绝不写正式字库。
  本脚本产出的是待审候选（hanzi-revisions.json），最终裁决在 hanzi-review.html 人工审阅页。

三种驱动入口：
  python3 agent_fix.py --issue-json event.json --comment-file comment.md --out result.json
      GitHub issues 事件（由 .github/workflows/agent-fix.yml 调用）
  python3 agent_fix.py --from-reports
      扫描 hanzi-reports.json 里 open 的反馈，逐条生成候选（可被 cron / workflow_dispatch 定时触发）
  python3 agent_fix.py --char 天 --issue "第一笔应上移" --dry-run
      本地手动单条

候选生成器 propose_candidate() 是可替换钩子：
  --strategy nudge（默认）  对现有笔画做安全的位置微调，确定性、可复现，用于演示与回归自检；
                             它解决不了「横撇改横」这类形状问题，仅作占位。
  --strategy file --candidate-json c.json   读取外部（LLM/VLM/你）生成的 {strokes, medians, ...}。
  --strategy hook --hook-cmd "python3 my_ai.py"   把 {char, issue, current} 以 JSON 写到子进程 stdin，
                             期望 stdout 返回同样的候选 JSON —— 接任意 AI 生成器的标准入口。

视觉初审 visual_review() 预留钩子：默认未启用（无服务端视觉模型），
真实接入时在函数内调用你的 VLM 对渲染图做笔顺/结构打分；未过可在 note 标注，仍不自动采纳。

数据隔离：--data-dir DIR 可把 strokes/revisions/reports 指向临时目录，供 CI 自检而不污染正式字库。

校验尺子与 MCP server 完全同源（hanzi_validate），保证「agent 提交的候选」和
「审阅页看到的报告」是同一把尺子量出来的。
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time

import hanzi_validate as hv

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = {"strokes": "hanzi-strokes.json", "revisions": "hanzi-revisions.json",
         "reports": "hanzi-reports.json"}


# ---------------------------------------------------------------- 存储（与 server.py 同格式）
def _path(data_dir, key):
    return os.path.join(data_dir, FILES[key])


def _load_list(data_dir, key):
    p = _path(data_dir, key)
    if not os.path.exists(p):
        return []
    try:
        return json.load(open(p, encoding="utf-8")).get(key, [])
    except Exception:
        return []


def _save_list(data_dir, key, rows):
    p = _path(data_dir, key)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({key: rows}, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)


def _load_library(data_dir):
    p = _path(data_dir, "strokes")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}


def _new_id(prefix):
    return "%s-%d-%04d" % (prefix, int(time.time() * 1000), os.getpid() % 10000)


# ---------------------------------------------------------------- 校验（复用同一把尺子）
def run_validation(char, strokes_in, medians_in, source, library):
    ref = library.get(char)
    report = hv.validate_glyph(strokes_in, medians_in, ref=ref, source=source)
    similar = hv.find_similar(char, medians_in, library)
    report["similarInLibrary"] = similar
    if similar:
        top = similar[0]
        report["warnings"].append(
            "与库内「%s」字形高度相似(%.0f%%)，疑似复制错字，须重点核对"
            % (top["char"], top["iou"] * 100))
    return report


# ---------------------------------------------------------------- 候选生成器（可替换钩子）
_PAIR = re.compile(r"(-?\d+(?:\.\d+)?)[ ,]+(-?\d+(?:\.\d+)?)")


def translate_path(d, dx, dy):
    """平移 SVG path 内所有绝对坐标对；本字库仅含 M/Q/L/C/Z，无相对指令，安全。"""
    if not dx and not dy:
        return d
    def repl(m):
        return "%g %g" % (round(float(m.group(1)) + dx, 3),
                          round(float(m.group(2)) + dy, 3))
    return _PAIR.sub(repl, d)


def _parse_target(issue):
    """从自然语言反馈里解析「第几笔」与方向词；无方向时做一个安全的演示微调。"""
    issue = issue or ""
    idx = None
    m = re.search(r"第\s*([一二三四五六七八九十\d]+)\s*笔", issue)
    if m:
        cn = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
              "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
        tok = m.group(1)
        idx = (int(tok) if tok.isdigit() else cn.get(tok, 1)) - 1
    dx = dy = 0
    if re.search(r"上移|上提|偏上|抬高|往上|向上|缩短|偏短", issue):
        dy = -6
    elif re.search(r"下移|下压|偏下|往下|向下|拉长|偏长", issue):
        dy = 6
    if re.search(r"左移|偏左|往左|向左", issue):
        dx = -6
    elif re.search(r"右移|偏右|往右|向右", issue):
        dx = 6
    if dx == 0 and dy == 0:
        dx, dy = 2, -4  # 无明确方向时的占位微调，保证可复现、可回归
    return idx, dx, dy


def _nudge(char, issue, current):
    idx, dx, dy = _parse_target(issue)
    strokes_in = list(current.get("strokes", []))
    medians_in = [[list(p) for p in m] for m in current.get("medians", [])]
    if not medians_in:
        raise ValueError("当前字形无笔画数据，nudge 无法工作")
    t = idx if idx is not None and 0 <= idx < len(medians_in) else 0
    strokes_in[t] = translate_path(strokes_in[t], dx, dy)
    medians_in[t] = [[round(float(p[0]) + dx, 3), round(float(p[1]) + dy, 3)]
                     for p in medians_in[t]]
    return {"strokes": strokes_in, "medians": medians_in,
            "note": "agent nudge：第%d笔整体平移(dx=%s,dy=%s)，依据反馈「%s」"
                    % (t + 1, dx, dy, issue or "无"),
            "source": "agent-nudge"}


def _from_obj(obj):
    if not isinstance(obj, dict) or "strokes" not in obj or "medians" not in obj:
        raise ValueError("候选 JSON 需含 strokes 与 medians 两个数组")
    return {"strokes": obj["strokes"], "medians": obj["medians"],
            "note": obj.get("note", ""), "source": obj.get("source", "ai-generated")}


def propose_candidate(char, issue, current, strategy="nudge", candidate_json=None, hook_cmd=None):
    """生成候选的可替换钩子。接真实 AI 生成器时只需替换 / 扩展本函数。"""
    if strategy == "nudge":
        return _nudge(char, issue, current)
    if strategy == "file":
        if not candidate_json:
            raise ValueError("--strategy file 需要 --candidate-json")
        return _from_obj(json.load(open(candidate_json, encoding="utf-8")))
    if strategy == "hook":
        if not hook_cmd:
            raise ValueError("--strategy hook 需要 --hook-cmd")
        payload = json.dumps({"char": char, "issue": issue, "current": current}, ensure_ascii=False)
        p = subprocess.run(hook_cmd, shell=True, input=payload, text=True,
                           capture_output=True, timeout=180)
        if p.returncode:
            raise RuntimeError("生成器 hook 失败(exit %d)：%s" % (p.returncode, (p.stderr or "")[:400]))
        return _from_obj(json.loads(p.stdout))
    raise ValueError("未知策略：%s" % strategy)


def visual_review(char, strokes_in, medians_in, current):
    """可选 VLM 视觉初审钩子。默认未启用；接真实 VLM 时在此打分，但不放宽「人工终裁」。"""
    return {"enabled": False,
            "reason": "未配置 VLM 端点；视觉/笔顺初审留给 hanzi-review.html 人工审阅页"}


# ---------------------------------------------------------------- issue 解析
def _field(body, names):
    lines = (body or "").splitlines()
    for i, line in enumerate(lines):
        s = line.strip().lstrip("#").strip().rstrip("：:").strip()
        if s in names:
            for j in range(i + 1, len(lines)):
                v = lines[j].strip()
                if v:
                    return v
    for line in lines:
        m = re.match(r"^\*\*(.+?)\*\*\s*[:：]\s*(.+)$", line.strip())
        if m and m.group(1).strip() in names:
            return m.group(2).strip()
    return ""


def parse_issue(payload):
    iss = payload.get("issue", {}) if isinstance(payload, dict) else {}
    body = iss.get("body", "") or ""
    char = _field(body, ["出问题的汉字", "汉字", "目标汉字", "char"])
    issue = _field(body, ["问题描述", "问题", "描述", "issue"]) or iss.get("title", "") or ""
    user = iss.get("user") or {}
    reporter = (user.get("login") if isinstance(user, dict) else None) or "github-issue"
    return {"number": iss.get("number"), "title": iss.get("title", ""), "char": char,
            "issue": issue, "reporter": reporter,
            "labels": [l.get("name") if isinstance(l, dict) else l for l in iss.get("labels", [])],
            "url": iss.get("html_url", "")}


# ---------------------------------------------------------------- 主流程
def process_one(data_dir, char, issue, reporter, strategy="nudge", candidate_json=None,
                hook_cmd=None, author=None, dry_run=False):
    char = (char or "").strip()
    if len(char) != 1:
        raise ValueError("char 必须是单个汉字，收到：%r" % char)
    library = _load_library(data_dir)
    if char not in library:
        raise ValueError("字库中没有「%s」，先在 hanzi-db.json 里收录再反馈" % char)
    current = library[char]

    cand = propose_candidate(char, issue, current, strategy, candidate_json, hook_cmd)
    report = run_validation(char, cand["strokes"], cand["medians"], cand["source"], library)
    visual = visual_review(char, cand["strokes"], cand["medians"], current)
    can_auto_accept = report["ok"] and not report["similarInLibrary"]

    revision = {"id": _new_id("rev"), "char": char, "strokes": cand["strokes"],
                "medians": cand["medians"], "author": author or reporter or "anonymous-agent",
                "note": cand.get("note", ""), "source": cand["source"],
                "issue": issue, "reporter": reporter, "ts": int(time.time()),
                "status": "pending", "validation": report, "visualReview": visual,
                "canAutoAccept": can_auto_accept}

    if not dry_run:
        with _write_guard():
            # 反馈入库（由 issue 驱动时保留来源链接）
            reps = _load_list(data_dir, "reports")
            reps.insert(0, {"id": _new_id("rep"), "char": char, "issue": issue or "（无描述）",
                            "reporter": reporter, "ts": int(time.time()), "status": "open",
                            "source": ("github-issue#" + str(_issue_no.get("number"))
                                       if _issue_no.get("number") else "agent")})
            _save_list(data_dir, "reports", reps)
            revs = _load_list(data_dir, "revisions")
            revs.insert(0, revision)
            _save_list(data_dir, "revisions", revs)

    return {"char": char, "revisionId": revision["id"], "status": "pending" if not dry_run else "dry-run",
            "strokeCount": report["strokeCount"], "validation": report, "visualReview": visual,
            "canAutoAccept": can_auto_accept, "revision": revision,
            "note": ("候选已入待审队列，须人工在审阅页核对笔顺/字形后采纳。"
                     if not dry_run else "dry-run：未写入任何文件")}


# 单条 issue 号，仅用于给 report 标注来源；进程内一次性设置
_issue_no = {}


class _write_guard:
    """轻量进程内互斥（CI 单进程足够；跨进程由原子 os.replace 保证文件不损坏）。"""
    _lock = threading.Lock()

    def __enter__(self):
        self._lock.acquire()
        return self

    def __exit__(self, *a):
        self._lock.release()


def process_reports(data_dir, strategy="nudge", candidate_json=None, hook_cmd=None,
                    author="agent-bot", dry_run=False, limit=20):
    """扫描 open 反馈，逐条生成候选；已有 pending 候选的字跳过，保证幂等。"""
    pending_chars = {r.get("char") for r in _load_list(data_dir, "revisions")
                     if r.get("status") == "pending"}
    open_reports = [r for r in _load_list(data_dir, "reports") if r.get("status") == "open"]
    out, skipped = [], []
    for rep in open_reports[:limit]:
        ch = rep.get("char")
        if ch in pending_chars:
            skipped.append(ch)
            continue
        try:
            res = process_one(data_dir, ch, rep.get("issue", ""), rep.get("reporter", "agent"),
                              strategy, candidate_json, hook_cmd, author, dry_run)
            out.append({"char": ch, "revisionId": res["revisionId"],
                        "ok": res["validation"]["ok"],
                        "canAutoAccept": res["canAutoAccept"],
                        "summary": hv.summarize(res["validation"])})
            pending_chars.add(ch)
        except Exception as e:
            out.append({"char": ch, "error": str(e)})
    return {"scanned": len(open_reports), "generated": len(out),
            "skippedExistingPending": sorted(set(skipped)), "results": out,
            "dryRun": dry_run}


def format_markdown(res, issue_no=None):
    v = res["validation"]
    tag = "✅ 硬校验通过" if v["ok"] else "❌ 硬校验未通过"
    lines = ["### 🤖 Agent 重画候选 · 「%s」" % res["char"], "",
             "**结构校验**：%s · %s" % (tag, hv.summarize(v)), ""]
    if v["errors"]:
        lines += ["**错误**"] + ["- " + e for e in v["errors"]] + [""]
    if v["warnings"]:
        lines += ["**注意**"] + ["- " + w for w in v["warnings"]] + [""]
    if v.get("similarInLibrary"):
        lines += ["**库内近似**（疑似复制错字，重点核对）"]
        lines += ["- 「%s」 %.0f%%" % (x["char"], x["iou"] * 100) for x in v["similarInLibrary"]]
        lines += [""]
    lines += ["**笔画数**：%s" % v["strokeCount"],
              "**候选来源**：%s" % res["revision"].get("source", ""),
              "**VLM 视觉初审**：%s" % ("已启用" if res["visualReview"].get("enabled") else "未启用（留人工）"),
              "**自动可发布**：%s" % ("是" if res["canAutoAccept"] else "否，须人工终裁"),
              "",
              "> 候选已存入 `hanzi-revisions.json`，将自动开一个 PR 供人工并排审阅。",
              "> agent 无权直接改正式字库——本次仅上报 / 重画 / 测量。"]
    if res["revision"].get("note"):
        lines += ["", "改动说明：" + res["revision"]["note"]]
    return "\n".join(lines)


# ---------------------------------------------------------------- 自检
def selftest():
    tmp = tempfile.mkdtemp(prefix="hanzi-agent-selftest-")
    real_rev = _path(HERE, "revisions")
    before = hashlib.sha256(open(real_rev, "rb").read()).hexdigest() if os.path.exists(real_rev) else None
    checks = []
    try:
        shutil.copy(_path(HERE, "strokes"), _path(tmp, "strokes"))
        _save_list(tmp, "reports", [])
        _save_list(tmp, "revisions", [])

        # 1) 合法 nudge 候选应通过结构硬校验、无库内近似
        r1 = process_one(tmp, "天", "第一笔上移", "selftest")
        ok1 = r1["validation"]["ok"] and r1["canAutoAccept"]
        checks.append(("合法 nudge 候选通过同一把尺子", ok1,
                       hv.summarize(r1["validation"])))

        # 2) 拿「空」冒充「天」——相似检测必须拦下
        lib = _load_library(tmp)
        fake = {"strokes": lib["空"]["strokes"], "medians": lib["空"]["medians"],
                "note": "恶意/错误冒充", "source": "ai-generated"}
        fake_path = os.path.join(tmp, "fake.json")
        json.dump(fake, open(fake_path, "w", encoding="utf-8"))
        r2 = process_one(tmp, "天", "重画", "selftest", strategy="file", candidate_json=fake_path)
        ok2 = bool(r2["validation"]["similarInLibrary"]) and not r2["canAutoAccept"]
        checks.append(("冒充候选被库内近似检测拦下", ok2,
                       "similarInLibrary=%s" % r2["validation"]["similarInLibrary"]))

        # 3) 退化数据（每笔仅 1 个中轴点）必须 FAIL
        bad = {"strokes": lib["天"]["strokes"], "medians": [[p[0]] for p in lib["天"]["medians"]],
               "note": "坏数据", "source": "manual-fix"}
        bad_path = os.path.join(tmp, "bad.json")
        json.dump(bad, open(bad_path, "w", encoding="utf-8"))
        r3 = process_one(tmp, "水", "重画", "selftest", strategy="file", candidate_json=bad_path)
        ok3 = not r3["validation"]["ok"]
        checks.append(("退化数据被硬校验拒绝", ok3,
                       "; ".join(r3["validation"]["errors"][:2])))

        # 4) 扫描 open 反馈能产出 pending 候选，且同字再次扫描幂等
        _save_list(tmp, "revisions", [])   # 清空前几步候选，隔离本用例
        _save_list(tmp, "reports", [{"id": "rep-test", "char": "一", "issue": "末笔应上移",
                                     "reporter": "selftest", "ts": 0, "status": "open"}])
        s1 = process_reports(tmp)
        s2 = process_reports(tmp)
        ok4 = (s1["generated"] == 1 and s2["generated"] == 0
               and s2["skippedExistingPending"] == ["一"])
        checks.append(("反馈扫描产出候选且重复扫描幂等", ok4,
                       "1st=%d / 2nd=%d skipped=%s" % (s1["generated"], s2["generated"],
                                                       s2["skippedExistingPending"])))

        # 5) 不污染正式数据
        after = hashlib.sha256(open(real_rev, "rb").read()).hexdigest() if os.path.exists(real_rev) else None
        checks.append(("自检未污染正式 revisions.json", before == after,
                       "hash 前后一致" if before == after else "!! 正式数据被改动"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("=" * 62)
    print("Agent 修复引擎自检")
    print("=" * 62)
    for name, ok, detail in checks:
        print(("  [PASS] " if ok else "  [FAIL] ") + name + "  →  " + str(detail))
    print("-" * 62)
    passed = sum(1 for _, ok, _ in checks if ok)
    print("  %d/%d 通过" % (passed, len(checks)))
    print("=" * 62)
    return 0 if passed == len(checks) else 1


# ---------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser(description="Agent 字形自动修复引擎（反馈 → 候选 → 硬校验 → 待审）")
    ap.add_argument("--data-dir", default=HERE, help="数据目录，默认脚本所在目录；自检用临时目录")
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--issue-json", help="GitHub issues 事件 JSON 文件路径")
    src.add_argument("--from-reports", action="store_true", help="扫描所有 open 反馈批量生成候选")
    src.add_argument("--char", help="单条模式：要修正的汉字")
    ap.add_argument("--issue", default="", help="问题描述（配合 --char）")
    ap.add_argument("--reporter", default="agent", help="反馈者名")
    ap.add_argument("--author", default=None, help="候选署名（默认同 reporter）")
    ap.add_argument("--strategy", default="nudge", choices=["nudge", "file", "hook"],
                    help="候选生成策略（默认 nudge；file/hook 接真实 AI 生成器）")
    ap.add_argument("--candidate-json", help="strategy=file 时的候选 JSON 文件")
    ap.add_argument("--hook-cmd", help="strategy=hook 时执行的生成器命令")
    ap.add_argument("--out", help="把机器可读结果写入该 JSON 文件（供 CI 后续步骤读取）")
    ap.add_argument("--comment-file", help="把 issue 回帖 Markdown 写入该文件")
    ap.add_argument("--limit", type=int, default=20, help="--from-reports 最多处理条数")
    ap.add_argument("--dry-run", action="store_true", help="只计算不写文件")
    ap.add_argument("--selftest", action="store_true", help="在临时目录跑端到端自检，不碰正式数据")
    a = ap.parse_args(argv)

    if a.selftest:
        return selftest()
    data_dir = os.path.abspath(a.data_dir)

    if a.from_reports:
        result = process_reports(data_dir, a.strategy, a.candidate_json, a.hook_cmd,
                                 a.author or "agent-bot", a.dry_run, a.limit)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if a.out:
            json.dump(result, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        return 0 if all("error" not in r for r in result["results"]) else 1

    if a.issue_json:
        payload = json.load(open(a.issue_json, encoding="utf-8"))
        parsed = parse_issue(payload)
        _issue_no.update(parsed)
        if not parsed["char"]:
            print("无法从 issue 解析出汉字（需表单字段「出问题的汉字」或正文写出单字）。", file=sys.stderr)
            return 2
        char, issue, reporter = parsed["char"], parsed["issue"], parsed["reporter"]
    elif a.char:
        char, issue, reporter = a.char, a.issue, a.reporter
        _issue_no.clear()
    else:
        ap.error("请指定 --issue-json / --from-reports / --char / --selftest 之一")

    try:
        res = process_one(data_dir, char, issue, reporter, a.strategy, a.candidate_json,
                          a.hook_cmd, a.author or None, a.dry_run)
    except Exception as e:
        print("候选生成失败：%s" % e, file=sys.stderr)
        return 2

    public = {k: res[k] for k in ("char", "revisionId", "status", "strokeCount",
                                  "validation", "visualReview", "canAutoAccept", "note")}
    public["revision"] = res["revision"]
    print(json.dumps(public, ensure_ascii=False, indent=2))
    if a.out:
        json.dump(public, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    if a.comment_file:
        open(a.comment_file, "w", encoding="utf-8").write(format_markdown(res, _issue_no.get("number")))
    # 结构硬校验失败时返回非 0，让 CI 醒目提示（候选仍已入队，供人工查看失败原因）
    return 0 if res["validation"]["ok"] else 3


if __name__ == "__main__":
    sys.exit(main())
