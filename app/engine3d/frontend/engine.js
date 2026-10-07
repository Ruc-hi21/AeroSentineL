/* AeroSentinel Digital Twin — procedural turbofan, live sensor HUD and life replay.
 *
 * Runs inside a Streamlit custom component iframe. Streamlit sends `streamlit:render`
 * messages whose args hold {mode, height, payload}; the payload is one engine unit's
 * cycle-by-cycle history built by app/engine3d/__init__.py. Clicking a sensor sends
 * {sensor, unit} back to Python.
 */
import * as T from './vendor/three-bundle.js';

const $ = (id) => document.getElementById(id);
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const lerp = (a, b, t) => a + (b - a) * t;
const ease = (t) => 1 - Math.pow(1 - clamp(t, 0, 1), 3);
const easeInOut = (t) => { t = clamp(t, 0, 1); return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; };
const REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/* ------------------------------------------------------------------ Streamlit bridge */
const IN_ST = window.parent !== window;
const post = (type, extra = {}) => IN_ST && window.parent.postMessage({ isStreamlitMessage: true, type, ...extra }, '*');
const Bridge = {
  ready: () => post('streamlit:componentReady', { apiVersion: 1 }),
  height: (h) => post('streamlit:setFrameHeight', { height: h }),
  value: (v) => post('streamlit:setComponentValue', { value: v, dataType: 'json' }),
};

/* ------------------------------------------------------------------ severity palette */
const BAND_CSS = ['#19f5a0', '#ffd23f', '#ff8a1f', '#ff2e4d'];
const BAND_TXT = ['NORMAL', 'AT RISK', 'HIGH RISK', 'FAILURE LIKELY'];
const STOPS = [[0, '#19f5a0'], [0.34, '#ffd23f'], [0.67, '#ff8a1f'], [1, '#ff2e4d']].map(([s, c]) => [s, new T.Color(c)]);
function sevColor(s, out = new T.Color()) {
  s = clamp(s, 0, 1);
  for (let i = 1; i < STOPS.length; i++) {
    if (s <= STOPS[i][0]) {
      const [s0, c0] = STOPS[i - 1], [s1, c1] = STOPS[i];
      return out.copy(c0).lerp(c1, (s - s0) / (s1 - s0));
    }
  }
  return out.copy(STOPS[STOPS.length - 1][1]);
}
const sevCss = (s) => '#' + sevColor(s).getHexString();
// Directed z-score (sigma from the healthy baseline, + = degrading) -> 0..1 severity.
// Calibrated on FD001 training engines: healthy ~0σ, RUL 30-60 ~1.5σ, last 15 cycles ~3-4σ.
// Bands: < 1.6σ nominal, < 2.4σ elevated, < 3.2σ warning, >= 3.2σ critical.
const zSev = (z) => clamp((z - 0.8) / 3.2, 0, 1);
const sevWord = (s) => (s < 0.25 ? 'NOMINAL' : s < 0.5 ? 'ELEVATED' : s < 0.75 ? 'WARNING' : 'CRITICAL');

/* ------------------------------------------------------------------ engine layout */
// Engine axis = world X. Inlet at -5, exhaust plug tip at +4.5. Radii in world units.
const MODULES = [
  { key: 'fan', name: 'FAN', explode: -2.6 },
  { key: 'lpc', name: 'LPC', explode: -1.6 },
  { key: 'hpc', name: 'HPC', explode: -0.55 },
  { key: 'comb', name: 'COMBUSTOR', explode: 0.45 },
  { key: 'hpt', name: 'HPT', explode: 1.25 },
  { key: 'lpt', name: 'LPT', explode: 2.15 },
  { key: 'noz', name: 'NOZZLE', explode: 3.2 },
  { key: 'byp', name: 'BYPASS', explode: 0 },
];
const MOD_SHORT = { fan: 'FAN', lpc: 'LPC', hpc: 'HPC', comb: 'COMB', hpt: 'HPT', lpt: 'LPT', noz: 'NOZ', byp: 'BYPASS' };
// Where each C-MAPSS sensor physically sits, which module it reports on and which HUD column shows it.
const LAYOUT = {
  sensor_1: { mod: 'fan', pos: [-4.7, 1.5, 0.6], side: 'L' },
  sensor_5: { mod: 'fan', pos: [-4.7, -1.4, 0.7], side: 'L' },
  sensor_2: { mod: 'lpc', pos: [-2.45, 0.95, 0.35], side: 'L' },
  sensor_6: { mod: 'byp', pos: [-1.6, 1.72, 0.65], side: 'L' },
  sensor_17: { mod: 'hpc', pos: [-1.2, 1.08, 0.35], side: 'L' },
  sensor_11: { mod: 'hpc', pos: [-0.65, 0.55, 0.6], side: 'L' },
  sensor_3: { mod: 'hpc', pos: [-0.25, 0.8, 0.25], side: 'L' },
  sensor_7: { mod: 'hpc', pos: [-0.25, -0.72, 0.4], side: 'L' },
  sensor_4: { mod: 'lpt', pos: [2.75, 1.05, 0.4], side: 'L' },
  sensor_10: { mod: 'noz', pos: [3.55, 0.85, 0.4], side: 'L' },
  sensor_18: { mod: 'fan', pos: [-4.45, 0.1, 0.05], side: 'R' },
  sensor_19: { mod: 'fan', pos: [-4.25, -0.18, 0.15], side: 'R' },
  sensor_8: { mod: 'fan', pos: [-3.95, 0.35, 0.3], side: 'R' },
  sensor_13: { mod: 'fan', pos: [-3.6, -0.45, 0.35], side: 'R' },
  sensor_15: { mod: 'byp', pos: [-0.4, -1.72, 0.55], side: 'R' },
  sensor_9: { mod: 'hpc', pos: [-1.1, 0.2, 0.22], side: 'R' },
  sensor_14: { mod: 'hpc', pos: [-1.6, -0.3, 0.32], side: 'R' },
  sensor_12: { mod: 'comb', pos: [0.45, 1.0, 0.3], side: 'R' },
  sensor_16: { mod: 'comb', pos: [0.45, -0.95, 0.3], side: 'R' },
  sensor_20: { mod: 'hpt', pos: [1.15, 0.95, 0.3], side: 'R' },
  sensor_21: { mod: 'lpt', pos: [2.1, 1.2, 0.3], side: 'R' },
};

/* ------------------------------------------------------------------ state */
const S = {
  mode: 'twin', height: 820, data: null, dataId: null, N: 0,
  t: 0, playing: false, speed: 1, lastIdx: -1, maxBand: 0, critSeen: new Set(), finished: false,
  selected: null, hovered: null, explode: 0, explodeTarget: 0, cinema: false, orbit: true,
  introStart: -1, introFull: true, introCardsShown: false, introPlayQueued: false, introScanDone: false,
  scanStart: -100, lastInteract: 0, frame: 0, sensors: [], modSev: {}, overall: 0, band: 0,
  camTween: null, home: { pos: new T.Vector3(), target: new T.Vector3(-0.2, 0, 0) },
};

/* ------------------------------------------------------------------ renderer & scene */
const app = $('app');
const canvas = $('gl');
const renderer = new T.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
renderer.toneMapping = T.ACESFilmicToneMapping;
renderer.toneMappingExposure = 0.95;

const scene = new T.Scene();
scene.background = makeBackgroundTexture();
scene.fog = new T.FogExp2(0x030916, 0.012);
const pmrem = new T.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new T.RoomEnvironment(), 0.04).texture;
scene.environmentIntensity = 0.75;

const camera = new T.PerspectiveCamera(36, 1, 0.1, 400);
camera.position.set(9, 4.5, 15);
const controls = new T.OrbitControls(camera, canvas);
controls.enableDamping = true;
controls.dampingFactor = 0.07;
controls.enablePan = false;
controls.minDistance = 4;
controls.maxDistance = 30;
controls.minPolarAngle = 0.25;
controls.maxPolarAngle = Math.PI * 0.62;
controls.autoRotate = true;
controls.autoRotateSpeed = 0.55;
controls.target.copy(S.home.target);
controls.addEventListener('start', () => { S.lastInteract = performance.now(); S.camTween = null; });

const composer = new T.EffectComposer(renderer);
composer.addPass(new T.RenderPass(scene, camera));
const bloom = new T.UnrealBloomPass(new T.Vector2(256, 256), 0.55, 0.3, 0.82);
composer.addPass(bloom);
composer.addPass(new T.OutputPass());

// Lights: cool key, cyan rim, warm combustor glow, red alert.
scene.add(new T.HemisphereLight(0x6fa8ff, 0x0a0f1e, 0.55));
const key = new T.DirectionalLight(0xdfeaff, 1.6); key.position.set(4, 8, 7); scene.add(key);
const rim = new T.DirectionalLight(0x00e5ff, 2.2); rim.position.set(-6, 3, -8); scene.add(rim);
const combLight = new T.PointLight(0xff7a2a, 6, 6, 1.6); combLight.position.set(0.45, 0, 0); scene.add(combLight);
const alertLight = new T.PointLight(0xff2e4d, 0, 14, 1.4); alertLight.position.set(0, 3, 3); scene.add(alertLight);

