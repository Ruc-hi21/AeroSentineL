/* AeroSentinel engine model: a sectioned turbofan with every C-MAPSS sensor at its station.
 *
 * Runs in a Streamlit custom component iframe. Streamlit sends `streamlit:render` with args
 * {mode, height, payload}; the payload is one engine's recorded history (app/engine3d/__init__.py).
 * Clicking a sensor returns {sensor, unit, t} to Python.
 *
 * Motion rules: the view opens on the latest reading. Rotors and airflow show a running engine.
 * Camera moves, the exploded view and event entries are GSAP tweens that explain a change of
 * view or state. Replay is user-started and labelled as recorded history. Reduced motion
 * freezes the flow and makes every transition instant.
 */
import * as T from './vendor/three-bundle.js';

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
const MIN_CYCLES = 30; // backend ROLLING_WINDOW: fewer cycles = insufficient data

/* ------------------------------------------------------------------ layout */
const MODULES = [
  { key: 'fan', name: 'Fan', explode: -2.6 }, { key: 'lpc', name: 'LPC', explode: -1.6 },
  { key: 'hpc', name: 'HPC', explode: -0.55 }, { key: 'comb', name: 'Combustor', explode: 0.45 },
  { key: 'hpt', name: 'HPT', explode: 1.25 }, { key: 'lpt', name: 'LPT', explode: 2.15 },
  { key: 'noz', name: 'Nozzle', explode: 3.2 }, { key: 'byp', name: 'Bypass', explode: 0 },
];
const LAYOUT = {
  sensor_1: { mod: 'fan', pos: [-4.7, 1.5, 0.6], side: 'L' }, sensor_5: { mod: 'fan', pos: [-4.7, -1.4, 0.7], side: 'L' },
  sensor_2: { mod: 'lpc', pos: [-2.45, 0.95, 0.35], side: 'L' }, sensor_6: { mod: 'byp', pos: [-1.6, 1.72, 0.65], side: 'L' },
  sensor_17: { mod: 'hpc', pos: [-1.2, 1.08, 0.35], side: 'L' }, sensor_11: { mod: 'hpc', pos: [-0.65, 0.55, 0.6], side: 'L' },
  sensor_3: { mod: 'hpc', pos: [-0.25, 0.8, 0.25], side: 'L' }, sensor_7: { mod: 'hpc', pos: [-0.25, -0.72, 0.4], side: 'L' },
  sensor_4: { mod: 'lpt', pos: [2.75, 1.05, 0.4], side: 'L' }, sensor_10: { mod: 'noz', pos: [3.55, 0.85, 0.4], side: 'L' },
  sensor_18: { mod: 'fan', pos: [-4.45, 0.1, 0.05], side: 'R' }, sensor_19: { mod: 'fan', pos: [-4.25, -0.18, 0.15], side: 'R' },
  sensor_8: { mod: 'fan', pos: [-3.95, 0.35, 0.3], side: 'R' }, sensor_13: { mod: 'fan', pos: [-3.6, -0.45, 0.35], side: 'R' },
  sensor_15: { mod: 'byp', pos: [-0.4, -1.72, 0.55], side: 'R' }, sensor_9: { mod: 'hpc', pos: [-1.1, 0.2, 0.22], side: 'R' },
  sensor_14: { mod: 'hpc', pos: [-1.6, -0.3, 0.32], side: 'R' }, sensor_12: { mod: 'comb', pos: [0.45, 1.0, 0.3], side: 'R' },
  sensor_16: { mod: 'comb', pos: [0.45, -0.95, 0.3], side: 'R' }, sensor_20: { mod: 'hpt', pos: [1.15, 0.95, 0.3], side: 'R' },
  sensor_21: { mod: 'lpt', pos: [2.1, 1.2, 0.3], side: 'R' },
};

/* ------------------------------------------------------------------ state */
const S = {
  mode: 'twin', data: null, dataId: null, N: 0, t: 0, playing: false, speed: 1, lastIdx: -1, maxBand: 0,
  critSeen: new Set(), selected: null, hovered: null, explode: 0, panels: true, rotate: false,
  sensors: [], modLevel: {}, frame: 0, started: false,
};

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
const combLight = new T.PointLight(0xff7a30, 2.4, 3.2, 2); combLight.position.set(0.45, 0, 0); scene.add(combLight);

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
const HOME_TARGET = new T.Vector3(-0.2, 0, 0);
const HOME_DIR = new T.Vector3(0.55, 0.34, 1).normalize();
controls.target.copy(HOME_TARGET);
controls.addEventListener('start', () => { gsap.killTweensOf(camera.position); gsap.killTweensOf(controls.target); });

