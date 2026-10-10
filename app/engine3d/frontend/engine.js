/* AeroSentinel 3D model viewer: one sectioned component with every sensor channel at its station.
 *
 * Runs in a Streamlit custom component iframe. Streamlit sends `streamlit:render` with args
 * {mode, height, payload}; the payload is one unit's recorded history (app/engine3d/__init__.py)
 * and names its component, whose geometry comes from ./models/<component>.js (turbofan, battery,
 * bearing). Clicking a sensor returns {sensor, unit, t} to Python.
 *
 * Motion rules: the view opens on the latest reading. Running parts (rotors, airflow, current,
 * a turning shaft) show a working component. Camera moves, the exploded view and event entries
 * are GSAP tweens that explain a change of view or state. Replay is user-started and labelled as
 * recorded history. Reduced motion freezes running parts and makes every transition instant.
 */
import * as T from './vendor/three-bundle.js';
import { build as buildTurbofan } from './models/turbofan.js?v=4.0.0';
import { build as buildBattery } from './models/battery.js?v=4.0.2';
import { build as buildBearing } from './models/bearing.js?v=4.0.1';

const BUILDERS = { turbofan: buildTurbofan, battery: buildBattery, bearing: buildBearing };
const gsap = window.gsap;
const $ = (id) => document.getElementById(id);
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const lerp = (a, b, t) => a + (b - a) * t;
const REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const D = (s) => (REDUCED ? 0 : s); // motion duration token, collapsed under reduced motion

/* ------------------------------------------------------------------ Streamlit bridge */
const IN_ST = window.parent !== window;
const post = (type, extra = {}) => IN_ST && window.parent.postMessage({ isStreamlitMessage: true, type, ...extra }, '*');
const Bridge = {
  ready: () => post('streamlit:componentReady', { apiVersion: 1 }),
  height: (h) => post('streamlit:setFrameHeight', { height: h }),
  value: (v) => post('streamlit:setComponentValue', { value: v, dataType: 'json' }),
};

/* ------------------------------------------------------------------ tokens */
const C = {
  bg: 0x0e1013, line: '#262b31', lineStrong: '#353b43', text1: '#e6e8eb', text2: '#a6adb6', text3: '#7f8790',
  accent: '#78a9ff', teal: '#3ddbd9',
};
const BAND_CSS = ['#42be65', '#f1c21b', '#ff832b', '#fa4d56'];
const BAND_TXT = ['Normal', 'At risk', 'High risk', 'Failure likely'];
const STATE = {
  CRITICAL: { label: 'Critical', color: '#fa4d56' }, WARNING: { label: 'Warning', color: '#ff832b' },
  DEGRADING: { label: 'Degrading', color: '#f1c21b' }, HEALTHY: { label: 'Healthy', color: '#42be65' },
  INSUFFICIENT: { label: 'Insufficient data', color: '#8d8d8d' },
};
// Directed drift (sigma from healthy baseline) bands; same as app/insights.py.
const LEVELS = [{ at: 3.2, label: 'Critical', color: '#fa4d56' }, { at: 2.4, label: 'Warning', color: '#ff832b' },
  { at: 1.6, label: 'Elevated', color: '#f1c21b' }];
const level = (z) => LEVELS.findIndex((l) => z >= l.at); // 0 critical .. 2 elevated, -1 nominal
const levelColor = (z) => { const i = level(z); return i < 0 ? C.text3 : LEVELS[i].color; };

/* ------------------------------------------------------------------ state */
const S = {
  mode: 'twin', data: null, dataId: null, N: 0, t: 0, playing: false, speed: 1, lastIdx: -1, maxBand: 0,
  critSeen: new Set(), selected: null, hovered: null, explode: 0, panels: true, rotate: false,
  sensors: [], modLevel: {}, frame: 0, started: false,
};
let MODEL = null; // the component model on screen (see ./models/*.js)

/* ------------------------------------------------------------------ renderer, scene, camera */
const app = $('app');
const canvas = $('gl');
const renderer = new T.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.toneMapping = T.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.0;