/* ------------------------------------------------------------------ textures */
function makeBackgroundTexture() {
  const c = document.createElement('canvas'); c.width = 1024; c.height = 640;
  const g = c.getContext('2d');
  const grd = g.createRadialGradient(512, 280, 40, 512, 320, 760);
  grd.addColorStop(0, '#0d2350'); grd.addColorStop(0.45, '#071330'); grd.addColorStop(1, '#02050d');
  g.fillStyle = grd; g.fillRect(0, 0, 1024, 640);
  const neb = g.createRadialGradient(780, 160, 10, 780, 160, 360);
  neb.addColorStop(0, 'rgba(124,77,255,0.16)'); neb.addColorStop(1, 'rgba(124,77,255,0)');
  g.fillStyle = neb; g.fillRect(0, 0, 1024, 640);
  const neb2 = g.createRadialGradient(170, 520, 10, 170, 520, 380);
  neb2.addColorStop(0, 'rgba(0,229,255,0.10)'); neb2.addColorStop(1, 'rgba(0,229,255,0)');
  g.fillStyle = neb2; g.fillRect(0, 0, 1024, 640);
  const t = new T.CanvasTexture(c); t.colorSpace = T.SRGBColorSpace; return t;
}
function makeHaloTexture() {
  const c = document.createElement('canvas'); c.width = c.height = 128;
  const g = c.getContext('2d');
  const grd = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  grd.addColorStop(0, 'rgba(255,255,255,1)'); grd.addColorStop(0.18, 'rgba(255,255,255,0.85)');
  grd.addColorStop(0.42, 'rgba(255,255,255,0.18)'); grd.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = grd; g.fillRect(0, 0, 128, 128);
  g.strokeStyle = 'rgba(255,255,255,0.9)'; g.lineWidth = 3; g.beginPath(); g.arc(64, 64, 40, 0, Math.PI * 2); g.stroke();
  return new T.CanvasTexture(c);
}
function makeDiscTexture(variant) {
  const c = document.createElement('canvas'); c.width = c.height = 1024;
  const g = c.getContext('2d'); g.translate(512, 512);
  g.strokeStyle = '#fff'; g.fillStyle = '#fff';
  if (variant === 0) {
    [[500, 2, 0.9], [470, 1, 0.35], [380, 1.5, 0.5], [300, 1, 0.25], [190, 2, 0.6], [120, 1, 0.3]].forEach(([r, w, a]) => {
      g.globalAlpha = a; g.lineWidth = w; g.beginPath(); g.arc(0, 0, r, 0, Math.PI * 2); g.stroke();
    });
    for (let i = 0; i < 360; i += 2) {
      const a = (i * Math.PI) / 180, long = i % 30 === 0, mid = i % 10 === 0;
      g.globalAlpha = long ? 0.95 : mid ? 0.6 : 0.3; g.lineWidth = long ? 3 : 1.4;
      const r0 = long ? 470 : mid ? 480 : 488;
      g.beginPath(); g.moveTo(Math.cos(a) * r0, Math.sin(a) * r0); g.lineTo(Math.cos(a) * 500, Math.sin(a) * 500); g.stroke();
    }
    g.font = '600 22px Rajdhani, sans-serif'; g.textAlign = 'center'; g.globalAlpha = 0.8;
    for (let i = 0; i < 360; i += 30) {
      const a = (i * Math.PI) / 180; g.save(); g.rotate(a + Math.PI / 2); g.fillText(String(i).padStart(3, '0'), 0, -438); g.restore();
    }
  } else {
    g.lineCap = 'round';
    [[420, 0.2, 1.3, 10, 0.8], [420, 2.4, 3.0, 10, 0.8], [420, 4.1, 5.6, 10, 0.8], [340, 0.6, 2.2, 4, 0.55], [340, 3.3, 5.9, 4, 0.55], [250, 1.0, 1.6, 14, 0.45], [250, 4.0, 4.6, 14, 0.45]].forEach(([r, a0, a1, w, a]) => {
      g.globalAlpha = a; g.lineWidth = w; g.beginPath(); g.arc(0, 0, r, a0, a1); g.stroke();
    });
    g.globalAlpha = 0.5; g.font = '700 20px Orbitron, sans-serif'; g.textAlign = 'center';
    g.fillText('AEROSENTINEL · DIGITAL TWIN · TF-01', 0, -372);
  }
  const t = new T.CanvasTexture(c); t.colorSpace = T.SRGBColorSpace; return t;
}
const HALO = makeHaloTexture();

/* ------------------------------------------------------------------ materials */
// Adds a view-dependent rim glow to a standard material; rim colour/strength stay live-editable.
function withRim(mat, color, power = 2.5, strength = 0.4) {
  mat.userData.rim = { uRimColor: { value: new T.Color(color) }, uRimPow: { value: power }, uRimStr: { value: strength } };
  mat.onBeforeCompile = (sh) => {
    Object.assign(sh.uniforms, mat.userData.rim);
    sh.fragmentShader = sh.fragmentShader
      .replace('#include <common>', '#include <common>\nuniform vec3 uRimColor; uniform float uRimPow; uniform float uRimStr;')
      .replace('#include <emissivemap_fragment>', '#include <emissivemap_fragment>\n float rimF = pow(1.0 - abs(dot(normal, normalize(vViewPosition))), uRimPow);\n totalEmissiveRadiance += uRimColor * rimF * uRimStr;');
  };
  return mat;
}
const metal = (color, rough = 0.32, metalness = 0.88) => new T.MeshStandardMaterial({ color, metalness, roughness: rough });

const MAT = {
  fanBlade: withRim(metal(0xb7c9e2, 0.2, 0.92), 0x00e5ff, 2.2, 0.55),
  spinner: withRim(metal(0xd8e4f5, 0.15, 1.0), 0x00e5ff, 3.0, 0.6),
  disk: metal(0x4a5a74, 0.38, 0.85),
  lpc: withRim(metal(0x9fb3cf, 0.28), 0x00e5ff, 2.4, 0.35),
  hpc: withRim(metal(0xa9b9d2, 0.26), 0x00e5ff, 2.4, 0.35),
  stator: metal(0x6d7f9c, 0.4, 0.8),
  hpt: withRim(new T.MeshStandardMaterial({ color: 0x8b6e60, metalness: 0.8, roughness: 0.35, emissive: 0xff5a1a, emissiveIntensity: 0.5 }), 0xffa040, 2.0, 0.6),
  lpt: withRim(new T.MeshStandardMaterial({ color: 0x8d7f78, metalness: 0.82, roughness: 0.33, emissive: 0xff6a20, emissiveIntensity: 0.22 }), 0xffa040, 2.2, 0.4),
  plug: withRim(metal(0x7f8ea8, 0.3), 0x00e5ff, 2.6, 0.4),
  shaft: metal(0x56627a, 0.3, 0.9),
};
[MAT.spinner, MAT.disk, MAT.plug, MAT.shaft].forEach((m) => { m.side = T.DoubleSide; });

function holoMaterial(color, opacity = 1) {
  return new T.ShaderMaterial({
    transparent: true, depthWrite: false, side: T.DoubleSide, blending: T.AdditiveBlending,
    uniforms: { uColor: { value: new T.Color(color) }, uTime: { value: 0 }, uOpacity: { value: opacity }, uAlert: { value: 0 } },
    vertexShader: `varying vec3 vN; varying vec3 vV; varying vec3 vP;
      void main(){ vec4 mv = modelViewMatrix * vec4(position,1.0); vN = normalize(normalMatrix*normal); vV = normalize(-mv.xyz); vP = position; gl_Position = projectionMatrix*mv; }`,
    fragmentShader: `uniform vec3 uColor; uniform float uTime; uniform float uOpacity; uniform float uAlert;
      varying vec3 vN; varying vec3 vV; varying vec3 vP;
      void main(){
        float f = pow(1.0 - abs(dot(normalize(vN), normalize(vV))), 2.0);
        float bands = smoothstep(0.93, 1.0, 0.5 + 0.5*sin(vP.y*24.0 - uTime*2.4));
        float sweep = 1.0 - smoothstep(0.0, 0.35, abs(mod(vP.y - uTime*2.2, 14.0) - 7.0));
        vec3 c = mix(uColor, vec3(1.0,0.18,0.3), uAlert);
        float a = (0.012 + f*0.42 + bands*0.035 + sweep*0.1) * uOpacity;
        gl_FragColor = vec4(c*(0.35 + f*1.15 + bands*0.5 + sweep*0.9), a);
      }`,
  });
}

/* ------------------------------------------------------------------ geometry helpers */
const V2 = (r, x) => new T.Vector2(r, x);
// Lathe a (radius, axial) profile around the engine axis (world X).
function lathe(points, mat, segs = 72, start = 0, len = Math.PI * 2) {
  const m = new T.Mesh(new T.LatheGeometry(points, segs, start, len), mat);
  m.rotation.z = -Math.PI / 2;
  return m;
}
// A twisted, tapered, cambered blade spanning radius hub..tip along +Y, chord along X.
function bladeGeometry({ hub, tip, chordHub, chordTip, thick, twistHub, twistTip, sweep = 0 }) {
  const g = new T.BoxGeometry(1, 1, 1, 2, 10, 1);
  const p = g.attributes.position;
  for (let i = 0; i < p.count; i++) {
    const x = p.getX(i), y = p.getY(i), z = p.getZ(i);
    const t = y + 0.5;
    const r = hub + (tip - hub) * t;
    const chord = chordHub + (chordTip - chordHub) * t;
    const cx = x * chord;
    let cz = z * thick * (1 - 1.4 * x * x);
    cz += (0.25 - x * x) * chord * 0.22;
    const tw = twistHub + (twistTip - twistHub) * t;
    const c = Math.cos(tw), s = Math.sin(tw);
    p.setXYZ(i, cx * c - cz * s + sweep * t * t, r, cx * s + cz * c);
  }
  g.computeVertexNormals();
  return g;
}
// Ring of `count` blades around the axis, as one instanced draw call.
function bladeRing(geo, mat, count, x, phase = 0) {
  const mesh = new T.InstancedMesh(geo, mat, count);
  const m = new T.Matrix4();
  for (let i = 0; i < count; i++) {
    m.makeRotationX(phase + (i / count) * Math.PI * 2);
    mesh.setMatrixAt(i, m);
  }
  mesh.position.x = x;
  return mesh;
}
function axialCylinder(r, x0, x1, mat, segs = 48) {
  const m = new T.Mesh(new T.CylinderGeometry(r, r, x1 - x0, segs, 1), mat);
  m.rotation.z = Math.PI / 2; m.position.x = (x0 + x1) / 2;
  return m;
}
function wireRings(profile, color, opacity, rings = 10, spokes = 24, start = 0, len = Math.PI * 2) {
  // Latitude rings + longitudinal lines over a (r, x) profile: the hologram wireframe.
  const pts = [];
  const sample = (u) => {
    const f = u * (profile.length - 1), i = Math.min(Math.floor(f), profile.length - 2), t = f - i;
    return [lerp(profile[i].x, profile[i + 1].x, t), lerp(profile[i].y, profile[i + 1].y, t)];
  };
  for (let k = 0; k <= rings; k++) {
    const [r, x] = sample(k / rings);
    for (let j = 0; j < 64; j++) {
      const a0 = start + (j / 64) * len, a1 = start + ((j + 1) / 64) * len;
      pts.push(x, r * Math.cos(a0), r * Math.sin(a0), x, r * Math.cos(a1), r * Math.sin(a1));
    }
  }
  for (let j = 0; j <= spokes; j++) {
    const a = start + (j / spokes) * len;
    if (len < Math.PI * 2 - 0.01 || j < spokes) {
      for (let k = 0; k < 40; k++) {
        const [r0, x0] = sample(k / 40), [r1, x1] = sample((k + 1) / 40);
        pts.push(x0, r0 * Math.cos(a), r0 * Math.sin(a), x1, r1 * Math.cos(a), r1 * Math.sin(a));
      }
    }
  }
  const g = new T.BufferGeometry();
  g.setAttribute('position', new T.Float32BufferAttribute(pts, 3));
  return new T.LineSegments(g, new T.LineBasicMaterial({ color, transparent: true, opacity, blending: T.AdditiveBlending, depthWrite: false }));
}

