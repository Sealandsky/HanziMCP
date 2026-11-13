#!/usr/bin/env python3
"""汉字 MCP server —— 让 Agent 实时取字 / 检索 / 取笔画。

两种运行方式：
  python3 server.py                   # stdio（Claude Desktop / Cursor / WorkBuddy 等本地 MCP 客户端）
  python3 server.py --http 8787       # HTTP（POST /mcp，浏览器或远程 MCP 客户端可连）

零第三方依赖，只用标准库。
"""
import argparse
import hashlib
import json
import os
import sys
import threading
import time
import unicodedata
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import hanzi_validate as hv

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "hanzi-db.json")
STROKE_PATH = os.path.join(HERE, "hanzi-strokes.json")
REVIEWS_PATH = os.path.join(HERE, "hanzi-revisions.json")
REPORTS_PATH = os.path.join(HERE, "hanzi-reports.json")
CONTRIB_PATH = os.path.join(HERE, "hanzi-contributors.json")

DB = json.load(open(DB_PATH, encoding="utf-8"))
CHARS = DB["chars"]
SET_META = DB["meta"]["sets"]
SERVER_INFO = {"name": "hanzi-mcp", "version": "1.1.0"}
PROTOCOL = "2025-06-18"

_strokes_cache = None
_write_lock = threading.Lock()


def strokes():
    global _strokes_cache
    if _strokes_cache is None:
        if os.path.exists(STROKE_PATH):
            _strokes_cache = json.load(open(STROKE_PATH, encoding="utf-8"))
        else:
            _strokes_cache = {}
    return _strokes_cache


# ---------------------------------------------------------------- 待审/反馈存储
# 闭环数据独立于正式字库，agent 只能写入候选与反馈，采纳权在人工审阅页。
def _load_list(path, key):
    if not os.path.exists(path):
        return []
    try:
        return json.load(open(path, encoding="utf-8")).get(key, [])
    except Exception:
        return []