/* ------------------------------------------------------------------ materials */
const metal = (color, rough, metalness = 0.85) => new T.MeshStandardMaterial({ color, roughness: rough, metalness });
const M = {
  shell: new T.MeshStandardMaterial({ color: 0x2b3139, metalness: 0.35, roughness: 0.62, side: T.DoubleSide }),
  core: new T.MeshStandardMaterial({ color: 0x23282f, metalness: 0.4, roughness: 0.58, side: T.DoubleSide }),
  cut: new T.MeshStandardMaterial({ color: 0x48505a, metalness: 0.05, roughness: 0.9, side: T.DoubleSide }),
  fan: metal(0xaab3bd, 0.3), spinner: metal(0xc6cdd5, 0.25, 0.9), disk: metal(0x4c5560, 0.45, 0.8),
  stator: metal(0x6a737e, 0.45, 0.75), lpc: metal(0x9aa4af, 0.32), hpc: metal(0x9aa4af, 0.32),
  comb: new T.MeshStandardMaterial({ color: 0x6d625a, metalness: 0.5, roughness: 0.5, emissive: 0xff6a1f, emissiveIntensity: 0.5 }),
  hpt: new T.MeshStandardMaterial({ color: 0x857a72, metalness: 0.75, roughness: 0.4, emissive: 0xff5a1a, emissiveIntensity: 0.25 }),
  lpt: new T.MeshStandardMaterial({ color: 0x8b847f, metalness: 0.78, roughness: 0.38, emissive: 0xff6a20, emissiveIntensity: 0.1 }),
  plug: metal(0x7d8792, 0.35), shaft: metal(0x56606b, 0.35, 0.9),
};
[M.spinner, M.disk, M.plug, M.shaft].forEach((m) => { m.side = T.DoubleSide; });
const EDGE = new T.LineBasicMaterial({ color: 0x5c646e });
const tmpC = new T.Color();
const tmpV = new T.Vector3();

/* ------------------------------------------------------------------ geometry helpers */
const V2 = (r, x) => new T.Vector2(r, x);
// Lathe a (radius, axial) profile around world X. phi 0..1.5pi leaves the upper-front quarter open.
function lathe(points, mat, segs = 72, start = 0, len = Math.PI * 2) {
  const m = new T.Mesh(new T.LatheGeometry(points, segs, start, len), mat);
  m.rotation.z = -Math.PI / 2;
  return m;
}
function bladeGeometry({ hub, tip, chordHub, chordTip, thick, twistHub, twistTip, sweep = 0 }) {
  const g = new T.BoxGeometry(1, 1, 1, 2, 10, 1);
  const p = g.attributes.position;
  for (let i = 0; i < p.count; i++) {
    const x = p.getX(i), y = p.getY(i), z = p.getZ(i), t = y + 0.5;
    const r = hub + (tip - hub) * t, chord = chordHub + (chordTip - chordHub) * t;
    const cx = x * chord;
    let cz = z * thick * (1 - 1.4 * x * x);
    cz += (0.25 - x * x) * chord * 0.22;
    const tw = twistHub + (twistTip - twistHub) * t, c = Math.cos(tw), s = Math.sin(tw);
    p.setXYZ(i, cx * c - cz * s + sweep * t * t, r, cx * s + cz * c);
  }
  g.computeVertexNormals();
  return g;
}
function bladeRing(geo, mat, count, x, phase = 0) {
  const mesh = new T.InstancedMesh(geo, mat, count), m = new T.Matrix4();
  for (let i = 0; i < count; i++) { m.makeRotationX(phase + (i / count) * Math.PI * 2); mesh.setMatrixAt(i, m); }
  mesh.position.x = x;
  return mesh;
}
function axialCylinder(r, x0, x1, mat, segs = 48) {
  const m = new T.Mesh(new T.CylinderGeometry(r, r, x1 - x0, segs, 1), mat);
  m.rotation.z = Math.PI / 2; m.position.x = (x0 + x1) / 2;
  return m;
}
// Section faces and outline where a closed (r, x) profile is cut at phi = 0 (+Z) and phi = 1.5pi (+Y).
function sectionCut(profile) {
  const g = new T.Group();
  const shape = new T.Shape(profile.map((p) => new T.Vector2(p.y, p.x)));
  const faceZ = new T.Mesh(new T.ShapeGeometry(shape), M.cut); faceZ.rotation.x = Math.PI / 2; // (a, r) -> (a, 0, r)
  const faceY = new T.Mesh(new T.ShapeGeometry(shape), M.cut);                                  // (a, r) -> (a, r, 0)
  const lineZ = new T.LineLoop(new T.BufferGeometry().setFromPoints(profile.map((p) => new T.Vector3(p.y, 0, p.x + 0.002))), EDGE);
  const lineY = new T.LineLoop(new T.BufferGeometry().setFromPoints(profile.map((p) => new T.Vector3(p.y, p.x + 0.002, 0))), EDGE);
  g.add(faceZ, faceY, lineZ, lineY);
  return g;
}
function ring(r, x) {
  const pts = []; for (let i = 0; i <= 96; i++) { const a = (i / 96) * Math.PI * 1.5; pts.push(new T.Vector3(x, -r * Math.sin(a), r * Math.cos(a))); }
  return new T.Line(new T.BufferGeometry().setFromPoints(pts), EDGE);
}