/* ------------------------------------------------------------------ build the engine */
const engine = new T.Group(); scene.add(engine);
const mods = {};
MODULES.forEach((m) => { const g = new T.Group(); g.userData = m; mods[m.key] = g; engine.add(g); });
const lpRotors = [], hpRotors = [];

// --- nacelle (hologram shell with wireframe) — belongs to the bypass module so it lifts in exploded view
const nacelleProfile = [V2(2.12, -4.95), V2(2.13, -4.3), V2(2.15, -3.4), V2(2.14, -1.0), V2(2.08, 0.6), V2(1.98, 1.6),
  V2(2.04, 1.68), V2(2.2, 1.55), V2(2.42, 0.2), V2(2.53, -1.6), V2(2.5, -3.3), V2(2.4, -4.5), V2(2.28, -4.98), V2(2.12, -4.95)];
const nacelleMat = holoMaterial(0x00e5ff, 1);
mods.byp.add(lathe(nacelleProfile, nacelleMat, 96));
const nacelleWire = wireRings([V2(2.3, -4.98), V2(2.45, -4.0), V2(2.53, -1.6), V2(2.42, 0.2), V2(2.16, 1.6)], 0x00e5ff, 0.13, 12, 32);
mods.byp.add(nacelleWire);
// fan exit guide vanes in the bypass duct
mods.byp.add(bladeRing(bladeGeometry({ hub: 1.2, tip: 2.12, chordHub: 0.22, chordTip: 0.26, thick: 0.02, twistHub: 0.25, twistTip: 0.2 }), MAT.stator, 44, -3.05));

// --- core cowl, cut away over the upper-front quarter so the compressor is visible
const coreProfile = [V2(1.08, -3.3), V2(1.13, -3.32), V2(1.24, -2.6), V2(1.31, -1.0), V2(1.31, 0.8), V2(1.27, 2.0), V2(1.2, 2.9), V2(1.0, 3.85),
  V2(0.96, 3.84), V2(1.15, 2.9), V2(1.22, 2.0), V2(1.26, 0.8), V2(1.26, -1.0), V2(1.19, -2.6), V2(1.08, -3.3)];
const coreMat = new T.MeshPhysicalMaterial({ color: 0x14284a, metalness: 0.6, roughness: 0.35, transparent: true, opacity: 0.55, side: T.DoubleSide, depthWrite: false, clearcoat: 0.6 });
const coreShell = lathe(coreProfile, coreMat, 80, 0, Math.PI * 1.5);
mods.byp.add(coreShell);
const coreHolo = lathe(coreProfile, holoMaterial(0x3d8bff, 0.35), 80, 0, Math.PI * 1.5);
mods.byp.add(coreHolo);
mods.byp.add(wireRings([V2(1.13, -3.32), V2(1.31, -1.0), V2(1.31, 0.8), V2(1.2, 2.9), V2(1.0, 3.85)], 0x3d8bff, 0.18, 8, 6, 0, Math.PI * 1.5));

// --- FAN: spinner, 22 wide-chord blades, hub
const spinnerPts = []; for (let i = 0; i <= 24; i++) { const t = i / 24; spinnerPts.push(V2(0.52 * Math.pow(Math.sin((t * Math.PI) / 2), 0.75), -4.75 + t * 0.85)); }
const fanRotor = new T.Group(); mods.fan.add(fanRotor); lpRotors.push(fanRotor);
fanRotor.add(lathe(spinnerPts, MAT.spinner, 64));
fanRotor.add(bladeRing(bladeGeometry({ hub: 0.48, tip: 2.08, chordHub: 0.42, chordTip: 0.66, thick: 0.05, twistHub: 1.05, twistTip: 0.32, sweep: -0.12 }), MAT.fanBlade, 22, -3.9));
fanRotor.add(axialCylinder(0.53, -3.95, -3.45, MAT.disk));
// spinner spiral marking (a classic touch)
{
  const pts = []; for (let i = 0; i <= 60; i++) { const t = i / 60, x = -4.72 + t * 0.78, r = 0.52 * Math.pow(Math.sin((t * Math.PI) / 2), 0.75) + 0.004, a = t * Math.PI * 1.6; pts.push(new T.Vector3(x, r * Math.cos(a), r * Math.sin(a))); }
  fanRotor.add(new T.Line(new T.BufferGeometry().setFromPoints(pts), new T.LineBasicMaterial({ color: 0xffffff })));
}

// --- LPC (booster): 3 stages on the LP spool
const lpcRotor = new T.Group(); mods.lpc.add(lpcRotor); lpRotors.push(lpcRotor);
[-3.05, -2.8, -2.55].forEach((x, i) => {
  lpcRotor.add(bladeRing(bladeGeometry({ hub: 0.55, tip: 1.0 - i * 0.02, chordHub: 0.12, chordTip: 0.14, thick: 0.02, twistHub: 0.8, twistTip: 0.5 }), MAT.lpc, 30, x, i * 0.1));
  mods.lpc.add(bladeRing(bladeGeometry({ hub: 0.56, tip: 1.0 - i * 0.02, chordHub: 0.08, chordTip: 0.09, thick: 0.015, twistHub: -0.5, twistTip: -0.4 }), MAT.stator, 36, x + 0.12));
});
lpcRotor.add(axialCylinder(0.55, -3.15, -2.45, MAT.disk));

// --- HPC: 9 stages on the HP spool (the FD001 fault module)
const hpcRotor = new T.Group(); mods.hpc.add(hpcRotor); hpRotors.push(hpcRotor);
for (let i = 0; i < 9; i++) {
  const x = -2.15 + i * 0.235, hub = 0.56 + i * 0.007, tip = 0.96 - i * 0.026;
  hpcRotor.add(bladeRing(bladeGeometry({ hub, tip, chordHub: 0.1, chordTip: 0.1, thick: 0.016, twistHub: 0.75, twistTip: 0.55 }), MAT.hpc, 34 + i * 3, x, i * 0.2));
  mods.hpc.add(bladeRing(bladeGeometry({ hub: hub + 0.01, tip: tip + 0.01, chordHub: 0.06, chordTip: 0.06, thick: 0.012, twistHub: -0.5, twistTip: -0.4 }), MAT.stator, 40 + i * 3, x + 0.11));
}
hpcRotor.add(lathe([V2(0.5, -2.25), V2(0.57, -2.2), V2(0.63, -0.1), V2(0.5, -0.05)], MAT.disk, 48));

// --- COMBUSTOR: annular can with an animated flame shader + fuel nozzles
const combMat = new T.ShaderMaterial({
  transparent: true, depthWrite: false, blending: T.AdditiveBlending, side: T.DoubleSide,
  uniforms: { uTime: { value: 0 }, uHeat: { value: 0.2 }, uPower: { value: 1 } },
  vertexShader: `varying vec3 vP; varying vec3 vN; varying vec3 vV;
    void main(){ vP = position; vec4 mv = modelViewMatrix*vec4(position,1.0); vN = normalize(normalMatrix*normal); vV = normalize(-mv.xyz); gl_Position = projectionMatrix*mv; }`,
  fragmentShader: `uniform float uTime; uniform float uHeat; uniform float uPower; varying vec3 vP; varying vec3 vN; varying vec3 vV;
    void main(){
      float ang = atan(vP.z, vP.x);
      float n = 0.5 + 0.5*sin(ang*18.0 + uTime*7.0) * sin(vP.y*20.0 - uTime*11.0 + ang*3.0);
      float holes = smoothstep(0.75, 1.0, 0.5 + 0.5*sin(ang*36.0)*sin(vP.y*42.0));
      float f = pow(1.0 - abs(dot(normalize(vN), normalize(vV))), 1.5);
      vec3 hot = mix(vec3(1.0,0.45,0.08), vec3(1.0,0.85,0.55), n*0.6 + uHeat*0.4);
      hot = mix(hot, vec3(1.0,0.18,0.12), uHeat*0.45);
      float a = (0.25 + n*0.45 + holes*0.5 + f*0.4) * uPower;
      gl_FragColor = vec4(hot*(0.9 + n*1.0 + holes*1.5)*uPower, clamp(a*0.85,0.0,1.0));
    }`,
});
{
  const pts = []; for (let i = 0; i <= 40; i++) { const a = (i / 40) * Math.PI * 2; pts.push(V2(0.76 + 0.13 * Math.cos(a), 0.45 + 0.36 * Math.sin(a))); }
  mods.comb.add(lathe(pts, combMat, 96));
  const nozzleGeo = new T.SphereGeometry(0.035, 10, 8);
  const nozzleMat = new T.MeshBasicMaterial({ color: new T.Color(3, 1.4, 0.4) });
  for (let i = 0; i < 20; i++) { const a = (i / 20) * Math.PI * 2, n = new T.Mesh(nozzleGeo, nozzleMat); n.position.set(0.08, 0.76 * Math.cos(a), 0.76 * Math.sin(a)); mods.comb.add(n); }
}