def _save_list(path, key, rows):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({key: rows}, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _new_id(prefix):
    return "%s-%d-%04d" % (prefix, int(time.time() * 1000), os.getpid() % 10000)


def load_revisions():
    return _load_list(REVIEWS_PATH, "revisions")


def save_revisions(rows):
    _save_list(REVIEWS_PATH, "revisions", rows)


def load_reports():
    return _load_list(REPORTS_PATH, "reports")


def save_reports(rows):
    _save_list(REPORTS_PATH, "reports", rows)


def load_contributors():
    return _load_list(CONTRIB_PATH, "contributions")


def save_contributors(rows):
    _save_list(CONTRIB_PATH, "contributions", rows)


# ---------------------------------------------------------------- 活动区数据
# 主站右侧活动栏的唯一数据口径：既供 GET /activity 实时返回，也在构建时
# 生成静态快照内联进 HTML（GitHub Pages 无后端时显示真实数据而非假数字）。
def _activity_rev():
    parts = []
    for path in (DB_PATH, STROKE_PATH, REVIEWS_PATH, REPORTS_PATH, CONTRIB_PATH):
        try:
            st = os.stat(path)
            parts.append("%d:%d" % (st.st_mtime_ns, st.st_size))
        except OSError:
            parts.append("0:0")
    return hashlib.md5("|".join(parts).encode()).hexdigest()[:16]


def activity_payload(rev=None):
    revisions = load_revisions()
    reports = load_reports()
    contributors = load_contributors()

    # 以正式字库记录的笔画数为准，不依赖笔画缓存（缓存可能尚未加载）
    stroke_total = sum(int(CHARS[c].get("strokes") or 0) for c in CHARS)
    accepted = [r for r in revisions if r.get("status") == "accepted"]
    rejected = [r for r in revisions if r.get("status") == "rejected"]
    pending = [r for r in revisions if r.get("status") == "pending"]
    open_reports = [r for r in reports if r.get("status") == "open"]

    events = []
    for r in revisions:
        status = r.get("status")
        ch = r.get("char") or "?"
        if status == "accepted":
            ts = r.get("acceptedTs") or r.get("ts") or 0
            actor = r.get("author") or "匿名贡献者"
            act, detail = "已采纳", "候选通过人工审阅，笔画已写回字库"
        elif status == "rejected":
            ts = r.get("rejectedTs") or r.get("ts") or 0
            actor = "人工审阅"
            act, detail = "驳回了", (r.get("rejectReason") or "候选未通过审阅")
        else:
            ts = r.get("ts") or 0
            actor = r.get("author") or "匿名贡献者"
            act, detail = "提交候选", (r.get("note") or "等待人工审阅")
        events.append({"id": r.get("id"), "ts": ts, "kind": status or "pending",
                       "char": ch, "actor": actor, "act": act, "detail": detail,
                       "strokes": (r.get("validation") or {}).get("strokeCount")})
    for r in reports:
        ch = r.get("char") or "?"
        issue = r.get("issue") or ""
        if r.get("status") == "open":
            events.append({"id": r.get("id"), "ts": r.get("ts") or 0, "kind": "reported",
                           "char": ch, "actor": r.get("reporter") or "用户",
                           "act": "反馈了", "detail": issue or "待处理字形问题"})
        else:
            events.append({"id": r.get("id"), "ts": r.get("ts") or 0, "kind": "resolved",
                           "char": ch, "actor": r.get("reporter") or "用户",
                           "act": "已处理", "detail": issue or "已关联修订"})
    events.sort(key=lambda e: e.get("ts") or 0, reverse=True)

    pins = [{"name": s.get("name", ""), "count": s.get("count", 0)} for s in SET_META][:4]
    return {
        "ok": True,
        "rev": rev or _activity_rev(),
        "generatedAt": int(time.time()),
        "stats": {
            "chars": len(CHARS), "strokes": stroke_total, "sets": len(SET_META),
            "revisions": len(revisions), "accepted": len(accepted),
            "rejected": len(rejected), "pending": len(pending),
            "reports": len(reports), "openReports": len(open_reports),
            "contributors": len(contributors),
        },
        "pins": pins,
        "events": events,
    }


def run_validation(char, strokes_in, medians_in, source="manual-fix"):
    """跑硬校验 + 独立重复比对，返回组装后的报告。"""
    ref = strokes().get(char)
    report = hv.validate_glyph(strokes_in, medians_in, ref=ref, source=source)
    similar = hv.find_similar(char, medians_in, strokes())
    report["similarInLibrary"] = similar
    if similar:
        top = similar[0]
        report["warnings"].append(
            "与库内「%s」字形高度相似(%.0f%%)，疑似复制错字，须重点核对"
            % (top["char"], top["iou"] * 100))
    return report


def strip_tones(s):
    s = (s or "").lower().replace("ü", "v")
    return "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c))


# ---------------------------------------------------------------- tools
TOOLS = [
    {
        "name": "get_hanzi",
        "description": "查询单个汉字的拼音、释义、所属分类、笔画数与 Unicode 码位。",
        "inputSchema": {
            "type": "object",
            "properties": {"char": {"type": "string", "description": "单个汉字，例如 天"}},
            "required": ["char"],
        },
    },
    {
        "name": "search_hanzi",
        "description": "按汉字 / 拼音（可省声调）/ 英文释义 / 分类名检索汉字，返回最相关的结果。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "检索词，如 tian、sky、数字、水"},
                "set": {"type": "string", "description": "限定分类（可选），如 天文太空"},
                "limit": {"type": "integer", "description": "返回条数上限，默认 10", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "list_sets",
        "description": "列出全部汉字分类及每类字数。",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "hanzi_paths",
        "description": "返回汉字的逐笔 SVG path 数据（含每笔中轴线 medians），用于绘制笔画书写动画。",
        "inputSchema": {
            "type": "object",
            "properties": {"char": {"type": "string", "description": "单个汉字"}},
            "required": ["char"],
        },
    },
    {
        "name": "report_hanzi",
        "description": "反馈字库里某个字的问题（笔顺错/笔画数不对/字形不像/缺笔等），进入待处理队列，不直接改正式数据。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "char": {"type": "string", "description": "出问题的单个汉字"},
                "issue": {"type": "string", "description": "问题描述，例如「第三笔应是竖勾不是竖」"},
                "reporter": {"type": "string", "description": "反馈者（人或 agent 名），可选", "default": "anonymous"},
            },
            "required": ["char", "issue"],
        },
    },
    {
        "name": "fix_hanzi",
        "description": "提交一个重画候选（strokes + medians）。会立即跑硬校验（结构/坐标/笔画数/重复检测/diff）并把候选存入待审队列，供人工审阅页裁决；不会覆盖正式数据。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "char": {"type": "string", "description": "要修正的单个汉字"},
                "strokes": {"type": "array", "items": {"type": "string"}, "description": "每笔的 SVG path 字符串数组"},
                "medians": {"type": "array", "items": {"type": "array"}, "description": "每笔中轴点 [[x,y],...] 的数组"},
                "author": {"type": "string", "description": "提交者（agent 名），写入署名", "default": "anonymous-agent"},
                "note": {"type": "string", "description": "改动说明", "default": ""},
                "source": {"type": "string", "description": "来源：arphic-reextract（从原字体重提）/ manual-fix / ai-generated", "default": "manual-fix"},
            },
            "required": ["char", "strokes", "medians"],
        },
    },
    {
        "name": "list_revisions",
        "description": "列出候选修订及校验结果。可按状态筛选：pending / accepted / rejected / all。",
        "inputSchema": {
            "type": "object",
            "properties": {"status": {"type": "string", "description": "状态筛选，默认 pending", "default": "pending"}},
        },
    },
    {
        "name": "validate_revision",
        "description": "对某个已提交的候选重新跑一遍完整硬校验，返回最新报告（不改动数据）。",
        "inputSchema": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "候选 id，形如 rev-... "}},
            "required": ["id"],
        },
    },
    {
        "name": "list_reports",
        "description": "列出字库问题反馈。可按状态筛选：open / resolved / all。",
        "inputSchema": {
            "type": "object",
            "properties": {"status": {"type": "string", "description": "状态筛选，默认 open", "default": "open"}},
        },
    },
]


