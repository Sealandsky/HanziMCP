#!/usr/bin/env python3
# Build hanzi-ai-studio.html: the "pre-pixel" version that uses the open-source
# hanzi-writer-data dataset (Make Me A Hanzi / Arphic Public License).
# Data is inlined so the file is self-contained / offline-capable.
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "hanzi_data.json"), encoding="utf-8") as f:
    DATA = json.load(f)

TEMPLATE = r"""<!doctype html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>汉字 AI 工作室 · 楷书笔画版（hanzi-writer-data）</title>
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20width='64'%20height='64'%20viewBox='0%200%2064%2064'%3E%3Crect%20width='64'%20height='64'%20rx='14'%20fill='%2318181b'/%3E%3Cg%20fill='none'%20stroke='%232d68ff'%20stroke-width='.9'%20stroke-opacity='.34'%3E%3Crect%20x='8.5'%20y='8.5'%20width='47'%20height='47'%20rx='2'/%3E%3Cpath%20d='M32%208.5V55.5M8.5%2032H55.5'%20stroke-dasharray='2.5%203'/%3E%3C/g%3E%3Cg%20transform='translate(32%2032)%20scale(0.048077%20-0.048077)%20translate(-537.000%20-403.000)'%3E%3Cpath%20d='M%20499%20681%20Q%20581%20697%20671%20713%20Q%20726%20725%20734%20732%20Q%20744%20741%20739%20750%20Q%20732%20763%20699%20773%20Q%20666%20780%20562%20747%20Q%20439%20719%20336%20709%20Q%20294%20703%20324%20684%20Q%20369%20659%20430%20668%20L%20499%20681%20Z'%20fill='%23f7f5ef'/%3E%3Cpath%20d='M%20509%20439%20Q%20615%20454%20771%20455%20Q%20843%20455%20848%20465%20Q%20854%20478%20836%20493%20Q%20781%20532%20739%20524%20Q%20652%20505%20506%20478%20L%20447%20470%20Q%20323%20452%20181%20432%20Q%20159%20429%20175%20411%20Q%20208%20381%20250%20391%20Q%20340%20416%20442%20430%20L%20509%20439%20Z'%20fill='%23f7f5ef'/%3E%3Cpath%20d='M%20506%20478%20Q%20512%20583%20534%20637%20Q%20540%20650%20530%20658%20Q%20518%20670%20499%20681%20C%20474%20698%20413%20693%20430%20668%20Q%20455%20637%20455%20606%20Q%20454%20531%20447%20470%20L%20442%20430%20Q%20412%20253%20320%20176%20Q%20232%20113%20145%2075%20Q%20130%2071%20127%2066%20Q%20121%2060%20138%2057%20Q%20214%2051%20362%20143%20Q%20390%20167%20413%20194%20Q%20470%20267%20494%20405%20L%20506%20478%20Z'%20fill='%23f7f5ef'/%3E%3Cpath%20d='M%20494%20405%20Q%20629%20144%20722%2051%20Q%20740%2033%20762%2031%20Q%20847%2030%20920%2027%20Q%20951%2026%20952%2033%20Q%20953%2042%20920%2059%20Q%20752%20134%20710%20180%20Q%20601%20294%20515%20430%20Q%20511%20434%20509%20439%20C%20493%20464%20473%20446%20494%20405%20Z'%20fill='%23f7f5ef'/%3E%3C/g%3E%3C/svg%3E">
<style>
  :root{
    --bg:#f7f8fa; --panel:#ffffff; --ink:#1b1f27; --muted:#6b7280;
    --line:#e5e7eb; --accent:#2563eb; --accent2:#0ea5e9; --ok:#16a34a; --warn:#d97706;
  }
  *{box-sizing:border-box}
  body{margin:0;font:14px/1.5 "Songti SC","STSong","SimSun","NSimSun","宋体","Noto Serif CJK SC","Source Han Serif SC","Source Han Serif CN","Noto Serif SC","AR PL UMing CN","Times New Roman",Georgia,serif;
       background:var(--bg);color:var(--ink)}
  header{padding:18px 24px;border-bottom:1px solid var(--line);background:var(--panel)}
  header h1{margin:0;font-size:18px;letter-spacing:.5px}
  header p{margin:6px 0 0;color:var(--muted);font-size:12.5px}
  .badge{display:inline-block;margin-left:8px;padding:1px 8px;border:1px solid var(--line);
         border-radius:999px;font-size:11px;color:var(--muted);vertical-align:middle}
  .layout{display:grid;grid-template-columns:minmax(320px,1fr) 380px;gap:18px;padding:18px 24px;align-items:start}
  @media(max-width:880px){.layout{grid-template-columns:1fr}}
  .stage{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px}
  .controls{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-bottom:14px}
  .controls label{font-size:12px;color:var(--muted)}
  select,button{font:inherit;padding:6px 12px;border:1px solid var(--line);border-radius:9px;background:#fff;cursor:pointer}
  button.primary{background:var(--accent);color:#fff;border-color:var(--accent)}
  button:active{transform:translateY(1px)}
  input[type=range]{vertical-align:middle}
  .glyphwrap{display:flex;justify-content:center;background:
     linear-gradient(#fff,#f1f3f6);border:1px solid var(--line);border-radius:12px;padding:10px}
  svg#glyph{width:100%;max-width:460px;height:auto;aspect-ratio:1/1}
  .progress{height:6px;background:var(--line);border-radius:999px;margin-top:12px;overflow:hidden}
  .progress > i{display:block;height:100%;width:0;background:linear-gradient(90deg,var(--accent),var(--accent2));transition:width .2s linear}
  .side{display:flex;flex-direction:column;gap:18px}
  .panel{background:var(--panel);border:1px solid var(--line);border-radius:14px;overflow:hidden}
  .panel h2{margin:0;padding:10px 14px;font-size:13px;border-bottom:1px solid var(--line);background:#fbfcfe}
  .sse{height:220px;overflow:auto;padding:8px 12px;font:12px/1.6 "SF Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,"Songti SC","SimSun","Noto Serif CJK SC",monospace}
  .sse .row{white-space:pre-wrap;word-break:break-all;border-bottom:1px dashed #f0f0f0;padding:3px 0}
  .sse .t{color:var(--muted)}
  .sse .e-job.start{color:var(--accent)} .sse .e-stroke.draw{color:var(--warn)}
  .sse .e-validate.ok{color:var(--ok)} .sse .e-job.done{color:var(--ink);font-weight:600}
  .dsl{font:12px/1.5 "SF Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,"Songti SC","SimSun","Noto Serif CJK SC",monospace;padding:8px 12px;max-height:300px;overflow:auto}
  .dsl .st{border-bottom:1px solid #f2f2f2;padding:6px 0}
  .dsl .st b{color:var(--accent)}
  .dsl .meta{color:var(--muted)}
  .dsl .path{color:#475569;word-break:break-all}
  footer{padding:10px 24px 24px;color:var(--muted);font-size:11.5px}
  code{background:#eef2ff;padding:1px 5px;border-radius:5px;color:#3730a3}
</style>
</head>
<body>
<header>
  <h1>汉字 AI 工作室 <span class="badge">楷书笔画版</span></h1>
  <p>数据源：开源 <code>hanzi-writer-data@2.0.1</code>（源自 Make Me A Hanzi，Arphic Public License）。
     每笔用 clipPath 裁切沿中轴(median)的粗描边，以 <code>stroke-dashoffset</code> 逐笔揭示轮廓；
     右侧事件流模拟 MCP <code>/api/live</code> 的「AI 逐笔绘制」推送。</p>
</header>

<div class="layout">
  <section class="stage">
    <div class="controls">
      <label>汉字</label>
      <select id="charSel"></select>
      <button class="primary" id="playBtn">▶ 播放绘制</button>
      <button id="pauseBtn">⏸ 暂停</button>
      <button id="replayBtn">↺ 重播</button>
      <label>速度 <input id="speed" type="range" min="0.3" max="3" step="0.1" value="1"><span id="spd">1.0×</span></label>
    </div>
    <div class="glyphwrap">
      <svg id="glyph" viewBox="0 0 1024 1024" aria-label="hanzi">
        <defs id="defs"></defs>
        <g id="ghost" transform="translate(0,900) scale(1,-1)"></g>
        <g id="ink"   transform="translate(0,900) scale(1,-1)"></g>
      </svg>
    </div>
    <div class="progress"><i id="bar"></i></div>
  </section>

  <aside class="side">
    <div class="panel">
      <h2>模拟事件流 · /api/live</h2>
      <div class="sse" id="sse"></div>
    </div>
    <div class="panel">
      <h2>笔画 DSL</h2>
      <div class="dsl" id="dsl"></div>
    </div>
  </aside>
</div>

<footer>
  说明：本页为「像素字之前的版本」复刻——直接调用开源 <code>hanzi-writer-data</code> 的真实笔画(medians)与轮廓(strokes)。
  动画是纯前端模拟，用以演示「AI 逐笔绘制 + 过程实时可视化」的链路；并未接入真实 LLM。
</footer>

<script>
const HANZI_DATA = __DATA__;

const SVGNS = "http://www.w3.org/2000/svg";
const CHARS = Object.keys(HANZI_DATA);
const $ = (id) => document.getElementById(id);
const defs = $("defs"), ghost = $("ghost"), ink = $("ink");
const sse = $("sse"), dsl = $("dsl"), bar = $("bar");

let current = CHARS[0];
let playing = false;
let timers = [];
let speed = 1;

function clearTimers(){ timers.forEach(clearTimeout); timers = []; }

function emit(type, payload){
  const row = document.createElement("div");
  row.className = "row e-" + type;
  const ts = new Date().toLocaleTimeString("zh-CN", {hour12:false});
  row.innerHTML = '<span class="t">'+ts+'</span>  '+type+'  '+JSON.stringify(payload);
  sse.prepend(row);
  while(sse.childElementCount > 60) sse.lastElementChild.remove();
}

function medianLength(med){
  let L = 0;
  for(let i=1;i<med.length;i++){
    const dx=med[i][0]-med[i-1][0], dy=med[i][1]-med[i-1][1];
    L += Math.hypot(dx,dy);
  }
  return L;
}

function buildChar(ch){
  clearTimers();
  playing = false;
  const d = HANZI_DATA[ch];
  defs.innerHTML=""; ghost.innerHTML=""; ink.innerHTML=""; bar.style.width="0%";
  const n = d.strokes.length;

  d.strokes.forEach((s,i)=>{
    // clipPath = the stroke outline; the reveal brush is clipped to it
    const cp = document.createElementNS(SVGNS,"clipPath");
    cp.setAttribute("id","clip-"+i);
    cp.setAttribute("clipPathUnits","userSpaceOnUse");
    const cpPath = document.createElementNS(SVGNS,"path");
    cpPath.setAttribute("d", s);
    cp.appendChild(cpPath); defs.appendChild(cp);

    // faint target outline (ghost)
    const g = document.createElementNS(SVGNS,"path");
    g.setAttribute("d", s);
    g.setAttribute("fill", "#1b1f27");
    g.setAttribute("opacity", "0.07");
    ghost.appendChild(g);

    // ink reveal: thick line along the median, clipped to the outline
    const med = d.medians[i];
    const dPath = "M " + med.map(p=>p[0]+" "+p[1]).join(" L ");
    const p = document.createElementNS(SVGNS,"path");
    p.setAttribute("d", dPath);
    p.setAttribute("clip-path", "url(#clip-"+i+")");
    p.setAttribute("stroke", "#111");
    p.setAttribute("stroke-width", "240");
    p.setAttribute("fill", "none");
    p.setAttribute("stroke-linecap", "round");
    p.setAttribute("stroke-linejoin", "round");
    p.setAttribute("pathLength", "1");
    p.style.strokeDasharray = "1";
    p.style.strokeDashoffset = "1";
    p.style.transition = "stroke-dashoffset 0s";
    p.dataset.idx = i;
    ink.appendChild(p);
  });

  buildDSL(ch, d);
  emit("job.start", {char:ch, strokes:n, agent:"hanzi-agent-01",
                     baseline:"hanzi-writer-data@2.0.1 (Make Me A Hanzi / Arphic PL)"});

  if(new URLSearchParams(location.search).has("full")){
    ink.querySelectorAll("path").forEach(p=> p.style.strokeDashoffset="0");
    emit("job.done", {char:ch, strokes:n, mode:"full"});
  }
}

function buildDSL(ch, d){
  dsl.innerHTML = "";
  d.strokes.forEach((s,i)=>{
    const len = medianLength(d.medians[i]);
    const div = document.createElement("div");
    div.className = "st";
    div.innerHTML =
      '<div><b>stroke #'+(i+1)+'</b> <span class="meta">· '+d.medians[i].length+
      ' pts · len '+len.toFixed(0)+' · '+(s.length>60? s.slice(0,57)+"…" : s)+'</span></div>';
    dsl.appendChild(div);
  });
}

function setOffsetInstant(v){
  ink.querySelectorAll("path").forEach(p=>{
    p.style.transition="none"; p.style.strokeDashoffset=String(v);
  });
}

function play(){
  if(playing) return;
  const n = HANZI_DATA[current].strokes.length;
  const full = new URLSearchParams(location.search).has("full");
  const total = full ? 0 : 3600;          // ms for the whole character
  const per = (total / n) / speed;
  setOffsetInstant(1);
  playing = true;
  bar.style.width = "0%";

  HANZI_DATA[current].strokes.forEach((s,i)=>{
    const startDelay = full ? 0 : i*per;
    timers.push(setTimeout(()=>{
      const p = ink.querySelector('path[data-idx="'+i+'"]');
      // force reflow so the transition restarts cleanly
      void p.getBoundingClientRect();
      p.style.transition = "stroke-dashoffset "+per+"ms linear";
      p.style.strokeDashoffset = "0";
      emit("stroke.draw", {stroke:i+1, of:n, points:HANZI_DATA[current].medians[i].length});
      bar.style.width = Math.round(((i+1)/n)*100)+"%";
    }, startDelay));
    timers.push(setTimeout(()=>{
      emit("validate.ok", {stroke:i+1, of:n, note:"bbox within grid"});
    }, startDelay + per));
  });
  timers.push(setTimeout(()=>{
    emit("job.done", {char:current, strokes:n});
    playing = false;
  }, total + 60));
}

function pause(){
  if(!playing) return;
  clearTimers();
  // freeze in-progress brushes at their current offset
  ink.querySelectorAll("path").forEach(p=>{
    const cs = getComputedStyle(p).strokeDashoffset;
    p.style.transition="none"; p.style.strokeDashoffset = cs;
  });
  playing = false;
  emit("job.paused", {char:current});
}

function init(){
  const sel = $("charSel");
  CHARS.forEach(c=>{
    const o = document.createElement("option"); o.value=c; o.textContent=c; sel.appendChild(o);
  });
  sel.value = current;
  sel.addEventListener("change", e=>{ current = e.target.value; buildChar(current); });
  $("playBtn").addEventListener("click", play);
  $("pauseBtn").addEventListener("click", pause);
  $("replayBtn").addEventListener("click", ()=>{ buildChar(current); play(); });
  $("speed").addEventListener("input", e=>{ speed=parseFloat(e.target.value); $("spd").textContent=speed.toFixed(1)+"×"; });

  buildChar(current);
  if(!new URLSearchParams(location.search).has("full")) play();
}
init();
</script>
</body>
</html>
"""

html = TEMPLATE.replace("__DATA__", json.dumps(DATA, ensure_ascii=False, separators=(",", ":")))
out_path = os.path.join(HERE, "hanzi-ai-studio.html")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(html)
print("wrote", out_path, len(html), "bytes; chars:", len(DATA))