// --- HPT (2 stages, red-hot) and LPT (5 stages) on their spools
const hptRotor = new T.Group(); mods.hpt.add(hptRotor); hpRotors.push(hptRotor);
[0.98, 1.24].forEach((x, i) => {
  hptRotor.add(bladeRing(bladeGeometry({ hub: 0.6, tip: 0.86 + i * 0.02, chordHub: 0.12, chordTip: 0.11, thick: 0.03, twistHub: -0.9, twistTip: -0.6 }), MAT.hpt, 40, x));
  mods.hpt.add(bladeRing(bladeGeometry({ hub: 0.6, tip: 0.87 + i * 0.02, chordHub: 0.08, chordTip: 0.08, thick: 0.02, twistHub: 0.7, twistTip: 0.5 }), MAT.stator, 30, x - 0.12));
});
hptRotor.add(axialCylinder(0.6, 0.9, 1.32, MAT.disk));
const lptRotor = new T.Group(); mods.lpt.add(lptRotor); lpRotors.push(lptRotor);
for (let i = 0; i < 5; i++) {
  const x = 1.55 + i * 0.29;
  lptRotor.add(bladeRing(bladeGeometry({ hub: 0.6, tip: 0.9 + i * 0.055, chordHub: 0.13, chordTip: 0.12, thick: 0.025, twistHub: -0.85, twistTip: -0.55 }), MAT.lpt, 46 + i * 4, x, i * 0.13));
  mods.lpt.add(bladeRing(bladeGeometry({ hub: 0.6, tip: 0.92 + i * 0.055, chordHub: 0.08, chordTip: 0.08, thick: 0.018, twistHub: 0.6, twistTip: 0.45 }), MAT.stator, 40 + i * 4, x - 0.13));
}
lptRotor.add(lathe([V2(0.45, 1.4), V2(0.6, 1.45), V2(0.6, 2.85), V2(0.45, 2.9)], MAT.disk, 48));

// --- NOZZLE: exhaust plug, shafts
mods.noz.add(lathe([V2(0.6, 2.85), V2(0.58, 3.2), V2(0.48, 3.7), V2(0.3, 4.15), V2(0.0, 4.55)], MAT.plug, 64));
const lpShaft = axialCylinder(0.12, -3.9, 2.9, MAT.shaft, 24); lpRotors.push(lpShaft); mods.lpc.add(lpShaft);

/* ------------------------------------------------------------------ exhaust plume */
const plumeMat = new T.ShaderMaterial({
  transparent: true, depthWrite: false, blending: T.AdditiveBlending, side: T.DoubleSide,
  uniforms: { uTime: { value: 0 }, uHeat: { value: 0.2 }, uAlpha: { value: 1 } },
  vertexShader: `varying vec2 vUv; varying vec3 vN; varying vec3 vV;
    void main(){ vUv = uv; vec4 mv = modelViewMatrix*vec4(position,1.0); vN = normalize(normalMatrix*normal); vV = normalize(-mv.xyz); gl_Position = projectionMatrix*mv; }`,
  fragmentShader: `uniform float uTime; uniform float uHeat; uniform float uAlpha; varying vec2 vUv; varying vec3 vN; varying vec3 vV;
    void main(){
      float along = vUv.y;
      float facing = abs(dot(normalize(vN), normalize(vV)));
      float n = 0.5 + 0.5*sin(vUv.x*44.0 + uTime*9.0 + along*28.0)*sin(along*60.0 - uTime*25.0);
      float flick = 0.8 + 0.2*sin(uTime*31.0 + along*17.0);
      float diamonds = smoothstep(0.6, 1.0, 0.5 + 0.5*cos(along*38.0)) * pow(along, 2.0);
      float a = pow(facing, 1.6) * pow(along, 1.7) * (0.28 + 0.22*n + diamonds*0.5) * flick * uAlpha;
      vec3 col = mix(vec3(0.25,0.55,1.0), vec3(1.0,0.48,0.14), 0.25 + uHeat*0.75);
      col = mix(col, vec3(1.0,0.92,0.8), pow(along, 7.0));
      gl_FragColor = vec4(col*1.15, a*0.7);
    }`,
});
const plume = new T.Mesh(new T.CylinderGeometry(0.98, 1.7, 5.2, 48, 24, true), plumeMat);
plume.rotation.z = Math.PI / 2; plume.position.x = 3.85 + 2.6;
mods.noz.add(plume);

/* ------------------------------------------------------------------ airflow particles */
const flowMat = new T.ShaderMaterial({
  transparent: true, depthWrite: false, blending: T.AdditiveBlending,
  uniforms: { uTime: { value: 0 }, uHeat: { value: 0.2 }, uPix: { value: 300 }, uFade: { value: 1 } },
  vertexShader: `
    attribute float aR; attribute float aAng; attribute float aPh; attribute float aSp; attribute float aType; attribute float aSize;
    uniform float uTime; uniform float uHeat; uniform float uPix; uniform float uFade;
    varying vec3 vCol; varying float vA;
    const float CX[11] = float[11](-7.0,-3.9,-3.2,-2.2,-0.1,0.9,1.5,2.8,3.9,4.4,7.5);
    const float CH[11] = float[11](0.15,0.5,0.55,0.57,0.63,0.63,0.62,0.6,0.32,0.05,0.05);
    const float CT[11] = float[11](0.95,1.0,1.0,0.95,0.74,0.86,0.9,1.1,0.95,0.92,1.55);
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
        c = mix(vec3(0.0,0.85,1.0), vec3(0.45,0.75,1.0), smoothstep(-3.0, 2.0, x)) * 0.8;
      } else {
        r = mix(pw(x, CX, CH), pw(x, CX, CT), aR);
        c = mix(vec3(0.0,0.9,1.0), vec3(0.8,0.92,1.0), smoothstep(-3.5,-0.3,x));
        c = mix(c, vec3(1.0,0.9,0.7)*1.9, smoothstep(-0.15,0.35,x));
        c = mix(c, vec3(1.0,0.5,0.15)*(1.2 + uHeat*1.0), smoothstep(0.75,2.0,x));
        c = mix(c, mix(vec3(1.0,0.4,0.12), vec3(1.0,0.15,0.1), uHeat)*0.9, smoothstep(3.6,7.0,x));
      }
      float ang = aAng + x*0.18 + (aType > 0.5 ? uTime*0.6 : 0.0);
      vec3 p = vec3(x, r*cos(ang), r*sin(ang));
      vec4 mv = modelViewMatrix*vec4(p,1.0);
      gl_Position = projectionMatrix*mv;
      gl_PointSize = aSize*uPix/(-mv.z);
      vCol = c;
      vA = smoothstep(0.0, 0.06, s)*(1.0 - smoothstep(0.78, 1.0, s))*uFade;
    }`,
  fragmentShader: `varying vec3 vCol; varying float vA;
    void main(){ float d = length(gl_PointCoord - 0.5); float a = smoothstep(0.5, 0.0, d); gl_FragColor = vec4(vCol, vA*a*0.5); }`,
});
{
  const N = 4200, g = new T.BufferGeometry();
  const at = (n) => new Float32Array(n);
  const aR = at(N), aAng = at(N), aPh = at(N), aSp = at(N), aType = at(N), aSize = at(N), pos = at(N * 3);
  for (let i = 0; i < N; i++) {
    const core = i % 2 === 0;
    aR[i] = Math.random(); aAng[i] = Math.random() * Math.PI * 2; aPh[i] = Math.random();
    aSp[i] = core ? 0.07 + Math.random() * 0.03 : 0.055 + Math.random() * 0.025;
    aType[i] = core ? 1 : 0; aSize[i] = core ? 0.05 + Math.random() * 0.05 : 0.035 + Math.random() * 0.04;
  }
  g.setAttribute('position', new T.BufferAttribute(pos, 3));
  [['aR', aR], ['aAng', aAng], ['aPh', aPh], ['aSp', aSp], ['aType', aType], ['aSize', aSize]].forEach(([k, v]) => g.setAttribute(k, new T.BufferAttribute(v, 1)));
  g.boundingSphere = new T.Sphere(new T.Vector3(0, 0, 0), 12);
  const flow = new T.Points(g, flowMat); flow.frustumCulled = false;
  engine.add(flow);
}

/* ------------------------------------------------------------------ scan plane */
const scanMat = new T.ShaderMaterial({
  transparent: true, depthWrite: false, blending: T.AdditiveBlending, side: T.DoubleSide,
  uniforms: { uA: { value: 0 }, uTime: { value: 0 } },
  vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.0); }',
  fragmentShader: `uniform float uA; uniform float uTime; varying vec2 vUv;
    void main(){
      vec2 p = vUv - 0.5; float d = length(p)*2.0;
      float edge = smoothstep(0.9, 0.985, d) * (1.0 - smoothstep(0.985, 1.0, d));
      float grid = smoothstep(0.92, 1.0, abs(sin(p.x*60.0))) + smoothstep(0.92, 1.0, abs(sin(p.y*60.0)));
      float a = (edge*1.4 + grid*0.12*(1.0-d) + 0.06) * uA * step(d, 1.0);
      gl_FragColor = vec4(vec3(0.3,0.95,1.0)*1.6, a);
    }`,
});
const scanPlane = new T.Mesh(new T.PlaneGeometry(5.6, 5.6), scanMat);
scanPlane.rotation.y = Math.PI / 2; scanPlane.visible = false; engine.add(scanPlane);