def tool_get_hanzi(args):
    ch = (args.get("char") or "").strip()
    if len(ch) != 1:
        return None, "char 必须是单个汉字"
    info = CHARS.get(ch)
    if not info:
        return None, "字库中没有「%s」" % ch
    return info, None


def tool_search_hanzi(args):
    q = (args.get("query") or "").strip()
    limit = int(args.get("limit") or 10)
    set_filter = (args.get("set") or "").strip()
    if not q:
        return None, "query 不能为空"
    nq = strip_tones(q)
    scored = []
    for info in CHARS.values():
        if set_filter and info["set"] != set_filter:
            continue
        score = 0
        if info["char"] == q:
            score = 100
        elif nq and strip_tones(info["pinyin"]).startswith(nq):
            score = 80
        elif nq and nq in strip_tones(info["pinyin"]):
            score = 60
        elif q and q in info["meaning"].lower():
            score = 50
        elif q and q in info["set"]:
            score = 30
        elif q and q in info["char"]:
            score = 20
        if score:
            scored.append((score, info))
    scored.sort(key=lambda x: (-x[0], x[1]["char"]))
    return {"query": q, "count": len(scored), "results": [i for _, i in scored[:limit]]}, None


def tool_list_sets(_args):
    return {"total": len(CHARS), "sets": SET_META}, None


def tool_hanzi_paths(args):
    ch = (args.get("char") or "").strip()
    data = strokes().get(ch)
    if not data:
        return None, "没有「%s」的笔画数据" % ch
    return {"char": ch, "strokeCount": len(data.get("strokes", [])),
            "strokes": data.get("strokes", []), "medians": data.get("medians", [])}, None


def tool_report_hanzi(args):
    ch = (args.get("char") or "").strip()
    issue = (args.get("issue") or "").strip()
    reporter = (args.get("reporter") or "anonymous").strip()
    if len(ch) != 1:
        return None, "char 必须是单个汉字"
    if not issue:
        return None, "issue 不能为空"
    with _write_lock:
        rows = load_reports()
        row = {"id": _new_id("rep"), "char": ch, "issue": issue,
               "reporter": reporter, "ts": int(time.time()), "status": "open"}
        rows.insert(0, row)
        save_reports(rows)
    return {"ok": True, "report": row,
            "hint": "已记入反馈队列。可再用 fix_hanzi 提交重画候选；采纳由人工审阅页裁决。"}, None