/* ------------------------------------------------------------------ engine */
const engine = new T.Group(); scene.add(engine);
const mods = {};
MODULES.forEach((m) => { const g = new T.Group(); mods[m.key] = g; engine.add(g); });
const lpRotors = [], hpRotors = [];

const nacelleProfile = [V2(2.12, -4.95), V2(2.13, -4.3), V2(2.15, -3.4), V2(2.14, -1.0), V2(2.08, 0.6), V2(1.98, 1.6),
  V2(2.04, 1.68), V2(2.2, 1.55), V2(2.42, 0.2), V2(2.53, -1.6), V2(2.5, -3.3), V2(2.4, -4.5), V2(2.28, -4.98), V2(2.12, -4.95)];
mods.byp.add(lathe(nacelleProfile, M.shell, 96, 0, Math.PI * 1.5), sectionCut(nacelleProfile.slice(0, -1)));
mods.byp.add(ring(2.29, -4.97), ring(2.06, 1.66));
mods.byp.add(bladeRing(bladeGeometry({ hub: 1.2, tip: 2.12, chordHub: 0.22, chordTip: 0.26, thick: 0.02, twistHub: 0.25, twistTip: 0.2 }), M.stator, 44, -3.05));

const coreProfile = [V2(1.08, -3.3), V2(1.13, -3.32), V2(1.24, -2.6), V2(1.31, -1.0), V2(1.31, 0.8), V2(1.27, 2.0), V2(1.2, 2.9), V2(1.0, 3.85),
  V2(0.96, 3.84), V2(1.15, 2.9), V2(1.22, 2.0), V2(1.26, 0.8), V2(1.26, -1.0), V2(1.19, -2.6), V2(1.08, -3.3)];
mods.byp.add(lathe(coreProfile, M.core, 80, 0, Math.PI * 1.5), sectionCut(coreProfile.slice(0, -1)));

const spinnerPts = []; for (let i = 0; i <= 24; i++) { const t = i / 24; spinnerPts.push(V2(0.52 * Math.pow(Math.sin((t * Math.PI) / 2), 0.75), -4.75 + t * 0.85)); }
const fanRotor = new T.Group(); mods.fan.add(fanRotor); lpRotors.push(fanRotor);
fanRotor.add(lathe(spinnerPts, M.spinner, 64));
fanRotor.add(bladeRing(bladeGeometry({ hub: 0.48, tip: 2.08, chordHub: 0.42, chordTip: 0.66, thick: 0.05, twistHub: 1.05, twistTip: 0.32, sweep: -0.12 }), M.fan, 22, -3.9));
fanRotor.add(axialCylinder(0.53, -3.95, -3.45, M.disk));