const scene = new T.Scene();
scene.background = new T.Color(C.bg);
scene.fog = new T.Fog(C.bg, 22, 46);
const pmrem = new T.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new T.RoomEnvironment(), 0.04).texture;
scene.environmentIntensity = 0.45;
scene.add(new T.HemisphereLight(0xc9d6e6, 0x101317, 0.9));
const keyLight = new T.DirectionalLight(0xffffff, 1.5); keyLight.position.set(5, 8, 7); scene.add(keyLight);
const fill = new T.DirectionalLight(0x9fb8d8, 0.5); fill.position.set(-6, 2, -6); scene.add(fill);

const camera = new T.PerspectiveCamera(32, 1, 0.1, 200);
const controls = new T.OrbitControls(camera, canvas);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.enablePan = false;
controls.minDistance = 4;
controls.maxDistance = 34;
controls.minPolarAngle = 0.3;
controls.maxPolarAngle = Math.PI * 0.6;
controls.autoRotateSpeed = 0.35;
controls.addEventListener('start', () => { gsap.killTweensOf(camera.position); gsap.killTweensOf(controls.target); });

/* ------------------------------------------------------------------ ground plane: orientation only */
const gridMat = new T.ShaderMaterial({
  transparent: true, depthWrite: false,
  vertexShader: 'varying vec3 vW; void main(){ vec4 w = modelMatrix*vec4(position,1.0); vW = w.xyz; gl_Position = projectionMatrix*viewMatrix*w; }',
  fragmentShader: `varying vec3 vW;
    void main(){ vec2 q = vW.xz; vec2 g = abs(fract(q - 0.5) - 0.5) / fwidth(q); float line = 1.0 - min(min(g.x, g.y), 1.0);
      float fade = 1.0 - smoothstep(4.0, 18.0, length(vW.xz)); gl_FragColor = vec4(vec3(0.16, 0.18, 0.2), line * 0.9 * fade); }`,
});
const ground = new T.Mesh(new T.PlaneGeometry(60, 60), gridMat);
ground.rotation.x = -Math.PI / 2; scene.add(ground);

/* ------------------------------------------------------------------ sensor markers */
const markerGeo = new T.SphereGeometry(0.055, 16, 12);
const ringTex = (() => {
  const c = document.createElement('canvas'); c.width = c.height = 64;
  const g = c.getContext('2d'); g.strokeStyle = '#fff'; g.lineWidth = 3; g.beginPath(); g.arc(32, 32, 26, 0, Math.PI * 2); g.stroke();
  return new T.CanvasTexture(c);
})();
let markers = {};
const modEls = {};

/* ------------------------------------------------------------------ component model */
function useModel(key) {
  key = BUILDERS[key] ? key : 'turbofan';
  if (MODEL && MODEL.key === key) return;
  if (MODEL) { scene.remove(MODEL.root); MODEL.dispose(); }
  MODEL = BUILDERS[key]();
  scene.add(MODEL.root);
  ground.position.y = MODEL.groundY;
  markers = {};
  for (const [k, L] of Object.entries(MODEL.layout)) {
    const g = new T.Group(); g.position.fromArray(L.pos);
    const dot = new T.Mesh(markerGeo, new T.MeshBasicMaterial({ color: 0x7f8790, depthTest: false, transparent: true }));
    const sel = new T.Sprite(new T.SpriteMaterial({ map: ringTex, color: 0x78a9ff, depthTest: false, transparent: true }));
    sel.scale.setScalar(0.32); sel.visible = false;
    dot.renderOrder = sel.renderOrder = 20;
    g.add(dot, sel); g.visible = false; MODEL.mods[L.mod].add(g);
    markers[k] = { group: g, dot, sel, screen: new T.Vector2(-999, -999) };
  }
  $('modules').innerHTML = '';
  Object.keys(modEls).forEach((k) => delete modEls[k]);
  MODEL.modules.forEach((m) => { const el = document.createElement('div'); el.className = 'mod'; el.textContent = m.name; $('modules').appendChild(el); modEls[m.key] = el; });
  $('panel-l').textContent = MODEL.panels.L; $('panel-r').textContent = MODEL.panels.R;
  home.target.fromArray(MODEL.view.target);
  home.dir.fromArray(MODEL.view.dir).normalize();
  controls.target.copy(home.target);
  resize();
}

