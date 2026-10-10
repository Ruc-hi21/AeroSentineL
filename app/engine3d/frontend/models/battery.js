/* Battery model: a sectioned cylindrical Li-ion cell (18650 format) along world X, positive cap at +X.
 * The cut shows the wound electrode stack (cathode, separator, anode layers) around the mandrel.
 * Parts take the colour of their drifting channels; the can warms with temperature drift and a slow
 * current trace runs along the tabs to the terminals. */
import { T, V2, metal, lathe, axialCylinder, sectionCut, ring, dispose } from './shared.js';

const MODULES = [
  { key: 'stack', name: 'Electrode stack', explode: [0, 0, 0] },
  { key: 'interface', name: 'Electrode interface', explode: [0, 0, 0] },
  { key: 'electrolyte', name: 'Electrolyte', explode: [0, 0, 0] },
  { key: 'terminal', name: 'Terminals', explode: [1.1, 0, 0] },
  { key: 'can', name: 'Can and thermal', explode: [0, 2.6, 0] },
];
// Thermocouple strip on the front of the can, 25 degrees below the cut edge (r 1.36 = can r 1.33 + clearance).
const TC = 25 * Math.PI / 180;
const SKIN_Y = -1.38 * Math.sin(TC), SKIN_Z = 1.38 * Math.cos(TC);
const LAYOUT = {
  soh: { mod: 'stack', pos: [-2.4, 0.0, 0.55], side: 'L' },
  capacity_ah: { mod: 'stack', pos: [-1.6, 0.0, 0.8], side: 'L' },
  discharge_min: { mod: 'stack', pos: [-0.7, 0.0, 0.95], side: 'L' },
  dvdt_mid: { mod: 'stack', pos: [0.2, 0.0, 0.65], side: 'L' },
  cc_charge_min: { mod: 'stack', pos: [1.1, 0.0, 0.9], side: 'L' },
  v_mean: { mod: 'interface', pos: [-1.1, 0.7, 0.0], side: 'L' },
  cv_charge_min: { mod: 'interface', pos: [-0.1, 0.95, 0.0], side: 'L' },
  rct_ohm: { mod: 'interface', pos: [0.9, 0.55, 0.0], side: 'L' },
  re_ohm: { mod: 'electrolyte', pos: [2.1, 0.4, 0.0], side: 'R' },
  v_start: { mod: 'terminal', pos: [3.55, 0.3, 0.1], side: 'R' },
  temp_max_c: { mod: 'can', pos: [-0.4, SKIN_Y, SKIN_Z], side: 'R' },
  temp_rise_c: { mod: 'can', pos: [0.4, SKIN_Y, SKIN_Z], side: 'R' },
  t_tmax_min: { mod: 'can', pos: [1.2, SKIN_Y, SKIN_Z], side: 'R' },
  charge_temp_max_c: { mod: 'can', pos: [-1.2, SKIN_Y, SKIN_Z], side: 'R' },
};