const lpcRotor = new T.Group(); mods.lpc.add(lpcRotor); lpRotors.push(lpcRotor);
[-3.05, -2.8, -2.55].forEach((x, i) => {
  lpcRotor.add(bladeRing(bladeGeometry({ hub: 0.55, tip: 1.0 - i * 0.02, chordHub: 0.12, chordTip: 0.14, thick: 0.02, twistHub: 0.8, twistTip: 0.5 }), M.lpc, 30, x, i * 0.1));
  mods.lpc.add(bladeRing(bladeGeometry({ hub: 0.56, tip: 1.0 - i * 0.02, chordHub: 0.08, chordTip: 0.09, thick: 0.015, twistHub: -0.5, twistTip: -0.4 }), M.stator, 36, x + 0.12));
});
lpcRotor.add(axialCylinder(0.55, -3.15, -2.45, M.disk));

const hpcRotor = new T.Group(); mods.hpc.add(hpcRotor); hpRotors.push(hpcRotor);
for (let i = 0; i < 9; i++) {
  const x = -2.15 + i * 0.235, hub = 0.56 + i * 0.007, tip = 0.96 - i * 0.026;
  hpcRotor.add(bladeRing(bladeGeometry({ hub, tip, chordHub: 0.1, chordTip: 0.1, thick: 0.016, twistHub: 0.75, twistTip: 0.55 }), M.hpc, 34 + i * 3, x, i * 0.2));
  mods.hpc.add(bladeRing(bladeGeometry({ hub: hub + 0.01, tip: tip + 0.01, chordHub: 0.06, chordTip: 0.06, thick: 0.012, twistHub: -0.5, twistTip: -0.4 }), M.stator, 40 + i * 3, x + 0.11));
}
hpcRotor.add(lathe([V2(0.5, -2.25), V2(0.57, -2.2), V2(0.63, -0.1), V2(0.5, -0.05)], M.disk, 48));

{
  const pts = []; for (let i = 0; i <= 40; i++) { const a = (i / 40) * Math.PI * 2; pts.push(V2(0.76 + 0.13 * Math.cos(a), 0.45 + 0.36 * Math.sin(a))); }
  mods.comb.add(lathe(pts, M.comb, 96));
  const nozzleGeo = new T.SphereGeometry(0.03, 10, 8);
  for (let i = 0; i < 20; i++) { const a = (i / 20) * Math.PI * 2, n = new T.Mesh(nozzleGeo, M.disk); n.position.set(0.08, 0.76 * Math.cos(a), 0.76 * Math.sin(a)); mods.comb.add(n); }
}

const hptRotor = new T.Group(); mods.hpt.add(hptRotor); hpRotors.push(hptRotor);
[0.98, 1.24].forEach((x, i) => {
  hptRotor.add(bladeRing(bladeGeometry({ hub: 0.6, tip: 0.86 + i * 0.02, chordHub: 0.12, chordTip: 0.11, thick: 0.03, twistHub: -0.9, twistTip: -0.6 }), M.hpt, 40, x));
  mods.hpt.add(bladeRing(bladeGeometry({ hub: 0.6, tip: 0.87 + i * 0.02, chordHub: 0.08, chordTip: 0.08, thick: 0.02, twistHub: 0.7, twistTip: 0.5 }), M.stator, 30, x - 0.12));
});
hptRotor.add(axialCylinder(0.6, 0.9, 1.32, M.disk));
const lptRotor = new T.Group(); mods.lpt.add(lptRotor); lpRotors.push(lptRotor);
for (let i = 0; i < 5; i++) {
  const x = 1.55 + i * 0.29;
  lptRotor.add(bladeRing(bladeGeometry({ hub: 0.6, tip: 0.9 + i * 0.055, chordHub: 0.13, chordTip: 0.12, thick: 0.025, twistHub: -0.85, twistTip: -0.55 }), M.lpt, 46 + i * 4, x, i * 0.13));
  mods.lpt.add(bladeRing(bladeGeometry({ hub: 0.6, tip: 0.92 + i * 0.055, chordHub: 0.08, chordTip: 0.08, thick: 0.018, twistHub: 0.6, twistTip: 0.45 }), M.stator, 40 + i * 4, x - 0.13));
}
lptRotor.add(lathe([V2(0.45, 1.4), V2(0.6, 1.45), V2(0.6, 2.85), V2(0.45, 2.9)], M.disk, 48));
mods.noz.add(lathe([V2(0.6, 2.85), V2(0.58, 3.2), V2(0.48, 3.7), V2(0.3, 4.15), V2(0.0, 4.55)], M.plug, 64));
const lpShaft = axialCylinder(0.12, -3.9, 2.9, M.shaft, 24); lpRotors.push(lpShaft); mods.lpc.add(lpShaft);