/* ------------------------------------------------------------------ holo platform, beam, stars */
const platform = new T.Group(); platform.position.y = -3.05; scene.add(platform);
const discA = new T.Mesh(new T.CircleGeometry(6.5, 96), new T.MeshBasicMaterial({ map: makeDiscTexture(0), color: new T.Color(0.0, 1.1, 1.5), transparent: true, opacity: 0.4, blending: T.AdditiveBlending, depthWrite: false }));
discA.rotation.x = -Math.PI / 2; platform.add(discA);
const discB = new T.Mesh(new T.CircleGeometry(5.2, 96), new T.MeshBasicMaterial({ map: makeDiscTexture(1), color: new T.Color(0.2, 0.7, 1.7), transparent: true, opacity: 0.35, blending: T.AdditiveBlending, depthWrite: false }));
discB.rotation.x = -Math.PI / 2; discB.position.y = 0.02; platform.add(discB);
const gridMat = new T.ShaderMaterial({
  transparent: true, depthWrite: false, blending: T.AdditiveBlending,
  uniforms: { uTime: { value: 0 }, uColor: { value: new T.Color(0x00e5ff) } },
  vertexShader: 'varying vec3 vW; void main(){ vec4 w = modelMatrix*vec4(position,1.0); vW = w.xyz; gl_Position = projectionMatrix*viewMatrix*w; }',
  fragmentShader: `uniform float uTime; uniform vec3 uColor; varying vec3 vW;
    void main(){
      vec2 p = vW.xz; vec2 q = p*0.8;
      vec2 g = abs(fract(q - 0.5) - 0.5) / fwidth(q);
      float line = 1.0 - min(min(g.x, g.y), 1.0);
      float d = length(p);
      float fade = 1.0 - smoothstep(5.0, 26.0, d);
      float pulse = smoothstep(0.35, 0.0, abs(d - mod(uTime*3.2, 30.0)));
      gl_FragColor = vec4(uColor*(0.7 + pulse*1.5), (line*0.13 + pulse*0.12) * fade);
    }`,
});
const grid = new T.Mesh(new T.PlaneGeometry(70, 70), gridMat);
grid.rotation.x = -Math.PI / 2; grid.position.y = -0.01; platform.add(grid);
const beamMat = new T.ShaderMaterial({
  transparent: true, depthWrite: false, blending: T.AdditiveBlending, side: T.DoubleSide,
  uniforms: { uTime: { value: 0 } },
  vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.0); }',
  fragmentShader: `uniform float uTime; varying vec2 vUv;
    void main(){ float a = pow(1.0 - vUv.y, 2.2)*0.07*(0.85 + 0.15*sin(vUv.x*80.0 + uTime*2.0)); gl_FragColor = vec4(0.2,0.85,1.0, a); }`,
});
const beam = new T.Mesh(new T.CylinderGeometry(3.4, 4.6, 3.0, 64, 1, true), beamMat);
beam.position.y = 1.5; platform.add(beam);

const starMat = new T.ShaderMaterial({
  transparent: true, depthWrite: false, blending: T.AdditiveBlending,
  uniforms: { uTime: { value: 0 } },
  vertexShader: `attribute float aS; attribute float aP; uniform float uTime; varying float vA;
    void main(){ vec4 mv = modelViewMatrix*vec4(position,1.0); gl_Position = projectionMatrix*mv; gl_PointSize = aS; vA = 0.45 + 0.55*sin(uTime*1.5 + aP*6.28); }`,
  fragmentShader: 'varying float vA; void main(){ float d = length(gl_PointCoord-0.5); gl_FragColor = vec4(vec3(0.75,0.88,1.0), smoothstep(0.5,0.0,d)*vA); }',
});
{
  const N = 1400, pos = new Float32Array(N * 3), aS = new Float32Array(N), aP = new Float32Array(N);
  for (let i = 0; i < N; i++) {
    const u = Math.random() * 2 - 1, th = Math.random() * Math.PI * 2, r = 70 + Math.random() * 90, s = Math.sqrt(1 - u * u);
    pos.set([r * s * Math.cos(th), r * u * 0.7 + 10, r * s * Math.sin(th)], i * 3);
    aS[i] = 1 + Math.random() * 2.4; aP[i] = Math.random();
  }
  const g = new T.BufferGeometry();
  g.setAttribute('position', new T.BufferAttribute(pos, 3)); g.setAttribute('aS', new T.BufferAttribute(aS, 1)); g.setAttribute('aP', new T.BufferAttribute(aP, 1));
  scene.add(new T.Points(g, starMat));
}

/* ------------------------------------------------------------------ sensor hotspots */
const hotspotGeo = new T.SphereGeometry(0.055, 16, 12);
const hotspots = {};
for (const [k, L] of Object.entries(LAYOUT)) {
  const g = new T.Group(); g.position.fromArray(L.pos);
  const core = new T.Mesh(hotspotGeo, new T.MeshBasicMaterial({ color: new T.Color(0, 3, 2), depthTest: false, transparent: true }));
  const halo = new T.Sprite(new T.SpriteMaterial({ map: HALO, color: new T.Color(0, 2, 1.4), blending: T.AdditiveBlending, depthTest: false, depthWrite: false, transparent: true }));
  halo.scale.setScalar(0.42);
  core.renderOrder = halo.renderOrder = 20;
  g.add(core, halo); g.visible = false;
  mods[L.mod].add(g);
  hotspots[k] = { group: g, core, halo, screen: new T.Vector2(-999, -999), visible: false, pulse: 0 };
}

/* ------------------------------------------------------------------ HUD: cards, modules */
const colL = $('col-left'), colR = $('col-right');
const modBox = $('modules');
const modEls = {};
MODULES.forEach((m) => {
  const el = document.createElement('div'); el.className = 'mod'; el.innerHTML = `${MOD_SHORT[m.key]}<em></em>`;
  modBox.appendChild(el); modEls[m.key] = el;
});

function buildCards() {
  colL.innerHTML = ''; colR.innerHTML = '';
  S.sensors = [];
  const factors = new Set((S.data && S.data.factors) || []);
  for (const k of Object.keys(LAYOUT)) {
    const sd = S.data && S.data.sensors.find((s) => s.key === k);
    if (!sd) continue;
    const el = document.createElement('div');
    el.className = 'card' + (sd.modeled ? '' : ' const') + (factors.has(k) ? ' factor' : '');
    el.innerHTML = `<div class="k">${esc(sd.code)}<small>${esc(sd.name)}</small></div><div class="v"><span>—</span><i>${esc(sd.unit)}</i></div>
      <div class="bar"><b></b></div><div class="z">—</div>`;
    el.title = `${sd.code} · ${sd.name}` + (sd.modeled ? '' : ' (constant in this dataset)') + (factors.has(k) ? ' · top SHAP driver of the RUL prediction' : '');
    el.addEventListener('mouseenter', () => { S.hovered = k; });
    el.addEventListener('mouseleave', () => { if (S.hovered === k) S.hovered = null; });
    el.addEventListener('click', () => selectSensor(k));
    (LAYOUT[k].side === 'L' ? colL : colR).appendChild(el);
    S.sensors.push({ ...sd, el, val: el.querySelector('.v span'), bar: el.querySelector('.bar b'), zEl: el.querySelector('.z'), z: 0, v: 0, sev: 0, anchor: { x: 0, y: 0 }, side: LAYOUT[k].side });
  }
  measureCards();
}
function measureCards() {
  const r0 = app.getBoundingClientRect();
  for (const s of S.sensors) {
    const r = s.el.getBoundingClientRect();
    s.anchor.x = (s.side === 'L' ? r.right : r.left) - r0.left;
    s.anchor.y = r.top + r.height / 2 - r0.top;
  }
}
function showCards() {
  S.sensors.forEach((s, i) => {
    s.el.classList.remove('in'); void s.el.offsetWidth;
    s.el.style.animationDelay = `${(i % 11) * 0.06}s`;
    s.el.classList.add('in');
  });
  S.sensors.forEach((s) => { const h = hotspots[s.key]; h.visible = true; h.pulse = 1; });
  setTimeout(measureCards, 1300);
}

/* ------------------------------------------------------------------ timeline */
const tl = $('timeline'), tlx = tl.getContext('2d');
let tlW = 0, tlH = 0;
function sizeTimeline() {
  const r = tl.getBoundingClientRect(), dpr = Math.min(window.devicePixelRatio || 1, 2);
  tlW = r.width; tlH = r.height; tl.width = Math.max(1, r.width * dpr); tl.height = Math.max(1, r.height * dpr);
  tlx.setTransform(dpr, 0, 0, dpr, 0, 0);
}
function drawTimeline() {
  const d = S.data; tlx.clearRect(0, 0, tlW, tlH);
  if (!d || S.N < 1 || tlW < 10) return;
  const padL = 34, padR = 40, padT = 6, padB = 14, w = tlW - padL - padR, h = tlH - padT - padB;
  const xOf = (i) => padL + (S.N === 1 ? w : (i / (S.N - 1)) * w);
  const rulMax = 130, hMax = Math.max(d.critical * 1.3, ...d.health) || 1;
  const yR = (v) => padT + h - (v / rulMax) * h, yH = (v) => padT + h - (clamp(v, 0, hMax) / hMax) * h;
  tlx.font = '600 9px JetBrains Mono, monospace'; tlx.textBaseline = 'middle';
  // RUL band limits
  (d.limits || []).forEach((lim, j) => {
    tlx.strokeStyle = BAND_CSS[j + 1] + '55'; tlx.setLineDash([3, 4]); tlx.beginPath(); tlx.moveTo(padL, yR(lim)); tlx.lineTo(padL + w, yR(lim)); tlx.stroke();
    tlx.fillStyle = BAND_CSS[j + 1] + 'aa'; tlx.fillText(String(lim), 6, yR(lim));
  });
  tlx.setLineDash([]);
  const cur = S.t;
  const path = (arr, yf) => { tlx.beginPath(); arr.forEach((v, i) => (i ? tlx.lineTo(xOf(i), yf(v)) : tlx.moveTo(xOf(i), yf(v)))); };
  // health threshold
  tlx.strokeStyle = 'rgba(255,138,31,0.45)'; tlx.setLineDash([2, 3]); tlx.beginPath(); tlx.moveTo(padL, yH(d.threshold)); tlx.lineTo(padL + w, yH(d.threshold)); tlx.stroke(); tlx.setLineDash([]);
  // full curves (dim) then the played part (bright), clipped at the playhead
  const drawCurves = (alpha) => {
    if (d.rul) {
      path(d.rul, yR);
      tlx.strokeStyle = `rgba(0,229,255,${alpha})`; tlx.lineWidth = 2; tlx.stroke();
      tlx.lineTo(xOf(S.N - 1), padT + h); tlx.lineTo(xOf(0), padT + h); tlx.closePath();
      const gr = tlx.createLinearGradient(0, padT, 0, padT + h); gr.addColorStop(0, `rgba(0,229,255,${alpha * 0.28})`); gr.addColorStop(1, 'rgba(0,229,255,0)');
      tlx.fillStyle = gr; tlx.fill();
    }
    path(d.health, yH); tlx.strokeStyle = `rgba(255,120,200,${alpha})`; tlx.lineWidth = 1.5; tlx.stroke();
  };
  drawCurves(0.18);
  tlx.save(); tlx.beginPath(); tlx.rect(0, 0, xOf(cur), tlH); tlx.clip(); drawCurves(0.95); tlx.restore();
  // band strip
  if (d.band) {
    for (let i = 0; i < S.N; i++) {
      const x0 = xOf(i - 0.5 < 0 ? 0 : i - 0.5), x1 = xOf(Math.min(S.N - 1, i + 0.5));
      tlx.fillStyle = BAND_CSS[d.band[i]] + (i <= cur ? 'ee' : '44'); tlx.fillRect(x0, padT + h + 5, Math.max(1, x1 - x0), 5);
    }
  }
  // playhead
  const px = xOf(cur);
  tlx.strokeStyle = '#fff'; tlx.lineWidth = 1.5; tlx.shadowColor = '#00e5ff'; tlx.shadowBlur = 10;
  tlx.beginPath(); tlx.moveTo(px, padT - 2); tlx.lineTo(px, padT + h + 10); tlx.stroke(); tlx.shadowBlur = 0;
  if (d.rul) { tlx.fillStyle = '#00e5ff'; tlx.beginPath(); tlx.arc(px, yR(interp(d.rul, cur)), 3.5, 0, Math.PI * 2); tlx.fill(); }
  tlx.fillStyle = '#ff78c8'; tlx.beginPath(); tlx.arc(px, yH(interp(d.health, cur)), 3, 0, Math.PI * 2); tlx.fill();
  // legend
  tlx.fillStyle = 'rgba(0,229,255,0.9)'; tlx.fillText('RUL', padL + w + 8, padT + 6);
  tlx.fillStyle = 'rgba(255,120,200,0.9)'; tlx.fillText('HEALTH', padL + w + 4, padT + 20);
  tlx.fillStyle = 'rgba(127,149,189,0.9)'; tlx.fillText(`C${d.cycles[Math.round(cur)]}`, clamp(px - 12, padL, padL + w - 24), padT + h + 2 - h);
}
function scrubTo(clientX) {
  const r = tl.getBoundingClientRect(), padL = 34, padR = 40;
  const f = clamp((clientX - r.left - padL) / (r.width - padL - padR), 0, 1);
  S.t = f * (S.N - 1); S.playing = false; S.finished = false; syncPlayButton();
}
let scrubbing = false;
tl.addEventListener('pointerdown', (e) => { if (!S.data) return; scrubbing = true; tl.setPointerCapture(e.pointerId); scrubTo(e.clientX); });
tl.addEventListener('pointermove', (e) => scrubbing && scrubTo(e.clientX));
tl.addEventListener('pointerup', () => { scrubbing = false; });

