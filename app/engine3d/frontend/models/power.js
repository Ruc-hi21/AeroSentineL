/* Power-electronics model: an IGBT power module on its heat sink, cut open at the front, layers along Y.
 * From the bottom: finned heat sink, thermal grease, copper baseplate, substrate solder, DBC substrate
 * (ceramic with copper tracks), IGBT and diode dies on their die attach, aluminium bond wires, the
 * housing frame with power terminals, the lid and the gate-driver board on top. Current pulses run
 * along the bond wires at the switching rate, the dies warm with temperature drift and the gate LED
 * blinks with the gate signal. Parts take the colour of their drifting channels.
 *
 * Exploded view: a classic stack-up. Every layer rises more than the one below it, so the layers
 * separate in order; the frame walls lie outside the substrate and the lid and frame ghost. */
import { T, physical, metal, canvasTexture, dispose } from './shared.js?v=7.0.0';
import { stackContext } from './power_stack.js?v=7.0.0';

const MODULES = [
  { key: 'gate', name: 'Gate drive', explode: [0, 0, 0] },
  { key: 'die', name: 'IGBT die', explode: [0, 0, 0] },
  { key: 'bond', name: 'Bond wires and die attach', explode: [0, 0, 0] },
  { key: 'thermal', name: 'Package and heat sink', explode: [0, 0, 0] },
];
// Layer heights (top of each layer) and the stack-up offsets used by the exploded view.
const Y = { sink: -1.6, grease: -1.57, base: -1.4, solder: -1.37, dbc: -1.27, trace: -1.24, attach: -1.225, die: -1.17 };
const RISE = { sink: 0, base: 0.35, solder: 0.7, dbc: 1.05, attach: 1.3, die: 1.5, wires: 1.85, frame: 2.3, lid: 2.8, pcb: 3.4 };
const DIES = [[-0.95, -0.35, 'igbt'], [-0.95, 0.4, 'diode'], [0.55, -0.35, 'igbt'], [0.55, 0.4, 'diode']];

const LAYOUT = {
  vce_on: { mod: 'bond', at: 'wires', pos: [-0.6, -0.95, -0.2], side: 'L' },
  r_on: { mod: 'bond', at: 'wires', pos: [0.9, -0.95, -0.2], side: 'L' },
  vce_ripple: { mod: 'bond', at: 'attach', pos: [0.15, -1.0, 0.1], side: 'L' },
  vce_off: { mod: 'die', at: 'die', pos: [-0.95, -1.13, -0.35], side: 'L' },
  ice_on: { mod: 'die', at: 'terminals', pos: [1.65, -0.75, 0.75], side: 'R' },
  vge_on: { mod: 'gate', at: 'pcb', pos: [-1.6, -0.2, -0.55], side: 'R' },
  pkg_temp: { mod: 'thermal', at: 'base', pos: [1.55, -1.38, 0.95], side: 'R' },
};

const dieTex = (kind) => canvasTexture(128, 128, (g, w, h) => {
  g.fillStyle = kind === 'igbt' ? '#2a3140' : '#30353d'; g.fillRect(0, 0, w, h);
  g.strokeStyle = '#8a95a3'; g.lineWidth = 2;
  if (kind === 'igbt') { for (let i = 1; i < 8; i++) { g.beginPath(); g.moveTo(10, i * 16); g.lineTo(w - 10, i * 16); g.stroke(); } g.fillStyle = '#b9c1ca'; g.fillRect(8, 8, 22, 22); }
  else { g.strokeRect(16, 16, w - 32, h - 32); }
});
const pcbTex = () => canvasTexture(512, 256, (g, w, h) => {
  g.fillStyle = '#0f3d2e'; g.fillRect(0, 0, w, h);
  g.strokeStyle = '#c59b4f'; g.lineWidth = 3;
  for (let i = 0; i < 14; i++) { g.beginPath(); g.moveTo(20 + i * 34, 20); g.lineTo(20 + i * 34, 120 + (i % 3) * 30); g.lineTo(60 + i * 30, h - 20); g.stroke(); }
  g.fillStyle = '#e6e8eb'; g.font = '600 22px sans-serif'; g.fillText('GATE DRIVER', 330, 40); g.font = '400 16px monospace'; g.fillText('AS-GD1 15V', 340, 64);
});