export function build() {
  const M = {
    can: new T.MeshStandardMaterial({ color: 0x5d6670, metalness: 0.8, roughness: 0.35, side: T.DoubleSide, emissive: 0x000000 }),
    wrap: new T.MeshStandardMaterial({ color: 0x2a3a52, metalness: 0.1, roughness: 0.7, side: T.DoubleSide }),
    cathode: new T.MeshStandardMaterial({ color: 0x6b7c95, metalness: 0.35, roughness: 0.55, side: T.DoubleSide }),
    anode: new T.MeshStandardMaterial({ color: 0x30353d, metalness: 0.2, roughness: 0.75, side: T.DoubleSide }),
    separator: new T.MeshStandardMaterial({ color: 0xc9ced6, metalness: 0.0, roughness: 0.9, side: T.DoubleSide }),
    electrolyte: new T.MeshStandardMaterial({ color: 0x78a9ff, metalness: 0, roughness: 0.2, transparent: true, opacity: 0.08, depthWrite: false }),
    cap: metal(0xb7bec7, 0.3, 0.9), tab: metal(0xc7ccd2, 0.35, 0.85), insul: new T.MeshStandardMaterial({ color: 0x8a6d3b, roughness: 0.8 }),
    mandrel: metal(0x8c949e, 0.4), patch: new T.MeshStandardMaterial({ color: 0xd6dbe1, roughness: 0.6 }),
  };
  M.cathode.emissive = new T.Color(0); M.separator.emissive = new T.Color(0); M.anode.emissive = new T.Color(0);
  const cutMats = { cathode: M.cathode, anode: M.anode, separator: M.separator };

  const root = new T.Group();
  const mods = {};
  MODULES.forEach((m) => { const g = new T.Group(); mods[m.key] = g; root.add(g); });
  const quarter = (p, mat, cut = mat) => [lathe(p, mat, 72, 0, Math.PI * 1.5), sectionCut(p.slice(0, -1), cut)];

  // Can: steel tube with a closed negative bottom, printed wrap on the outside.
  const canP = [V2(1.24, -3.42), V2(1.3, -3.42), V2(1.3, 3.18), V2(1.24, 3.18), V2(1.24, -3.36), V2(0.0, -3.36), V2(0.0, -3.42), V2(1.24, -3.42)];
  mods.can.add(...quarter(canP, M.can));
  const wrapP = [V2(1.3, -3.3), V2(1.33, -3.3), V2(1.33, 3.05), V2(1.3, 3.05), V2(1.3, -3.3)];
  mods.can.add(...quarter(wrapP, M.wrap));
  mods.can.add(ring(1.3, -3.42), ring(1.3, 3.18));
  // Thermocouple strip lying flat on the can: its thin axis (Y) turned onto the surface normal.
  const patch = new T.Mesh(new T.BoxGeometry(2.8, 0.02, 0.22), M.patch);
  patch.position.set(0, -1.345 * Math.sin(TC), 1.345 * Math.cos(TC)); patch.rotation.x = Math.PI / 2 + TC; mods.can.add(patch);
  // Insulator discs above and below the stack.
  [[-3.05, -2.97], [2.86, 2.94]].forEach(([x0, x1]) => mods.can.add(...quarter([V2(0.15, x0), V2(1.2, x0), V2(1.2, x1), V2(0.15, x1), V2(0.15, x0)], M.insul)));

  // Wound electrode stack: alternating cathode / separator / anode / separator layers.
  const kinds = ['cathode', 'separator', 'anode', 'separator'];
  let r = 0.2, k = 0;
  const layers = { cathode: [], anode: [], separator: [] };
  while (r < 1.17) {
    const kind = kinds[k % 4], t = kind === 'separator' ? 0.018 : 0.05;
    const p = [V2(r, -2.9), V2(r + t, -2.9), V2(r + t, 2.8), V2(r, 2.8), V2(r, -2.9)];
    const target = kind === 'separator' ? mods.interface : mods.stack;
    const meshes = quarter(p, M[kind], cutMats[kind]);
    target.add(...meshes); layers[kind].push(...meshes);
    r += t + 0.004; k++;
  }
  mods.stack.add(axialCylinder(0.15, -2.95, 2.85, M.mandrel, 24));

  // Electrolyte: a faint fill of the stack volume.
  const fill = new T.Mesh(new T.CylinderGeometry(1.2, 1.2, 5.7, 48, 1, true, 0, Math.PI * 1.5), M.electrolyte);
  fill.rotation.z = Math.PI / 2; fill.position.x = -0.05; mods.electrolyte.add(fill);

  // Terminals: positive button cap with crimp ring at +X, tabs from the stack to both ends.
  mods.terminal.add(lathe([V2(0.0, 3.18), V2(1.22, 3.18), V2(1.26, 3.26), V2(0.62, 3.3), V2(0.6, 3.5), V2(0.0, 3.5)], M.cap, 64));
  mods.terminal.add(ring(0.6, 3.5));
  const tabGeo = new T.BoxGeometry(0.42, 0.03, 0.18);
  const tabP = new T.Mesh(tabGeo, M.tab); tabP.position.set(3.0, 0.62, -0.5); tabP.rotation.x = 0.4; mods.terminal.add(tabP);
  const tabN = new T.Mesh(tabGeo, M.tab); tabN.position.set(-3.18, -0.6, -0.45); tabN.rotation.x = -0.4; mods.terminal.add(tabN);

  // Current trace: particles running out of the stack along the tabs to the terminals.
  const flowMat = new T.PointsMaterial({ color: 0x78a9ff, size: 0.06, transparent: true, opacity: 0.55, depthWrite: false });
  const N = 90, pos = new Float32Array(N * 3), phase = new Float32Array(N);
  for (let i = 0; i < N; i++) phase[i] = Math.random();
  const flowGeo = new T.BufferGeometry(); flowGeo.setAttribute('position', new T.BufferAttribute(pos, 3));
  const flow = new T.Points(flowGeo, flowMat); flow.frustumCulled = false; root.add(flow);
  const path = (s, i) => {
    const out = i % 2 === 0; // half to the positive cap, half to the negative can bottom
    const a = (phase[i] * 6.28) % (Math.PI * 1.5);
    const rr = 0.25 + 0.9 * (1 - s);
    return out ? [2.2 + s * 1.2, rr * -Math.sin(a) * (1 - s), rr * Math.cos(a) * (1 - s)]
      : [-2.2 - s * 1.1, rr * -Math.sin(a) * (1 - s), rr * Math.cos(a) * (1 - s)];
  };

  let rate = 0.15;
  return {
    key: 'battery', root, mods, modules: MODULES, layout: LAYOUT, materials: M,
    panels: { L: 'Capacity and charge', R: 'Resistance, voltage and temperature' },
    view: { target: [0.05, 0, 0], dir: [0.55, 0.34, 1], twin: [3.9, 1.9], hero: [4.6, 2.3], min: 6 },
    groundY: -2.1,
    labels: { stack: [-0.3, -1.75, 0], terminal: [3.5, -1.75, 0], can: [0, 1.75, 0] },
    apply({ modLevel, z, levels }) {
      const tint = (mats, mod, strength) => {
        const lv = modLevel[mod];
        mats.forEach((m) => {
          if (lv < 0) m.emissive.setRGB(0, 0, 0);
          else { m.emissive.set(levels[lv].color); m.emissiveIntensity = strength[lv]; }
        });
      };
      tint([M.cathode, M.anode], 'stack', [0.35, 0.22, 0.12]);
      tint([M.separator], 'interface', [0.45, 0.3, 0.15]);
      // The can warms with peak-temperature drift.
      const heat = Math.max(0, Math.min(1, (z.temp_max_c || 0) / 4));
      M.can.emissive.setRGB(1.0 * heat, 0.42 * heat, 0.12 * heat); M.can.emissiveIntensity = 0.5;
      const elv = modLevel.electrolyte;
      M.electrolyte.color.set(elv < 0 ? 0x78a9ff : levels[elv].color);
      rate = 0.12 + 0.12 * Math.max(0, Math.min(1, -(z.capacity_ah || 0) / 4));
    },
    tick(dt, tsec, { reduced, explode }) {
      flowMat.opacity = 0.55 * (1 - explode);
      M.electrolyte.opacity = 0.08 * (1 - explode);
      if (reduced) return;
      for (let i = 0; i < N; i++) {
        phase[i] = (phase[i] + dt * rate) % 1;
        const p = path(phase[i], i);
        pos[i * 3] = p[0]; pos[i * 3 + 1] = p[1]; pos[i * 3 + 2] = p[2];
      }
      flowGeo.attributes.position.needsUpdate = true;
    },
    resize() {},
    conditionText(c, i) { return c ? `${Math.round(c.ambient_c[i])} °C ambient  ${c.load_a[i].toFixed(1)} A discharge` : ''; },
    dispose() { dispose(root); },
  };
}