/* ------------------------------------------------------------------ data helpers */
function interp(arr, t) {
  if (!arr || !arr.length) return 0;
  const i0 = clamp(Math.floor(t), 0, arr.length - 1), i1 = Math.min(i0 + 1, arr.length - 1), f = t - i0;
  return lerp(arr[i0], arr[i1], f);
}
const pad4 = (n) => String(Math.max(0, Math.round(n))).padStart(4, '0');

/* ------------------------------------------------------------------ playback & controls */
const playBtn = $('btn-play');
function syncPlayButton() { playBtn.textContent = S.playing ? '❚❚ PAUSE' : '▶ PLAY'; playBtn.classList.toggle('on', S.playing); }
function play(fromStart = false) {
  if (!S.data) return;
  if (fromStart || S.t >= S.N - 1) { S.t = 0; S.lastIdx = -1; S.maxBand = S.data.band ? S.data.band[0] : 0; S.critSeen.clear(); }
  S.playing = true; S.finished = false; syncPlayButton();
}
playBtn.onclick = () => { if (S.playing) { S.playing = false; syncPlayButton(); } else play(); };
$('btn-replay').onclick = () => { play(true); triggerScan(); };
document.querySelectorAll('#speed button').forEach((b) => {
  b.onclick = () => { S.speed = +b.dataset.speed; document.querySelectorAll('#speed button').forEach((x) => x.classList.toggle('on', x === b)); };
});
$('btn-explode').onclick = (e) => { S.explodeTarget = S.explodeTarget ? 0 : 1; e.currentTarget.classList.toggle('on', !!S.explodeTarget); };
$('btn-scan').onclick = () => triggerScan();
$('btn-orbit').onclick = (e) => { S.orbit = !S.orbit; e.currentTarget.classList.toggle('on', S.orbit); };
$('btn-cinema').onclick = (e) => {
  S.cinema = !S.cinema; app.classList.toggle('cinema', S.cinema); e.currentTarget.classList.toggle('on', S.cinema);
  resize(); flyHome(1.2);
};
window.addEventListener('keydown', (e) => {
  if (e.code === 'Space') { e.preventDefault(); playBtn.click(); }
  else if (e.key === 'e') $('btn-explode').click();
  else if (e.key === 's') triggerScan();
  else if (e.key === 'c') $('btn-cinema').click();
  else if (e.key === 'Escape') { S.selected = null; refreshSelection(); flyHome(1.0); }
});

function triggerScan() { S.scanStart = performance.now(); flash(); }
function flash() { const f = $('flash'); f.classList.remove('go'); void f.offsetWidth; f.classList.add('go'); }
let alertTimer = null;
function showAlert(title, sub, color, ms = 2600) {
  const a = $('alert'); $('alert-title').textContent = title; $('alert-sub').textContent = sub;
  a.querySelector('.alert-inner').style.setProperty('--c', color);
  a.classList.add('show'); clearTimeout(alertTimer); alertTimer = setTimeout(() => a.classList.remove('show'), ms);
}
function toast(html, color) {
  const t = document.createElement('div'); t.className = 'toast'; t.style.setProperty('--c', color); t.innerHTML = html;
  $('toasts').appendChild(t); setTimeout(() => t.remove(), 4000);
  while ($('toasts').children.length > 4) $('toasts').firstChild.remove();
}

/* ------------------------------------------------------------------ camera framing */
let W = 1, H = 1;
const HOME_DIR = new T.Vector3(0.62, 0.3, 1).normalize();
function homeDistance() {
  const twin = S.mode === 'twin';
  const usableW = twin && !S.cinema && W > 760 ? (W - 2 * (W > 980 ? 250 : 196)) / W : 0.94;
  const usableH = twin ? (H - (W > 760 ? 250 : 200)) / H : 0.9;
  const vt = Math.tan(T.MathUtils.degToRad(camera.fov / 2)), ht = vt * camera.aspect;
  return Math.max(5.6 / (ht * usableW), 3.1 / (vt * usableH), 6) * (twin ? 1.0 : 1.05);
}
function setHome() { S.home.pos.copy(S.home.target).addScaledVector(HOME_DIR, homeDistance()); }
function flyTo(pos, target, secs) {
  S.camTween = { t0: performance.now(), dur: secs * 1000, p0: camera.position.clone(), q0: controls.target.clone(), p1: pos.clone(), q1: target.clone() };
}
function flyHome(secs = 1.4) { setHome(); flyTo(S.home.pos, S.home.target, secs); }
function resize() {
  const r = app.getBoundingClientRect(); W = Math.max(1, r.width); H = Math.max(1, r.height);
  renderer.setSize(W, H, false); composer.setSize(W, H);
  camera.aspect = W / H;
  if (S.mode === 'twin' && W > 760) camera.setViewOffset(W, H, 0, 36, W, H); else camera.clearViewOffset();
  camera.updateProjectionMatrix();
  flowMat.uniforms.uPix.value = H * renderer.getPixelRatio() * 0.9;
  const lc = $('lines'), dpr = Math.min(window.devicePixelRatio || 1, 2);
  lc.width = W * dpr; lc.height = H * dpr; lx.setTransform(dpr, 0, 0, dpr, 0, 0);
  sizeTimeline(); measureCards(); setHome();
}
const lx = $('lines').getContext('2d');
new ResizeObserver(() => resize()).observe(app);

/* ------------------------------------------------------------------ selection & picking */
function selectSensor(k) {
  S.selected = S.selected === k ? null : k;
  refreshSelection();
  if (S.selected) {
    const h = hotspots[k], wp = h.group.getWorldPosition(new T.Vector3());
    const dir = camera.position.clone().sub(controls.target).normalize();
    flyTo(wp.clone().addScaledVector(dir, 6.2), wp, 1.2);
    Bridge.value({ sensor: k, unit: S.data ? S.data.unit : null, t: Date.now() });
  } else flyHome(1.0);
}
function refreshSelection() { S.sensors.forEach((s) => s.el.classList.toggle('sel', s.key === S.selected)); }
const tip = $('tooltip');
canvas.addEventListener('pointermove', (e) => {
  if (S.mode !== 'twin' || !S.data) return;
  const r = app.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top;
  let best = null, bd = 18;
  for (const s of S.sensors) { const h = hotspots[s.key]; const d = Math.hypot(h.screen.x - mx, h.screen.y - my); if (h.visible && d < bd) { bd = d; best = s; } }
  S.hovered = best ? best.key : (S.hovered && S.sensors.find((s) => s.key === S.hovered && s.el.matches(':hover')) ? S.hovered : null);
  if (best) {
    tip.style.display = 'block'; tip.style.left = `${Math.min(mx + 16, W - 270)}px`; tip.style.top = `${my + 14}px`;
    tip.innerHTML = `<b>${best.code} · ${best.name}</b><div class="mono">${best.v.toFixed(best.decimals)} ${best.unit} · ${best.modeled ? (best.z >= 0 ? '+' : '') + best.z.toFixed(1) + 'σ ' + sevWord(best.sev) : 'constant in this dataset'}</div><div class="mono" style="color:#7f95bd">${MOD_SHORT[LAYOUT[best.key].mod]} module · click to focus</div>`;
    canvas.style.cursor = 'pointer';
  } else { tip.style.display = 'none'; canvas.style.cursor = ''; }
});
canvas.addEventListener('pointerleave', () => { tip.style.display = 'none'; });
canvas.addEventListener('click', () => { if (S.hovered && S.mode === 'twin') selectSensor(S.hovered); });
canvas.addEventListener('dblclick', () => { S.selected = null; refreshSelection(); flyHome(1.0); });