export function build() {
  const M = {
    sink: metal(0xa7b0ba, 0.4, 0.85), grease: new T.MeshStandardMaterial({ color: 0x8d949c, roughness: 0.9 }),
    copper: physical(0xc47a3c, 0.25, 1.0, { emissive: 0x000000 }), solder: metal(0x9aa3ad, 0.45, 0.8),
    ceramic: new T.MeshStandardMaterial({ color: 0xe9e4d8, roughness: 0.6, emissive: 0x000000 }),
    trace: physical(0xd08a4a, 0.22, 1.0, { emissive: 0x000000 }),
    igbt: new T.MeshStandardMaterial({ map: dieTex('igbt'), roughness: 0.35, metalness: 0.4, emissive: 0x000000 }),
    diode: new T.MeshStandardMaterial({ map: dieTex('diode'), roughness: 0.35, metalness: 0.4, emissive: 0x000000 }),
    attach: metal(0xb9c1ca, 0.35, 0.9), wire: physical(0xdfe4ea, 0.2, 1.0, { emissive: 0x000000 }),
    frame: physical(0x1d2127, 0.55, 0.1, { emissive: 0x000000 }), lid: physical(0x262b31, 0.5, 0.1),
    terminal: physical(0xd08a4a, 0.25, 1.0),
    pcb: new T.MeshStandardMaterial({ map: pcbTex(), roughness: 0.55, metalness: 0.1, emissive: 0x000000 }),
    chip: physical(0x15181c, 0.45, 0.2), cap: physical(0x3a6cc2, 0.4, 0.3), pin: physical(0xc59b4f, 0.3, 1.0),
    led: new T.MeshBasicMaterial({ color: 0x5fd4f8, toneMapped: false }),
  };
  const root = new T.Group();
  const mods = {};
  MODULES.forEach((m) => { const g = new T.Group(); mods[m.key] = g; root.add(g); });
  const layers = {}; // name -> group, moved by the exploded view
  const layer = (name, mod) => { const g = new T.Group(); layers[name] = g; mods[mod].add(g); return g; };
  const box = (w, h, d, mat, x, y, z, r = 0.02) => { const m = new T.Mesh(new T.RoundedBoxGeometry(w, h, d, 2, r), mat); m.position.set(x, y, z); return m; };

  // Heat sink with fins, thermal grease, copper baseplate (with a thermistor).
  const sink = layer('sink', 'thermal');
  // the heat sink itself is shared by all three phases (power_stack.js)
  sink.add(box(4.0, 0.03, 2.5, M.grease, 0, Y.grease - 0.015, 0, 0.005));
  const base = layer('base', 'thermal');
  base.add(box(4.0, 0.17, 2.5, M.copper, 0, Y.base - 0.085, 0, 0.02));
  base.add(box(0.22, 0.1, 0.14, M.chip, 1.55, Y.base + 0.05, 0.95, 0.01));
  [[-1.75, -1.0], [1.75, -1.0], [-1.75, 1.0], [1.75, 1.0]].forEach(([x, z]) => base.add(new T.Mesh(new T.CylinderGeometry(0.09, 0.09, 0.06, 6), M.solder).translateX(x).translateY(Y.base + 0.03).translateZ(z)));

  // Substrate solder, DBC ceramic with copper tracks.
  const solder = layer('solder', 'bond');
  solder.add(box(3.5, 0.03, 2.1, M.solder, 0, Y.solder - 0.015, 0, 0.005));
  const dbc = layer('dbc', 'die');
  dbc.add(box(3.6, 0.1, 2.2, M.ceramic, 0, Y.dbc - 0.05, 0, 0.01));
  [[-0.95, 0, 1.3, 1.8], [0.55, 0, 1.3, 1.8], [1.55, 0, 0.45, 1.8], [-1.6, 0, 0.3, 1.8]].forEach(([x, z, w, d]) =>
    dbc.add(box(w, 0.03, d, M.trace, x, Y.trace - 0.015, z, 0.005)));

  // Dies on their die attach.
  const attach = layer('attach', 'bond');
  const dies = layer('die', 'die');
  DIES.forEach(([x, z, kind]) => {
    attach.add(box(0.62, 0.015, 0.55, M.attach, x, Y.attach - 0.0075, z, 0.003));
    dies.add(box(0.58, 0.05, 0.5, M[kind], x, Y.die - 0.025, z, 0.004));
  });

  // Bond wires: arcs from each die to the next copper track; current pulses travel along them.
  const wires = layer('wires', 'bond');
  const wireCurves = [];
  DIES.forEach(([x, z]) => {
    for (let k = 0; k < 5; k++) {
      const zz = z - 0.18 + k * 0.09, x0 = x + 0.1, x1 = x + 0.82;
      const c = new T.QuadraticBezierCurve3(new T.Vector3(x0, Y.die, zz), new T.Vector3((x0 + x1) / 2, Y.die + 0.32, zz), new T.Vector3(x1, Y.trace, zz));
      wireCurves.push(c);
      wires.add(new T.Mesh(new T.TubeGeometry(c, 20, 0.012, 6, false), M.wire));
    }
  });
  const PN = wireCurves.length * 3, ppos = new Float32Array(PN * 3), pph = new Float32Array(PN);
  for (let i = 0; i < PN; i++) pph[i] = Math.random();
  const pGeo = new T.BufferGeometry(); pGeo.setAttribute('position', new T.BufferAttribute(ppos, 3));
  const pMat = new T.PointsMaterial({ color: 0x8fe6ff, size: 0.05, transparent: true, opacity: 0.9, depthWrite: false, blending: T.AdditiveBlending });
  const pulses = new T.Points(pGeo, pMat); pulses.frustumCulled = false; wires.add(pulses);

  // Housing frame (back and sides; the front is cut away) with three power terminals, then the lid.
  const frame = layer('frame', 'thermal');
  frame.add(box(4.0, 0.95, 0.12, M.frame, 0, Y.base + 0.47, -1.19, 0.02));
  [-1.94, 1.94].forEach((x) => frame.add(box(0.12, 0.95, 2.5, M.frame, x, Y.base + 0.47, 0, 0.02)));
  frame.add(box(4.0, 0.25, 0.12, M.frame, 0, Y.base + 0.13, 1.19, 0.02)); // low front lip
  const terms = layer('terminals', 'die');
  [-1.3, 0, 1.3].forEach((x) => {
    terms.add(box(0.36, 1.1, 0.05, M.terminal, x, Y.base + 0.4, -1.0, 0.01));
    terms.add(box(0.36, 0.05, 0.5, M.terminal, x, Y.base + 0.95, -1.2, 0.01));
  });
  const lid = layer('lid', 'thermal');
  const lidMesh = box(4.0, 0.08, 1.25, M.lid, 0, Y.base + 0.99, -0.62, 0.02); lid.add(lidMesh); // back half: the front stays open

  // Gate-driver board on stand-offs, gate pins down to the substrate, gate LED.
  const pcb = layer('pcb', 'gate');
  pcb.add(box(3.4, 0.05, 1.3, M.pcb, -0.1, Y.base + 1.55, -0.5, 0.01));
  [[-1.6, -1.0], [1.4, -1.0], [-1.6, 0.0], [1.4, 0.0]].forEach(([x, z]) => pcb.add(box(0.08, 0.55, 0.08, M.pin, x, Y.base + 1.27, z, 0.01)));
  [[-0.9, -0.6, 0.5, 0.06, 0.4], [0.2, -0.4, 0.35, 0.06, 0.35], [1.0, -0.7, 0.3, 0.06, 0.25]].forEach(([x, z, w, h, d]) => pcb.add(box(w, h, d, M.chip, x, Y.base + 1.6, z, 0.01)));
  for (let i = 0; i < 4; i++) { const c = new T.Mesh(new T.CylinderGeometry(0.07, 0.07, 0.22, 16), M.cap); c.position.set(-1.4 + i * 0.25, Y.base + 1.69, -0.95); pcb.add(c); }
  const gatePins = [[-1.6, -0.55], [-0.15, -0.55]].map(([x, z]) => box(0.04, 0.9, 0.04, M.pin, x, Y.base + 1.08, z, 0.005));
  pcb.add(...gatePins);
  const led = new T.Mesh(new T.SphereGeometry(0.04, 12, 10), M.led); led.position.set(1.3, Y.base + 1.6, 0.05); pcb.add(led);

  // The rest of the 3-phase inverter around this module: phases V and W, DC link, AC outputs, fan.
  const stack = stackContext(root, layers.sink, M);

  let heat = 0, rate = 1.0, phase = 0;
  const tmp = new T.Vector3();
  return {
    key: 'power', root, mods, modules: MODULES, layout: LAYOUT, materials: M, layers,
    shells: [M.frame, M.lid, ...stack.materials],
    panels: { L: 'On-state and blocking', R: 'Current, gate and temperature' },
    view: { target: [0.4, -0.9, -2.6], dir: [0.55, 0.7, 1], twin: [4.6, 2.6], hero: [5.2, 3.0], min: 8 },
    groundY: Y.sink - 1.06,
    labels: { gate: [2.3, Y.base + 1.6, -0.5], die: [2.3, Y.die, 0.4], bond: [2.3, Y.die + 0.35, 0.0], thermal: [2.6, Y.sink - 0.3, 0] },
    apply({ modLevel, z, levels }) {
      const tint = (mats, mod, strength) => mats.forEach((mat) => {
        const lv = modLevel[mod];
        if (lv < 0) mat.emissive.setRGB(0, 0, 0); else { mat.emissive.set(levels[lv].color); mat.emissiveIntensity = strength[lv]; }
      });
      tint([M.wire], 'bond', [0.45, 0.3, 0.15]);
      tint([M.trace, M.ceramic], 'die', [0.2, 0.13, 0.06]);
      tint([M.pcb], 'gate', [0.25, 0.16, 0.08]);
      tint([M.copper, M.frame], 'thermal', [0.12, 0.08, 0.04]);
      // The dies glow with temperature and on-state voltage drift (heat from the degrading die attach).
      heat = Math.max(0, Math.min(1, Math.max(z.pkg_temp || 0, z.vce_on || 0) / 4));
      stack.setHeat(heat);
      [M.igbt, M.diode].forEach((m) => { m.emissive.setRGB(1.0 * heat, 0.35 * heat, 0.08 * heat); m.emissiveIntensity = 1.4; });
      rate = 0.8 + Math.max(0, Math.min(1, (z.ice_on || 0) / 4)) * 0.6;
    },
    tick(dt, tsec, { reduced, explode }) {
      // Exploded view: each layer rises more than the one below it.
      for (const [name, g] of Object.entries(layers)) g.position.y = (RISE[name] ?? 0) * explode;
      stack.tick(dt, explode, reduced);
      pMat.opacity = 0.9 * (1 - explode);
      if (reduced) return;
      phase += dt * rate;
      const on = (phase % 1) < 0.5; // square gate signal: current flows while the switch is on
      led.material.color.set(on ? 0x5fd4f8 : 0x0f2a3a);
      for (let i = 0; i < PN; i++) {
        pph[i] = (pph[i] + dt * 1.4) % 1;
        const c = wireCurves[i % wireCurves.length];
        c.getPoint(pph[i], tmp);
        ppos[i * 3] = tmp.x; ppos[i * 3 + 1] = on ? tmp.y : -50; ppos[i * 3 + 2] = tmp.z;
      }
      pGeo.attributes.position.needsUpdate = true;
    },
    resize() {},
    conditionText() { return 'square gate drive, package held above rating'; },
    dispose() { stack.dispose(); dispose(root); },
  };
}