/* ------------------------------------------------------------------ airflow: the gas path, cool bypass and core heating after the combustor */
const flowMat = new T.ShaderMaterial({
  transparent: true, depthWrite: false, blending: T.AdditiveBlending,
  uniforms: { uTime: { value: 0 }, uHeat: { value: 0 }, uPix: { value: 300 }, uFade: { value: 1 } },
  vertexShader: `
    attribute float aR; attribute float aAng; attribute float aPh; attribute float aSp; attribute float aType; attribute float aSize;
    uniform float uTime; uniform float uHeat; uniform float uPix; uniform float uFade;
    varying vec3 vCol; varying float vA;
    const float CX[11] = float[11](-7.0,-3.9,-3.2,-2.2,-0.1,0.9,1.5,2.8,3.9,4.4,7.5);
    const float CH[11] = float[11](0.15,0.5,0.55,0.57,0.63,0.63,0.62,0.6,0.32,0.05,0.05);
    const float CT[11] = float[11](0.95,1.0,1.0,0.95,0.74,0.86,0.9,1.1,0.95,0.92,1.4);
    const float BX[11] = float[11](-7.0,-5.0,-3.9,-3.2,-1.0,0.8,1.6,2.9,3.9,6.0,7.5);
    const float BH[11] = float[11](1.1,1.1,1.12,1.2,1.34,1.34,1.29,1.22,1.04,1.0,1.0);
    const float BT[11] = float[11](2.0,2.04,2.05,2.08,2.1,2.05,1.96,2.02,2.12,2.3,2.5);
    float pw(float x, float xs[11], float ys[11]){
      if (x <= xs[0]) return ys[0];
      for (int i = 0; i < 10; i++){ if (x <= xs[i+1]) return mix(ys[i], ys[i+1], (x - xs[i])/(xs[i+1]-xs[i])); }
      return ys[10];
    }
    void main(){
      float s = fract(aPh + uTime*aSp);
      float x = mix(-7.0, 7.5, s);
      float r; vec3 c;
      if (aType < 0.5) {
        r = mix(pw(x, BX, BH), pw(x, BX, BT), aR);
        c = vec3(0.42, 0.55, 0.72);
      } else {
        r = mix(pw(x, CX, CH), pw(x, CX, CT), aR);
        c = mix(vec3(0.45, 0.6, 0.78), vec3(0.85, 0.85, 0.85), smoothstep(-3.5, -0.3, x));
        c = mix(c, vec3(1.0, 0.62, 0.32) * (1.0 + uHeat * 0.5), smoothstep(-0.1, 0.6, x));
        c = mix(c, vec3(0.75, 0.42, 0.28), smoothstep(2.0, 6.0, x));
      }
      float ang = aAng + x*0.18;
      vec4 mv = modelViewMatrix*vec4(x, r*cos(ang), r*sin(ang), 1.0);
      gl_Position = projectionMatrix*mv;
      gl_PointSize = aSize*uPix/(-mv.z);
      vCol = c;
      vA = smoothstep(0.0, 0.06, s)*(1.0 - smoothstep(0.75, 1.0, s))*uFade;
    }`,
  fragmentShader: `varying vec3 vCol; varying float vA;
    void main(){ float d = length(gl_PointCoord - 0.5); gl_FragColor = vec4(vCol, vA*smoothstep(0.5, 0.15, d)*0.32); }`,
});
{
  const N = 2200, g = new T.BufferGeometry(), at = (n) => new Float32Array(n);
  const aR = at(N), aAng = at(N), aPh = at(N), aSp = at(N), aType = at(N), aSize = at(N);
  for (let i = 0; i < N; i++) {
    const core = i % 2 === 0;
    aR[i] = Math.random(); aAng[i] = Math.random() * Math.PI * 2; aPh[i] = Math.random();
    aSp[i] = core ? 0.06 + Math.random() * 0.02 : 0.05 + Math.random() * 0.02;
    aType[i] = core ? 1 : 0; aSize[i] = 0.035 + Math.random() * 0.03;
  }
  g.setAttribute('position', new T.BufferAttribute(at(N * 3), 3));
  [['aR', aR], ['aAng', aAng], ['aPh', aPh], ['aSp', aSp], ['aType', aType], ['aSize', aSize]].forEach(([k, v]) => g.setAttribute(k, new T.BufferAttribute(v, 1)));
  const flow = new T.Points(g, flowMat); flow.frustumCulled = false; engine.add(flow);
}

