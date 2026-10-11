/* AeroSentinel 3D model viewer: one sectioned component with every sensor channel at its station.
 *
 * Runs in a Streamlit custom component iframe. Streamlit sends `streamlit:render` with args
 * {mode, height, payload}; the payload is one unit's recorded history (app/engine3d/__init__.py)
 * and names its component, whose geometry comes from ./models/<component>.js (turbofan, battery,
 * bearing). Clicking a sensor returns {sensor, unit, t} to Python.
 *
 * Rendering: physically based materials lit by a studio environment, a brand-blue rim light, soft
 * shadows on the floor and a restrained bloom so status colours and hot parts glow.
 *
 * Motion rules: a component is built up on arrival by a scan plane sweeping along it (nothing moves
 * through anything else), then the view rests on the latest reading. In the exploded view outer shells
 * fade to a ghost instead of travelling through the parts inside them.
 * Running parts (rotors, airflow, current, a turning shaft) show a working component. Every sensor
 * beyond the elevated drift limit is tied to its station by a leader line; warning and critical
 * stations pulse. Camera moves, the exploded view and event entries are GSAP tweens that explain a
 * change of view or state. Replay is user-started and labelled as recorded history. Reduced motion
 * freezes running parts and pulses and makes every transition instant.
 */
import * as T from './vendor/three-bundle.js';
import { build as buildTurbofan } from './models/turbofan.js?v=6.0.0';
import { build as buildBattery } from './models/battery.js?v=6.0.0';
import { build as buildGearbox } from './models/gearbox.js?v=6.0.1';
import { build as buildHydraulic } from './models/hydraulic.js?v=6.0.0';
import { build as buildPower } from './models/power.js?v=6.0.0';

// The gearbox model is keyed "bearing": its data is the FEMTO gearbox-bearing set.
const BUILDERS = { turbofan: buildTurbofan, battery: buildBattery, bearing: buildGearbox, hydraulic: buildHydraulic, power: buildPower };
const gsap = window.gsap;
gsap.ticker.lagSmoothing(0); // keep tweens on wall-clock time even when a slow GPU drops frames
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
  accent: '#3fa2ff', brand: '#1683f2', cyan: '#5fd4f8', teal: '#3ddbd9',
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
  sensors: [], modLevel: {}, frame: 0, started: false, reveal: 1, alarm: null, rendered: false,
};
let MODEL = null; // the component model on screen (see ./models/*.js)

/* ------------------------------------------------------------------ renderer, scene, camera */
const app = $('app');
const canvas = $('gl');
const renderer = new T.WebGLRenderer({ canvas, antialias: false, powerPreference: 'high-performance' });
renderer.toneMapping = T.NeutralToneMapping; // keeps status colours true to the rest of the console
renderer.toneMappingExposure = 1.05;
renderer.shadowMap.enabled = true;
renderer.localClippingEnabled = true; // the build-up scan clips the model behind a moving plane
renderer.shadowMap.type = T.PCFShadowMap; // soft in r186 (shadow.radius)

const scene = new T.Scene();
scene.background = (() => {
  // Studio backdrop: near-black with a faint brand-blue lift behind the model.
  const c = document.createElement('canvas'); c.width = c.height = 512;
  const g = c.getContext('2d'), grd = g.createRadialGradient(256, 214, 8, 256, 256, 380);
  grd.addColorStop(0, '#17212e'); grd.addColorStop(0.42, '#10151c'); grd.addColorStop(1, '#0b0d10');
  g.fillStyle = grd; g.fillRect(0, 0, 512, 512);
  const t = new T.CanvasTexture(c); t.colorSpace = T.SRGBColorSpace; return t;
})();
scene.fog = new T.Fog(0x0d1014, 22, 46);
const pmrem = new T.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new T.RoomEnvironment(), 0.04).texture;
scene.environmentIntensity = 0.45;
scene.add(new T.HemisphereLight(0xc9d6e6, 0x0c0f14, 0.75));
const keyLight = new T.DirectionalLight(0xffffff, 1.45); keyLight.position.set(3.5, 10, 6); scene.add(keyLight);
keyLight.castShadow = true;
keyLight.shadow.mapSize.set(2048, 2048);
Object.assign(keyLight.shadow.camera, { left: -9, right: 9, top: 9, bottom: -9, near: 1, far: 40 });
keyLight.shadow.bias = -0.0004; keyLight.shadow.normalBias = 0.03; keyLight.shadow.radius = 5;
const fill = new T.DirectionalLight(0x9fb8d8, 0.45); fill.position.set(-6, 2, -6); scene.add(fill);
// Brand rim: a cool blue edge from behind separates the metal from the backdrop.
const rim = new T.DirectionalLight(0x3f8cff, 1.3); rim.position.set(-5, 5, -9); scene.add(rim);
const under = new T.DirectionalLight(0x5fd4f8, 0.35); under.position.set(4, -6, 3); scene.add(under);

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
let userTouched = false;
controls.addEventListener('start', () => { userTouched = true; gsap.killTweensOf(camera.position); gsap.killTweensOf(controls.target); });