def tool_fix_hanzi(args):
    ch = (args.get("char") or "").strip()
    strokes_in = args.get("strokes")
    medians_in = args.get("medians")
    author = (args.get("author") or "anonymous-agent").strip()
    note = (args.get("note") or "").strip()
    source = (args.get("source") or "manual-fix").strip()
    if len(ch) != 1:
        return None, "char 必须是单个汉字"
    if not isinstance(strokes_in, list) or not isinstance(medians_in, list):
        return None, "strokes 与 medians 必须是数组"
    report = run_validation(ch, strokes_in, medians_in, source=source)
    with _write_lock:
        rows = load_revisions()
        row = {"id": _new_id("rev"), "char": ch, "strokes": strokes_in,
               "medians": medians_in, "author": author, "note": note,
               "source": source, "ts": int(time.time()), "status": "pending",
               "validation": report}
        rows.insert(0, row)
        save_revisions(rows)
    return {"ok": True, "id": row["id"], "char": ch, "status": "pending",
            "validation": report,
            "canAutoAccept": report["ok"] and not report["similarInLibrary"],
            "hint": "候选已存待审。结构硬校验通过不等于可发布——仍需人工在审阅页核对笔顺/字形后裁决。"}, None


def tool_list_revisions(args):
    status = (args.get("status") or "pending").strip()
    rows = load_revisions()
    if status != "all":
        rows = [r for r in rows if r.get("status") == status]
    view = [{k: r.get(k) for k in ("id", "char", "author", "source", "note", "ts", "status", "validation")}
            for r in rows]
    return {"count": len(view), "revisions": view}, None


def tool_validate_revision(args):
    rid = (args.get("id") or "").strip()
    if not rid:
        return None, "id 不能为空"
    rows = load_revisions()
    row = next((r for r in rows if r.get("id") == rid), None)
    if not row:
        return None, "找不到候选 %s" % rid
    report = run_validation(row["char"], row["strokes"], row["medians"], source=row.get("source", "manual-fix"))
    with _write_lock:
        rows = load_revisions()
        for r in rows:
            if r.get("id") == rid:
                r["validation"] = report
                break
        save_revisions(rows)
    return {"id": rid, "char": row["char"], "validation": report}, None


def tool_list_reports(args):
    status = (args.get("status") or "open").strip()
    rows = load_reports()
    if status != "all":
        rows = [r for r in rows if r.get("status") == status]
    return {"count": len(rows), "reports": rows}, None


# ---- 人工裁决：仅审阅页通过专用 HTTP 端点调用，不作为 MCP 工具暴露 ----
def accept_revision(rid):
    with _write_lock:
        rows = load_revisions()
        row = next((r for r in rows if r.get("id") == rid), None)
        if not row:
            return None, "找不到候选 %s" % rid
        if row.get("status") != "pending":
            return None, "候选 %s 已是 %s，不能重复采纳" % (rid, row["status"])
        report = run_validation(row["char"], row["strokes"], row["medians"], source=row.get("source", "manual-fix"))
        if not report["ok"]:
            return None, "硬校验未通过，禁止采纳：%s" % "; ".join(report["errors"])
        ch = row["char"]
        # 写回正式字形数据
        data = dict(strokes())            # copy-on-write，避免半写状态
        data[ch] = {"strokes": row["strokes"], "medians": row["medians"]}
        tmp = STROKE_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp, STROKE_PATH)
        global _strokes_cache
        _strokes_cache = data                # 刷新内存缓存，MCP 立即读到新字形
        # 同步字库里的笔画数字段
        if ch in CHARS:
            CHARS[ch]["strokes"] = len(row["strokes"])
            with open(DB_PATH, "w", encoding="utf-8") as f:
                json.dump(DB, f, ensure_ascii=False, indent=1)
        # 标记候选
        row["status"] = "accepted"
        row["validation"] = report
        row["acceptedTs"] = int(time.time())
        save_revisions(rows)
        # 记贡献者署名
        contrib = load_contributors()
        contrib.insert(0, {"id": _new_id("crd"), "char": ch, "author": row["author"],
                           "note": row.get("note", ""), "source": row.get("source", ""),
                           "revisionId": rid, "ts": int(time.time())})
        save_contributors(contrib)
        # 关联的 open 反馈标记为 resolved
        reps = load_reports()
        changed = False
        for rp in reps:
            if rp.get("char") == ch and rp.get("status") == "open":
                rp["status"] = "resolved"
                rp["resolvedBy"] = rid
                changed = True
        if changed:
            save_reports(reps)
    return {"ok": True, "char": ch, "revisionId": rid, "author": row["author"],
            "strokeCount": len(row["strokes"]),
            "hint": "已采纳并写回正式字库；MCP 的 hanzi_paths 现在返回新字形。前端展示页需重新运行 build_hanzi_mcp.py 才会同步。"}, None