/* ------------------------------------------------------------------ ground plane: orientation only */
const gridMat = new T.ShaderMaterial({
  transparent: true, depthWrite: false,
  vertexShader: 'varying vec3 vW; void main(){ vec4 w = modelMatrix*vec4(position,1.0); vW = w.xyz; gl_Position = projectionMatrix*viewMatrix*w; }',
  fragmentShader: `varying vec3 vW;
    void main(){ vec2 q = vW.xz; vec2 g = abs(fract(q - 0.5) - 0.5) / fwidth(q); float line = 1.0 - min(min(g.x, g.y), 1.0);
      float fade = 1.0 - smoothstep(4.0, 18.0, length(vW.xz)); gl_FragColor = vec4(vec3(0.16, 0.18, 0.2), line * 0.9 * fade); }`,
});
const ground = new T.Mesh(new T.PlaneGeometry(60, 60), gridMat);
ground.rotation.x = -Math.PI / 2; ground.position.y = -2.9; scene.add(ground);

/* ------------------------------------------------------------------ sensor markers */
const markerGeo = new T.SphereGeometry(0.055, 16, 12);
const ringTex = (() => {
  const c = document.createElement('canvas'); c.width = c.height = 64;
  const g = c.getContext('2d'); g.strokeStyle = '#fff'; g.lineWidth = 3; g.beginPath(); g.arc(32, 32, 26, 0, Math.PI * 2); g.stroke();
  return new T.CanvasTexture(c);
})();
const markers = {};
for (const [k, L] of Object.entries(LAYOUT)) {
  const g = new T.Group(); g.position.fromArray(L.pos);
  const dot = new T.Mesh(markerGeo, new T.MeshBasicMaterial({ color: 0x7f8790, depthTest: false, transparent: true }));
  const sel = new T.Sprite(new T.SpriteMaterial({ map: ringTex, color: 0x78a9ff, depthTest: false, transparent: true }));
  sel.scale.setScalar(0.32); sel.visible = false;
  dot.renderOrder = sel.renderOrder = 20;
  g.add(dot, sel); g.visible = false; mods[L.mod].add(g);
  markers[k] = { group: g, dot, sel, screen: new T.Vector2(-999, -999) };
}

/* ------------------------------------------------------------------ HUD */
const modEls = {};
MODULES.forEach((m) => { const el = document.createElement('div'); el.className = 'mod'; el.textContent = m.name; $('modules').appendChild(el); modEls[m.key] = el; });
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const pad = (n) => String(n).padStart(3, '0');

function buildRows() {
  $('rows-left').innerHTML = ''; $('rows-right').innerHTML = '';
  S.sensors = [];
  for (const k of Object.keys(LAYOUT)) {
    const sd = S.data.sensors.find((s) => s.key === k);
    if (!sd) continue;
    const el = document.createElement('div');
    el.className = 'row' + (sd.modeled ? '' : ' const');
    el.innerHTML = `<span class="k">${esc(sd.code)}</span><span class="n">${esc(sd.name)}</span><span class="v"></span><span class="z"></span>`;
    el.title = `${sd.code}: ${sd.name}${sd.unit ? ` (${sd.unit})` : ''}${sd.modeled ? '' : '. Constant in this dataset, not used by the model.'}`;
    el.addEventListener('mouseenter', () => { S.hovered = k; });
    el.addEventListener('mouseleave', () => { if (S.hovered === k) S.hovered = null; });
    el.addEventListener('click', () => select(k));
    (LAYOUT[k].side === 'L' ? $('rows-left') : $('rows-right')).appendChild(el);
    S.sensors.push({ ...sd, zs: sd.z, el, vEl: el.querySelector('.v'), zEl: el.querySelector('.z'), v: 0, zNow: 0 });
    markers[k].group.visible = true;
  }
}