/* ------------------------------------------------------------------ post: bloom on emissive status colour and hot parts */
const composer = new T.EffectComposer(renderer, new T.WebGLRenderTarget(1, 1, { type: T.HalfFloatType, samples: 4 }));
composer.addPass(new T.RenderPass(scene, camera));
// Threshold 1.0: only HDR values bloom (boosted status markers, hot sections, polished-steel glints).
const bloom = new T.UnrealBloomPass(new T.Vector2(1, 1), 0.42, 0.45, 1.0);
composer.addPass(bloom);
composer.addPass(new T.OutputPass());

/* Quality governor: if frames stay slow (software WebGL, small laptops), drop the pixel ratio, then
 * bloom and shadows. Never steps back up within a session. */
const Q = { level: 2, samples: [], fixed: (() => { try { return localStorage.getItem('as-quality') === 'high'; } catch (e) { return false; } })() };
function pixelRatio() { return Q.level === 2 ? Math.min(window.devicePixelRatio || 1, 2) : 1; }
function governQuality(dt) {
  if (Q.fixed || Q.level === 0 || S.frame < 20) return;
  Q.samples.push(dt); if (Q.samples.length < 30) return;
  const sorted = Q.samples.slice().sort((a, b) => a - b), median = sorted[15];
  Q.samples.length = 0;
  if (median < 0.04) return;
  Q.level -= 1;
  if (Q.level === 0) { bloom.enabled = false; renderer.shadowMap.enabled = false; keyLight.castShadow = false; shadowPlane.visible = false; }
  renderer.setPixelRatio(pixelRatio()); resize();
}

/* ------------------------------------------------------------------ floor: grid, contact shadow, stage light, alarm ripple */
const gridMat = new T.ShaderMaterial({
  transparent: true, depthWrite: false,
  vertexShader: 'varying vec3 vW; void main(){ vec4 w = modelMatrix*vec4(position,1.0); vW = w.xyz; gl_Position = projectionMatrix*viewMatrix*w; }',
  fragmentShader: `varying vec3 vW;
    void main(){ vec2 q = vW.xz; vec2 g = abs(fract(q - 0.5) - 0.5) / fwidth(q); float line = 1.0 - min(min(g.x, g.y), 1.0);
      vec2 q4 = vW.xz / 4.0; vec2 g4 = abs(fract(q4 - 0.5) - 0.5) / fwidth(q4); float major = 1.0 - min(min(g4.x, g4.y), 1.0);
      float fade = 1.0 - smoothstep(4.0, 18.0, length(vW.xz));
      vec3 col = mix(vec3(0.13, 0.16, 0.21), vec3(0.16, 0.27, 0.42), major);
      gl_FragColor = vec4(col, max(line * 0.7, major * 0.75) * fade); }`,
});
const floor = new T.Group(); scene.add(floor);
const ground = new T.Mesh(new T.PlaneGeometry(60, 60), gridMat);
ground.rotation.x = -Math.PI / 2; floor.add(ground);
const shadowPlane = new T.Mesh(new T.PlaneGeometry(40, 40), new T.ShadowMaterial({ color: 0x000000, opacity: 0.55 }));
shadowPlane.rotation.x = -Math.PI / 2; shadowPlane.position.y = 0.004; shadowPlane.receiveShadow = true; floor.add(shadowPlane);
const radialTex = (stops) => {
  const c = document.createElement('canvas'); c.width = c.height = 256;
  const g = c.getContext('2d'), grd = g.createRadialGradient(128, 128, 0, 128, 128, 128);
  stops.forEach(([o, col]) => grd.addColorStop(o, col)); g.fillStyle = grd; g.fillRect(0, 0, 256, 256);
  const t = new T.CanvasTexture(c); t.colorSpace = T.SRGBColorSpace; return t;
};
const stage = new T.Mesh(new T.PlaneGeometry(16, 16), new T.MeshBasicMaterial({
  map: radialTex([[0, 'rgba(31,131,242,0.4)'], [0.35, 'rgba(22,90,190,0.13)'], [1, 'rgba(10,40,100,0)']]),
  transparent: true, depthWrite: false, blending: T.AdditiveBlending, toneMapped: false,
}));
stage.rotation.x = -Math.PI / 2; stage.position.y = 0.008; floor.add(stage);
const ripples = [0, 1].map(() => {
  const m = new T.Mesh(new T.RingGeometry(0.97, 1.0, 128), new T.MeshBasicMaterial({
    color: 0xfa4d56, transparent: true, opacity: 0, depthWrite: false, blending: T.AdditiveBlending, side: T.DoubleSide }));
  m.rotation.x = -Math.PI / 2; m.position.y = 0.012; floor.add(m); return m;
});

