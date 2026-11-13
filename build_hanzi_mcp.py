#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build hanzi-mcp.html: a faithful frontend clone of iconmcp.com
with the line icons replaced by Chinese characters (汉字).

Single self-contained file (inline CSS + JS + data). Reproducible.
"""
import json, html, urllib.request, urllib.parse, re, math, os, sys, datetime

# ---- Character dataset -------------------------------------------------
# Each set mirrors an iconmcp "set" (Weather & nature, Space, ...).
# chars: (character, pinyin(with tone), short meaning)
SETS = [
    ("天文太空", [
        ("天","tiān","sky / heaven"),("空","kōng","empty / sky"),("宇","yǔ","space"),
        ("宙","zhòu","universe"),("辰","chén","stars / time"),("球","qiú","sphere / ball"),
        ("轨","guǐ","orbit / track"),("航","háng","navigate / sail"),("箭","jiàn","arrow"),
        ("卫","wèi","guard / satellite"),("彗","huì","comet"),("冥","míng","dark / deep"),
        ("银","yín","silver"),("河","hé","river"),("斗","dǒu","dipper / fight"),
        ("极","jí","pole / extreme"),("日","rì","sun / day"),("月","yuè","moon / month"),
        ("星","xīng","star"),("光","guāng","light"),("云","yún","cloud"),("气","qì","air / gas"),
    ]),
    ("天气自然", [
        ("风","fēng","wind"),("雨","yǔ","rain"),("雪","xuě","snow"),("雷","léi","thunder"),
        ("电","diàn","lightning"),("霜","shuāng","frost"),("露","lù","dew"),("虹","hóng","rainbow"),
        ("雾","wù","fog"),("山","shān","mountain"),("水","shuǐ","water"),("火","huǒ","fire"),
        ("田","tián","field"),("禾","hé","grain"),("林","lín","forest"),("石","shí","stone"),
        ("沙","shā","sand"),("浪","làng","wave"),("海","hǎi","sea"),("潮","cháo","tide"),
        ("泉","quán","spring"),("岩","yán","rock"),
    ]),
    ("数字", [
        ("一","yī","one"),("二","èr","two"),("三","sān","three"),("四","sì","four"),
        ("五","wǔ","five"),("六","liù","six"),("七","qī","seven"),("八","bā","eight"),
        ("九","jiǔ","nine"),("十","shí","ten"),("百","bǎi","hundred"),("千","qiān","thousand"),
        ("万","wàn","ten-thousand"),("亿","yì","hundred-million"),("零","líng","zero"),
        ("半","bàn","half"),("双","shuāng","pair"),("两","liǎng","two"),
    ]),
    ("人物身体", [
        ("人","rén","person"),("口","kǒu","mouth"),("手","shǒu","hand"),("足","zú","foot"),
        ("目","mù","eye"),("耳","ěr","ear"),("心","xīn","heart"),("身","shēn","body"),
        ("子","zǐ","child"),("女","nǚ","woman"),("男","nán","man"),("老","lǎo","old"),
        ("少","shào","young"),("父","fù","father"),("母","mǔ","mother"),("兄","xiōng","elder brother"),
        ("弟","dì","younger brother"),("友","yǒu","friend"),("君","jūn","lord"),("臣","chén","subject"),
    ]),
    ("动物", [
        ("马","mǎ","horse"),("牛","niú","ox"),("羊","yáng","sheep"),("鱼","yú","fish"),
        ("鸟","niǎo","bird"),("虫","chóng","insect"),("虎","hǔ","tiger"),("龙","lóng","dragon"),
        ("蛇","shé","snake"),("兔","tù","rabbit"),("犬","quǎn","dog"),("鹿","lù","deer"),
        ("象","xiàng","elephant"),("龟","guī","turtle"),("燕","yàn","swallow"),("凤","fèng","phoenix"),
        ("鹏","péng","roc"),
    ]),
    ("食物", [
        ("米","mǐ","rice"),("面","miàn","noodle / flour"),("茶","chá","tea"),("酒","jiǔ","wine"),
        ("盐","yán","salt"),("糖","táng","sugar"),("果","guǒ","fruit"),("菜","cài","vegetable"),
        ("肉","ròu","meat"),("饼","bǐng","cake / biscuit"),("粥","zhōu","congee"),("羹","gēng","soup"),
        ("饭","fàn","meal"),("豆","dòu","bean"),("瓜","guā","melon"),("蜜","mì","honey"),
    ]),
    ("方位", [
        ("东","dōng","east"),("南","nán","south"),("西","xī","west"),("北","běi","north"),
        ("上","shàng","up"),("下","xià","down"),("左","zuǒ","left"),("右","yòu","right"),
        ("中","zhōng","center"),("内","nèi","inside"),("外","wài","outside"),("前","qián","front"),
        ("后","hòu","back"),("旁","páng","beside"),("侧","cè","side"),
    ]),
    ("时间", [
        ("年","nián","year"),("月","yuè","month"),("日","rì","day"),("时","shí","hour"),
        ("分","fēn","minute"),("秒","miǎo","second"),("春","chūn","spring"),("夏","xià","summer"),
        ("秋","qiū","autumn"),("冬","dōng","winter"),("朝","zhāo","morning"),("夕","xī","dusk"),
        ("晨","chén","dawn"),("暮","mù","dusk"),("古","gǔ","ancient"),("今","jīn","now"),
        ("早","zǎo","early"),("晚","wǎn","late"),
    ]),
]

data = {
    "sets": [
        {"id": name, "name": name,
         "chars": [{"c": c, "p": p, "m": m} for (c, p, m) in chars]}
        for (name, chars) in SETS
    ]
}
total = sum(len(s["chars"]) for s in data["sets"])

# ---- Stroke data (hanzi-writer-data, Make Me A Hanzi / Arphic Public License) ----
# Bundled at build time so the writing animation works fully offline,
# no runtime fetch / CORS dependency.
#
# 数据优先级（保证人工裁决的修正在重建时不被 CDN 覆盖）：
#   1. 本地 hanzi-strokes.json —— 闭环采纳写回的"已裁决覆盖层"
#   2. CDN hanzi-writer-data —— 仅对覆盖层尚缺的字补全
LOCAL_STROKE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hanzi-strokes.json")
STROKES = {}
if os.path.exists(LOCAL_STROKE_PATH):
    try:
        STROKES = json.load(open(LOCAL_STROKE_PATH, encoding="utf-8"))
        print("loaded %d glyphs from local review overrides (hanzi-strokes.json)" % len(STROKES))
    except Exception as e:
        print("  (could not read local overrides: %s)" % e)

all_chars = [c["c"] for s in data["sets"] for c in s["chars"]]
for ch in all_chars:
    if ch in STROKES:
        continue  # 已由本地覆盖层提供，不再用 CDN 覆盖
    try:
        u = "https://cdn.jsdelivr.net/npm/hanzi-writer-data@2.0.1/%s.json" % urllib.parse.quote(ch)
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=25) as r:
            STROKES[ch] = json.loads(r.read().decode())
    except Exception as e:
        print("  (skip stroke data for %s: %s)" % (ch, e))
print("stroke data loaded: %d / %d chars" % (len(STROKES), len(all_chars)))
STROKES_JSON = json.dumps(STROKES, ensure_ascii=False)

DATA_JSON = json.dumps(data, ensure_ascii=False)

# ---- 活动区真实数据 ----
# 与 server.py 的 GET /activity 共用同一个 activity_payload()，保证构建快照
# 与运行时接口口径完全一致；Pages 无后端时首屏也是真实数据，不是假数字。
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import server as hanzi_server
from build_favicon import FAVICON_LINKS
ACTIVITY = hanzi_server.activity_payload()
ACTIVITY_JSON = json.dumps(ACTIVITY, ensure_ascii=False)


def _activity_snapshot_html(a):
    # 把真实快照直接写进 HTML：无 JS / 无后端时也能看到真实数字与事件
    st = a['stats']
    esc = lambda x: html.escape(str(x if x is not None else ''))
    pins = '\n'.join(
        '        <span class="pill p%d" title="%d 个汉字">%s</span>' % (i + 1, q['count'], esc(q['name']))
        for i, q in enumerate(a['pins'][:4]))

    def day(ts):
        try:
            return datetime.datetime.fromtimestamp(ts or 0).strftime('%m-%d')
        except Exception:
            return '--'

    rows = '\n'.join(
        '        <div class="feedrow" data-ch="%s"><b>%s</b> <span class="act">%s</span> '
        '<span class="cn">%s</span><span class="ftime">%s</span></div>'
        % (esc(e['char']), esc(e['actor']), esc(e['act']), esc(e['char']), day(e['ts']))
        for e in a['events'][:6]) or '        <div class="feedempty">暂无动态</div>'
    built = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    return '''      <div class="map-card" title="按分类字数分布">
%s
      </div>

      <div class="stats">
        <span><b class="warm">⚙ %d</b> 次笔画修正</span>
        <span><b class="warm">+ %d</b> 收录汉字</span>
      </div>

      <div class="livebar offline" title="启动 server.py --http 8787 后自动切换为实时刷新；也可用 ?api=http://127.0.0.1:8787 连接本地服务"><span class="dot"></span><span class="lv-label">SNAPSHOT</span><span class="lc" id="livecount">静态快照 · 构建于 %s</span></div>
      <div class="feed" id="feed">
%s
        <div class="feedmore" id="feedmore">共 %d 条记录 · 静态快照</div>
      </div>''' % (pins, st['accepted'], st['chars'], built, rows, len(a['events']))


ACTIVITY_HTML = _activity_snapshot_html(ACTIVITY)

# ---- HTML / CSS / JS ---------------------------------------------------
CSS = """
:root{
  --serif:"Songti SC","STSong","SimSun","NSimSun","宋体","Noto Serif CJK SC","Source Han Serif SC","Source Han Serif CN","Noto Serif SC","AR PL UMing CN","Times New Roman",Georgia,serif;
  --mono:"SF Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,"Songti SC","SimSun","Noto Serif CJK SC",monospace;
  --canvas:#ffffff;
  --ink:#18181b;
  --muted:#9b9ba3;
  --faint:#c9c9cf;
  --line:rgba(0,0,0,.08);
  --line2:rgba(0,0,0,.05);
  --hover:#f4f4f5;
  --pill:#ffffff;
  --panel:#ffffff;
  --accent:#2d68ff;
  --warm:#c2410c;
  --shadow:0 1px 2px rgba(0,0,0,.04), 0 8px 30px rgba(0,0,0,.10);
  --navy:#0b1020;
  --gridline:rgba(45,104,255,.13);
  --seg-on:#ffffff;
}
html.dark{
  --canvas:#0a0a0b;
  --ink:#f4f4f5;
  --muted:#7c7c84;
  --faint:#3a3a40;
  --line:rgba(255,255,255,.10);
  --line2:rgba(255,255,255,.06);
  --hover:#232327;
  --pill:#1c1c1f;
  --panel:#151517;
  --accent:#5b8bff;
  --warm:#f0883e;
  --shadow:0 1px 2px rgba(0,0,0,.4), 0 10px 34px rgba(0,0,0,.5);
  --navy:#0b1020;
  --gridline:rgba(91,139,255,.27);
  --seg-on:#333338;
}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{
  background:var(--canvas);
  color:var(--ink);
  font-family:var(--serif);
  font-size:14px;
  letter-spacing:.01em;
}
.app{position:relative;min-height:100vh;padding-bottom:120px}
.wordmark{position:absolute;top:22px;left:26px;font-size:27px;font-weight:800;letter-spacing:-0.03em;display:flex;align-items:baseline;gap:6px;z-index:5}
.wordmark .ver{font-size:13px;font-weight:500;color:var(--muted);letter-spacing:0}

