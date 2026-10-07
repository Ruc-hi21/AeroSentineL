"""Animated canvas widgets rendered in sandboxed iframes (st.components.v1.html).

Data goes in as JSON; nothing comes back. Each widget is self-contained HTML/CSS/JS.
"""

import json

import streamlit.components.v1 as components

from src.config import RISK_BANDS, RISK_LIMITS, RUL_CAP

_FONTS = ('<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700;900&family=Rajdhani:wght@500;600;700'
          '&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">')
_BASE_CSS = """
*{box-sizing:border-box} html,body{margin:0;background:transparent;overflow:hidden;color:#dbe8ff;font-family:Rajdhani,sans-serif}
.panel{position:relative;height:100vh;border-radius:18px;overflow:hidden;border:1px solid rgba(0,229,255,.16);
  background:radial-gradient(120% 100% at 50% 30%,rgba(16,40,86,.75),rgba(4,10,24,.9))}
"""


def fleet_radar(units, height=470):
    """Radar sweep: one blip per engine. Distance from centre = predicted RUL, so the inner rings are the risk bands."""
    blips = [{
        "u": int(r["unit"]),
        "rul": float(r["predicted_rul"]) if "predicted_rul" in units else float(RUL_CAP),
        "b": RISK_BANDS.index(r["risk_band"]) if "risk_band" in units else 0,
        "p": float(r["risk_probability"]) if "risk_probability" in units else 1.0,
        "h": float(r["health_score"]),
    } for _, r in units.iterrows()]
    data = json.dumps({"blips": blips, "cap": RUL_CAP, "limits": [RISK_LIMITS[b] for b in RISK_BANDS[1:]]})
    components.html(f"""<!doctype html><html><head>{_FONTS}<style>{_BASE_CSS}
.legend{{position:absolute;right:16px;top:14px;display:flex;flex-direction:column;gap:6px;font-weight:700;letter-spacing:.08em;font-size:13px}}
.legend div{{display:flex;align-items:center;gap:8px}} .legend i{{width:9px;height:9px;border-radius:50%}}
.title{{position:absolute;left:18px;top:14px;font-family:Orbitron;font-size:12px;letter-spacing:.24em;color:#00e5ff}}
.title small{{display:block;font-family:'JetBrains Mono';font-size:10px;letter-spacing:.1em;color:#7f95bd;margin-top:4px}}
.tip{{position:absolute;pointer-events:none;display:none;padding:8px 10px;border-radius:8px;background:rgba(4,10,24,.95);
  border:1px solid rgba(0,229,255,.5);font-family:'JetBrains Mono';font-size:11px;line-height:1.5;box-shadow:0 0 18px rgba(0,229,255,.25)}}
</style></head><body><div class="panel"><canvas id="c"></canvas>
<div class="title">FLEET THREAT RADAR<small>CENTRE = FAILURE · RINGS = RISK-BAND LIMITS</small></div>
<div class="legend" id="lg"></div><div class="tip" id="tip"></div></div>
<script>
const D = {data};
const COL = ['#19f5a0','#ffd23f','#ff8a1f','#ff2e4d'], NAME = ['NORMAL','AT RISK','HIGH RISK','FAILURE LIKELY'];
const cv = document.getElementById('c'), cx = cv.getContext('2d'), tip = document.getElementById('tip');
let W=0,H=0,R=0,X0=0,Y0=0; const dpr = Math.min(devicePixelRatio||1,2);
const counts=[0,0,0,0]; D.blips.forEach(b=>counts[b.b]++);
document.getElementById('lg').innerHTML = NAME.map((n,i)=>`<div style="color:${{COL[i]}}"><i style="background:${{COL[i]}};box-shadow:0 0 8px ${{COL[i]}}"></i>${{n}} · ${{counts[i]}}</div>`).join('');
const GA = Math.PI*(3-Math.sqrt(5));
D.blips.forEach((b,i)=>{{ b.a = (i*GA) % (Math.PI*2); b.glow = 0; b.r = Math.min(b.rul, D.cap)/D.cap; }});
[...D.blips].filter(b=>b.b===3).sort((p,q)=>p.rul-q.rul).slice(0,6).forEach((b,i)=>{{ b.tag=i; }});
function size(){{ W=innerWidth; H=innerHeight; cv.width=W*dpr; cv.height=H*dpr; cv.style.width=W+'px'; cv.style.height=H+'px';
  cx.setTransform(dpr,0,0,dpr,0,0); R=Math.min(W*0.42,H*0.43); X0=W*0.46; Y0=H*0.54; }}
addEventListener('resize', size); size();
const t0 = performance.now(); let sweep = -Math.PI/2, last = t0, mouse=null;
function pos(b,k){{ const r = b.r*R*k; return [X0+Math.cos(b.a)*r, Y0+Math.sin(b.a)*r]; }}
function frame(now){{
  const dt=(now-last)/1000; last=now; const e=(now-t0)/1000; const grow = 1-Math.pow(1-Math.min(1,e/1.6),3);
  sweep += dt*1.25; cx.clearRect(0,0,W,H);
  // band zones
  const lim=[D.cap,...D.limits];
  for(let i=0;i<4;i++){{ const r=lim[i]/D.cap*R; const g=cx.createRadialGradient(X0,Y0,0,X0,Y0,r);
    g.addColorStop(0,COL[i]+'00'); g.addColorStop(1,COL[i]+(i===3?'30':'14')); cx.fillStyle=g; cx.beginPath(); cx.arc(X0,Y0,r,0,7); cx.fill(); }}
  // rings + labels
  cx.font='600 10px JetBrains Mono'; cx.textAlign='left';
  lim.forEach((l,i)=>{{ const r=l/D.cap*R; cx.strokeStyle=i?COL[i]+'99':'rgba(0,229,255,.5)'; cx.lineWidth=i?1.2:1.6; cx.setLineDash(i?[4,5]:[]);
    cx.beginPath(); cx.arc(X0,Y0,r,0,7); cx.stroke(); cx.setLineDash([]); cx.fillStyle=i?COL[i]:'#7f95bd'; cx.fillText(l+(i?'':' CYC'),X0+4,Y0-r-4); }});
  // crosshair + ticks
  cx.strokeStyle='rgba(0,229,255,.12)'; cx.lineWidth=1; cx.beginPath(); cx.moveTo(X0-R,Y0); cx.lineTo(X0+R,Y0); cx.moveTo(X0,Y0-R); cx.lineTo(X0,Y0+R); cx.stroke();
  for(let d=0;d<360;d+=5){{ const a=d*Math.PI/180, l=d%30?5:11; cx.strokeStyle=d%30?'rgba(0,229,255,.25)':'rgba(0,229,255,.6)';
    cx.beginPath(); cx.moveTo(X0+Math.cos(a)*(R+3),Y0+Math.sin(a)*(R+3)); cx.lineTo(X0+Math.cos(a)*(R+3+l),Y0+Math.sin(a)*(R+3+l)); cx.stroke(); }}
  // sweep wedge
  if (cx.createConicGradient){{ const g=cx.createConicGradient(sweep-1.2,X0,Y0); g.addColorStop(0,'rgba(0,229,255,0)'); g.addColorStop(0.19,'rgba(0,229,255,0.28)'); g.addColorStop(0.191,'rgba(0,229,255,0)');
    cx.fillStyle=g; cx.beginPath(); cx.moveTo(X0,Y0); cx.arc(X0,Y0,R,sweep-1.2,sweep); cx.closePath(); cx.fill(); }}
  cx.strokeStyle='rgba(160,245,255,.95)'; cx.lineWidth=2; cx.shadowColor='#00e5ff'; cx.shadowBlur=14;
  cx.beginPath(); cx.moveTo(X0,Y0); cx.lineTo(X0+Math.cos(sweep)*R,Y0+Math.sin(sweep)*R); cx.stroke(); cx.shadowBlur=0;
  // blips: flare when the sweep passes, then fade like phosphor
  let hover=null;
  D.blips.forEach(b=>{{ let d=((sweep-b.a)%(Math.PI*2)+Math.PI*2)%(Math.PI*2); if(d<dt*1.3+0.02) b.glow=1; b.glow=Math.max(0.18,b.glow-dt*0.45);
    const [x,y]=pos(b,grow); const c=COL[b.b], crit=b.b>=2, s=2.6+b.p*2.4+(crit?1.5:0);
    cx.globalAlpha=Math.min(1,b.glow+(crit?0.35:0)); cx.fillStyle=c; cx.shadowColor=c; cx.shadowBlur=12*b.glow+(crit?8:0);
    cx.beginPath(); cx.arc(x,y,s,0,7); cx.fill(); cx.shadowBlur=0;
    if(crit){{ const pr=(e*1.4+b.u*0.13)%1; cx.globalAlpha=(1-pr)*0.8; cx.strokeStyle=c; cx.lineWidth=1.2; cx.beginPath(); cx.arc(x,y,s+pr*16,0,7); cx.stroke(); }}
    if(b.tag!==undefined){{ // the most urgent engines get a callout pushed outward along their bearing
      const lr=(D.limits[1]/D.cap)*R*grow+22+(b.tag%2)*16, lx=X0+Math.cos(b.a)*lr, ly=Y0+Math.sin(b.a)*lr;
      cx.globalAlpha=0.9; cx.strokeStyle=c; cx.lineWidth=1; cx.beginPath(); cx.moveTo(x,y); cx.lineTo(lx,ly); cx.stroke();
      cx.fillStyle='#fff'; cx.font='700 10px JetBrains Mono'; cx.textAlign=Math.cos(b.a)<0?'right':'left';
      cx.fillText('U'+String(b.u).padStart(3,'0')+' · '+Math.round(b.rul)+'c',lx+(Math.cos(b.a)<0?-4:4),ly+3); cx.textAlign='left'; }}
    if(mouse && Math.hypot(mouse[0]-x,mouse[1]-y)<9) hover=[b,x,y];
    cx.globalAlpha=1; }});
  if(hover){{ const [b,x,y]=hover; cx.strokeStyle='#fff'; cx.lineWidth=1.4; cx.beginPath(); cx.arc(x,y,11,0,7); cx.stroke();
    tip.style.display='block'; tip.style.left=Math.min(x+14,W-190)+'px'; tip.style.top=(y+12)+'px';
    tip.innerHTML=`<b style="color:${{COL[b.b]}}">UNIT ${{String(b.u).padStart(3,'0')}} · ${{NAME[b.b]}}</b><br>RUL ${{b.rul.toFixed(0)}} cycles<br>confidence ${{(b.p*100).toFixed(0)}}%<br>health ${{b.h.toFixed(2)}}`; }}
  else tip.style.display='none';
  requestAnimationFrame(frame);
}}
cv.addEventListener('mousemove',ev=>{{ mouse=[ev.offsetX,ev.offsetY]; }}); cv.addEventListener('mouseleave',()=>{{ mouse=null; }});
requestAnimationFrame(frame);
</script></body></html>""", height=height)