/* ------------------------------------------------------------------ build-up scan: a plane sweeps along the component */
const scan = { plane: new T.Plane(new T.Vector3(-1, 0, 0), 0), tween: null };
const scanGlow = new T.Mesh(new T.PlaneGeometry(1, 1), new T.MeshBasicMaterial({
  map: (() => {
    const c = document.createElement('canvas'); c.width = c.height = 256; const g = c.getContext('2d');
    const grd = g.createRadialGradient(128, 128, 40, 128, 128, 128);
    grd.addColorStop(0, 'rgba(95,212,248,0.05)'); grd.addColorStop(0.8, 'rgba(95,212,248,0.35)'); grd.addColorStop(1, 'rgba(95,212,248,0)');
    g.fillStyle = grd; g.fillRect(0, 0, 256, 256);
    const t = new T.CanvasTexture(c); t.colorSpace = T.SRGBColorSpace; return t;
  })(),
  transparent: true, depthWrite: false, blending: T.AdditiveBlending, side: T.DoubleSide, toneMapped: false,
}));
scanGlow.rotation.y = Math.PI / 2; scanGlow.visible = false; scene.add(scanGlow);
function eachMaterial(fn) {
  MODEL.root.traverse((o) => { (Array.isArray(o.material) ? o.material : o.material ? [o.material] : []).forEach((m) => fn(m, o)); });
}
function setClip(on) {
  eachMaterial((m) => { if (!m.isShaderMaterial) { m.clippingPlanes = on ? [scan.plane] : null; m.needsUpdate = true; } });
  // custom-shader particles cannot be clipped: hold them back until the part they flow through exists
  MODEL.root.traverse((o) => { if (o.isPoints) o.visible = !on; });
}
function scanIn(delay, dur) {
  if (scan.tween) scan.tween.kill();
  const box = new T.Box3();
  MODEL.root.traverse((o) => { if (o.isMesh && o.geometry) box.expandByObject(o); });
  if (box.isEmpty() || REDUCED) { setClip(false); scanGlow.visible = false; return; }
  const size = box.getSize(new T.Vector3()), mid = box.getCenter(new T.Vector3());
  scan.plane.constant = box.min.x - 0.05;
  setClip(true);
  scanGlow.visible = true;
  scanGlow.scale.set(size.z * 1.25 + 0.4, size.y * 1.25 + 0.4, 1);
  scanGlow.position.set(scan.plane.constant, mid.y, mid.z);
  scan.tween = gsap.to(scan.plane, {
    constant: box.max.x + 0.05, duration: dur, delay, ease: 'power2.inOut',
    onUpdate: () => { scanGlow.position.x = scan.plane.constant; },
    onComplete: () => { setClip(false); scanGlow.visible = false; scan.tween = null; },
  });
}

/* ------------------------------------------------------------------ exploded view: shells fade to a ghost */
function ghostShells(amount) {
  for (const m of MODEL.shells || []) {
    if (m.userData.baseOpacity === undefined) { m.userData.baseOpacity = m.opacity; m.userData.baseTransparent = m.transparent; }
    const ghost = amount > 0.01;
    if (ghost !== !!m.userData.ghosted) {
      m.userData.ghosted = ghost;
      m.transparent = ghost || m.userData.baseTransparent;
      m.depthWrite = !ghost;
      m.needsUpdate = true;
    }
    m.opacity = ghost ? m.userData.baseOpacity * (1 - 0.86 * amount) : m.userData.baseOpacity;
  }
}

/* ------------------------------------------------------------------ sensor markers */
const markerGeo = new T.SphereGeometry(0.06, 20, 14);
const spriteTex = (draw) => { const c = document.createElement('canvas'); c.width = c.height = 128; draw(c.getContext('2d')); return new T.CanvasTexture(c); };
const ringTex = spriteTex((g) => { g.strokeStyle = '#fff'; g.lineWidth = 6; g.beginPath(); g.arc(64, 64, 52, 0, Math.PI * 2); g.stroke(); });
const haloTex = spriteTex((g) => {
  const grd = g.createRadialGradient(64, 64, 30, 64, 64, 62);
  grd.addColorStop(0, 'rgba(255,255,255,0)'); grd.addColorStop(0.7, 'rgba(255,255,255,0.9)'); grd.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = grd; g.beginPath(); g.arc(64, 64, 62, 0, Math.PI * 2); g.fill();
});
let markers = {};
const modEls = {};