def reject_revision(rid, reason=""):
    with _write_lock:
        rows = load_revisions()
        row = next((r for r in rows if r.get("id") == rid), None)
        if not row:
            return None, "找不到候选 %s" % rid
        if row.get("status") != "pending":
            return None, "候选 %s 已是 %s" % (rid, row["status"])
        row["status"] = "rejected"
        row["rejectReason"] = reason or "人工审阅未通过"
        row["rejectedTs"] = int(time.time())
        save_revisions(rows)
    return {"ok": True, "revisionId": rid, "status": "rejected"}, None


HANDLERS = {
    "get_hanzi": tool_get_hanzi,
    "search_hanzi": tool_search_hanzi,
    "list_sets": tool_list_sets,
    "hanzi_paths": tool_hanzi_paths,
    "report_hanzi": tool_report_hanzi,
    "fix_hanzi": tool_fix_hanzi,
    "list_revisions": tool_list_revisions,
    "validate_revision": tool_validate_revision,
    "list_reports": tool_list_reports,
}


def call_tool(name, args):
    fn = HANDLERS.get(name)
    if not fn:
        return {"content": [{"type": "text", "text": "未知工具：%s" % name}], "isError": True}
    payload, err = fn(args or {})
    if err:
        return {"content": [{"type": "text", "text": err}], "isError": True}
    return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, indent=2)}],
            "structuredContent": payload, "isError": False}


# ---------------------------------------------------------------- JSON-RPC
def handle(msg):
    """处理单条 JSON-RPC 消息，返回响应 dict；通知返回 None。"""
    if not isinstance(msg, dict):
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "invalid request"}}
    mid = msg.get("id")
    method = msg.get("method")
    params = msg.get("params") or {}

    if method == "initialize":
        result = {
            "protocolVersion": params.get("protocolVersion") or PROTOCOL,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": SERVER_INFO,
            "instructions": ("汉字 MCP：查询拼音/释义/分类/笔画数、检索汉字、获取逐笔路径；"
                             "并可通过 report_hanzi 反馈错字、fix_hanzi 提交重画候选（自动硬校验后进入待审），"
                             "采纳由人工在审阅页裁决，agent 无权直接改正式数据。"),
        }
        return {"jsonrpc": "2.0", "id": mid, "result": result}
    if method in ("notifications/initialized", "initialized"):
        return None
    if method == "ping":
        return {"jsonrpc": "2.0", "id": mid, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        return {"jsonrpc": "2.0", "id": mid,
                "result": call_tool(params.get("name"), params.get("arguments") or {})}
    if method == "resources/list":
        return {"jsonrpc": "2.0", "id": mid, "result": {"resources": []}}
    if method == "prompts/list":
        return {"jsonrpc": "2.0", "id": mid, "result": {"prompts": []}}
    if mid is None:
        return None
    return {"jsonrpc": "2.0", "id": mid,
            "error": {"code": -32601, "message": "method not found: %s" % method}}


def run_stdio():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": None,
                                         "error": {"code": -32700, "message": "parse error"}}) + "\n")
            sys.stdout.flush()
            continue
        resp = handle(msg)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