/* ------------------------------------------------------------------ HUD */
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

function buildRows() {
  $('rows-left').innerHTML = ''; $('rows-right').innerHTML = '';
  S.sensors = [];
  for (const k of Object.keys(MODEL.layout)) {
    const sd = S.data.sensors.find((s) => s.key === k);
    if (!sd) continue;
    const el = document.createElement('div');
    el.className = 'row' + (sd.modeled ? '' : ' const');
    el.innerHTML = `<span class="k">${esc(sd.code)}</span><span class="n">${esc(sd.name)}</span><span class="v"></span><span class="z"></span>`;
    el.title = `${sd.code}: ${sd.name}${sd.unit ? ` (${sd.unit})` : ''}${sd.modeled ? '' : '. Not used by the model for this data.'}`;
    el.addEventListener('mouseenter', () => { S.hovered = k; });
    el.addEventListener('mouseleave', () => { if (S.hovered === k) S.hovered = null; });
    el.addEventListener('click', () => select(k));
    (MODEL.layout[k].side === 'L' ? $('rows-left') : $('rows-right')).appendChild(el);
    S.sensors.push({ ...sd, zs: sd.z, el, vEl: el.querySelector('.v'), zEl: el.querySelector('.z'), v: 0, zNow: 0 });
    markers[k].group.visible = true;
  }
}

function pushEvent(cycle, text, color) {
  const box = $('events');
  const el = document.createElement('div');
  el.className = 'ev'; el.style.setProperty('--c', color);
  const tag = S.data && S.data.time_title ? S.data.time_title[0] : 'C';
  el.innerHTML = `<b>${tag}${cycle}</b><span>${esc(text)}</span>`;
  box.prepend(el);
  gsap.fromTo(el, { autoAlpha: 0, x: -8 }, { autoAlpha: 1, x: 0, duration: D(0.24), ease: 'power2.out' });
  while (box.children.length > 4) box.lastChild.remove();
}