/* ------------------------------------------------------------------ apply data to scene + HUD */
const tmpC = new T.Color();
function applyState(now, dt) {
  const d = S.data;
  const tsec = now / 1000;
  // module severities from the sensors that report on them
  const modSev = { fan: 0, lpc: 0, hpc: 0, comb: 0, hpt: 0, lpt: 0, noz: 0, byp: 0 };
  let overall = 0;
  if (d) {
    for (const s of S.sensors) {
      s.v = interp(s.values, S.t);
      s.z = s.modeled ? interp(s.z_arr, S.t) : 0;
      s.sev = s.modeled ? zSev(s.z) : 0;
      const m = LAYOUT[s.key].mod; modSev[m] = Math.max(modSev[m], s.sev); overall = Math.max(overall, s.sev);
    }
  }
  S.modSev = modSev; S.overall = overall;
  const idx = d ? clamp(Math.round(S.t), 0, S.N - 1) : 0;
  const band = d && d.band ? d.band[idx] : 0;
  S.band = band;

  // --- engine visuals
  const setRim = (mat, sev, base, baseStr) => {
    const rimU = mat.userData.rim; if (!rimU) return;
    if (sev < 0.2) rimU.uRimColor.value.set(base); else rimU.uRimColor.value.copy(sevColor(sev, tmpC));
    rimU.uRimStr.value = baseStr + sev * 1.6 + (sev > 0.75 ? 0.5 * Math.sin(tsec * 8) : 0);
  };
  setRim(MAT.fanBlade, modSev.fan, 0x00e5ff, 0.55);
  setRim(MAT.lpc, modSev.lpc, 0x00e5ff, 0.35);
  setRim(MAT.hpc, modSev.hpc, 0x00e5ff, 0.35);
  MAT.hpc.emissive.copy(sevColor(modSev.hpc, tmpC)).multiplyScalar(modSev.hpc > 0.25 ? modSev.hpc * 0.8 : 0);
  MAT.lpc.emissive.copy(sevColor(modSev.lpc, tmpC)).multiplyScalar(modSev.lpc > 0.25 ? modSev.lpc * 0.6 : 0);
  const heat = Math.max(modSev.lpt, modSev.hpt * 0.8, modSev.hpc * 0.6);
  MAT.hpt.emissiveIntensity = 0.45 + heat * 1.1 + 0.08 * Math.sin(tsec * 13);
  MAT.lpt.emissiveIntensity = 0.2 + heat * 0.7;
  combMat.uniforms.uHeat.value = Math.max(modSev.comb, modSev.hpc);
  combMat.uniforms.uPower.value = 0.85 + 0.15 * Math.sin(tsec * 17) * Math.sin(tsec * 7.3) + combMat.uniforms.uHeat.value * 0.35;
  combLight.intensity = 5 + combMat.uniforms.uPower.value * 4;
  plumeMat.uniforms.uHeat.value = flowMat.uniforms.uHeat.value = heat;
  const alertLvl = band === 3 ? 0.35 + 0.25 * Math.sin(tsec * 5) : band === 2 ? 0.12 : 0;
  nacelleMat.uniforms.uAlert.value = lerp(nacelleMat.uniforms.uAlert.value, alertLvl, 0.1);
  alertLight.intensity = band === 3 ? 18 + 14 * Math.sin(tsec * 5) : 0;
  // vibration when the engine is badly degraded
  const vib = Math.max(0, overall - 0.65) * 0.05;
  engine.position.set(0, Math.sin(tsec * 71) * vib, Math.cos(tsec * 53) * vib);

  // hotspots
  for (const s of S.sensors) {
    const h = hotspots[s.key]; if (!h) continue;
    const c = s.modeled ? sevColor(s.sev, tmpC) : tmpC.set(0x5d7aa8);
    const boost = s.key === S.selected || s.key === S.hovered ? 2.2 : 1;
    h.core.material.color.copy(c).multiplyScalar(1.8 * boost);
    h.halo.material.color.copy(c).multiplyScalar(0.85 * boost);
    h.pulse = Math.max(0, h.pulse - dt * 1.5);
    const sc = (0.2 + 0.05 * Math.sin(tsec * (3 + s.sev * 6) + s.key.length) + s.sev * 0.18 + h.pulse * 0.35) * (boost > 1 ? 1.6 : 1);
    h.halo.scale.setScalar(h.visible ? sc : 0.0001);
    h.core.scale.setScalar(h.visible ? 1 + (boost > 1 ? 0.6 : 0) : 0.0001);
    h.group.visible = h.visible && S.mode === 'twin';
  }

  // --- HUD (throttled DOM writes)
  if (!d || S.mode !== 'twin') return;
  if (S.frame % 2 === 0) {
    $('cycle-now').textContent = pad4(d.cycles[idx]);
    for (const s of S.sensors) {
      s.val.textContent = s.v.toFixed(s.decimals);
      if (s.modeled) {
        s.zEl.textContent = `${s.z >= 0 ? '+' : ''}${s.z.toFixed(1)}σ`;
        s.bar.style.width = `${clamp(s.z / 5, 0.02, 1) * 100}%`;
        s.el.style.setProperty('--c', sevCss(s.sev));
      } else {
        s.zEl.textContent = 'CONST'; s.bar.style.width = '0%'; s.el.style.setProperty('--c', '#5d7aa8');
      }
    }
    for (const m of MODULES) {
      const el = modEls[m.key], sv = modSev[m.key];
      el.style.setProperty('--c', sevCss(sv)); el.classList.toggle('crit', sv >= 0.75);
      el.querySelector('em').style.opacity = 0.35 + sv * 0.65;
    }
    const health = interp(d.health, S.t);
    const frac = clamp(health / (d.critical * 1.25), 0, 1);
    $('g-health-arc').style.strokeDashoffset = String(314.16 * (1 - frac));
    $('g-health-val').textContent = health.toFixed(2);
    app.style.setProperty('--band', BAND_CSS[band]);
    $('band-name').textContent = d.band ? BAND_TXT[band] : 'NO RISK MODEL';
    $('band-prob').textContent = d.prob ? `CONFIDENCE ${(d.prob[idx] * 100).toFixed(0)}%` : '';
    $('caution').classList.toggle('on', band >= 2);
    if (d.rul) {
      $('rul-val').textContent = Math.round(interp(d.rul, S.t));
      $('rul-range').textContent = idx === S.N - 1 && d.rul_low != null ? `80% RANGE ${Math.round(d.rul_low)}–${Math.round(d.rul_high)} CYC` : `LIVE ESTIMATE · CYCLE ${d.cycles[idx]}`;
    }
    const vg = $('vignette'); vg.classList.toggle('crit', band === 3); vg.classList.toggle('high', band === 2);
  }

  // --- discrete events when the playhead crosses a cycle
  if (idx !== S.lastIdx) {
    if (S.playing && S.lastIdx >= 0 && idx > S.lastIdx) {
      if (d.band && band > S.maxBand) {
        S.maxBand = band; flash();
        const worst = Object.entries(modSev).sort((a, b) => b[1] - a[1])[0][0];
        showAlert(`⚠ ${BAND_TXT[band]}`, `RISK ESCALATION AT CYCLE ${d.cycles[idx]} · ${MOD_SHORT[worst]} MODULE DEGRADING`, BAND_CSS[band]);
      }
      for (const s of S.sensors) {
        if (s.modeled && s.sev >= 0.75 && !S.critSeen.has(s.key)) {
          S.critSeen.add(s.key); hotspots[s.key].pulse = 1;
          toast(`⚠ <b>${s.code}</b> ${s.name} · CRITICAL DRIFT ${s.z >= 0 ? '+' : ''}${s.z.toFixed(1)}σ`, '#ff2e4d');
        }
      }
    }
    S.lastIdx = idx;
  }
}

/* ------------------------------------------------------------------ overlay lines */
function drawOverlay(now) {
  lx.clearRect(0, 0, W, H);
  if (S.mode !== 'twin' || !S.data) return;
  const v = new T.Vector3();
  for (const [k, h] of Object.entries(hotspots)) {
    h.group.getWorldPosition(v).project(camera);
    h.screen.set((v.x * 0.5 + 0.5) * W, (-v.y * 0.5 + 0.5) * H);
  }
  // module names in exploded view
  if (S.explode > 0.05) {
    lx.font = '700 11px Orbitron, sans-serif'; lx.textAlign = 'center';
    for (const m of MODULES) {
      if (m.key === 'byp') continue;
      const g = mods[m.key]; v.set(-0.9 + (m.key === 'fan' ? -3.2 : m.key === 'lpc' ? -2.0 : m.key === 'hpc' ? -0.2 : m.key === 'comb' ? 1.35 : m.key === 'hpt' ? 2.0 : m.key === 'lpt' ? 3.1 : 4.6), 2.45, 0);
      v.x += g.position.x; v.project(camera);
      const x = (v.x * 0.5 + 0.5) * W, y = (-v.y * 0.5 + 0.5) * H;
      lx.globalAlpha = S.explode; lx.fillStyle = sevCss(S.modSev[m.key] || 0);
      lx.fillText(m.name, x, y); lx.fillRect(x - 0.5, y + 6, 1, 26);
    }
    lx.globalAlpha = 1; lx.textAlign = 'left';
  }
  if (S.cinema) return;
  const dash = (now / 40) % 20;
  for (const s of S.sensors) {
    const h = hotspots[s.key]; if (!h.visible || !s.el.classList.contains('in')) continue;
    const active = s.key === S.selected || s.key === S.hovered;
    const a = active ? 1 : s.modeled ? 0.22 + s.sev * 0.7 : 0.12;
    const col = s.modeled ? sevCss(s.sev) : '#5d7aa8';
    const dir = s.side === 'L' ? 1 : -1;
    const ax = s.anchor.x, ay = s.anchor.y, ex = ax + 22 * dir;
    lx.globalAlpha = a * 0.35; lx.strokeStyle = col; lx.lineWidth = active ? 5 : 3.5; lx.setLineDash([]);
    lx.beginPath(); lx.moveTo(ax, ay); lx.lineTo(ex, ay); lx.lineTo(h.screen.x, h.screen.y); lx.stroke();
    lx.globalAlpha = a; lx.lineWidth = active ? 1.8 : 1;
    if (active || s.sev >= 0.5) { lx.setLineDash([6, 4]); lx.lineDashOffset = -dash * dir; }
    lx.beginPath(); lx.moveTo(ax, ay); lx.lineTo(ex, ay); lx.lineTo(h.screen.x, h.screen.y); lx.stroke();
    lx.setLineDash([]);
    lx.beginPath(); lx.arc(ax, ay, 2.2, 0, Math.PI * 2); lx.fillStyle = col; lx.fill();
    if (active) {
      const r = 14 + 2 * Math.sin(now / 160), rot = now / 600;
      lx.lineWidth = 1.6; lx.globalAlpha = 1;
      for (let q = 0; q < 4; q++) { lx.beginPath(); lx.arc(h.screen.x, h.screen.y, r, rot + q * Math.PI / 2, rot + q * Math.PI / 2 + 0.9); lx.stroke(); }
    }
  }
  lx.globalAlpha = 1;
}