class MCPHandler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Mcp-Session-Id, If-None-Match")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Expose-Headers", "Mcp-Session-Id, ETag")

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _serve_html(self, filename):
        """同源托管单文件页面（主站 / 审阅台），避免 file:// 打开时的跨域限制。"""
        p = os.path.join(HERE, filename)
        if os.path.exists(p):
            body = open(p, "rb").read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self._cors()
            self.end_headers()
            self.wfile.write(body)
        else:
            self._json({"error": filename + " 缺失"}, 404)

    def _serve_icon(self, filename, mime):
        """静态图标：浏览器默认请求 /favicon.ico 或显式访问 /favicon.svg 时命中。"""
        p = os.path.join(HERE, filename)
        if not os.path.exists(p):
            self._json({"error": filename + " 缺失"}, 404)
            return
        body = open(p, "rb").read()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=86400")
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _serve_activity(self):
        rev = _activity_rev()
        etag = '"%s"' % rev
        if self.headers.get("If-None-Match") == etag:
            self.send_response(304)
            self.send_header("ETag", etag)
            self._cors()
            self.end_headers()
            return
        raw = json.dumps(activity_payload(rev), ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("ETag", etag)
        self.send_header("Cache-Control", "no-store")
        self._cors()
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path.startswith("/health"):
            self._json({"ok": True, "server": SERVER_INFO, "chars": len(CHARS),
                        "pendingRevisions": sum(1 for r in load_revisions() if r.get("status") == "pending"),
                        "openReports": sum(1 for r in load_reports() if r.get("status") == "open")})
        elif self.path.split("?")[0] == "/favicon.ico":
            self._serve_icon("favicon.ico", "image/x-icon")
        elif self.path.split("?")[0] == "/favicon.svg":
            self._serve_icon("favicon.svg", "image/svg+xml")
        elif self.path.split("?")[0].rstrip("/") == "/activity":
            self._serve_activity()
        elif self.path.startswith("/sets"):
            self._json({"total": len(CHARS), "sets": SET_META})
        elif self.path.startswith("/reviews"):
            # 审阅页数据：待审候选 + 当前正式字形（供并排对比）
            pending = [r for r in load_revisions() if r.get("status") == "pending"]
            for r in pending:
                r["current"] = strokes().get(r["char"])
                r["info"] = CHARS.get(r["char"])
            self._json({"pending": pending,
                        "reports": [x for x in load_reports() if x.get("status") == "open"],
                        "contributors": load_contributors()[:20]})
        elif self.path.startswith("/revisions"):
            self._json({"revisions": load_revisions()})
        elif self.path.startswith("/reports"):
            self._json({"reports": load_reports()})
        elif self.path.split("?")[0].rstrip("/") == "/review":
            self._serve_html("hanzi-review.html")
        elif self.path.split("?")[0].rstrip("/") in ("", "/index", "/home", "/hanzi"):
            # 主站：汉字图标库（单文件自包含）
            self._serve_html("hanzi-mcp.html")
        else:
            self._json({"ok": True, "site": "GET / （汉字主站）",
                        "endpoint": "POST /mcp", "reviewPage": "GET /review",
                        "review": "GET /reviews · POST /review/accept|reject",
                        "activity": "GET /activity", "icon": "GET /favicon.svg | /favicon.ico", "chars": len(CHARS)})

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"

        # 人工裁决端点（非 MCP 工具）：审阅页专用
        if self.path.startswith("/review/accept"):
            try:
                body = json.loads(raw.decode("utf-8")) if raw else {}
            except Exception:
                body = {}
            payload, err = accept_revision(body.get("id", ""))
            self._json({"error": err} if err else payload, 400 if err else 200)
            return
        if self.path.startswith("/review/reject"):
            try:
                body = json.loads(raw.decode("utf-8")) if raw else {}
            except Exception:
                body = {}
            payload, err = reject_revision(body.get("id", ""), body.get("reason", ""))
            self._json({"error": err} if err else payload, 400 if err else 200)
            return

        try:
            msg = json.loads(raw.decode("utf-8"))
        except Exception:
            self._json({"jsonrpc": "2.0", "id": None,
                        "error": {"code": -32700, "message": "parse error"}}, 400)
            return
        if isinstance(msg, list):
            out = [r for r in (handle(m) for m in msg) if r is not None]
            self._json(out)
        else:
            resp = handle(msg)
            if resp is None:
                self.send_response(202)
                self._cors()
                self.end_headers()
            else:
                self._json(resp)

    def log_message(self, *a):
        pass


def run_http(port):
    srv = ThreadingHTTPServer(("127.0.0.1", port), MCPHandler)
    print("汉字 MCP HTTP 已启动： http://127.0.0.1:%d/mcp  （健康检查 /health）" % port, file=sys.stderr)
    srv.serve_forever()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--http", type=int, metavar="PORT", help="以 HTTP 模式运行（默认 stdio）")
    a = ap.parse_args()
    if a.http:
        run_http(a.http)
    else:
        run_stdio()