/* ------------------------------------------------------------------ timeline */
const tl = $('timeline'), tlx = tl.getContext('2d');
let tlW = 0, tlH = 0;
function sizeTimeline() {
  const r = tl.getBoundingClientRect(), dpr = Math.min(window.devicePixelRatio || 1, 2);
  tlW = r.width; tlH = r.height; tl.width = Math.max(1, r.width * dpr); tl.height = Math.max(1, r.height * dpr);
  tlx.setTransform(dpr, 0, 0, dpr, 0, 0);
}
const TL = { l: 34, r: 74, t: 6, b: 14 };
function drawTimeline() {
  const d = S.data; tlx.clearRect(0, 0, tlW, tlH);
  if (!d || tlW < 10) return;
  const w = tlW - TL.l - TL.r, h = tlH - TL.t - TL.b;
  const xOf = (i) => TL.l + (S.N <= 1 ? w : (i / (S.N - 1)) * w);
  const hMax = Math.max(d.critical * 1.3, ...d.health), hMin = Math.min(0, ...d.health);
  const top = (d.rul_cap || 125) + 5;
  const yR = (v) => TL.t + h - (v / top) * h, yH = (v) => TL.t + h - ((v - hMin) / (hMax - hMin)) * h;
  tlx.font = '11px "IBM Plex Mono", monospace'; tlx.textBaseline = 'middle';
  // band limits on the RUL scale, labelled
  (d.limits || []).forEach((lim, j) => {
    tlx.strokeStyle = BAND_CSS[j + 1]; tlx.globalAlpha = 0.45; tlx.setLineDash([2, 3]);
    tlx.beginPath(); tlx.moveTo(TL.l, yR(lim)); tlx.lineTo(TL.l + w, yR(lim)); tlx.stroke();
    tlx.globalAlpha = 1; tlx.setLineDash([]); tlx.fillStyle = BAND_CSS[j + 1]; tlx.fillText(String(lim), 6, yR(lim));
  });
  const path = (arr, f) => { tlx.beginPath(); arr.forEach((v, i) => (i ? tlx.lineTo(xOf(i), f(v)) : tlx.moveTo(xOf(i), f(v)))); };
  const drawCurves = (alpha) => {
    tlx.globalAlpha = alpha;
    if (d.rul) { path(d.rul, yR); tlx.strokeStyle = C.accent; tlx.lineWidth = 1.75; tlx.stroke(); }
    path(d.health, yH); tlx.strokeStyle = C.teal; tlx.lineWidth = 1.25; tlx.stroke();
    tlx.globalAlpha = 1;
  };
  drawCurves(0.25);
  tlx.save(); tlx.beginPath(); tlx.rect(0, 0, xOf(S.t) + 0.5, tlH); tlx.clip(); drawCurves(1); tlx.restore();
  if (d.band) {
    for (let i = 0; i < S.N; i++) {
      const x0 = xOf(Math.max(0, i - 0.5)), x1 = xOf(Math.min(S.N - 1, i + 0.5));
      tlx.fillStyle = BAND_CSS[d.band[i]]; tlx.globalAlpha = i <= S.t ? 0.9 : 0.25;
      tlx.fillRect(x0, TL.t + h + 6, Math.max(1, x1 - x0), 4);
    }
    tlx.globalAlpha = 1;
  }
  const px = xOf(S.t);
  tlx.strokeStyle = C.text1; tlx.lineWidth = 1; tlx.beginPath(); tlx.moveTo(px, TL.t - 2); tlx.lineTo(px, TL.t + h + 10); tlx.stroke();
  // legend, right gutter
  tlx.fillStyle = C.accent; tlx.fillRect(TL.l + w + 12, TL.t + 6, 10, 2); tlx.fillStyle = C.text2; tlx.fillText('RUL', TL.l + w + 28, TL.t + 7);
  tlx.fillStyle = C.teal; tlx.fillRect(TL.l + w + 12, TL.t + 22, 10, 2); tlx.fillStyle = C.text2; tlx.fillText('Health', TL.l + w + 28, TL.t + 23);
  tlx.fillStyle = C.text3; tlx.fillText('Band', TL.l + w + 28, TL.t + h + 8);
}
function scrubTo(clientX) {
  const r = tl.getBoundingClientRect(), w = r.width - TL.l - TL.r;
  S.t = clamp((clientX - r.left - TL.l) / w, 0, 1) * (S.N - 1);
  S.playing = false; syncPlay();
}
let scrubbing = false;
tl.addEventListener('pointerdown', (e) => { if (!S.data) return; scrubbing = true; tl.setPointerCapture(e.pointerId); scrubTo(e.clientX); });
tl.addEventListener('pointermove', (e) => scrubbing && scrubTo(e.clientX));
tl.addEventListener('pointerup', () => { scrubbing = false; });

/* ------------------------------------------------------------------ data helpers */
function interp(arr, t) {
  if (!arr || !arr.length) return 0;
  const i0 = clamp(Math.floor(t), 0, arr.length - 1), i1 = Math.min(i0 + 1, arr.length - 1);
  return lerp(arr[i0], arr[i1], t - i0);
}
function stateAt(idx) {
  const d = S.data, band = d.band ? d.band[idx] : null;
  if (band === 3) return 'CRITICAL';
  if (band === 2) return 'WARNING';
  if (band === null && !d.rul) return 'INSUFFICIENT';
  if (idx + 1 < (d.min_history || 30)) return 'INSUFFICIENT';
  if (band === 1 || d.health[idx] > d.threshold) return 'DEGRADING';
  return 'HEALTHY';
}