/* ------------------------------------------------------------------ component model */
function useModel(key) {
  key = BUILDERS[key] ? key : 'turbofan';
  if (MODEL && MODEL.key === key) return false;
  if (MODEL) { scene.remove(MODEL.root); MODEL.dispose(); }
  MODEL = BUILDERS[key]();
  MODEL.root.traverse((o) => {
    if (!o.isMesh) return;
    const mats = Array.isArray(o.material) ? o.material : [o.material];
    if (mats.some((m) => m.transparent || m.blending === T.AdditiveBlending)) return;
    o.castShadow = true;
    if (o.userData.receive !== false) o.receiveShadow = true;
  });
  scene.add(MODEL.root);
  floor.position.y = MODEL.groundY;
  markers = {};
  for (const [k, L] of Object.entries(MODEL.layout)) {
    const g = new T.Group(); g.position.fromArray(L.pos);
    const dot = new T.Mesh(markerGeo, new T.MeshBasicMaterial({ color: 0x9aa3ad, depthTest: false, transparent: true }));
    const halo = new T.Sprite(new T.SpriteMaterial({ map: haloTex, color: 0xfa4d56, depthTest: false, transparent: true, opacity: 0,
      blending: T.AdditiveBlending, depthWrite: false }));
    const sel = new T.Sprite(new T.SpriteMaterial({ map: ringTex, color: C.accent, depthTest: false, transparent: true }));
    sel.scale.setScalar(0.34); sel.visible = false; halo.visible = false;
    dot.renderOrder = 21; sel.renderOrder = 22; halo.renderOrder = 20;
    g.add(halo, dot, sel); g.visible = false;
    ((L.at && MODEL.layers && MODEL.layers[L.at]) || MODEL.mods[L.mod]).add(g); // a marker can ride on a moving layer
    markers[k] = { group: g, dot, sel, halo, pop: 1, phase: Math.random(), screen: new T.Vector2(-999, -999) };
  }
  $('modules').innerHTML = '';
  Object.keys(modEls).forEach((k) => delete modEls[k]);
  MODEL.modules.forEach((m) => { const el = document.createElement('div'); el.className = 'mod'; el.textContent = m.name; $('modules').appendChild(el); modEls[m.key] = el; });
  $('panel-l').textContent = MODEL.panels.L; $('panel-r').textContent = MODEL.panels.R;
  home.target.fromArray(MODEL.view.target);
  home.dir.fromArray(MODEL.view.dir).normalize();
  controls.target.copy(home.target);
  resize();
  return true;
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
    const side = MODEL.layout[k].side;
    (side === 'L' ? $('rows-left') : $('rows-right')).appendChild(el);
    S.sensors.push({ ...sd, zs: sd.z, el, side, vEl: el.querySelector('.v'), zEl: el.querySelector('.z'), v: 0, zNow: 0, vDisp: null, zDisp: 0 });
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
  gsap.fromTo(el, { autoAlpha: 0, x: -10 }, { autoAlpha: 1, x: 0, duration: D(0.3), ease: 'power2.out' });
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
  const drawCurves = (alpha, fillUnder) => {
    tlx.globalAlpha = alpha;
    if (d.rul) {
      if (fillUnder) {
        path(d.rul, yR); tlx.lineTo(xOf(S.N - 1), TL.t + h); tlx.lineTo(xOf(0), TL.t + h); tlx.closePath();
        const grd = tlx.createLinearGradient(0, TL.t, 0, TL.t + h);
        grd.addColorStop(0, 'rgba(63,162,255,0.22)'); grd.addColorStop(1, 'rgba(63,162,255,0)');
        tlx.fillStyle = grd; tlx.fill();
      }
      path(d.rul, yR); tlx.strokeStyle = C.accent; tlx.lineWidth = 1.75; tlx.stroke();
    }
    path(d.health, yH); tlx.strokeStyle = C.teal; tlx.lineWidth = 1.25; tlx.stroke();
    tlx.globalAlpha = 1;
  };
  drawCurves(0.25, false);
  tlx.save(); tlx.beginPath(); tlx.rect(0, 0, xOf(S.t) + 0.5, tlH); tlx.clip(); drawCurves(1, true); tlx.restore();
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
  if (d.rul) { // playhead on the RUL curve
    const py = yR(interp(d.rul, S.t));
    tlx.fillStyle = 'rgba(63,162,255,0.25)'; tlx.beginPath(); tlx.arc(px, py, 6, 0, Math.PI * 2); tlx.fill();
    tlx.fillStyle = C.accent; tlx.beginPath(); tlx.arc(px, py, 3, 0, Math.PI * 2); tlx.fill();
  }
  // legend, right gutter
  tlx.fillStyle = C.accent; tlx.fillRect(TL.l + w + 12, TL.t + 6, 10, 2); tlx.fillStyle = C.text2; tlx.fillText(d.rul_short || 'RUL', TL.l + w + 28, TL.t + 7);
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
  app.classList.toggle('playing', S.playing);
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
  gsap.to(S, { explode: on ? 1 : 0, duration: D(0.9), ease: 'power3.inOut', overwrite: true });
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
  const pr = pixelRatio();
  renderer.setPixelRatio(pr);
  renderer.setSize(W, H, false);
  composer.setPixelRatio(pr); composer.setSize(W, H);
  bloom.resolution.set(W * pr, H * pr);
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
  Object.entries(markers).forEach(([k, m]) => {
    m.sel.visible = k === S.selected;
    if (m.sel.visible) gsap.fromTo(m.sel.scale, { x: 0.9, y: 0.9 }, { x: 0.34, y: 0.34, duration: D(0.45), ease: 'back.out(2)' });
  });
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
    const lv = best.modeled ? level(best.zDisp) : -1;
    const drift = best.modeled ? `${best.zDisp >= 0 ? '+' : ''}${best.zDisp.toFixed(1)} sigma from baseline` : 'not used by the model';
    tip.style.setProperty('--c', lv < 0 ? C.lineStrong : LEVELS[lv].color);
    tip.innerHTML = `<b>${esc(best.code)}</b> ${esc(best.name)}<div class="m">${best.v.toFixed(best.decimals)} ${esc(best.unit)}, ${drift}</div>`
      + (lv >= 0 ? `<div class="lv">${LEVELS[lv].label} drift</div>` : '');
    canvas.style.cursor = 'pointer';
  } else { tip.style.display = 'none'; canvas.style.cursor = ''; }
});
canvas.addEventListener('pointerleave', () => { tip.style.display = 'none'; S.hovered = null; });
canvas.addEventListener('click', () => { if (S.hovered && S.mode === 'twin') select(S.hovered); });
canvas.addEventListener('dblclick', () => { S.selected = null; refreshSelection(); flyHome(0.8); });