def analysis_sequence(result, source_name, height=330):
    """Replays the pipeline stages with this run's real numbers, ending on the fleet verdict."""
    units = result.units
    bands = units["risk_band"].value_counts().to_dict() if "risk_band" in units else {}
    stages = [
        ("VALIDATE", f"{result.validation['rows']:,} rows", f"{result.validation['units']} units · {len(result.validation['warnings'])} warnings"),
        ("CLEAN", f"{result.cleaning['rows_out']:,} kept", f"{result.cleaning['dropped_duplicates']} dupes · {result.cleaning['filled_values']} filled"),
        ("HEALTH", f"{int((units['health_condition'] == 'abnormal').sum())} abnormal", "baseline drift scored"),
        ("FEATURES", "multi-scale", "trends · drift · rolling stats"),
        ("RUL MODEL", "XGBoost", result.stages.get("rul", "-")),
        ("RISK MODEL", "XGBoost", result.stages.get("risk", "-")),
        ("EXPLAIN", "SHAP", result.stages.get("explain", "-")),
    ]
    log = [
        f"job {result.job_id} · source {source_name}",
        f"validated {result.validation['rows']:,} rows across {result.validation['units']} engines",
        f"cleaned: {result.cleaning['dropped_invalid_rows']} invalid, {result.cleaning['dropped_duplicates']} duplicate rows removed",
        f"risk bands: " + ", ".join(f"{k.replace('_', ' ').lower()} {v}" for k, v in bands.items()),
        f"{int(units['needs_review'].sum())} units flagged for human review",
        f"completed in {result.duration_ms:.0f} ms · model {result.model_version}",
    ]
    crit = int(bands.get("FAILURE_LIKELY", 0)) + int(bands.get("HIGH_RISK", 0))
    data = json.dumps({"stages": stages, "log": log, "units": len(units), "crit": crit, "status": result.status})
    components.html(f"""<!doctype html><html><head>{_FONTS}<style>{_BASE_CSS}
.wrap{{padding:22px 26px}} .row{{display:flex;align-items:flex-start;justify-content:space-between;position:relative;margin-top:8px}}
.line{{position:absolute;left:40px;right:40px;top:27px;height:2px;background:rgba(0,229,255,.15)}}
.line b{{display:block;height:100%;width:0;background:linear-gradient(90deg,#00e5ff,#9b6bff);box-shadow:0 0 12px #00e5ff;transition:width .45s ease}}
.st{{position:relative;z-index:1;width:13%;text-align:center;opacity:.35;transition:all .4s}}
.st.on{{opacity:1}} .node{{width:54px;height:54px;margin:0 auto;border-radius:50%;display:grid;place-items:center;font-family:Orbitron;font-size:18px;
  border:2px solid rgba(0,229,255,.3);background:rgba(4,12,30,.9);transition:all .4s}}
.st.on .node{{border-color:#00e5ff;box-shadow:0 0 22px rgba(0,229,255,.6),inset 0 0 14px rgba(0,229,255,.3);color:#00e5ff}}
.st.run .node{{animation:spin 0.8s linear infinite;border-top-color:#fff}}
.nm{{font-family:Orbitron;font-size:10px;letter-spacing:.16em;margin-top:9px}} .v{{font-family:'JetBrains Mono';font-size:12px;color:#fff;margin-top:4px}}
.s{{font-size:11.5px;color:#7f95bd}}
.term{{margin-top:18px;font-family:'JetBrains Mono';font-size:12px;line-height:1.7;color:#9fd8ff;min-height:110px;padding:10px 14px;border-radius:12px;
  background:rgba(0,0,0,.35);border:1px solid rgba(0,229,255,.12)}} .term span{{color:#19f5a0}}
.top{{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px 16px}}
.done{{font-family:Orbitron;font-weight:900;letter-spacing:.2em;font-size:14px;color:#19f5a0;opacity:0;transform:scale(.8);
  transition:all .5s cubic-bezier(.2,.9,.3,1.4);text-shadow:0 0 18px #19f5a0}} .done.show{{opacity:1;transform:none}}
.hd{{font-family:Orbitron;font-size:12px;letter-spacing:.24em;color:#00e5ff}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}
</style></head><body><div class="panel"><div class="wrap"><div class="top"><div class="hd">ANALYSIS PIPELINE</div><div class="done" id="done"></div></div>
<div class="row" id="row"><div class="line"><b id="ln"></b></div></div><div class="term" id="term"></div></div></div>
<script>
const D = {data}; const ICON = ['✓','⌁','♥','∑','◷','⚠','◆'];
const row = document.getElementById('row'), term = document.getElementById('term'), ln = document.getElementById('ln');
D.stages.forEach((s,i)=>{{ const el=document.createElement('div'); el.className='st'; el.innerHTML=`<div class="node">${{ICON[i]}}</div><div class="nm">${{s[0]}}</div><div class="v">${{s[1]}}</div><div class="s">${{s[2]}}</div>`; row.appendChild(el); }});
const sts=[...row.querySelectorAll('.st')]; const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const esc=s=>String(s).replace(/[&<>]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;'}})[c]);
(async()=>{{
  for(let i=0;i<sts.length;i++){{ sts[i].classList.add('on','run'); ln.style.width=(i/(sts.length-1)*100)+'%'; await sleep(330); sts[i].classList.remove('run'); }}
  for(const l of D.log){{ const div=document.createElement('div'); term.appendChild(div);
    for(let c=1;c<l.length;c+=2){{ div.innerHTML='<span>›</span> '+esc(l.slice(0,c)); await sleep(6); }}
    div.innerHTML='<span>›</span> '+esc(l); }}
  const d=document.getElementById('done'); d.textContent=(D.status==='COMPLETED'?'✓ ANALYSIS COMPLETE':'⚠ PARTIAL RESULT')+' · '+D.units+' UNITS'+(D.crit?' · '+D.crit+' SEVERE':'');
  if(D.crit){{ d.style.color='#ff8a1f'; d.style.textShadow='0 0 18px #ff8a1f'; }} d.classList.add('show');
}})();
</script></body></html>""", height=height)