/* ------------------------------------------------------------------ controls */
const playBtn = $('btn-play');
function syncPlay() {
  playBtn.textContent = S.playing ? 'Pause' : (S.t >= S.N - 1 ? 'Replay' : 'Resume');
  $('mode').textContent = S.playing ? `Replaying recorded history, ${S.speed}x` : (Math.round(S.t) >= S.N - 1 ? 'Latest reading' : 'Paused');
}
function play() {
  if (!S.data) return;
  if (S.t >= S.N - 1) { S.t = 0; S.lastIdx = -1; S.maxBand = S.data.band ? S.data.band[0] : 0; S.critSeen.clear(); $('events').innerHTML = ''; }
  S.playing = true; syncPlay();
}
playBtn.onclick = () => { if (S.playing) { S.playing = false; syncPlay(); } else play(); };
$('btn-latest').onclick = () => { if (!S.data) return; S.playing = false; S.t = S.N - 1; syncPlay(); };
document.querySelectorAll('#speed .btn').forEach((b) => {
  b.onclick = () => { S.speed = +b.dataset.speed; document.querySelectorAll('#speed .btn').forEach((x) => x.classList.toggle('on', x === b)); syncPlay(); };
});
$('btn-explode').onclick = (e) => {
  const on = S.explode < 0.5;
  gsap.to(S, { explode: on ? 1 : 0, duration: D(0.8), ease: 'power2.inOut', overwrite: true });
  e.currentTarget.classList.toggle('on', on);
};
$('btn-rotate').onclick = (e) => { S.rotate = !S.rotate; e.currentTarget.classList.toggle('on', S.rotate); };
$('btn-panels').onclick = (e) => {
  S.panels = !S.panels; app.classList.toggle('panels-hidden', !S.panels);
  e.currentTarget.textContent = S.panels ? 'Hide panels' : 'Show panels';
  setTimeout(() => { setHome(); flyHome(0.6); }, 250);
};
window.addEventListener('keydown', (e) => {
  if (e.code === 'Space') { e.preventDefault(); playBtn.click(); }
  else if (e.key === 'e') $('btn-explode').click();
  else if (e.key === 'h') $('btn-panels').click();
  else if (e.key === 'Escape') { S.selected = null; refreshSelection(); flyHome(0.8); }
});

/* ------------------------------------------------------------------ camera */
let W = 1, H = 1;
const home = { pos: new T.Vector3(), target: new T.Vector3(-0.2, 0, 0), dir: new T.Vector3(0.55, 0.34, 1).normalize() };
function homeDistance() {
  const twin = S.mode === 'twin';
  const side = twin && S.panels && W > 720 ? 2 * (W > 980 ? 256 : 196) : 0;
  const usableW = (W - side) / W * 0.92;
  const usableH = twin ? (H - 64 - 132 - 30) / H : 0.86;
  const vt = Math.tan(T.MathUtils.degToRad(camera.fov / 2)), ht = vt * camera.aspect;
  const [hw, hh] = MODEL ? MODEL.view[twin ? 'twin' : 'hero'] : [4.5, 2.8];
  return Math.max(hw / (ht * usableW), hh / (vt * usableH), MODEL ? MODEL.view.min : 7);
}
function setHome() { home.pos.copy(home.target).addScaledVector(home.dir, homeDistance()); }
function flyTo(pos, target, secs, ease = 'power2.inOut') {
  gsap.to(camera.position, { x: pos.x, y: pos.y, z: pos.z, duration: D(secs), ease, overwrite: true });
  gsap.to(controls.target, { x: target.x, y: target.y, z: target.z, duration: D(secs), ease, overwrite: true });
}
function flyHome(secs = 0.8) { setHome(); flyTo(home.pos, home.target, secs); }
function resize() {
  const r = app.getBoundingClientRect(); W = Math.max(1, r.width); H = Math.max(1, r.height);
  renderer.setSize(W, H, false);
  camera.aspect = W / H;
  // Shift the model up so it centres in the space between the top bar and the timeline.
  if (S.mode === 'twin' && W > 720) camera.setViewOffset(W, H, 0, 34, W, H); else camera.clearViewOffset();
  camera.updateProjectionMatrix();
  if (MODEL) MODEL.resize(H, renderer.getPixelRatio());
  const lc = $('lines'), dpr = Math.min(window.devicePixelRatio || 1, 2);
  lc.width = W * dpr; lc.height = H * dpr; lx.setTransform(dpr, 0, 0, dpr, 0, 0);
  sizeTimeline(); setHome();
}
const lx = $('lines').getContext('2d');
new ResizeObserver(() => resize()).observe(app);