.stage{display:flex;align-items:flex-start;gap:0;padding:74px 26px 0}
.library{flex:1;min-width:0;padding-right:30px}

/* category sections */
.catsec{margin-bottom:34px}
.cathead{font-size:13.5px;font-weight:600;color:var(--ink);margin:0 0 14px;display:flex;align-items:center;gap:7px;letter-spacing:-0.01em}
.cathead .cc{font-weight:500;color:var(--muted);font-size:12.5px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(74px,1fr));gap:6px 6px}
.card{position:relative;aspect-ratio:1/1;display:flex;flex-direction:column;align-items:center;justify-content:center;cursor:pointer;border-radius:13px;padding:6px 4px;color:var(--ink);transition:background .14s ease}
.card .cv{width:62%;max-width:52px;aspect-ratio:1/1;display:flex;align-items:center;justify-content:center}
.card .cv svg{width:100%;height:100%;display:block}
.card .lbl{margin-top:3px;text-align:center;line-height:1.15;overflow:hidden;max-width:100%}
.card .lbl .p{display:block;font-size:10px;color:var(--muted);letter-spacing:0;white-space:nowrap;text-overflow:ellipsis;overflow:hidden}
.card:hover{background:var(--hover)}
.card.sel{background:var(--hover)}
.card.sel::after{content:"";position:absolute;top:7px;right:7px;width:6px;height:6px;border-radius:50%;background:var(--accent)}
.card .fallback{font-size:30px;font-weight:600}
.empty{color:var(--muted);padding:40px 4px;font-size:14px}

/* right activity panel */
.activity{width:268px;flex:none;border-left:1px solid var(--line);padding:0 0 40px 26px;position:sticky;top:74px;align-self:flex-start}
.useagent{display:flex;align-items:center;justify-content:space-between;gap:10px;cursor:pointer;padding:4px 0 16px}
.useagent .ua-l{display:flex;align-items:center;gap:8px;color:var(--ink);font-size:13.5px}
.useagent .ua-l svg{width:16px;height:16px;color:var(--muted)}
.useagent .ua-brand{font-weight:800;font-size:15px;letter-spacing:-0.02em}
.map-card{position:relative;height:128px;border-radius:14px;overflow:hidden;border:1px solid var(--line);
  background:
    radial-gradient(circle at 1px 1px, var(--faint) 1.4px, transparent 1.6px) 0 0/14px 14px,
    linear-gradient(180deg, var(--hover), var(--canvas));
  margin-bottom:14px}
.map-card .pill{position:absolute;background:var(--ink);color:var(--canvas);font-size:10.5px;font-weight:500;padding:3px 8px;border-radius:999px;white-space:nowrap;box-shadow:0 2px 6px rgba(0,0,0,.18)}
.map-card .p1{top:16px;left:18px}
.map-card .p2{top:54px;right:20px}
.map-card .p3{bottom:18px;left:30px}
.map-card .p4{bottom:30px;right:26px}
.stats{display:flex;gap:16px;font-size:12px;color:var(--muted);margin-bottom:18px}
.stats b{font-weight:600}
.stats .warm{color:var(--warm);font-weight:600}
/* live activity indicator */
.livebar{display:flex;align-items:center;gap:7px;font-size:11.5px;font-weight:600;letter-spacing:.04em;
  color:var(--muted);margin:2px 0 14px;text-transform:uppercase}
