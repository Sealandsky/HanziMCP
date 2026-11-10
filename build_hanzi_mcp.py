#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build hanzi-mcp.html: a faithful frontend clone of iconmcp.com
with the line icons replaced by Chinese characters (汉字).

Single self-contained file (inline CSS + JS + data). Reproducible.
"""
import json, html, urllib.request, urllib.parse, re, math, os

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

# ---- HTML / CSS / JS ---------------------------------------------------
CSS = """
:root{
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
}
html.dark{
  --canvas:#0a0a0b;
  --ink:#f4f4f5;
  --muted:#7c7c84;
  --faint:#3a3a40;
  --line:rgba(255,255,255,.10);
  --line2:rgba(255,255,255,.06);
  --hover:#161618;
  --pill:#161618;
  --panel:#161618;
  --accent:#5b8bff;
  --warm:#f0883e;
  --shadow:0 1px 2px rgba(0,0,0,.4), 0 10px 34px rgba(0,0,0,.5);
  --navy:#0b1020;
}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{
  background:var(--canvas);
  color:var(--ink);
  font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,"PingFang SC","Noto Sans SC","Microsoft YaHei",sans-serif;
  -webkit-font-smoothing:antialiased;
  font-feature-settings:"cv11","ss01";
  font-size:14px;
  letter-spacing:-0.01em;
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
.feedrow{display:flex;align-items:baseline;gap:5px;font-size:12.5px;color:var(--muted);line-height:1.3;animation:fin .4s ease both}
@keyframes fin{from{opacity:0;transform:translateY(-5px)}to{opacity:1;transform:none}}
.feedrow b{color:var(--ink);font-weight:600}
.feedrow .cn{color:var(--ink);font-weight:700;background:var(--hover);border-radius:6px;padding:0 5px;font-size:13px}
.feedrow .act{color:var(--muted)}
.feedrow.awriting .cn{background:var(--accent);color:#fff}
.feedrow .fdot{display:inline-block;width:5px;height:5px;border-radius:50%;background:var(--accent);margin-right:2px;vertical-align:middle;animation:blink 1s infinite}
@keyframes blink{50%{opacity:.25}}
.feedmore{font-size:12px;color:var(--muted);padding-top:2px}

/* card currently being written by a live agent */
.card.writing{background:color-mix(in srgb,var(--accent) 10%,transparent);box-shadow:inset 0 0 0 1.5px color-mix(in srgb,var(--accent) 28%,transparent)}
.card.writing .cv{filter:drop-shadow(0 0 9px color-mix(in srgb,var(--accent) 60%,transparent))}
.card .writer{position:absolute;top:-7px;left:50%;transform:translateX(-50%);white-space:nowrap;
  background:var(--accent);color:#fff;font-size:9px;font-weight:600;padding:2px 7px;border-radius:999px;
  box-shadow:0 2px 6px rgba(45,104,255,.35);opacity:0;transition:opacity .18s;pointer-events:none;z-index:2}
.card.writing .writer{opacity:1}
/* glowing pen tip that travels along the stroke currently being written */
.pentip-g{pointer-events:none}
.pentip-g .tip-halo{fill:var(--accent);opacity:.26}
.pentip-g .tip-mid{fill:var(--accent);opacity:.55}
.pentip-g .tip-core{fill:var(--accent);stroke:#ffffff;stroke-width:16;paint-order:stroke}
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

/* detail modal */
.backdrop{position:fixed;inset:0;background:rgba(10,10,12,.42);backdrop-filter:blur(3px);display:none;align-items:center;justify-content:center;z-index:60;padding:24px}
.backdrop.open{display:flex}
.panel{position:relative;background:var(--panel);border:1px solid var(--line);border-radius:18px;width:min(720px,100%);max-height:88vh;overflow:auto;box-shadow:0 24px 70px rgba(0,0,0,.32);padding:26px 28px}
.pclose{position:absolute;top:14px;right:16px;border:none;background:transparent;color:var(--muted);font-size:24px;line-height:1;cursor:pointer;border-radius:8px;width:34px;height:34px}
.pclose:hover{background:var(--hover);color:var(--ink)}
.phead{display:flex;gap:24px;align-items:center;margin-bottom:20px}
.preview{position:relative;width:150px;height:150px;flex:none;border:1px solid var(--line);border-radius:14px;display:flex;align-items:center;justify-content:center;background:var(--canvas)}
.pchar{width:120px;height:120px;color:var(--ink)}
.pchar svg{width:100%;height:100%}
.replaybtn{position:absolute;bottom:8px;right:8px;border:1px solid var(--line);background:var(--pill);color:var(--ink);width:30px;height:30px;border-radius:9px;cursor:pointer;font-size:15px}
.replaybtn:hover{background:var(--hover)}
.pinfo{flex:1;min-width:0}
.pinfo h2{margin:0 0 4px;font-size:40px;font-weight:800;letter-spacing:-0.02em}
.py{color:var(--muted);font-size:14px;margin-bottom:12px}
.tags{display:flex;flex-wrap:wrap;gap:6px}
.tag{font-size:11.5px;color:var(--muted);border:1px solid var(--line);border-radius:999px;padding:3px 10px}
.tabs{display:flex;gap:4px;border-bottom:1px solid var(--line);margin-bottom:14px;flex-wrap:wrap}
.tab{border:none;background:transparent;color:var(--muted);font:inherit;font-size:13px;padding:8px 12px;cursor:pointer;border-bottom:2px solid transparent;margin-bottom:-1px}
.tab:hover{color:var(--ink)}
.tab.active{color:var(--ink);border-bottom-color:var(--accent);font-weight:600}
.code{position:relative;background:var(--canvas);border:1px solid var(--line);border-radius:12px;padding:16px 16px;font-family:"SF Mono",ui-monospace,Menlo,Consolas,monospace;font-size:12.5px;line-height:1.6;white-space:pre-wrap;word-break:break-word;color:var(--ink)}
.copy{position:absolute;top:10px;right:10px;border:1px solid var(--line);background:var(--pill);color:var(--ink);font:inherit;font-size:12px;padding:5px 11px;border-radius:8px;cursor:pointer}
.copy:hover{background:var(--hover)}
.agent .panel{max-width:560px}
.agent p{color:var(--muted);font-size:13.5px;line-height:1.6}
.agent h3{margin:4px 0 10px;font-size:19px}
.agent code{background:var(--hover);padding:2px 6px;border-radius:6px;font-size:13px}

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
const INSTANT = new URLSearchParams(location.search).has("static"); // ?static=1 → skip draw animation

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
      d.addEventListener("mouseenter",()=>{ if(d.dataset.done==="1" && !d.classList.contains("writing") && d.isConnected) drawCard(d,c.c,INSTANT); });
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

// ============ LIVE: agents writing characters in real time ============
const LIVE_ON = !new URLSearchParams(location.search).has("live0"); // ?live0=1 disables
const AGENTS = ["王羲之","颜真卿","欧阳询","苏轼","米芾","赵孟頫","柳公权","褚遂良"];
const MAX_LIVE = 4;                       // how many agents write at the same time
const SVGNS = "http://www.w3.org/2000/svg";
const feedEl = $("#feed");
let writerBusy = new Set();     // chars currently being written (avoid overlap)
let feedCount = 0;

function pushFeed(name, ch, writing){
  if(!feedEl) return;
  const more = $("#feedmore");
  const row=document.createElement("div");
  row.className="feedrow"+(writing?" awriting":"");
  row.innerHTML=`<b>${name}</b> <span class="act">${writing?"正在书写":"写好了"}</span> `+
    (writing?`<span class="fdot"></span>`:"")+`<span class="cn">${ch}</span>`;
  feedEl.insertBefore(row, more||null);
  while(feedEl.querySelectorAll(".feedrow").length>6){
    const rows=feedEl.querySelectorAll(".feedrow");
    rows[rows.length-1].remove();
  }
  feedCount++;
  if(more) more.textContent=`+ 已完成 ${feedCount} 次书写`;
  return row;
}

// write one random visible character stroke-by-stroke, then log it
function liveWrite(){
  if(!LIVE_ON || document.hidden) return;
  const cards=[...library.querySelectorAll(".card")].filter(d=>STROKES[d.dataset.ch] && !writerBusy.has(d.dataset.ch));
  if(!cards.length) return;
  const card=cards[Math.floor(Math.random()*cards.length)];
  const ch=card.dataset.ch;
  const name=AGENTS[Math.floor(Math.random()*AGENTS.length)];
  const nStrokes=STROKES[ch].strokes.length;
  if(!nStrokes) return;
  writerBusy.add(ch);

  // reset to a blank slate, then write it live with a travelling pen tip
  const holder=card.querySelector(".cv");
  holder.innerHTML='<svg viewBox="0 0 1024 1024" preserveAspectRatio="xMidYMid meet"></svg>';
  const writer=document.createElement("span");
  writer.className="writer"; writer.textContent=name;
  card.appendChild(writer);
  card.classList.add("writing");
  const row=pushFeed(name,ch,true);
  updateLiveCount();

  animateLive(holder.querySelector("svg"), STROKES[ch], ()=>{
    if(card.isConnected){ card.classList.remove("writing"); writer.remove(); }
    if(row && row.isConnected){
      row.classList.remove("awriting");
      const dot=row.querySelector(".fdot"); if(dot) dot.remove();
      const act=row.querySelector(".act"); if(act) act.textContent=`写好了 · ${nStrokes} 笔`;
      row.style.animation="none";
    }
    writerBusy.delete(ch);   // release lock even if the card was filtered away
    updateLiveCount();
  });
}
function updateLiveCount(){
  const lc=$("#livecount");
  if(lc) lc.textContent = writerBusy.size ? (writerBusy.size+" 位正在书写") : (AGENTS.length+" 位书家在线");
}

function startLive(){
  if(!LIVE_ON){ const lb=document.querySelector(".livebar"); if(lb) lb.style.display="none"; return; }
  updateLiveCount();
  // launch several at once so multiple cursors are writing from the start
  setTimeout(()=>{ liveWrite(); liveWrite(); }, 500);
  setTimeout(()=>{ liveWrite(); }, 1100);
  setTimeout(()=>{ liveWrite(); }, 1700);
  // keep ~MAX_LIVE agents writing in parallel at all times
  setInterval(()=>{
    if(document.hidden) return;
    const free=MAX_LIVE-writerBusy.size;
    for(let k=0;k<free;k++) liveWrite();
  },800);
}

// ---- stroke-by-stroke writing animation (hanzi-writer-data) ----
let clipSeq=0;   // SVG ids are document-global → must be unique across all cards
function showStrokes(ch){
  const prev=$("#pchar");
  prev.innerHTML='<svg viewBox="0 0 1024 1024" preserveAspectRatio="xMidYMid meet"></svg>';
  const svg=prev.querySelector("svg");
  const d=STROKES[ch];
  if(!d){prev.innerHTML='<div style="font-size:54px">'+ch+'</div>';return;}
  buildAndAnimate(svg,d);
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
  let delay=0;
  inkEls.forEach(p=>{
    if(instant||INSTANT) return;   // fully-visible by default; no dash needed
    const len=p.getTotalLength();
    p.style.strokeDasharray=len;
    p.style.strokeDashoffset=len;
    p.animate([{strokeDashoffset:len},{strokeDashoffset:0}],{duration:430,delay:delay,easing:"ease-in-out",fill:"forwards"});
    delay+=430;
  });
}
// point at fraction f (0..1) along a polyline of [x,y] points — used to drive the pen tip
function polyPointAt(pts,f){
  if(!pts||!pts.length) return null;
  if(pts.length===1) return pts[0];
  const seg=[]; let total=0;
  for(let i=1;i<pts.length;i++){const l=Math.hypot(pts[i][0]-pts[i-1][0],pts[i][1]-pts[i-1][1]);seg.push(l);total+=l;}
  if(total===0) return pts[0];
  let d=Math.max(0,Math.min(1,f))*total;
  for(let i=0;i<seg.length;i++){
    if(d<=seg[i]){const t=seg[i]===0?0:d/seg[i];
      return [pts[i][0]+(pts[i+1][0]-pts[i][0])*t, pts[i][1]+(pts[i+1][1]-pts[i][1])*t];}
    d-=seg[i];
  }
  return pts[pts.length-1];
}
// timer-driven live writing: reveals each stroke AND moves a glowing pen tip along it
function animateLive(svg,d,onDone){
  const {inkEls,gEl}=renderGlyph(svg,d);
  if(!inkEls.length){ onDone&&onDone(); return; }
  const tip=document.createElementNS(SVGNS,"g");
  tip.setAttribute("class","pentip-g");
  tip.innerHTML='<circle class="tip-halo" r="190"></circle><circle class="tip-mid" r="118"></circle><circle class="tip-core" r="62"></circle>';
  gEl.appendChild(tip);
  const lens=inkEls.map(p=>{const L=p.getTotalLength();p.style.strokeDasharray=L;p.style.strokeDashoffset=L;return L;});
  const medians=d.medians||[];
  let si=0, t=0; const PER=440, HOLD=90;   // ms per stroke + pause between strokes
  const timer=setInterval(()=>{
    if(!svg.isConnected){ clearInterval(timer); onDone&&onDone(); return; }
    if(si>=inkEls.length){ tip.remove(); clearInterval(timer); onDone&&onDone(); return; }
    t+=16;
    const prog=Math.min(1,t/PER);
    inkEls[si].style.strokeDashoffset=(lens[si]*(1-prog)).toFixed(2);
    const pt=polyPointAt(medians[si],prog);
    if(pt) tip.setAttribute("transform","translate("+pt[0].toFixed(1)+","+pt[1].toFixed(1)+")");
    if(t>=PER+HOLD){ t=0; si++; }
  },16);
}

function codeFor(c,tab){
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
    case "SVG": return `<svg width="64" height="64" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
  <text x="32" y="46" font-size="52" text-anchor="middle"
        font-family="'Noto Sans SC','PingFang SC',sans-serif">${c.c}</text>
</svg>`;
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
function openChar(c){
  curChar=c;curTab="HTML";
  showStrokes(c.c);
  $("#replay").onclick=()=>showStrokes(c.c);
  $("#pname").textContent=c.c;
  $("#ppinyin").textContent=`${c.p} · ${c.m}`;
  $("#ptags").innerHTML=`<span class="tag">${uhex(c.c)}</span><span class="tag">${c.set}</span><span class="tag">${c.p}</span>`;
  buildTabs();
  library.querySelectorAll(".card.sel").forEach(c=>c.classList.remove("sel"));
  const card=library.querySelector('[data-ch="'+c.c+'"]');
  if(card) card.classList.add("sel");
  $("#backdrop").classList.add("open");
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
  $("#code").textContent=codeFor(curChar,curTab);
}
function copyCode(){
  navigator.clipboard?.writeText($("#code").textContent).then(()=>{
    const b=$("#copybtn");b.textContent="已复制";setTimeout(()=>b.textContent="复制",1200);
  });
}
function openAgent(){
  $("#backdrop2").classList.add("open");
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
function closeAll(){document.querySelectorAll(".backdrop").forEach(b=>b.classList.remove("open"));library.querySelectorAll(".card.sel").forEach(c=>c.classList.remove("sel"));}

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
  const charQ=sp.get("char");
  if(charQ){const all=DATA.sets.flatMap(s=>s.chars.map(c=>({...c,set:s.name})));
    const hit=all.find(c=>c.c===charQ); if(hit)openChar(hit);}
  if(sp.has("agent")) openAgent();
  startLive();
})();
"""

SEARCH_ICO = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></svg>'
AGENT_CODE = """{
  "mcpServers": {
    "hanzi": {
      "command": "python3",
      "args": ["/Users/chenjiahua/WorkBuddy/2026-11-04-20-38-20/server.py"]
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

      <div class="map-card">
        <span class="pill p1">中原</span>
        <span class="pill p2">江南</span>
        <span class="pill p3">巴蜀</span>
        <span class="pill p4">关中</span>
      </div>

      <div class="stats">
        <span><b class="warm">⚙ 2,018</b> 笔画修正</span>
        <span><b class="warm">+ 3,546</b> 新增汉字</span>
      </div>

      <div class="feed">
        <div class="feedrow"><b>王羲之</b> 正在临摹 <span class="cn">永</span></div>
        <div class="feedrow"><b>颜真卿</b> 正在临摹 <span class="cn">颜</span></div>
        <div class="feedrow"><b>欧阳询</b> 正在临摹 <span class="cn">九</span></div>
        <div class="feedrow"><b>苏轼</b> 正在临摹 <span class="cn">水</span></div>
        <div class="feedrow"><b>米芾</b> 正在临摹 <span class="cn">山</span></div>
        <div class="feedrow"><b>赵孟頫</b> 正在临摹 <span class="cn">天</span></div>
        <div class="feedmore">+ 还有 5 条动态</div>
      </div>

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
    <button class="pclose" id="close1">×</button>
    <div class="phead">
      <div class="preview"><div class="pchar" id="pchar"></div><button class="replaybtn" id="replay" title="重播笔画">↻</button></div>
      <div class="pinfo">
        <h2 id="pname"></h2>
        <div class="py" id="ppinyin"></div>
        <div class="tags" id="ptags"></div>
      </div>
    </div>
    <div class="tabs" id="tabs"></div>
    <div class="code"><button class="copy" id="copybtn">复制</button><span id="code"></span></div>
  </div>
</div>

<!-- agent modal -->
<div class="backdrop agent" id="backdrop2">
  <div class="panel">
    <button class="pclose" id="close2">×</button>
    <h3>在 Agent 中使用 汉字MCP</h3>
    <p>把下面这段配置加进任意支持 MCP 的客户端，即可用 <code>get_hanzi</code> 工具取字。</p>
    <div class="code"><button class="copy" onclick="navigator.clipboard&&navigator.clipboard.writeText(this.parentElement.querySelector('span').textContent)">复制</button><span>{AGENT_CODE}</span></div>
  </div>
</div>
"""

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

      <div class="map-card">
        <span class="pill p1">中原</span>
        <span class="pill p2">江南</span>
        <span class="pill p3">巴蜀</span>
        <span class="pill p4">关中</span>
      </div>

      <div class="stats">
        <span><b class="warm">⚙ 2,018</b> 笔画修正</span>
        <span><b class="warm">+ 3,546</b> 新增汉字</span>
      </div>

      <div class="feed">
        <div class="feedrow"><b>王羲之</b> 正在临摹 <span class="cn">永</span></div>
        <div class="feedrow"><b>颜真卿</b> 正在临摹 <span class="cn">颜</span></div>
        <div class="feedrow"><b>欧阳询</b> 正在临摹 <span class="cn">九</span></div>
        <div class="feedrow"><b>苏轼</b> 正在临摹 <span class="cn">水</span></div>
        <div class="feedrow"><b>米芾</b> 正在临摹 <span class="cn">山</span></div>
        <div class="feedrow"><b>赵孟頫</b> 正在临摹 <span class="cn">天</span></div>
        <div class="feedmore">+ 还有 5 条动态</div>
      </div>

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
    <button class="pclose" id="close1">×</button>
    <div class="phead">
      <div class="preview"><div class="pchar" id="pchar"></div><button class="replaybtn" id="replay" title="重播笔画">↻</button></div>
      <div class="pinfo">
        <h2 id="pname"></h2>
        <div class="py" id="ppinyin"></div>
        <div class="tags" id="ptags"></div>
      </div>
    </div>
    <div class="tabs" id="tabs"></div>
    <div class="code"><button class="copy" id="copybtn">复制</button><span id="code"></span></div>
  </div>
</div>

<!-- agent modal -->
<div class="backdrop agent" id="backdrop2">
  <div class="panel" style="max-width:620px">
    <button class="pclose" id="close2">×</button>
    <h3>在 Agent 中使用 汉字MCP</h3>
    <p>这是一个真实可运行的 MCP server（<code>server.py</code>，纯标准库），暴露 <code>get_hanzi</code> · <code>search_hanzi</code> · <code>list_sets</code> · <code>hanzi_paths</code> 四个工具。</p>

    <div style="font-size:12px;font-weight:600;color:var(--muted);margin:16px 0 8px;letter-spacing:.02em">方式一 · 本地 stdio（Claude Desktop / Cursor / WorkBuddy）</div>
    <div class="code"><button class="copy" onclick="navigator.clipboard&&navigator.clipboard.writeText(this.parentElement.querySelector('span').textContent)">复制</button><span>{AGENT_CODE}</span></div>

    <div style="font-size:12px;font-weight:600;color:var(--muted);margin:16px 0 8px;letter-spacing:.02em">方式二 · HTTP（浏览器可直接访问 / 远程客户端）</div>
    <div class="code"><button class="copy" onclick="navigator.clipboard&&navigator.clipboard.writeText(this.parentElement.querySelector('span').textContent)">复制</button><span>{AGENT_CODE}</span></div>

    <div style="display:flex;align-items:center;gap:10px;margin-top:14px">
      <button class="btn" onclick="testMCP(this)" style="border:1px solid var(--line);background:var(--ink);color:var(--canvas);border-radius:9px;padding:7px 14px;font:inherit;font-size:13px;cursor:pointer">测试连接</button>
      <span id="mcptest" style="font-size:12.5px;color:var(--muted)">点一下检测 HTTP 服务是否在跑</span>
    </div>
  </div>
</div>
"""

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

      <div class="map-card">
        <span class="pill p1">中原</span>
        <span class="pill p2">江南</span>
        <span class="pill p3">巴蜀</span>
        <span class="pill p4">关中</span>
      </div>

      <div class="stats">
        <span><b class="warm">⚙ 2,018</b> 笔画修正</span>
        <span><b class="warm">+ 3,546</b> 新增汉字</span>
      </div>

      <div class="feed">
        <div class="feedrow"><b>王羲之</b> 正在临摹 <span class="cn">永</span></div>
        <div class="feedrow"><b>颜真卿</b> 正在临摹 <span class="cn">颜</span></div>
        <div class="feedrow"><b>欧阳询</b> 正在临摹 <span class="cn">九</span></div>
        <div class="feedrow"><b>苏轼</b> 正在临摹 <span class="cn">水</span></div>
        <div class="feedrow"><b>米芾</b> 正在临摹 <span class="cn">山</span></div>
        <div class="feedrow"><b>赵孟頫</b> 正在临摹 <span class="cn">天</span></div>
        <div class="feedmore">+ 还有 5 条动态</div>
      </div>

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
    <button class="pclose" id="close1">×</button>
    <div class="phead">
      <div class="preview"><div class="pchar" id="pchar"></div><button class="replaybtn" id="replay" title="重播笔画">↻</button></div>
      <div class="pinfo">
        <h2 id="pname"></h2>
        <div class="py" id="ppinyin"></div>
        <div class="tags" id="ptags"></div>
      </div>
    </div>
    <div class="tabs" id="tabs"></div>
    <div class="code"><button class="copy" id="copybtn">复制</button><span id="code"></span></div>
  </div>
</div>

<!-- agent modal -->
<div class="backdrop agent" id="backdrop2">
  <div class="panel" style="max-width:620px">
    <button class="pclose" id="close2">×</button>
    <h3>在 Agent 中使用 汉字MCP</h3>
    <p>这是一个真实可运行的 MCP server（<code>server.py</code>，纯标准库），暴露 <code>get_hanzi</code> · <code>search_hanzi</code> · <code>list_sets</code> · <code>hanzi_paths</code> 四个工具。</p>

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

      <div class="map-card">
        <span class="pill p1">中原</span>
        <span class="pill p2">江南</span>
        <span class="pill p3">巴蜀</span>
        <span class="pill p4">关中</span>
      </div>

      <div class="stats">
        <span><b class="warm">⚙ 2,018</b> 笔画修正</span>
        <span><b class="warm">+ 3,546</b> 新增汉字</span>
      </div>

      <div class="livebar"><span class="dot"></span><span>Live</span><span class="lc" id="livecount">7 位书家在线</span></div>
      <div class="feed" id="feed">
        <div class="feedrow"><b>王羲之</b> <span class="act">写好了</span> <span class="cn">天</span></div>
        <div class="feedrow"><b>颜真卿</b> <span class="act">写好了</span> <span class="cn">山</span></div>
        <div class="feedrow"><b>欧阳询</b> <span class="act">写好了</span> <span class="cn">九</span></div>
        <div class="feedrow"><b>苏轼</b> <span class="act">写好了</span> <span class="cn">水</span></div>
        <div class="feedrow"><b>米芾</b> <span class="act">写好了</span> <span class="cn">风</span></div>
        <div class="feedmore" id="feedmore">+ 实时更新中</div>
      </div>

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
    <button class="pclose" id="close1">×</button>
    <div class="phead">
      <div class="preview"><div class="pchar" id="pchar"></div><button class="replaybtn" id="replay" title="重播笔画">↻</button></div>
      <div class="pinfo">
        <h2 id="pname"></h2>
        <div class="py" id="ppinyin"></div>
        <div class="tags" id="ptags"></div>
      </div>
    </div>
    <div class="tabs" id="tabs"></div>
    <div class="code"><button class="copy" id="copybtn">复制</button><span id="code"></span></div>
  </div>
</div>

<!-- agent modal -->
<div class="backdrop agent" id="backdrop2">
  <div class="panel" style="max-width:620px">
    <button class="pclose" id="close2">×</button>
    <h3>在 Agent 中使用 汉字MCP</h3>
    <p>这是一个真实可运行的 MCP server（<code>server.py</code>，纯标准库），暴露 <code>get_hanzi</code> · <code>search_hanzi</code> · <code>list_sets</code> · <code>hanzi_paths</code> 四个工具。</p>

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

      <div class="map-card">
        <span class="pill p1">中原</span>
        <span class="pill p2">江南</span>
        <span class="pill p3">巴蜀</span>
        <span class="pill p4">关中</span>
      </div>

      <div class="stats">
        <span><b class="warm">⚙ 2,018</b> 笔画修正</span>
        <span><b class="warm">+ 3,546</b> 新增汉字</span>
      </div>

      <div class="livebar"><span class="dot"></span><span>Live</span><span class="lc" id="livecount">7 位书家在线</span></div>
      <div class="feed" id="feed">
        <div class="feedrow"><b>王羲之</b> <span class="act">写好了</span> <span class="cn">天</span></div>
        <div class="feedrow"><b>颜真卿</b> <span class="act">写好了</span> <span class="cn">山</span></div>
        <div class="feedrow"><b>欧阳询</b> <span class="act">写好了</span> <span class="cn">九</span></div>
        <div class="feedrow"><b>苏轼</b> <span class="act">写好了</span> <span class="cn">水</span></div>
        <div class="feedrow"><b>米芾</b> <span class="act">写好了</span> <span class="cn">风</span></div>
        <div class="feedmore" id="feedmore">+ 实时更新中</div>
      </div>

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
    <button class="pclose" id="close1">×</button>
    <div class="phead">
      <div class="preview"><div class="pchar" id="pchar"></div><button class="replaybtn" id="replay" title="重播笔画">↻</button></div>
      <div class="pinfo">
        <h2 id="pname"></h2>
        <div class="py" id="ppinyin"></div>
        <div class="tags" id="ptags"></div>
      </div>
    </div>
    <div class="tabs" id="tabs"></div>
    <div class="code"><button class="copy" id="copybtn">复制</button><span id="code"></span></div>
  </div>
</div>

<!-- agent modal -->
<div class="backdrop agent" id="backdrop2">
  <div class="panel" style="max-width:620px">
    <button class="pclose" id="close2">×</button>
    <h3>在 Agent 中使用 汉字MCP</h3>
    <p>这是一个真实可运行的 MCP server（<code>server.py</code>，纯标准库），暴露 <code>get_hanzi</code> · <code>search_hanzi</code> · <code>list_sets</code> · <code>hanzi_paths</code> 四个工具。</p>

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
<style>{CSS}</style>
</head>
<body>
__BODY__
<script>{JS}</script>
</body>
</html>""".replace("{CSS}", CSS).replace("__BODY__", BODY_TPL).replace("{TOTAL}", str(total)).replace("{AGENT_CODE}", AGENT_CODE).replace("{JS}", JS2).replace("__STROKES__", STROKES_JSON)

with open("hanzi-mcp.html", "w", encoding="utf-8") as f:
    f.write(HTML)
print(f"wrote hanzi-mcp.html  ({len(HTML)} bytes, {total} hanzi across {len(SETS)} sets)")