/* ------------------------------------------------------------------ selection */
function select(k) {
  S.selected = S.selected === k ? null : k;
  refreshSelection();
  if (S.selected) {
    const wp = markers[k].group.getWorldPosition(new T.Vector3());
    const dir = camera.position.clone().sub(controls.target).normalize();
    flyTo(wp.clone().addScaledVector(dir, 6.5), wp, 0.9);
    Bridge.value({ sensor: k, unit: S.data ? S.data.unit : null, t: Date.now() });
  } else flyHome(0.8);
}
function refreshSelection() {
  S.sensors.forEach((s) => s.el.classList.toggle('sel', s.key === S.selected));
  Object.entries(markers).forEach(([k, m]) => { m.sel.visible = k === S.selected; });
}
const tip = $('tooltip');
canvas.addEventListener('pointermove', (e) => {
  if (S.mode !== 'twin' || !S.data) return;
  const r = app.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top;
  let best = null, bd = 14;
  for (const s of S.sensors) { const m = markers[s.key]; const d = Math.hypot(m.screen.x - mx, m.screen.y - my); if (d < bd) { bd = d; best = s; } }
  S.hovered = best ? best.key : null;
  if (best) {
    tip.style.display = 'block'; tip.style.left = `${Math.min(mx + 14, W - 270)}px`; tip.style.top = `${my + 12}px`;
    const drift = best.modeled ? `${best.zNow >= 0 ? '+' : ''}${best.zNow.toFixed(1)} sigma from baseline` : 'not used by the model';
    tip.innerHTML = `<b>${esc(best.code)}</b> ${esc(best.name)}<div class="m">${best.v.toFixed(best.decimals)} ${esc(best.unit)}, ${drift}</div>`;
    canvas.style.cursor = 'pointer';
  } else { tip.style.display = 'none'; canvas.style.cursor = ''; }
});
canvas.addEventListener('pointerleave', () => { tip.style.display = 'none'; S.hovered = null; });
canvas.addEventListener('click', () => { if (S.hovered && S.mode === 'twin') select(S.hovered); });
canvas.addEventListener('dblclick', () => { S.selected = null; refreshSelection(); flyHome(0.8); });

/* ------------------------------------------------------------------ apply state */
function applyState(tsec) {
  const d = S.data;
  const modLevel = Object.fromEntries(MODEL.modules.map((m) => [m.key, -1]));
  const z = {};
  for (const s of S.sensors) {
    s.v = interp(s.values, S.t);
    s.zNow = s.modeled ? interp(s.zs, S.t) : 0;
    if (s.modeled) {
      z[s.key] = s.zNow;
      const lv = level(s.zNow), mod = MODEL.layout[s.key].mod;
      if (lv >= 0 && (modLevel[mod] < 0 || lv < modLevel[mod])) modLevel[mod] = lv;
    }
  }
  S.modLevel = modLevel;
  MODEL.apply({ modLevel, z, tsec, levels: LEVELS, reduced: REDUCED });

  for (const s of S.sensors) {
    const m = markers[s.key];
    const color = s.modeled ? levelColor(s.zNow) : '#4a525c';
    m.dot.material.color.set(color === C.text3 ? '#9aa3ad' : color);
    m.dot.scale.setScalar(s.key === S.selected || s.key === S.hovered ? 1.6 : 1);
  }
  if (!d || S.mode !== 'twin' || S.frame % 2) return;

  const idx = clamp(Math.round(S.t), 0, S.N - 1);
  const state = stateAt(idx);
  $('cycle').innerHTML = `${esc(d.time_title || 'Cycle')} ${d.cycles[idx]} <em>of ${d.cycles[S.N - 1]}</em>`;
  if (d.conditions) $('flight').textContent = MODEL.conditionText(d.conditions, idx);
  app.style.setProperty('--state', STATE[state].color);
  $('state').textContent = STATE[state].label;
  const band = d.band ? d.band[idx] : null;
  const rul = d.rul ? Math.round(interp(d.rul, S.t)) : null;
  $('band').innerHTML = [rul != null ? `RUL ${rul} ${d.life_unit || 'cycles'}` : null, band != null ? `${BAND_TXT[band]} ${Math.round(d.prob[idx] * 100)}%` : null]
    .filter(Boolean).map((t) => `<span>${esc(t)}</span>`).join('');
  for (const s of S.sensors) {
    s.vEl.textContent = s.v.toFixed(s.decimals);
    if (s.modeled) { s.zEl.textContent = `${s.zNow >= 0 ? '+' : ''}${s.zNow.toFixed(1)}`; s.el.style.setProperty('--c', levelColor(s.zNow)); }
    else s.zEl.textContent = 'n/u';
  }
  for (const m of MODEL.modules) {
    const lv = S.modLevel[m.key];
    modEls[m.key].style.setProperty('--c', lv < 0 ? C.lineStrong : LEVELS[lv].color);
    modEls[m.key].title = `${m.name}: ${lv < 0 ? 'nominal' : LEVELS[lv].label.toLowerCase()} sensor drift`;
  }

  // Events only fire while replaying forward through the record.
  if (idx !== S.lastIdx) {
    if (S.playing && S.lastIdx >= 0 && idx > S.lastIdx) {
      if (band != null && band > S.maxBand) { S.maxBand = band; pushEvent(d.cycles[idx], `Risk band escalated to ${BAND_TXT[band].toLowerCase()}`, BAND_CSS[band]); }
      for (const s of S.sensors) {
        if (s.modeled && s.zNow >= LEVELS[0].at && !S.critSeen.has(s.key)) {
          S.critSeen.add(s.key);
          pushEvent(d.cycles[idx], `${s.code} drift passed ${LEVELS[0].at} sigma (${s.name})`, LEVELS[0].color);
        }
      }
    }
    S.lastIdx = idx;
  }
}