.livebar .dot{width:7px;height:7px;border-radius:50%;background:#22c55e;box-shadow:0 0 0 0 rgba(34,197,94,.55);animation:pulse 1.8s infinite}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(34,197,94,.55)}70%{box-shadow:0 0 0 7px rgba(34,197,94,0)}100%{box-shadow:0 0 0 0 rgba(34,197,94,0)}}
.livebar .lc{font-weight:500;color:var(--faint);letter-spacing:0;text-transform:none}
.feed{display:flex;flex-direction:column;gap:13px;margin-bottom:22px;min-height:150px}
.feedrow{display:flex;align-items:baseline;gap:5px;font-size:12.5px;color:var(--muted);line-height:1.3;animation:fin .4s ease both;flex-wrap:nowrap;min-width:0}
@keyframes fin{from{opacity:0;transform:translateY(-5px)}to{opacity:1;transform:none}}
.feedrow b{color:var(--ink);font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0}
.feedrow .cn{color:var(--ink);font-weight:700;background:var(--hover);border-radius:6px;padding:0 5px;font-size:13px;white-space:nowrap;flex:none}
.feedrow .act{color:var(--muted);white-space:nowrap;flex:none}
.feedmore{font-size:12px;color:var(--muted);padding-top:2px}
.feedrow[data-ch]{cursor:pointer;padding:2px 4px;margin:0 -4px;border-radius:6px;transition:background .14s}
.feedrow[data-ch]:hover{background:var(--hover)}
.feedrow[data-ch]:hover .cn{background:var(--accent);color:#fff}
.ftime{margin-left:auto;color:var(--faint);font-size:11px;white-space:nowrap;flex:none}
.feedempty{color:var(--muted);font-size:12.5px;padding:8px 0}
.livebar.offline .dot{background:var(--faint);box-shadow:none;animation:none}

.sponsor{display:block;text-decoration:none;color:#fff;background:var(--navy);border-radius:14px;padding:16px;margin-bottom:18px;position:relative;overflow:hidden;min-height:96px}
.sponsor .stxt{color:#fff;font-size:14px;font-weight:600;line-height:1.35;max-width:78%}
.sponsor .sp-pill{position:absolute;top:14px;right:14px;background:rgba(255,255,255,.14);color:#fff;font-size:10.5px;padding:3px 9px;border-radius:999px;backdrop-filter:blur(4px)}
.sponsor .scollage{position:absolute;right:-10px;bottom:-10px;width:96px;height:70px;border-radius:12px;background:linear-gradient(135deg,#3b82f6,#8b5cf6);opacity:.9;transform:rotate(-8deg)}
.credit{font-size:12px;color:var(--muted)}
.credit a{color:var(--muted);text-decoration:none}
.credit a:hover{color:var(--ink)}

/* floating search pill */
.searchpill{position:fixed;left:50%;transform:translateX(-50%);bottom:26px;z-index:30;
  display:flex;align-items:center;gap:8px;width:min(560px,calc(100vw - 32px));
  background:var(--pill);border:1px solid var(--line);border-radius:999px;
  padding:6px 8px 6px 6px;box-shadow:var(--shadow)}
.sp-setwrap{position:relative}
.sp-set{display:flex;align-items:center;gap:5px;border:none;background:transparent;color:var(--ink);
  font:inherit;font-weight:600;font-size:13.5px;padding:7px 12px;border-radius:999px;cursor:pointer}
.sp-set:hover{background:var(--hover)}
.sp-set .caret{color:var(--muted);font-size:10px}
.sp-menu{position:absolute;bottom:calc(100% + 10px);left:0;min-width:180px;background:var(--panel);
  border:1px solid var(--line);border-radius:12px;box-shadow:var(--shadow);padding:6px;display:flex;flex-direction:column;gap:1px;z-index:40}
.sp-menu[hidden]{display:none}
.sp-menu button{display:flex;justify-content:space-between;align-items:center;border:none;background:transparent;color:var(--ink);
  font:inherit;font-size:13px;padding:7px 10px;border-radius:8px;cursor:pointer;text-align:left}
.sp-menu button:hover{background:var(--hover)}
.sp-menu button.active{color:var(--accent);font-weight:600}
.sp-menu button .mc{color:var(--muted);font-size:11.5px}
.sp-div{width:1px;height:22px;background:var(--line);flex:none}
.sp-mag{color:var(--muted);display:flex;width:18px;height:18px;flex:none}
.searchpill input{flex:1;min-width:0;border:none;outline:none;background:transparent;color:var(--ink);font:inherit;font-size:14px;padding:6px 4px}
.searchpill input::placeholder{color:var(--muted)}
.sp-kbd{border:1px solid var(--line);border-radius:6px;padding:2px 7px;font-size:11px;color:var(--muted);font-family:inherit;flex:none}
.sp-ic{flex:none;width:32px;height:32px;display:flex;align-items:center;justify-content:center;border:none;background:transparent;color:var(--muted);border-radius:999px;cursor:pointer}
.sp-ic:hover{background:var(--hover);color:var(--ink)}
.sp-ic svg{width:17px;height:17px}

/* detail modal — 布局参考 iconmcp.com（左预览 / 右信息） */
.backdrop{position:fixed;inset:0;background:rgba(10,10,12,.42);backdrop-filter:blur(3px);display:none;align-items:center;justify-content:center;z-index:60;padding:24px}
.backdrop.open{display:flex}
.panel{position:relative;background:var(--panel);border:1px solid var(--line);border-radius:24px;
  width:min(1040px,100%);height:min(88vh,720px);box-shadow:0 30px 90px rgba(0,0,0,.28);
  display:grid;grid-template-columns:minmax(300px,.92fr) 1.08fr;grid-template-rows:minmax(0,1fr);overflow:hidden}
/* 左：预览画布 */
.pv{padding:32px 30px 26px;display:flex;flex-direction:column;align-items:center;justify-content:center;
  border-right:1px solid var(--line);min-width:0;min-height:0;background:var(--canvas)}
.pv-stage{position:relative;width:100%;max-width:400px;aspect-ratio:1/1;flex:none;border-radius:6px}
.pv-grid,.pv-keys{position:absolute;inset:0;pointer-events:none;opacity:0;transition:opacity .18s}
.pv-grid{background-image:linear-gradient(to right,var(--gridline) 1px,transparent 1px),linear-gradient(to bottom,var(--gridline) 1px,transparent 1px);background-size:25px 25px}
.pv-stage.g-grid .pv-grid{opacity:1}
.pv-stage.g-keys .pv-keys{opacity:1}
.pv-keys svg{width:100%;height:100%;display:block}
.pchar{position:absolute;inset:14%;display:flex;align-items:center;justify-content:center;color:var(--ink);transition:inset .18s}
.pv-stage.g-pad .pchar{inset:23%}
.pchar svg{width:100%;height:100%;display:block;overflow:visible}
.pv-replay{position:absolute;top:8px;right:8px;width:32px;height:32px;border:1px solid var(--line);
  background:var(--pill);color:var(--muted);border-radius:9px;cursor:pointer;font-size:16px;line-height:1;z-index:3}
.pv-replay:hover{background:var(--hover);color:var(--ink)}
.pv-chips{display:flex;gap:8px;margin-top:26px;flex-wrap:wrap;justify-content:center}
.chip{border:1px solid transparent;background:transparent;color:var(--muted);font:inherit;font-size:12.5px;
  font-weight:500;padding:7px 15px;border-radius:999px;cursor:pointer;transition:.15s}
.chip:hover{color:var(--ink);background:var(--hover)}
.chip.on{background:var(--hover);color:var(--ink);font-weight:600}
/* 右：信息区 */
.pd{padding:24px 32px 24px;min-width:0;min-height:0;overflow:auto;display:flex;flex-direction:column}
.pd-top{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}
.pd-cat{font-size:13px;color:var(--muted);font-weight:500;display:flex;align-items:center;gap:7px}
.pd-cat .star{font-size:15px}
.pd-top-r{display:flex;gap:2px}
.iconbtn{width:32px;height:32px;border:none;background:transparent;color:var(--muted);border-radius:9px;
  cursor:pointer;font-size:19px;line-height:1;display:flex;align-items:center;justify-content:center}
.iconbtn:hover{background:var(--hover);color:var(--ink)}
.pd h2{margin:0 0 4px;font-size:36px;line-height:1.1;font-weight:800;letter-spacing:-.03em}
.pd-sub{display:flex;align-items:center;gap:9px;flex-wrap:wrap;color:var(--muted);font-size:13.5px;margin-bottom:16px}
.pd-sub .py{color:var(--ink);font-weight:600;font-size:14px}
.pd-badge{background:var(--hover);border-radius:999px;padding:2px 9px;font-size:11.5px;color:var(--muted)}
.seg{display:flex;background:var(--hover);border-radius:999px;padding:3px;margin-bottom:16px;max-width:340px}
.seg-btn{flex:1;border:none;background:transparent;color:var(--muted);font:inherit;font-size:13px;font-weight:500;
  padding:8px 12px;border-radius:999px;cursor:pointer;transition:.15s;white-space:nowrap}
.seg-btn.on{background:var(--seg-on);color:var(--ink);font-weight:600;box-shadow:0 1px 4px rgba(0,0,0,.08)}
.sizerow{display:flex;align-items:center;gap:20px;margin-bottom:16px}
.sizebox{width:68px;height:68px;flex:none;border-radius:16px;background:var(--hover);
  display:flex;align-items:center;justify-content:center;color:var(--muted);overflow:hidden}
.sizebox span{line-height:1;font-weight:500;transition:font-size .15s}
.size-ctl{flex:1;min-width:0}
.size-head{display:flex;justify-content:space-between;font-size:13px;color:var(--ink);font-weight:500;margin-bottom:11px}
.size-head span:last-child{color:var(--muted);font-weight:500}
#psize{width:100%;height:4px;margin:0;appearance:none;-webkit-appearance:none;border-radius:999px;
  background:linear-gradient(90deg,var(--ink) 0 var(--fill,50%),var(--line) var(--fill,50%) 100%);cursor:pointer;display:block}
#psize::-webkit-slider-thumb{appearance:none;width:15px;height:15px;border-radius:50%;background:var(--canvas);
  border:2.5px solid var(--ink);box-shadow:0 1px 3px rgba(0,0,0,.18);cursor:pointer}
#psize::-moz-range-thumb{width:12px;height:12px;border-radius:50%;background:var(--canvas);border:2.5px solid var(--ink);cursor:pointer}
.size-ticks{display:flex;justify-content:space-between;font-size:11px;color:var(--muted);margin-top:10px}
.btn-grid{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-bottom:16px}
.act{border:1px solid transparent;background:var(--hover);color:var(--ink);font:inherit;font-size:13px;font-weight:600;
  padding:11px 14px;border-radius:999px;cursor:pointer;transition:.15s;display:flex;align-items:center;justify-content:center;gap:7px}
.act:hover{filter:brightness(.96)}
.act.primary{background:var(--ink);color:var(--canvas)}
.act.primary:hover{opacity:.88}
.act:active{transform:scale(.985)}
.code-tabs{display:flex;gap:16px;margin-bottom:8px;flex-wrap:wrap}
.tab{border:none;background:transparent;color:var(--muted);font:inherit;font-size:12.5px;font-weight:500;
  padding:0 0 3px;cursor:pointer;border-bottom:1.5px solid transparent}
.tab:hover{color:var(--ink)}
.tab.active{color:var(--ink);border-bottom-color:var(--ink);font-weight:600}
.code{position:relative;background:var(--canvas);border:1px solid var(--line);border-radius:12px;
  padding:12px 14px;font-family:var(--mono);font-size:11.5px;
  line-height:1.6;white-space:pre-wrap;word-break:break-word;color:var(--ink);max-height:110px;overflow:auto;margin-bottom:16px}
.copy{position:absolute;top:10px;right:10px;border:1px solid var(--line);background:var(--pill);color:var(--ink);font:inherit;font-size:12px;padding:5px 11px;border-radius:8px;cursor:pointer}
.copy:hover{background:var(--hover)}
.tags{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:16px}
.tag{font-size:11.5px;color:var(--muted);background:var(--hover);border-radius:999px;padding:5px 11px;cursor:default}
.rel-head{font-size:13px;color:var(--muted);margin-bottom:10px}
.rel-list{display:flex;gap:9px;flex-wrap:wrap}
.rel{border:1px solid var(--line);background:var(--canvas);border-radius:12px;width:52px;height:52px;
  display:flex;align-items:center;justify-content:center;font-size:24px;color:var(--ink);cursor:pointer;transition:.15s}
.rel:hover{background:var(--hover);border-color:var(--faint)}
/* 反馈气泡 */
.bubble{position:absolute;top:58px;right:34px;width:252px;background:var(--panel);border:1px solid var(--line);
  border-radius:12px;box-shadow:var(--shadow);padding:12px 14px;font-size:12px;line-height:1.55;color:var(--muted);z-index:5;display:none}
.bubble.open{display:block}
.bubble code{display:block;background:var(--hover);color:var(--ink);padding:7px 9px;border-radius:7px;
  margin:8px 0;font-size:11px;word-break:break-all;font-family:var(--mono)}
.bubble button{border:none;background:var(--ink);color:var(--canvas);border-radius:7px;padding:6px 12px;font:inherit;font-size:11.5px;cursor:pointer}
/* agent modal 沿用 panel 外壳但改回单列 */
.agent .panel{display:block;max-width:620px;max-height:88vh;overflow:auto;padding:28px 30px;border-radius:20px}
.agent p{color:var(--muted);font-size:13.5px;line-height:1.6}
.agent h3{margin:4px 0 10px;font-size:19px}
.agent code{background:var(--hover);padding:2px 6px;border-radius:6px;font-size:13px}

@media (max-width:880px){
  .panel{grid-template-columns:1fr;grid-template-rows:auto auto;height:auto;max-height:92vh;overflow:auto;border-radius:20px}
  .pv{border-right:none;border-bottom:1px solid var(--line);padding:22px 20px}
  .pv-stage{max-width:270px}
  .pd{padding:22px 20px;overflow:visible}
  .pd h2{font-size:34px}
  .bubble{right:20px}
}
@media (max-width:880px){
  .activity{display:none}
  .library{padding-right:0}
  .stage{padding-left:18px;padding-right:18px}
  .wordmark{left:18px}
}
"""

JS = r"""
const DATA = __DATA__;
const STROKES = __STROKES__;
const ALL = "全部";
let activeSet = ALL, query = "";
// 列表卡片始终显示静态终帧；笔顺动画只在点击打开的弹窗里播放。

const $ = s => document.querySelector(s);
const library = $("#library");
const searchInput = $("#search");
const TOTAL = DATA.sets.reduce((a,s)=>a+s.chars.length,0);
$("#wmtotal").textContent = TOTAL;

function norm(s){return (s||"").toLowerCase().replace(/[āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜü]/g,
  m=>({"ā":"a","á":"a","ǎ":"a","à":"a","ē":"e","é":"e","ě":"e","è":"e","ī":"i","í":"i","ǐ":"i","ì":"i","ō":"o","ó":"o","ǒ":"o","ò":"o","ū":"u","ú":"u","ǔ":"u","ù":"u","ǖ":"v","ǘ":"v","ǚ":"v","ǜ":"v","ü":"v"}[m]||m));}

function buildSetMenu(){
  const menu=$("#setmenu"); menu.innerHTML="";
  const items=[{name:ALL,count:TOTAL}].concat(DATA.sets.map(s=>({name:s.name,count:s.chars.length})));
  items.forEach(it=>{
    const b=document.createElement("button");
    b.className=(it.name===activeSet?"active":"");
    b.innerHTML=`<span>${it.name}</span><span class="mc">${it.count}</span>`;
    b.onclick=()=>{activeSet=it.name;query="";searchInput.value="";$("#setbtn").firstChild.textContent=it.name===ALL?"汉字 ":it.name;menu.hidden=true;render();};
    menu.appendChild(b);
  });
}
function currentChars(){
  let chars = activeSet===ALL ? DATA.sets.flatMap(s=>s.chars.map(c=>({...c,set:s.name})))
                               : DATA.sets.find(s=>s.name===activeSet).chars.map(c=>({...c,set:activeSet}));
  if(query){const q=norm(query);
    chars=chars.filter(c=>norm(c.c).includes(q)||norm(c.p).includes(q)||norm(c.m).includes(q)||norm(c.set).includes(q));}
  return chars;
}
let renderGen=0;
function render(){
  renderGen++;
  const chars=currentChars();
  library.innerHTML="";
  if(!chars.length){library.innerHTML=`<div class="empty">没有匹配的汉字 · no matches</div>`;return;}
  // group by set — like iconmcp's category banded grid ("Actions 29", "Navigation 24"…)
  const groups={};
  chars.forEach(c=>{ (groups[c.set]=groups[c.set]||[]).push(c); });
  const order = activeSet===ALL ? DATA.sets.map(s=>s.name) : [activeSet];
  order.forEach(name=>{
    const list=groups[name]; if(!list||!list.length) return;
    const sec=document.createElement("section");
    sec.className="catsec";
    sec.innerHTML=`<div class="cathead">${name}<span class="cc">${list.length}</span></div>`;
    const g=document.createElement("div"); g.className="grid";
    list.forEach(c=>{
      const d=document.createElement("div");
      d.className="card";
      d.dataset.ch=c.c;
      d.innerHTML=`<div class="cv"></div><div class="lbl"><span class="p">${c.p}</span></div>`;
      d.onclick=()=>openChar(c);
      // 不做 hover 重播：浏览列表时保持静止，只有点击弹窗才播放笔顺动画
      g.appendChild(d);
      drawCard(d,c.c,true);   // final frame by default on load
    });
    sec.appendChild(g);
    library.appendChild(sec);
  });
}
// draw a single character stroke-by-stroke inside a card
function drawCard(card,ch,instant){
  const holder=card.querySelector(".cv");
  if(!holder) return;
  if(!STROKES[ch]){ holder.innerHTML=`<span class="fallback">${ch}</span>`; card.dataset.done="1"; return; }
  try{
    holder.innerHTML='<svg viewBox="0 0 1024 1024" preserveAspectRatio="xMidYMid meet"></svg>';
    const svg=holder.querySelector("svg");
    buildAndAnimate(svg,STROKES[ch],instant);
  }catch(e){ holder.innerHTML=`<span class="fallback">${ch}</span>`; }
  card.dataset.done="1";
}
function uhex(ch){return "U+"+ch.charCodeAt(0).toString(16).toUpperCase().padStart(4,"0");}

// ============ 活动区：真实数据（构建快照 + 服务端轮询） ============
// 数据来源只有一处：server.py 的 activity_payload()。构建时把快照内联进 HTML，
// 运行时若同源或 ?api= 指定了服务，则通过 /activity 轮询（ETag 304 增量）。
const ACTIVITY_SNAPSHOT = __ACTIVITY__;
const API_BASE = (new URLSearchParams(location.search).get("api") || "").replace(/\/$/, "");
const POLL_MS = 8000;
let activityETag = "", activityOnline = false, lastActivity = ACTIVITY_SNAPSHOT;

function relTime(ts){
  if(!ts) return "时间未知";
  const d=Math.max(0,Math.floor(Date.now()/1000)-ts);
  if(d<60) return "刚刚";
  if(d<3600) return Math.floor(d/60)+" 分钟前";
  if(d<86400) return Math.floor(d/3600)+" 小时前";
  const dt=new Date(ts*1000);
  return (dt.getMonth()+1)+"月"+dt.getDate()+"日";
}
function escHTML(x){return String(x==null?"":x).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}

function renderActivity(data,online){
  if(!data) return;
  const st=data.stats||{};
  const statsEl=document.querySelector(".stats");
  if(statsEl) statsEl.innerHTML=`<span><b class="warm">⚙ ${st.accepted||0}</b> 次笔画修正</span><span><b class="warm">+ ${st.chars||0}</b> 收录汉字</span>`;

  const pins=data.pins||[];
  pins.slice(0,4).forEach((p,i)=>{
    const el=document.querySelector(".map-card .p"+(i+1));
    if(el){el.textContent=p.name;el.title=(p.count||0)+" 个汉字";}
  });
  const mc=document.querySelector(".map-card");
  if(mc) mc.title="按分类字数分布："+pins.map(p=>p.name+" "+(p.count||0)).join(" · ");

  const bar=document.querySelector(".livebar");
  if(bar){
    bar.style.display="flex";
    bar.classList.toggle("offline",!online);
    const label=bar.querySelector(".lv-label"), lc=bar.querySelector("#livecount");
    const todo=(st.pending||0)+(st.openReports||0);
    if(label) label.textContent=online?"LIVE":"SNAPSHOT";
    if(lc) lc.textContent=online
      ? (todo?`${st.pending||0} 项待审 · ${st.openReports||0} 条待处理`:`已连接 · 每 ${POLL_MS/1000} 秒刷新`)
      : "静态快照 · 启动 server.py 可实时刷新";
  }

  const feed=document.querySelector("#feed");
  const more=document.querySelector("#feedmore");
  const evs=(data.events||[]).slice(0,6);
  if(feed){
    const rows=evs.map(e=>`<div class="feedrow" data-ch="${escHTML(e.char)}" title="${escHTML(e.detail||"")} · 点击查看 ${escHTML(e.char)} 详情"><b>${escHTML(e.actor)}</b> <span class="act">${escHTML(e.act)}</span> <span class="cn">${escHTML(e.char)}</span><span class="ftime">${relTime(e.ts)}</span></div>`).join("")
      || '<div class="feedempty">暂无动态</div>';
    feed.innerHTML=rows+(more?more.outerHTML:"");
    feed.querySelectorAll(".feedrow[data-ch]").forEach(row=>{
      row.onclick=()=>{
        const all=DATA.sets.flatMap(s=>s.chars.map(c=>({...c,set:s.name})));
        const hit=all.find(c=>c.c===row.dataset.ch);
        if(hit) openChar(hit);
      };
    });
  }
  const m=document.querySelector("#feedmore");
  if(m){
    const t=new Date((data.generatedAt||Date.now()/1000)*1000).toLocaleTimeString("zh-CN",{hour12:false});
    m.textContent=online?`共 ${(data.events||[]).length} 条记录 · 更新于 ${t}`
                        :`共 ${(data.events||[]).length} 条记录 · 静态快照`;
  }
}

async function pollActivity(first){
  const url=(API_BASE||"")+"/activity";
  try{
    const headers={};
    // 跨源时避免 If-None-Match 触发 preflight；同源走 304 增量
    if(activityETag && !API_BASE) headers["If-None-Match"]=activityETag;
    const r=await fetch(url,{headers,cache:"no-store"});
    if(r.status===304){
      if(!activityOnline){activityOnline=true;renderActivity(lastActivity,true);}
      return;
    }
    if(!r.ok) throw new Error("HTTP "+r.status);
    const data=await r.json();
    if(!data||!data.stats) throw new Error("bad payload");
    activityETag=r.headers.get("ETag")||"";
    lastActivity=data; activityOnline=true;
    renderActivity(data,true);
  }catch(e){
    if(first||activityOnline){
      activityOnline=false;
      renderActivity(lastActivity||ACTIVITY_SNAPSHOT,false);
    }
  }
}
function startActivity(){
  renderActivity(ACTIVITY_SNAPSHOT,false);
  pollActivity(true);
  setInterval(()=>{if(!document.hidden)pollActivity(false);},POLL_MS);
  document.addEventListener("visibilitychange",()=>{if(!document.hidden)pollActivity(false);});
}

// ---- stroke-by-stroke writing animation (hanzi-writer-data) ----
let clipSeq=0;   // SVG ids are document-global → must be unique across all cards
function showStrokes(ch,instant){
  const prev=$("#pchar");
  prev.innerHTML='<svg viewBox="0 0 1024 1024" preserveAspectRatio="xMidYMid meet"></svg>';
  const svg=prev.querySelector("svg");
  const d=STROKES[ch];
  if(!d){prev.innerHTML='<div style="font-size:54px">'+ch+'</div>';return;}
  buildAndAnimate(svg,d,instant);
}
// build the glyph geometry; returns the ink strokes + the transform group
function renderGlyph(svg,d){
  let xmin=1e9,xmax=-1e9,ymin=1e9,ymax=-1e9;
  (d.strokes||[]).forEach(s=>{
    const n=s.match(/-?\d+\.?\d*/g)||[];
    for(let i=0;i+1<n.length;i+=2){const x=+n[i],y=+n[i+1];
      xmin=Math.min(xmin,x);xmax=Math.max(xmax,x);ymin=Math.min(ymin,y);ymax=Math.max(ymax,y);}
  });
  (d.medians||[]).forEach(m=>m.forEach(p=>{
    xmin=Math.min(xmin,p[0]);xmax=Math.max(xmax,p[0]);ymin=Math.min(ymin,p[1]);ymax=Math.max(ymax,p[1]);}));
  const margin=72, span=Math.max(xmax-xmin,ymax-ymin)||1, sc=(1024-2*margin)/span;
  const cx=(xmin+xmax)/2, cy=(ymin+ymax)/2;          // center the glyph, not the bbox origin
  const tx=512-sc*cx, ty=512+sc*cy, sw=Math.min(150,span*0.16);
  if(!isFinite(sc)||!isFinite(tx)||!isFinite(ty)||!isFinite(sw)) throw new Error("bad geometry");
  let defs="",body="";
  (d.strokes||[]).forEach((sd,i)=>{
    const pid=clipSeq++;
    const med=(d.medians[i]||[]).map(p=>p[0]+" "+p[1]).join(" L ");
    defs+=`<clipPath id="clip${pid}"><path d="${sd}"/></clipPath>`;
    body+=`<g clip-path="url(#clip${pid})"><path class="ink" d="M ${med}" fill="none" stroke="currentColor" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round"/></g>`;
  });
  svg.innerHTML=`<g transform="translate(${tx.toFixed(2)},${ty.toFixed(2)}) scale(${sc.toFixed(4)},${(-sc).toFixed(4)})"><defs>${defs}</defs>${body}</g>`;
  return {inkEls:[...svg.querySelectorAll(".ink")], gEl:svg.querySelector("g")};
}
function buildAndAnimate(svg,d,instant){
  const {inkEls}=renderGlyph(svg,d);
  if(instant) return;   // 卡片显示静态终帧；只有弹窗播放动画
  let delay=0;
  inkEls.forEach(p=>{
    const len=p.getTotalLength();
    p.style.strokeDasharray=len;
    p.style.strokeDashoffset=len;
    p.animate([{strokeDashoffset:len},{strokeDashoffset:0}],{duration:430,delay:delay,easing:"ease-in-out",fill:"forwards"});
    delay+=430;
  });
  // 终帧兜底：动画跑完后移除 dash。若 WAAPI 的 fill:forwards 因后台标签页、
  // 虚拟时间或浏览器降级没落定，字仍完整可见，不会整字消失。
  setTimeout(()=>inkEls.forEach(p=>{p.style.strokeDasharray="";p.style.strokeDashoffset="";}),delay+120);
}
function codeFor(c,tab,size){
  const u=uhex(c.c);
  switch(tab){
    case "HTML": return `<!-- ${c.c} · ${c.p} · ${c.m} -->
<span class="hanzi" title="${c.p}">${c.c}</span>
<!-- unicode ${u} -->`;
    case "React": return `import React from 'react';

export function Hanzi() {
  return (
    <span className="hanzi" title="${c.p}">${c.c}</span>
  );
}`;
    case "Vue": return `<template>
  <span class="hanzi" :title="'${c.p}'">${c.c}</span>
</template>`;
    case "SVG": return glyphSVGString(c.c,size||24);
    case "MCP": return `{
  "tool": "get_hanzi",
  "arguments": { "char": "${c.c}" }
}

// → {
//   "glyph": "${c.c}",
//   "pinyin": "${c.p}",
//   "meaning": "${c.m}",
//   "unicode": "${u}",
//   "set": "${c.set}"
// }`;
  }
  return "";
}
let curChar=null, curTab="HTML";
const TABS=["HTML","React","Vue","SVG","MCP"];

// ---- 详情弹窗：导出 / 预览控制（布局参考 iconmcp.com）----
const SIZES=[16,20,24,32,48];
let curMode="anim";
function exportSize(){const el=$("#psize");return SIZES[el?+el.value:2];}
function inkColor(){return (getComputedStyle(document.documentElement).getPropertyValue("--ink")||"#18181b").trim();}
function glyphSVGString(ch,size,ink){
  const d=STROKES[ch];
  if(!d) return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 64 64"><text x="32" y="48" font-size="52" text-anchor="middle">${ch}</text></svg>`;
  const tmp=document.createElementNS("http://www.w3.org/2000/svg","svg");
  renderGlyph(tmp,d);
  const inner=tmp.innerHTML.replace(/currentColor/g,ink||inkColor());
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 1024 1024" fill="none">\n  ${inner}\n</svg>`;
}
function flash(btn,txt){
  if(!btn) return;
  const old=btn.textContent;btn.textContent=txt;
  clearTimeout(btn._flash);btn._flash=setTimeout(()=>{btn.textContent=old;},1300);
}
function legacyCopy(t,btn,ok){
  const ta=document.createElement("textarea");ta.value=t;ta.style.position="fixed";ta.style.opacity="0";
  document.body.appendChild(ta);ta.select();
  try{document.execCommand("copy");flash(btn,ok);}catch(e){flash(btn,"复制失败");}
  ta.remove();
}
function copyText(t,btn,ok){
  if(navigator.clipboard&&navigator.clipboard.writeText) navigator.clipboard.writeText(t).then(()=>flash(btn,ok)).catch(()=>legacyCopy(t,btn,ok));
  else legacyCopy(t,btn,ok);
}
function downloadBlob(blob,name){
  const a=document.createElement("a"),url=URL.createObjectURL(blob);
  a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1500);
}
function copySVG(){if(!curChar)return;copyText(glyphSVGString(curChar.c,exportSize()),$("#copysvg"),"✓ 已复制");}
function downloadSVG(){if(!curChar)return;
  downloadBlob(new Blob([glyphSVGString(curChar.c,exportSize())],{type:"image/svg+xml;charset=utf-8"}),curChar.c+".svg");
  flash($("#dltsvg"),"✓ 已下载");}
function downloadPNG(){
  if(!curChar)return;
  const size=512, ch=curChar.c;
  const url=URL.createObjectURL(new Blob([glyphSVGString(ch,size,"#18181b")],{type:"image/svg+xml;charset=utf-8"}));
  const img=new Image();
  img.onload=()=>{
    const cv=document.createElement("canvas");cv.width=cv.height=size;
    const cx=cv.getContext("2d");cx.fillStyle="#ffffff";cx.fillRect(0,0,size,size);cx.drawImage(img,0,0,size,size);
    URL.revokeObjectURL(url);
    cv.toBlob(b=>{if(b){downloadBlob(b,ch+".png");flash($("#dltpng"),"✓ 已下载");}else flash($("#dltpng"),"导出失败");});
  };
  img.onerror=()=>{URL.revokeObjectURL(url);flash($("#dltpng"),"导出失败");};
  img.src=url;
}
function buildRelated(c){
  const box=$("#prelated");box.innerHTML="";
  const all=DATA.sets.flatMap(s=>s.chars.map(x=>({...x,set:s.name})));
  const n=((STROKES[c.c]||{}).strokes||[]).length;
  const pool=all.filter(x=>x.c!==c.c&&x.set===c.set)
    .sort((a,b)=>Math.abs(((STROKES[a.c]||{}).strokes||[]).length-n)-Math.abs(((STROKES[b.c]||{}).strokes||[]).length-n));
  pool.slice(0,6).forEach(x=>{
    const d=document.createElement("div");d.className="rel";d.textContent=x.c;
    d.title=x.p+" · "+x.m;d.onclick=()=>openChar(x);box.appendChild(d);
  });
  if(!pool.length) box.innerHTML='<span style="font-size:12px;color:var(--muted)">暂无同分类汉字</span>';
}

// ---- URL 状态双向同步（对齐 iconmcp.com 的 ?icon= 深链接）----
// 打开/关闭详情时写回地址栏；浏览器前进/后退也能还原弹窗。
// 只增删 char / agent，保留 set / theme / live 等既有参数。
function clearModal(sp){sp.delete("char");sp.delete("icon");sp.delete("agent");}
function modalURL(mutate,push){
  const sp=new URLSearchParams(location.search);
  mutate(sp);
  const q=sp.toString();
  const url=location.pathname+(q?"?"+q:"")+location.hash;
  try{
    (push?history.pushState:history.replaceState).call(history,{hanziModal:1},"",url);
  }catch(e){ /* file:// 下浏览器禁止 pushState：弹窗照常工作，仅地址栏不变 */ }
}
function setCharURL(ch,push){
  const sp=new URLSearchParams(location.search);
  if((sp.get("char")||sp.get("icon"))===ch && !sp.has("agent")) return;
  modalURL(s=>{clearModal(s);s.set("char",ch);},push);
}
function setAgentURL(push){
  if(new URLSearchParams(location.search).has("agent")) return;
  modalURL(s=>{clearModal(s);s.set("agent","1");},push);
}
function clearModalURL(){
  const sp=new URLSearchParams(location.search);
  if(!sp.has("char")&&!sp.has("icon")&&!sp.has("agent")) return;
  modalURL(clearModal,false);
}
function openChar(c){
  curChar=c;curTab="HTML";curMode="anim";
  document.querySelectorAll("#pseg .seg-btn").forEach(b=>b.classList.toggle("on",b.dataset.m==="anim"));
  $("#pbubble").classList.remove("open");
  showStrokes(c.c,false);
  $("#replay").onclick=()=>showStrokes(c.c,curMode==="static");
  const n=((STROKES[c.c]||{}).strokes||[]).length;
  $("#pname").textContent=c.c;
  $("#pcat").textContent=c.set;
  $("#ppinyin").textContent=c.p;
  $("#pmeaning").textContent=c.m;
  $("#pstrokes").textContent=n+" 笔";
  $("#psizechar").textContent=c.c;
  $("#ptags").innerHTML=`<span class="tag">${uhex(c.c)}</span><span class="tag">${c.set}</span><span class="tag">${c.p}</span><span class="tag">${n} 笔</span>`;
  $("#pbcode").textContent=`report_hanzi(char="${c.c}", note="…")`;
  buildRelated(c);
  buildTabs();
  library.querySelectorAll(".card.sel").forEach(x=>x.classList.remove("sel"));
  const card=library.querySelector('[data-ch="'+c.c+'"]');
  if(card) card.classList.add("sel");
  $("#backdrop").classList.add("open");
  setCharURL(c.c,true);
}
function buildTabs(){
  const t=$("#tabs");t.innerHTML="";
  TABS.forEach(name=>{
    const b=document.createElement("button");
    b.className="tab"+(name===curTab?" active":"");
    b.textContent=name;
    b.onclick=()=>{curTab=name;buildTabs();renderCode();};
    t.appendChild(b);
  });
  renderCode();
}
function renderCode(){
  $("#code").textContent=codeFor(curChar,curTab,exportSize());
}
function copyCode(){
  if(!curChar) return;
  copyText($("#code").textContent,$("#copybtn"),"✓ 已复制");
}
function openAgent(){
  $("#backdrop2").classList.add("open");
  setAgentURL(true);
}
// 连通检测：真正打一次本地 MCP HTTP 服务
function testMCP(btn){
  const el=$("#mcptest");
  el.style.color="var(--muted)"; el.textContent="检测中…";
  fetch("http://127.0.0.1:8787/health",{cache:"no-store"})
    .then(r=>r.json())
    .then(d=>{ if(d&&d.ok){ el.style.color="#16a34a"; el.textContent="✓ 已连接 · "+d.chars+" 个汉字 · v"+(d.server&&d.server.version||""); }
               else { el.style.color="#dc2626"; el.textContent="✗ 服务异常"; } })
    .catch(()=>{ el.style.color="#dc2626"; el.textContent="✗ 未启动 —— 先运行 python3 server.py --http 8787"; });
}
function closeAll(){
  document.querySelectorAll(".backdrop").forEach(b=>b.classList.remove("open"));
  library.querySelectorAll(".card.sel").forEach(c=>c.classList.remove("sel"));
  $("#pbubble").classList.remove("open");
  clearModalURL();
}

searchInput.addEventListener("input",e=>{query=e.target.value;render();});
document.addEventListener("keydown",e=>{
  if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==="k"){e.preventDefault();searchInput.focus();searchInput.select();}
  if(e.key==="Escape")closeAll();
});
document.querySelectorAll(".backdrop").forEach(b=>b.addEventListener("click",e=>{if(e.target===b)closeAll();}));
document.querySelector("#close1").onclick=closeAll;
document.querySelector("#close2").onclick=closeAll;
document.querySelector("#copybtn").onclick=copyCode;
document.querySelector("#agentbtn").onclick=openAgent;
document.querySelector("#copysvg").onclick=copySVG;
document.querySelector("#dltsvg").onclick=downloadSVG;
document.querySelector("#dltpng").onclick=downloadPNG;
document.querySelectorAll(".pv-chips .chip").forEach(b=>b.onclick=()=>{
  const on=b.classList.toggle("on");
  $("#pvstage").classList.toggle("g-"+b.dataset.t,on);
});
document.querySelectorAll("#pseg .seg-btn").forEach(b=>b.onclick=()=>{
  document.querySelectorAll("#pseg .seg-btn").forEach(x=>x.classList.toggle("on",x===b));
  curMode=b.dataset.m;
  if(curChar) showStrokes(curChar.c,curMode==="static");
});
$("#psize").oninput=e=>{
  const i=+e.target.value,sz=SIZES[i];
  e.target.style.setProperty("--fill",(i/(SIZES.length-1)*100)+"%");
  $("#psizeval").textContent=sz+" px";
  $("#psizechar").style.fontSize=Math.min(sz,48)+"px";
  if(curTab==="SVG") renderCode();
};
$("#pflag").onclick=()=>$("#pbubble").classList.toggle("open");
$("#pbcopy").onclick=()=>copyText($("#pbcode").textContent,$("#pbcopy"),"✓ 已复制");

// 浏览器前进/后退：按 URL 还原弹窗（不再写回，避免污染历史栈）
window.addEventListener("popstate",()=>{
  const sp=new URLSearchParams(location.search);
  const ch=sp.get("char")||sp.get("icon");
  if(sp.has("agent")){
    document.querySelectorAll(".backdrop").forEach(b=>b.classList.remove("open"));
    $("#backdrop2").classList.add("open");
  }else if(ch){
    const all=DATA.sets.flatMap(s=>s.chars.map(c=>({...c,set:s.name})));
    const hit=all.find(c=>c.c===ch);
    if(hit){openChar(hit);return;}   // URL 已一致，setCharURL 不会重复 push
    closeAll();
  }else{
    document.querySelectorAll(".backdrop").forEach(b=>b.classList.remove("open"));
    library.querySelectorAll(".card.sel").forEach(c=>c.classList.remove("sel"));
  }
});

// platform-aware keyboard hint (⌘K on Mac, Ctrl K elsewhere) — matches iconmcp.com
(function(){
  const isMac=/Mac|iPhone|iPad|iPod/.test(navigator.platform||navigator.userAgent||"");
  const k=$("#kbdhint"); if(k) k.textContent=isMac?"⌘K":"Ctrl K";
})();

// theme toggle — persisted under the same key iconmcp.com uses ("iconus-theme")
(function(){
  const SUN='<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>';
  const MOON='<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8Z"/></svg>';
  const root=document.documentElement;
  function apply(t){root.classList.toggle("dark",t==="dark");const b=$("#themetoggle");if(b)b.innerHTML=t==="dark"?SUN:MOON;}
  let t; try{t=localStorage.getItem("iconus-theme")}catch(e){}
  if(!t){const q=new URLSearchParams(location.search).get("theme");if(q==="dark"||q==="light")t=q;}
  if(!t) t=matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light";
  apply(t);
  const btn=$("#themetoggle");
  if(btn) btn.onclick=()=>{const cur=root.classList.contains("dark")?"dark":"light";const nxt=cur==="dark"?"light":"dark";apply(nxt);try{localStorage.setItem("iconus-theme",nxt)}catch(e){}};
})();

// deep-link: ?char=中 opens detail; ?set=数字 preselects a set
(function(){
  const sp=new URLSearchParams(location.search);
  const setQ=sp.get("set");
  if(setQ && DATA.sets.some(s=>s.name===setQ)){activeSet=setQ;
    $("#setbtn").firstChild.textContent=setQ;}
  buildSetMenu();
  // set dropdown toggle
  const setBtn=$("#setbtn"), setMenu=$("#setmenu");
  setBtn.onclick=e=>{e.stopPropagation();setMenu.hidden=!setMenu.hidden;};
  document.addEventListener("click",()=>setMenu.hidden=true);
  render();
  const charQ=sp.get("char")||sp.get("icon");
  if(charQ){const all=DATA.sets.flatMap(s=>s.chars.map(c=>({...c,set:s.name})));
    const hit=all.find(c=>c.c===charQ); if(hit)openChar(hit);}
  if(sp.has("agent")) openAgent();
  startActivity();
})();
"""

SEARCH_ICO = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></svg>'
AGENT_CODE = """{
  "mcpServers": {
    "hanzi": {
      "command": "python3",
      "args": ["/path/to/HanziMCP/server.py"]
    }
  }
}"""
JS2 = JS.replace("__DATA__", DATA_JSON)

BODY_TPL = """
<div class="app">
  <div class="wordmark">汉字<span class="ver" id="wmtotal">148</span></div>

  <div class="stage">
    <main class="library" id="library"></main>

    <aside class="activity">
      <div class="useagent" id="agentbtn">
        <div class="ua-l">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 17 17 7M9 7h8v8"/></svg>
          Use in your agent
        </div>
        <div class="ua-brand">汉字MCP</div>
      </div>

__ACTIVITY_HTML__

      <a class="sponsor" href="https://iconmcp.com" target="_blank" rel="noopener">
        <span class="sp-pill">Sponsor</span>
        <div class="stxt">Capture anything, beautifully.</div>
        <div class="scollage"></div>
      </a>

      <div class="credit"><a href="https://x.com/creativedash" target="_blank" rel="noopener">@creativedash</a></div>
    </aside>
  </div>

  <div class="searchpill">
    <div class="sp-setwrap">
      <button class="sp-set" id="setbtn">汉字 <span class="caret">▾</span></button>
      <div class="sp-menu" id="setmenu" hidden></div>
    </div>
    <span class="sp-div"></span>
    <span class="sp-mag"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></svg></span>
    <input id="search" placeholder="搜索 {TOTAL} 汉字（拼音 / 释义 / 字形）" autocomplete="off">
    <kbd class="sp-kbd" id="kbdhint">⌘K</kbd>
    <button class="sp-ic" title="网格视图"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg></button>
    <button class="sp-ic" title="筛选"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="4" y1="6" x2="20" y2="6"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="18" x2="20" y2="18"/></svg></button>
    <button class="sp-ic" id="themetoggle" title="Light and dark mode" aria-label="Light and dark mode"></button>
  </div>
</div>

<!-- char modal -->
<div class="backdrop" id="backdrop">
  <div class="panel">
    <div class="pv">
      <div class="pv-stage g-grid g-keys" id="pvstage">
        <div class="pv-grid"></div>
        <div class="pv-keys">
          <svg viewBox="0 0 400 400" fill="none" stroke="var(--accent)" stroke-width="1">
            <rect x="30" y="30" width="340" height="340" opacity=".55"/>
            <circle cx="200" cy="200" r="170" opacity=".42"/>
            <rect x="70" y="70" width="260" height="260" opacity=".38"/>
            <line x1="200" y1="30" x2="200" y2="370" opacity=".38" stroke-dasharray="6 7"/>
            <line x1="30" y1="200" x2="370" y2="200" opacity=".38" stroke-dasharray="6 7"/>
          </svg>
        </div>
        <div class="pchar" id="pchar"></div>
        <button class="pv-replay" id="replay" title="重播笔顺">↻</button>
      </div>
      <div class="pv-chips">
        <button class="chip on" data-t="grid">Grid</button>
        <button class="chip on" data-t="keys">Keylines</button>
        <button class="chip" data-t="pad">Padding</button>
      </div>
    </div>
    <div class="pd">
      <div class="pd-top">
        <span class="pd-cat"><span class="star">☆</span><span id="pcat"></span></span>
        <div class="pd-top-r">
          <button class="iconbtn" id="pflag" title="上报字形问题">⚑</button>
          <button class="iconbtn pclose" id="close1">×</button>
        </div>
      </div>
      <div class="bubble" id="pbubble">
        发现字形问题？在 MCP 里调用下面的工具提交反馈，采纳权归人工审阅。
        <code id="pbcode"></code>
        <button id="pbcopy">复制指令</button>
      </div>
      <h2 id="pname"></h2>
      <div class="pd-sub"><span class="py" id="ppinyin"></span><span class="pd-badge" id="pstrokes"></span><span id="pmeaning"></span></div>
      <div class="seg" id="pseg">
        <button class="seg-btn on" data-m="anim">笔顺动画</button>
        <button class="seg-btn" data-m="static">静态字形</button>
      </div>
      <div class="sizerow">
        <div class="sizebox"><span id="psizechar"></span></div>
        <div class="size-ctl">
          <div class="size-head"><span>Size</span><span id="psizeval">24 px</span></div>
          <input type="range" id="psize" min="0" max="4" step="1" value="2" aria-label="导出尺寸">
          <div class="size-ticks"><span>16</span><span>20</span><span>24</span><span>32</span><span>48</span></div>
        </div>
      </div>
      <div class="btn-grid">
        <button class="act primary" id="copysvg">▣ 复制 SVG</button>
        <button class="act" id="copybtn">&lt;/&gt; 复制代码</button>
        <button class="act" id="dltsvg">⬇ SVG</button>
        <button class="act" id="dltpng">▧ PNG</button>
      </div>
      <div class="code-tabs" id="tabs"></div>
      <div class="code"><span id="code"></span></div>
      <div class="tags" id="ptags"></div>
      <div class="related"><div class="rel-head">Related</div><div class="rel-list" id="prelated"></div></div>
    </div>
  </div>
</div>

<!-- agent modal -->
<div class="backdrop agent" id="backdrop2">
  <div class="panel">
    <button class="iconbtn pclose" id="close2">×</button>
    <h3>在 Agent 中使用 汉字MCP</h3>
    <p>这是一个真实可运行的 MCP server（<code>server.py</code>，纯标准库；把下面 JSON 里的路径改成你自己的仓库路径），暴露 <code>get_hanzi</code> · <code>search_hanzi</code> · <code>list_sets</code> · <code>hanzi_paths</code> · <code>report_hanzi</code> · <code>fix_hanzi</code> · <code>validate_revision</code> · <code>list_revisions</code> · <code>list_reports</code> 共 9 个工具。</p>

    <div style="font-size:12px;font-weight:600;color:var(--muted);margin:16px 0 8px;letter-spacing:.02em">方式一 · 本地 stdio（Claude Desktop / Cursor / WorkBuddy）</div>
    <div class="code"><button class="copy" onclick="navigator.clipboard&&navigator.clipboard.writeText(this.parentElement.querySelector('span').textContent)">复制</button><span>{AGENT_CODE}</span></div>

    <div style="font-size:12px;font-weight:600;color:var(--muted);margin:16px 0 8px;letter-spacing:.02em">方式二 · HTTP（浏览器可直接访问 / 远程客户端）</div>
    <div class="code"><button class="copy" onclick="navigator.clipboard&&navigator.clipboard.writeText(this.parentElement.querySelector('span').textContent)">复制</button><span>python3 server.py --http 8787
# → POST http://127.0.0.1:8787/mcp   （健康检查 GET /health）</span></div>

    <div style="display:flex;align-items:center;gap:10px;margin-top:14px">
      <button class="btn" onclick="testMCP(this)" style="border:1px solid var(--line);background:var(--ink);color:var(--canvas);border-radius:9px;padding:7px 14px;font:inherit;font-size:13px;cursor:pointer">测试连接</button>
      <span id="mcptest" style="font-size:12.5px;color:var(--muted)">点一下检测 HTTP 服务是否在跑</span>
    </div>
  </div>
</div>
"""

HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>汉字MCP · hanzi library</title>
{FAVICON}
<style>{CSS}</style>
</head>
<body>
__BODY__
<script>{JS}</script>
</body>
</html>""".replace("{CSS}", CSS).replace("{FAVICON}", FAVICON_LINKS).replace("__BODY__", BODY_TPL).replace("__ACTIVITY_HTML__", ACTIVITY_HTML).replace("{TOTAL}", str(total)).replace("{AGENT_CODE}", AGENT_CODE).replace("{JS}", JS2).replace("__STROKES__", STROKES_JSON).replace("__ACTIVITY__", ACTIVITY_JSON)

with open("hanzi-mcp.html", "w", encoding="utf-8") as f:
    f.write(HTML)
print(f"wrote hanzi-mcp.html  ({len(HTML)} bytes, {total} hanzi across {len(SETS)} sets)")