function pushEvent(cycle, text, color) {
  const box = $('events');
  const el = document.createElement('div');
  el.className = 'ev'; el.style.setProperty('--c', color);
  el.innerHTML = `<b>C${cycle}</b><span>${esc(text)}</span>`;
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
  const yR = (v) => TL.t + h - (v / 130) * h, yH = (v) => TL.t + h - ((v - hMin) / (hMax - hMin)) * h;
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
  if (idx + 1 < MIN_CYCLES) return 'INSUFFICIENT';
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
const home = { pos: new T.Vector3(), target: HOME_TARGET.clone() };
function homeDistance() {
  const twin = S.mode === 'twin';
  const side = twin && S.panels && W > 720 ? 2 * (W > 980 ? 256 : 196) : 0;
  const usableW = (W - side) / W * 0.92;
  const usableH = twin ? (H - 64 - 132 - 30) / H : 0.86;
  const vt = Math.tan(T.MathUtils.degToRad(camera.fov / 2)), ht = vt * camera.aspect;
  // Half-extents to keep in view: the twin can crop the plume side slightly, the hero shows the whole engine.
  return Math.max((twin ? 4.5 : 5.9) / (ht * usableW), (twin ? 2.8 : 3.2) / (vt * usableH), 7);
}
function setHome() { home.pos.copy(home.target).addScaledVector(HOME_DIR, homeDistance()); }
function flyTo(pos, target, secs, ease = 'power2.inOut') {
  gsap.to(camera.position, { x: pos.x, y: pos.y, z: pos.z, duration: D(secs), ease, overwrite: true });
  gsap.to(controls.target, { x: target.x, y: target.y, z: target.z, duration: D(secs), ease, overwrite: true });
}
function flyHome(secs = 0.8) { setHome(); flyTo(home.pos, home.target, secs); }
function resize() {
  const r = app.getBoundingClientRect(); W = Math.max(1, r.width); H = Math.max(1, r.height);
  renderer.setSize(W, H, false);
  camera.aspect = W / H;
  // Shift the engine up so it centres in the space between the top bar and the timeline.
  if (S.mode === 'twin' && W > 720) camera.setViewOffset(W, H, 0, 34, W, H); else camera.clearViewOffset();
  camera.updateProjectionMatrix();
  flowMat.uniforms.uPix.value = H * renderer.getPixelRatio() * 0.9;
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
    const drift = best.modeled ? `${best.zNow >= 0 ? '+' : ''}${best.zNow.toFixed(1)} sigma from baseline` : 'constant in this dataset';
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
  const modLevel = Object.fromEntries(MODULES.map((m) => [m.key, -1]));
  let t50 = 0;
  for (const s of S.sensors) {
    s.v = interp(s.values, S.t);
    s.zNow = s.modeled ? interp(s.zs, S.t) : 0;
    if (s.modeled) {
      const lv = level(s.zNow), mod = LAYOUT[s.key].mod;
      if (lv >= 0 && (modLevel[mod] < 0 || lv < modLevel[mod])) modLevel[mod] = lv;
      if (s.key === 'sensor_4') t50 = s.zNow;
    }
  }
  S.modLevel = modLevel;
  // Module tint: a degrading module takes on its status colour; healthy metal stays neutral.
  const tint = (mat, mod) => {
    const lv = modLevel[mod];
    if (lv < 0) { mat.emissive.setRGB(0, 0, 0); return; }
    mat.emissive.set(LEVELS[lv].color); mat.emissiveIntensity = [0.32, 0.2, 0.1][lv];
  };
  tint(M.fan, 'fan'); tint(M.lpc, 'lpc'); tint(M.hpc, 'hpc');
  // Hot section glows with EGT (T50) drift; a gentle flicker reads as combustion, not alarm.
  const heat = clamp(t50 / 4, 0, 1);
  M.comb.emissiveIntensity = 0.45 + heat * 0.35 + (REDUCED ? 0 : 0.04 * Math.sin(tsec * 13));
  M.hpt.emissiveIntensity = 0.22 + heat * 0.45;
  M.lpt.emissiveIntensity = 0.08 + heat * 0.3;
  combLight.intensity = 2.2 + heat * 2;
  flowMat.uniforms.uHeat.value = heat;

  for (const s of S.sensors) {
    const m = markers[s.key];
    const color = s.modeled ? levelColor(s.zNow) : '#4a525c';
    m.dot.material.color.set(color === C.text3 ? '#9aa3ad' : color);
    m.dot.scale.setScalar(s.key === S.selected || s.key === S.hovered ? 1.6 : 1);
  }
  if (!d || S.mode !== 'twin' || S.frame % 2) return;

  const idx = clamp(Math.round(S.t), 0, S.N - 1);
  const state = stateAt(idx);
  $('cycle').innerHTML = `Cycle ${d.cycles[idx]} <em>of ${d.cycles[S.N - 1]}</em>`;
  app.style.setProperty('--state', STATE[state].color);
  $('state').textContent = STATE[state].label;
  const band = d.band ? d.band[idx] : null;
  const rul = d.rul ? Math.round(interp(d.rul, S.t)) : null;
  $('band').innerHTML = [rul != null ? `RUL ${rul} cycles` : null, band != null ? `${BAND_TXT[band]} ${Math.round(d.prob[idx] * 100)}%` : null]
    .filter(Boolean).map((t) => `<span>${esc(t)}</span>`).join('');
  for (const s of S.sensors) {
    s.vEl.textContent = s.v.toFixed(s.decimals);
    if (s.modeled) { s.zEl.textContent = `${s.zNow >= 0 ? '+' : ''}${s.zNow.toFixed(1)}`; s.el.style.setProperty('--c', levelColor(s.zNow)); }
    else s.zEl.textContent = 'const';
  }
  for (const m of MODULES) {
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
    const left = LAYOUT[s.key].side === 'L';
    const ax = (left ? rr.right : rr.left) - r0.left, ay = rr.top + rr.height / 2 - r0.top, ex = ax + (left ? 14 : -14);
    lx.strokeStyle = active ? C.accent : LEVELS[Math.max(lv, 0)].color;
    lx.globalAlpha = active ? 1 : 0.65; lx.lineWidth = active ? 1.5 : 1;
    lx.beginPath(); lx.moveTo(ax, ay); lx.lineTo(ex, ay); lx.lineTo(m.screen.x, m.screen.y); lx.stroke();
  }
  lx.globalAlpha = 1;
  if (S.explode > 0.05) {
    lx.font = '500 11px "IBM Plex Sans", sans-serif'; lx.textAlign = 'center'; lx.globalAlpha = S.explode;
    const labelX = { fan: -3.9, lpc: -2.8, hpc: -1.1, comb: 0.45, hpt: 1.1, lpt: 2.2, noz: 3.7 };
    for (const m of MODULES) {
      if (!(m.key in labelX)) continue;
      v.set(labelX[m.key] + mods[m.key].position.x, -2.35, 0).project(camera);
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
  S.data = p; S.dataId = p.id; S.N = p.cycles.length;
  S.t = S.N - 1; S.playing = false; S.lastIdx = -1; S.critSeen.clear(); S.selected = null;
  Object.values(markers).forEach((m) => { m.group.visible = false; });
  buildRows(); refreshSelection(); $('events').innerHTML = '';
  $('unit-name').textContent = `Engine ${pad(p.unit)}`;
  $('unit-meta').textContent = [p.source, p.model ? `model ${p.model}` : null].filter(Boolean).join(', ');
  syncPlay();
  if (first) intro();
}
function intro() {
  resize();
  // Arrive from slightly further out: the motion says "this is the engine you selected".
  camera.position.copy(home.target).addScaledVector(HOME_DIR, homeDistance() * 1.3);
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
  for (const m of MODULES) {
    const g = mods[m.key];
    g.position.x = m.explode * S.explode;
    if (m.key === 'byp') g.position.y = S.explode * 2.8;
  }
  flowMat.uniforms.uFade.value = 1 - S.explode;
  if (!REDUCED) {
    lpRotors.forEach((r) => { r.rotation.x += dt * 2.2; });
    hpRotors.forEach((r) => { r.rotation.x += dt * 4.4; });
    flowMat.uniforms.uTime.value = tsec;
  }
  controls.autoRotate = S.rotate && !REDUCED;
  controls.update(dt);
  applyState(tsec);
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
    if (!S.started) { S.started = true; intro(); }
    return;
  }
  const p = args.payload;
  if (p && p.id !== S.dataId) loadPayload(p);
}
window.addEventListener('message', (e) => { const m = e.data; if (m && m.type === 'streamlit:render') onRender(m.args || {}); });

resize();
setHome();
camera.position.copy(home.pos);
requestAnimationFrame(frame);
Bridge.ready();
if (!IN_ST) onRender({ mode: new URLSearchParams(location.search).get('mode') || 'hero', height: window.innerHeight });
// Debug handle for the browser console (read-only inspection).
window.AS_DEBUG = { T, scene, camera, controls, S, M };