/* ------------------------------------------------------------------ leader lines: only where attention is needed */
function drawOverlay() {
  lx.clearRect(0, 0, W, H);
  if (S.mode !== 'twin' || !S.data) return;
  const v = new T.Vector3(), r0 = app.getBoundingClientRect();
  for (const m of Object.values(markers)) {
    if (!m.group.visible) continue;
    m.group.getWorldPosition(v).project(camera);
    m.screen.set((v.x * 0.5 + 0.5) * W, (-v.y * 0.5 + 0.5) * H);
  }
  if (!S.panels) return;
  // Lines only where attention is needed: the selected/hovered sensor and the strongest critical drifts.
  const critical = new Set(S.sensors.filter((s) => s.modeled && level(s.zNow) === 0)
    .sort((a, b) => b.zNow - a.zNow).slice(0, 5).map((s) => s.key));
  for (const s of S.sensors) {
    const active = s.key === S.selected || s.key === S.hovered;
    const lv = s.modeled ? level(s.zNow) : -1;
    if (!active && !critical.has(s.key)) continue;
    const rr = s.el.getBoundingClientRect(), m = markers[s.key];
    const left = MODEL.layout[s.key].side === 'L';
    const ax = (left ? rr.right : rr.left) - r0.left, ay = rr.top + rr.height / 2 - r0.top, ex = ax + (left ? 14 : -14);
    lx.strokeStyle = active ? C.accent : LEVELS[Math.max(lv, 0)].color;
    lx.globalAlpha = active ? 1 : 0.65; lx.lineWidth = active ? 1.5 : 1;
    lx.beginPath(); lx.moveTo(ax, ay); lx.lineTo(ex, ay); lx.lineTo(m.screen.x, m.screen.y); lx.stroke();
  }
  lx.globalAlpha = 1;
  if (S.explode > 0.05) {
    lx.font = '500 11px "IBM Plex Sans", sans-serif'; lx.textAlign = 'center'; lx.globalAlpha = S.explode;
    for (const m of MODEL.modules) {
      const at = MODEL.labels[m.key];
      if (!at) continue;
      const off = MODEL.mods[m.key].position;
      v.set(at[0] + off.x, at[1] + off.y, at[2] + off.z).project(camera);
      const x = (v.x * 0.5 + 0.5) * W, y = (-v.y * 0.5 + 0.5) * H;
      const lv = S.modLevel[m.key];
      lx.fillStyle = lv === undefined || lv < 0 ? C.text2 : LEVELS[lv].color;
      lx.fillText(m.name, x, y);
    }
    lx.globalAlpha = 1; lx.textAlign = 'left';
  }
}