/* ------------------------------------------------------------------ boot & intro */
async function boot(p) {
  const log = $('boot-log'), bar = $('boot-bar');
  const lines = [
    ['> AEROSENTINEL DIGITAL TWIN // CORE ONLINE', ''],
    [`> LINKING TELEMETRY · UNIT ${String(p.unit).padStart(3, '0')} · ${p.source || 'UPLOAD'}`, 'OK'],
    [`> ${p.cycles.length} CYCLES · ${p.sensors.length} SENSOR CHANNELS · MODEL ${p.model || ''}`, 'OK'],
    ['> RECONSTRUCTING TURBOFAN GEOMETRY', 'OK'],
    ['> CALIBRATING HEALTH BASELINE', 'OK'],
    ['> ARMING PROGNOSTICS (XGBOOST · SHAP)', 'OK'],
  ];
  const rows = [];
  const render = () => { log.innerHTML = rows.join('\n'); };
  for (let i = 0; i < lines.length; i++) {
    const [txt, ok] = lines[i];
    for (let c = 2; c <= txt.length; c += 3) { rows[i] = esc(txt.slice(0, c)) + '<span class="ok">▌</span>'; render(); await sleep(7); }
    rows[i] = esc(txt) + (ok ? ` <span class="ok">[${ok}]</span>` : ''); render();
    bar.style.width = `${((i + 1) / lines.length) * 100}%`;
    await sleep(90);
  }
  await sleep(280);
  $('boot').classList.add('done');
}
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function startIntro(full) {
  S.introStart = performance.now(); S.introFull = full; S.introCardsShown = false; S.introScanDone = false; S.introPlayQueued = true;
  S.playing = false; syncPlayButton();
  S.t = 0; S.lastIdx = -1; S.critSeen.clear(); S.maxBand = S.data && S.data.band ? S.data.band[0] : 0;
  Object.values(hotspots).forEach((h) => { h.visible = false; });
  S.sensors.forEach((s) => s.el.classList.remove('in'));
  setHome();
  if (full) { camera.position.set(16, 7, 26); controls.target.set(-0.2, 0, 0); }
  controls.enabled = false;
  flyTo(S.home.pos, S.home.target, full ? 3.4 : 1.6);
}
function updateIntro(now) {
  if (S.introStart < 0) return 1;
  const e = (now - S.introStart) / 1000;
  const assembleDur = S.introFull ? 2.6 : 0.01;
  if (e > (S.introFull ? 2.3 : 0.2) && !S.introScanDone) { S.introScanDone = true; triggerScan(); }
  if (e > (S.introFull ? 2.7 : 0.4) && !S.introCardsShown) { S.introCardsShown = true; showCards(); }
  if (e > (S.introFull ? 4.0 : 1.4) && S.introPlayQueued) {
    S.introPlayQueued = false; controls.enabled = true;
    if (REDUCED || !S.data) { S.t = Math.max(0, S.N - 1); } else play(true);
  }
  if (e > 4.5) S.introStart = -1;
  return S.introFull ? e / assembleDur : 1;
}

/* ------------------------------------------------------------------ payload */
function loadPayload(p) {
  const first = !S.data;
  S.data = p; S.dataId = p.id; S.N = p.cycles.length;
  p.sensors.forEach((s) => { s.z_arr = s.z; });
  buildCards();
  $('unit-line').textContent = `ENGINE UNIT ${String(p.unit).padStart(3, '0')} · ${p.source || ''} · MODEL ${p.model || ''}`.toUpperCase();
  $('cycle-max').textContent = pad4(p.cycles[S.N - 1]);
  S.selected = null;
  if (first && !REDUCED) { boot(p).then(() => startIntro(true)); }
  else { $('boot').classList.add('done'); flash(); startIntro(false); if (!first) toast(`RELINKED · <b>UNIT ${p.unit}</b> · ${S.N} CYCLES`, '#00e5ff'); }
}

/* ------------------------------------------------------------------ main loop */
let last = performance.now();
const introOffsets = { fan: -9, lpc: -7, hpc: -5, comb: 4, hpt: 6, lpt: 8, noz: 10, byp: 0 };
function frame() {
  requestAnimationFrame(frame);
  // One clock for everything: intro, tweens and scan are all stamped with performance.now().
  const now = performance.now();
  if (document.hidden) { last = now; return; }
  const dt = Math.min(0.05, (now - last) / 1000); last = now; S.frame++;
  const tsec = now / 1000;

  // playback: a full engine life plays in ~20 s at 1x
  if (S.playing && S.data && S.N > 1) {
    S.t += dt * (S.N / 20) * S.speed;
    if (S.t >= S.N - 1) {
      S.t = S.N - 1; S.playing = false; S.finished = true; syncPlayButton();
      const d = S.data, b = d.band ? d.band[S.N - 1] : 0;
      const worst = Object.entries(S.modSev).sort((a, c) => c[1] - a[1])[0];
      const rulTxt = d.rul ? `RUL ${Math.round(d.rul[S.N - 1])} CYC` : '';
      showAlert('ASSESSMENT COMPLETE', `${d.band ? BAND_TXT[b] : ''} · ${rulTxt} · ${worst[1] > 0.25 ? 'INSPECT ' + MOD_SHORT[worst[0]] + ' MODULE' : 'ALL MODULES NOMINAL'}`, d.band ? BAND_CSS[b] : '#00e5ff', 4200);
    }
  }

  // intro assembly + explode
  const asm = ease(updateIntro(now));
  S.explode = lerp(S.explode, S.explodeTarget, 1 - Math.exp(-dt * 4));
  for (const m of MODULES) {
    const g = mods[m.key], k = MODULES.indexOf(m);
    const local = S.introFull && S.introStart >= 0 ? ease(((now - S.introStart) / 1000 - 0.15 - k * 0.12) / 1.6) : 1;
    g.position.x = m.explode * S.explode + (1 - local) * introOffsets[m.key];
    g.scale.setScalar(lerp(0.55, 1, local));
    if (m.key === 'byp') { g.position.y = S.explode * 2.9 + (1 - local) * 5; }
  }
  nacelleMat.uniforms.uOpacity.value = (1 - S.explode * 0.55) * (S.introFull && S.introStart >= 0 ? clamp(asm, 0, 1) : 1);
  coreMat.opacity = 0.55 * (1 - S.explode * 0.7);
  flowMat.uniforms.uFade.value = 1 - S.explode;
  plumeMat.uniforms.uAlpha.value = 1 - S.explode;

  // rotors: LP spool (fan, LPC, LPT) and HP spool (HPC, HPT)
  lpRotors.forEach((r) => { r.rotation.x += dt * 2.6; });
  hpRotors.forEach((r) => { r.rotation.x += dt * 5.2; });

  // scan sweep
  const se = (now - S.scanStart) / 1000;
  if (se >= 0 && se < 2.2) {
    scanPlane.visible = true;
    const x = lerp(-5.6, 5.2, easeInOut(se / 2.2));
    scanPlane.position.x = x; scanMat.uniforms.uA.value = Math.sin(Math.PI * clamp(se / 2.2, 0, 1));
    for (const [k, h] of Object.entries(hotspots)) {
      const hx = h.group.getWorldPosition(tmpV).x;
      if (Math.abs(hx - x) < 0.18) h.pulse = 1;
    }
  } else scanPlane.visible = false;

  // camera tween / orbit
  if (S.camTween) {
    const ct = S.camTween, f = easeInOut((now - ct.t0) / ct.dur);
    camera.position.lerpVectors(ct.p0, ct.p1, f); controls.target.lerpVectors(ct.q0, ct.q1, f);
    if (f >= 1) S.camTween = null;
  }
  controls.autoRotate = S.orbit && !S.camTween && now - S.lastInteract > 5000 && S.introStart < 0;
  controls.update(dt);

  // shader clocks
  [nacelleMat, coreHolo.material, combMat, plumeMat, flowMat, scanMat, gridMat, beamMat, starMat].forEach((m) => { if (m.uniforms && m.uniforms.uTime) m.uniforms.uTime.value = tsec; });
  discA.rotation.z += dt * 0.05; discB.rotation.z -= dt * 0.09;

  applyState(now, dt);
  composer.render();
  drawOverlay(now);
  if (S.mode === 'twin') drawTimeline();
}
const tmpV = new T.Vector3();

/* ------------------------------------------------------------------ args from Streamlit */
function onRender(args) {
  const mode = args.mode || 'twin';
  if (mode !== S.mode) { S.mode = mode; app.className = `mode-${mode}`; }
  const h = args.height || (mode === 'hero' ? 420 : 820);
  if (h !== S.height) { S.height = h; }
  Bridge.height(h);
  if (mode === 'hero') {
    $('boot').classList.add('done');
    if (S.introStart === -1 && !S.heroStarted) { S.heroStarted = true; resize(); startIntro(true); setTimeout(() => { controls.enabled = true; }, 3500); }
    return;
  }
  const p = args.payload;
  if (p && p.id !== S.dataId) { resize(); loadPayload(p); }
}
window.addEventListener('message', (e) => {
  const m = e.data;
  if (m && m.type === 'streamlit:render') onRender(m.args || {});
});

resize();
requestAnimationFrame(frame);
Bridge.ready();
if (!IN_ST) {
  // Standalone preview (opened directly in a browser): hero mode with no data.
  onRender({ mode: new URLSearchParams(location.search).get('mode') || 'hero', height: window.innerHeight });
}
// Debug handle for tuning in the browser console (read-only use).
window.AS_DEBUG = { T, scene, renderer, bloom, composer, camera, controls, MAT, mods, nacelleMat, coreMat, combMat, plumeMat, flowMat, beamMat, gridMat, discA, discB, S };