/* ------------------------------------------------------------------ apply state */
const tmpColor = new T.Color();
function applyState(dt, tsec, rawDt = dt) {
  const d = S.data;
  const modLevel = Object.fromEntries(MODEL.modules.map((m) => [m.key, -1]));
  const z = {};
  // Displayed values ease toward the record, so switching unit or scrubbing reads as a change, not a jump.
  const k = REDUCED ? 1 : 1 - Math.exp(-Math.min(rawDt, 0.5) * 9); // wall-clock easing, even on slow frames
  for (const s of S.sensors) {
    s.v = interp(s.values, S.t);
    s.zNow = s.modeled ? interp(s.zs, S.t) : 0;
    s.vDisp = s.vDisp === null ? s.v : lerp(s.vDisp, s.v, k);
    s.zDisp = lerp(s.zDisp, s.zNow, k);
    if (s.modeled) {
      z[s.key] = s.zNow;
      const lv = level(s.zNow), mod = MODEL.layout[s.key].mod;
      if (lv >= 0 && (modLevel[mod] < 0 || lv < modLevel[mod])) modLevel[mod] = lv;
    }
  }
  // Components with part classifiers (hydraulic) colour each part by its predicted condition instead.
  if (d && d.parts) {
    const i = clamp(Math.round(S.t), 0, S.N - 1);
    for (const [mod, sev] of Object.entries(d.parts)) if (mod in modLevel) modLevel[mod] = [-1, 2, 1, 0][sev[i]];
  }
  S.modLevel = modLevel;
  MODEL.apply({ modLevel, z, tsec, levels: LEVELS, reduced: REDUCED });

  for (const s of S.sensors) {
    const m = markers[s.key];
    const lv = s.modeled ? level(s.zDisp) : -1;
    // Danger stations glow (colour above the bloom threshold); nominal ones stay matte grey.
    if (lv < 0) m.dot.material.color.set(s.modeled ? '#9aa3ad' : '#4a525c');
    else m.dot.material.color.copy(tmpColor.set(LEVELS[lv].color)).multiplyScalar([3.4, 3.0, 1.7][lv]);
    const active = s.key === S.selected || s.key === S.hovered;
    m.dot.scale.setScalar((active ? 1.6 : lv === 0 ? 1.25 : 1) * m.pop);
    // Warning and critical stations pulse; critical twice as fast.
    const pulse = lv === 0 || lv === 1;
    m.halo.visible = pulse && m.pop > 0.5;
    if (m.halo.visible) {
      const ph = REDUCED ? 0.35 : (tsec * (lv === 0 ? 0.9 : 0.55) + m.phase) % 1;
      m.halo.scale.setScalar((0.22 + ph * 0.75) * m.pop);
      m.halo.material.opacity = (1 - ph) * (lv === 0 ? 0.95 : 0.7);
      m.halo.material.color.set(LEVELS[lv].color);
    }
  }
  if (!d || S.mode !== 'twin') return;
  const idx = clamp(Math.round(S.t), 0, S.N - 1);
  const state = stateAt(idx);
  S.alarm = state === 'CRITICAL' || state === 'WARNING' ? state : null;
  if (S.frame % 2) return;

  $('cycle').innerHTML = `${esc(d.time_title || 'Cycle')} ${d.cycles[idx]} <em>of ${d.cycles[S.N - 1]}</em>`;
  if (d.conditions) $('flight').textContent = MODEL.conditionText(d.conditions, idx);
  app.style.setProperty('--state', STATE[state].color);
  app.dataset.state = state;
  $('state').textContent = STATE[state].label;
  const band = d.band ? d.band[idx] : null;
  const rul = d.rul ? Math.round(interp(d.rul, S.t)) : null;
  const lifeTxt = (n) => ((d.life_unit || 'cycles') === '%' ? `${n}%` : `${n} ${d.life_unit || 'cycles'}`);
  $('band').innerHTML = [rul != null ? `${d.rul_short || 'RUL'} ${lifeTxt(rul)}` : null, band != null ? `${BAND_TXT[band]} ${Math.round(d.prob[idx] * 100)}%` : null]
    .filter(Boolean).map((t) => `<span>${esc(t)}</span>`).join('');
  const counts = { L: [0, 0], R: [0, 0] };
  for (const s of S.sensors) {
    s.vEl.textContent = s.vDisp.toFixed(s.decimals);
    if (s.modeled) {
      const lv = level(s.zDisp);
      s.zEl.textContent = `${s.zDisp >= 0 ? '+' : ''}${s.zDisp.toFixed(1)}`;
      s.el.style.setProperty('--c', levelColor(s.zDisp));
      s.el.classList.toggle('hot', lv === 0 || lv === 1);
      s.el.classList.toggle('crit', lv === 0);
      if (lv === 0 || lv === 1) counts[s.side][lv] += 1;
    } else s.zEl.textContent = 'n/u';
  }
  for (const side of ['L', 'R']) {
    const [c, w] = counts[side], el = $(side === 'L' ? 'cnt-l' : 'cnt-r');
    const html = `${c ? `<em class="c">${c}</em>` : ''}${w ? `<em class="w">${w}</em>` : ''}drift`;
    if (el.innerHTML !== html) { el.innerHTML = html; el.title = `${c} critical, ${w} warning`; }
  }
  for (const m of MODEL.modules) {
    const lv = S.modLevel[m.key];
    modEls[m.key].style.setProperty('--c', lv < 0 ? C.lineStrong : LEVELS[lv].color);
    modEls[m.key].classList.toggle('crit', lv === 0);
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

/* ------------------------------------------------------------------ leader lines: every sensor beyond the elevated limit */
function leaderPath(ax, ay, mx, my, dir) {
  // Short horizontal stub out of the panel, then a smooth curve that arrives at the station.
  const x0 = ax + dir * 12, pts = [[ax, ay], [x0, ay]];
  const span = Math.abs(mx - x0);
  const c1x = x0 + dir * Math.max(24, span * 0.5), c2x = mx - dir * Math.min(36, span * 0.2);
  for (let i = 1; i <= 28; i++) {
    const t = i / 28, u = 1 - t;
    pts.push([u * u * u * x0 + 3 * u * u * t * c1x + 3 * u * t * t * c2x + t * t * t * mx,
      u * u * u * ay + 3 * u * u * t * ay + 3 * u * t * t * my + t * t * t * my]);
  }
  return pts;
}
function strokePath(pts, frac) {
  let total = 0;
  for (let i = 1; i < pts.length; i++) total += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
  let left = total * frac;
  lx.beginPath(); lx.moveTo(pts[0][0], pts[0][1]);
  let end = pts[0];
  for (let i = 1; i < pts.length && left > 0; i++) {
    const seg = Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
    if (seg <= left) { lx.lineTo(pts[i][0], pts[i][1]); end = pts[i]; left -= seg; }
    else { const f = left / seg; end = [lerp(pts[i - 1][0], pts[i][0], f), lerp(pts[i - 1][1], pts[i][1], f)]; lx.lineTo(end[0], end[1]); left = 0; }
  }
  lx.stroke();
  return end;
}
function drawOverlay(tsec) {
  lx.clearRect(0, 0, W, H);
  if (S.mode !== 'twin' || !S.data) return;
  const v = new T.Vector3(), r0 = app.getBoundingClientRect();
  for (const m of Object.values(markers)) {
    if (!m.group.visible) continue;
    m.group.getWorldPosition(v).project(camera);
    m.screen.set((v.x * 0.5 + 0.5) * W, (-v.y * 0.5 + 0.5) * H);
  }
  if (!S.panels) return;
  const lines = [];
  for (const s of S.sensors) {
    const active = s.key === S.selected || s.key === S.hovered;
    const lv = s.modeled ? level(s.zDisp) : -1;
    if (!active && lv < 0) continue;
    lines.push({ s, lv, active, order: active ? 9 : 3 - lv });
  }
  lines.sort((a, b) => a.order - b.order); // elevated first, critical and the active line on top
  const panelL = $('rows-left').getBoundingClientRect(), panelR = $('rows-right').getBoundingClientRect();
  for (const { s, lv, active } of lines) {
    const rr = s.el.getBoundingClientRect(), m = markers[s.key];
    const left = s.side === 'L', pr = left ? panelL : panelR;
    const ax = (left ? rr.right : rr.left) - r0.left;
    const ay = clamp(rr.top + rr.height / 2, pr.top + 6, pr.bottom - 6) - r0.top;
    const pts = leaderPath(ax, ay, m.screen.x, m.screen.y, left ? 1 : -1);
    const color = active ? C.accent : LEVELS[lv].color;
    lx.strokeStyle = color; lx.fillStyle = color;
    lx.lineWidth = active ? 2 : lv === 0 ? 1.4 : lv === 1 ? 1.2 : 1;
    lx.globalAlpha = active ? 1 : lv === 0 ? 0.9 : lv === 1 ? 0.75 : 0.5;
    if (!active && lv === 0 && !REDUCED) { lx.setLineDash([6, 4]); lx.lineDashOffset = -((tsec * 22) % 10); }
    else if (!active && lv === 2) { lx.setLineDash([2, 4]); lx.lineDashOffset = 0; }
    else lx.setLineDash([]);
    const frac = active ? 1 : S.reveal;
    const end = strokePath(pts, frac);
    lx.setLineDash([]);
    lx.beginPath(); lx.arc(ax, ay, 2, 0, Math.PI * 2); lx.fill();
    if (frac >= 0.999) { lx.beginPath(); lx.arc(end[0], end[1], active ? 5 : 3.5, 0, Math.PI * 2); lx.stroke(); }
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

/* ------------------------------------------------------------------ payload & intro choreography */
function loadPayload(p) {
  const switched = useModel(p.component || 'turbofan');
  const first = !S.data;
  S.data = p; S.dataId = p.id; S.N = p.cycles.length;
  S.t = S.N - 1; S.playing = false; S.lastIdx = -1; S.critSeen.clear(); S.selected = null;
  Object.values(markers).forEach((m) => { m.group.visible = false; });
  buildRows(); refreshSelection(); $('events').innerHTML = '';
  $('unit-name').textContent = p.label || `Engine ${String(p.unit).padStart(3, '0')}`;
  $('unit-meta').textContent = [p.source, p.model ? `model ${p.model}` : null, p.corrected ? 'readings corrected to the reference condition' : null]
    .filter(Boolean).join(', ');
  $('flight').textContent = '';
  syncPlay();
  if (first || switched) intro(true);
  else { // another unit of the same component: re-trace the leader lines only
    S.reveal = 0; gsap.to(S, { reveal: 1, duration: D(0.7), ease: 'power2.out', overwrite: true });
  }
}
function intro(withHud) {
  resize();
  // The component assembles module by module while the camera sweeps in to the working view.
  const start = home.target.clone().addScaledVector(home.dir.clone().applyAxisAngle(new T.Vector3(0, 1, 0), 0.75)
    .add(new T.Vector3(0, 0.25, 0)).normalize(), homeDistance() * 1.55);
  camera.position.copy(REDUCED ? home.pos : start);
  controls.target.copy(home.target);
  flyTo(home.pos, home.target, 1.9, 'power3.inOut');
  scanIn(0.15, 1.5);
  const ms = Object.values(markers);
  ms.forEach((m) => { m.pop = REDUCED ? 1 : 0; });
  gsap.to(ms, { pop: 1, duration: D(0.45), ease: 'back.out(2.2)', stagger: D(0.02), delay: D(1.55) });
  S.reveal = REDUCED ? 1 : 0;
  gsap.to(S, { reveal: 1, duration: D(0.9), ease: 'power2.out', delay: D(1.8), overwrite: true });
  if (withHud && !REDUCED) {
    gsap.set('#hud', { opacity: 1 });
    const tlHud = gsap.timeline({ delay: 0.25 });
    tlHud.from('.top', { y: -16, autoAlpha: 0, duration: 0.5, ease: 'power3.out', clearProps: 'all' })
      .from('.panel.left', { x: -28, autoAlpha: 0, duration: 0.55, ease: 'power3.out', clearProps: 'transform,opacity,visibility' }, '-=0.3')
      .from('.panel.right', { x: 28, autoAlpha: 0, duration: 0.55, ease: 'power3.out', clearProps: 'transform,opacity,visibility' }, '<')
      .from('.panel .row', { autoAlpha: 0, x: (i, el) => (el.closest('.left') ? -8 : 8), duration: 0.3, stagger: 0.018, ease: 'power2.out', clearProps: 'all' }, '-=0.3')
      .from('.modules .mod', { y: -6, autoAlpha: 0, duration: 0.3, stagger: 0.04, ease: 'power2.out', clearProps: 'all' }, '<')
      .from('.bottom', { y: 18, autoAlpha: 0, duration: 0.5, ease: 'power3.out', clearProps: 'all' }, '<');
  } else gsap.set('#hud', { opacity: 1 });
}

/* hero: a slow turntable; the component stays assembled */
function heroMotion() { S.explode = 0; }

/* ------------------------------------------------------------------ loop */
let last = performance.now();
function frame() {
  requestAnimationFrame(frame);
  const now = performance.now();
  if (document.hidden) { last = now; return; }
  const raw = (now - last) / 1000, dt = Math.min(0.05, raw); last = now; S.frame++;
  governQuality(raw);
  const tsec = now / 1000;

  if (S.playing && S.data && S.N > 1) {
    S.t += dt * (S.N / 20) * S.speed; // one recorded life in about 20 s at 1x
    if (S.t >= S.N - 1) {
      S.t = S.N - 1; S.playing = false; syncPlay();
      pushEvent(S.data.cycles[S.N - 1], 'Replay reached the latest reading', C.lineStrong);
    }
  }
  for (const m of MODEL.modules) {
    MODEL.mods[m.key].position.set(m.explode[0] * S.explode, m.explode[1] * S.explode, m.explode[2] * S.explode);
  }
  ghostShells(S.explode);
  MODEL.tick(dt, tsec, { reduced: REDUCED, explode: S.explode });
  controls.autoRotate = !REDUCED && (S.rotate || (S.mode === 'hero' && !userTouched));
  controls.autoRotateSpeed = S.mode === 'hero' ? 0.6 : 0.35;
  controls.update(dt);
  if (S.data) applyState(dt, tsec, raw);
  else MODEL.apply({ modLevel: Object.fromEntries(MODEL.modules.map((m) => [m.key, -1])), z: {}, tsec, levels: LEVELS, reduced: REDUCED });
  // Alarm ripple on the floor while the unit is in a warning or critical state.
  ripples.forEach((rp, i) => {
    const on = S.mode === 'twin' && S.alarm && !REDUCED;
    rp.visible = !!on;
    if (!on) return;
    const ph = (tsec * (S.alarm === 'CRITICAL' ? 0.42 : 0.28) + i * 0.5) % 1;
    rp.scale.setScalar(1.2 + ph * 7.5);
    rp.material.color.set(STATE[S.alarm].color);
    rp.material.opacity = (1 - ph) * (1 - ph) * 0.2;
    rp.position.set(home.target.x, 0.012, home.target.z);
  });
  stage.position.set(home.target.x, 0.008, home.target.z);
  composer.render(dt);
  drawOverlay(tsec);
  if (S.mode === 'twin') drawTimeline();
  if (!S.rendered) { S.rendered = true; gsap.to('#loader', { autoAlpha: 0, duration: D(0.45), delay: D(0.1) }); }
}

/* ------------------------------------------------------------------ args from Streamlit */
function onRender(args) {
  const mode = args.mode || 'twin';
  if (mode !== S.mode) { S.mode = mode; app.className = `mode-${mode}`; heroMotion(mode === 'hero'); resize(); }
  Bridge.height(args.height || (mode === 'hero' ? 420 : 820));
  if (mode === 'hero') {
    const switched = useModel(args.component || 'turbofan');
    if (!S.started || switched) { S.started = true; intro(false); heroMotion(true); }
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
window.AS_DEBUG = { T, scene, camera, controls, S, composer, get MODEL() { return MODEL; } };