/* ------------------------------------------------------------------ payload & intro */
function loadPayload(p) {
  const first = !S.data;
  const switched = !MODEL || MODEL.key !== (p.component || 'turbofan');
  useModel(p.component || 'turbofan');
  S.data = p; S.dataId = p.id; S.N = p.cycles.length;
  S.t = S.N - 1; S.playing = false; S.lastIdx = -1; S.critSeen.clear(); S.selected = null;
  Object.values(markers).forEach((m) => { m.group.visible = false; });
  buildRows(); refreshSelection(); $('events').innerHTML = '';
  $('unit-name').textContent = p.label || `Engine ${String(p.unit).padStart(3, '0')}`;
  $('unit-meta').textContent = [p.source, p.model ? `model ${p.model}` : null, p.corrected ? 'readings corrected to the reference condition' : null]
    .filter(Boolean).join(', ');
  $('flight').textContent = '';
  syncPlay();
  if (first || switched) intro();
}
function intro() {
  resize();
  // Arrive from slightly further out: the motion says "this is the unit you selected".
  camera.position.copy(home.target).addScaledVector(home.dir, homeDistance() * 1.3);
  controls.target.copy(home.target);
  flyTo(home.pos, home.target, 1.0, 'expo.out');
  gsap.to('#hud', { opacity: 1, duration: D(0.24), delay: D(0.2) });
}

/* ------------------------------------------------------------------ loop */
let last = performance.now();
function frame() {
  requestAnimationFrame(frame);
  const now = performance.now();
  if (document.hidden) { last = now; return; }
  const dt = Math.min(0.05, (now - last) / 1000); last = now; S.frame++;
  const tsec = now / 1000;

  if (S.playing && S.data && S.N > 1) {
    S.t += dt * (S.N / 20) * S.speed; // one recorded life in about 20 s at 1x
    if (S.t >= S.N - 1) {
      S.t = S.N - 1; S.playing = false; syncPlay();
      pushEvent(S.data.cycles[S.N - 1], 'Replay reached the latest reading', C.lineStrong);
    }
  }
  for (const m of MODEL.modules) {
    const g = MODEL.mods[m.key];
    g.position.set(m.explode[0] * S.explode, m.explode[1] * S.explode, m.explode[2] * S.explode);
  }
  MODEL.tick(dt, tsec, { reduced: REDUCED, explode: S.explode });
  controls.autoRotate = S.rotate && !REDUCED;
  controls.update(dt);
  if (S.data) applyState(tsec);
  else MODEL.apply({ modLevel: Object.fromEntries(MODEL.modules.map((m) => [m.key, -1])), z: {}, tsec, levels: LEVELS, reduced: REDUCED });
  renderer.render(scene, camera);
  drawOverlay();
  if (S.mode === 'twin') drawTimeline();
}

/* ------------------------------------------------------------------ args from Streamlit */
function onRender(args) {
  const mode = args.mode || 'twin';
  if (mode !== S.mode) { S.mode = mode; app.className = `mode-${mode}`; }
  Bridge.height(args.height || (mode === 'hero' ? 420 : 820));
  if (mode === 'hero') {
    useModel(args.component || 'turbofan');
    if (!S.started) { S.started = true; intro(); }
    return;
  }
  const p = args.payload;
  if (p && p.id !== S.dataId) loadPayload(p);
}
window.addEventListener('message', (e) => { const m = e.data; if (m && m.type === 'streamlit:render') onRender(m.args || {}); });

useModel('turbofan');
resize();
setHome();
camera.position.copy(home.pos);
requestAnimationFrame(frame);
Bridge.ready();
if (!IN_ST) {
  const q = new URLSearchParams(location.search);
  onRender({ mode: q.get('mode') || 'hero', component: q.get('component') || 'turbofan', height: window.innerHeight });
}
// Debug handle for the browser console (read-only inspection).
window.AS_DEBUG = { T, scene, camera, controls, S, get MODEL() { return MODEL; } };
