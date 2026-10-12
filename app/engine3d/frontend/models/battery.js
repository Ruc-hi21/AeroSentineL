/* Battery model: a sectioned cylindrical Li-ion cell (18650 format) along world X, positive cap at +X.
 * The cut shows the wound electrode stack layer by layer: aluminium foil coated with cathode, the
 * separator, copper foil coated with graphite anode. Parts take the colour of their drifting channels,
 * the can warms with temperature drift, lithium ions shuttle across the separators while the cell
 * discharges and a current trace runs along the tabs to the terminals. */
import { T, V2, physical, metal, lathe, axialCylinder, sectionCut, ring, canvasTexture, dispose } from './shared.js?v=7.0.0';
import { moduleContext } from './battery_module.js?v=7.0.0';

const MODULES = [
  { key: 'stack', name: 'Electrode stack', explode: [0, 0, 0], intro: [-7, 0, 0] },
  { key: 'interface', name: 'Electrode interface', explode: [0, 0, 0], intro: [-7, 0, 0] },
  { key: 'electrolyte', name: 'Electrolyte', explode: [0, 0, 0], intro: [-7, 0, 0] },
  { key: 'terminal', name: 'Terminals', explode: [1.1, 0, 0], intro: [3.8, 0, 0] },
  { key: 'can', name: 'Can and thermal', explode: [0, 0, 0] },
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

// Wound stack, radially: repeating cathode coat | Al foil | cathode coat | separator | anode coat | Cu foil | anode coat | separator.
const R0 = 0.2, R1 = 1.18, X0 = -2.9, X1 = 2.8;
const PERIOD = [['cath', 0.022], ['al', 0.007], ['cath', 0.022], ['sep', 0.014], ['anode', 0.024], ['cu', 0.007], ['anode', 0.024], ['sep', 0.014]];
const LAYERS = (() => { // [kind, r0, r1]
  const out = []; let r = R0, i = 0;
  while (r < R1) { const [k, t] = PERIOD[i % PERIOD.length]; out.push([k, r, Math.min(R1, r + t)]); r += t; i++; }
  return out;
})();
const COLORS = { cath: '#4d5866', al: '#c9cfd6', anode: '#1d2126', cu: '#c47a3c', sep: '#e8ebef' };

// Section-face texture for the stack: v runs along the radius (R0 at the bottom row, R1 at the top).
function stackTexture(only) {
  const tex = canvasTexture(4, 2048, (g, w, h) => {
    g.clearRect(0, 0, w, h);
    for (const [k, a, b] of LAYERS) {
      if (only ? k !== only : k === 'sep') continue;
      g.fillStyle = COLORS[k];
      const y0 = h - ((b - R0) / (R1 - R0)) * h, y1 = h - ((a - R0) / (R1 - R0)) * h;
      g.fillRect(0, y0, w, Math.max(1, y1 - y0));
    }
  });
  tex.wrapS = T.RepeatWrapping;
  tex.repeat.set(1, 1 / (R1 - R0)); tex.offset.set(0, -R0 / (R1 - R0)); // shape UVs are (axial, radius)
  return tex;
}

// Printed PVC sleeve: canvas u runs round the cell (0..270 degrees), v along the axis (+X at the top).
function wrapTexture() {
  return canvasTexture(1024, 2048, (g, w, h) => {
    const grd = g.createLinearGradient(0, 0, w, 0);
    grd.addColorStop(0, '#0b2350'); grd.addColorStop(0.5, '#0d2f6a'); grd.addColorStop(1, '#0a1f47');
    g.fillStyle = grd; g.fillRect(0, 0, w, h);
    // brand band round the positive end and a thin band at the negative end
    g.fillStyle = '#1683f2'; g.fillRect(0, 150, w, 36); g.fillStyle = '#5fd4f8'; g.fillRect(0, 196, w, 6);
    g.fillStyle = '#1683f2'; g.fillRect(0, h - 170, w, 10);
    // text runs along the axis on the visible front face, below the thermocouple strip (about 35..52 degrees)
    g.save(); g.translate(w * 0.162, h * 0.52); g.rotate(-Math.PI / 2);
    g.textAlign = 'center'; g.textBaseline = 'middle';
    g.fillStyle = '#e6e8eb'; g.font = '600 60px "IBM Plex Sans", "Segoe UI", sans-serif'; g.fillText('Li-ion 18650', -330, 0);
    g.fillStyle = '#a9c7f0'; g.font = '400 50px "IBM Plex Mono", Consolas, monospace'; g.fillText('3.7 V  2.0 Ah  NASA PCoE', 250, 2);
    g.restore();
    g.save(); g.translate(w * 0.08, h * 0.12); g.rotate(-Math.PI / 2); g.fillStyle = '#e6e8eb'; g.font = '600 120px sans-serif';
    g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText('+', 0, 0); g.restore();
    g.save(); g.translate(w * 0.08, h * 0.9); g.rotate(-Math.PI / 2); g.fillStyle = '#e6e8eb'; g.font = '600 120px sans-serif';
    g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText('−', 0, 0); g.restore();
  });
}

export function build() {
  const M = {
    can: physical(0x8a929c, 0.32, 0.95, { emissive: 0x000000, side: T.DoubleSide, clearcoat: 0.2 }),
    wrap: new T.MeshPhysicalMaterial({ map: wrapTexture(), roughness: 0.45, metalness: 0.05, clearcoat: 0.3, clearcoatRoughness: 0.35, side: T.DoubleSide }),
    wrapEdge: new T.MeshStandardMaterial({ color: 0x0b2350, roughness: 0.4, side: T.DoubleSide }),
    stack: new T.MeshStandardMaterial({ color: 0x2b3038, metalness: 0.3, roughness: 0.6, side: T.DoubleSide, emissive: 0x000000 }),
    stackCut: new T.MeshStandardMaterial({ map: stackTexture(null), metalness: 0.15, roughness: 0.55, side: T.DoubleSide, emissive: 0x000000 }),
    sepCut: new T.MeshStandardMaterial({ map: stackTexture('sep'), alphaTest: 0.5, roughness: 0.85, side: T.DoubleSide, emissive: 0x000000 }),
    electrolyte: new T.MeshStandardMaterial({ color: 0x3fa2ff, metalness: 0, roughness: 0.2, transparent: true, opacity: 0.07, depthWrite: false }),
    cap: physical(0xb3bac2, 0.34, 1.0, { clearcoat: 0.3 }), tab: metal(0xc7ccd2, 0.35, 0.85), gasket: new T.MeshStandardMaterial({ color: 0x15181c, roughness: 0.7 }),
    insul: new T.MeshStandardMaterial({ color: 0x8a6d3b, roughness: 0.8 }), vent: new T.MeshStandardMaterial({ color: 0x0b0d10, roughness: 0.9 }),
    mandrel: metal(0x8c949e, 0.4), patch: new T.MeshStandardMaterial({ color: 0xd6dbe1, roughness: 0.6 }),
  };

  const root = new T.Group();
  const mods = {};
  MODULES.forEach((m) => { const g = new T.Group(); mods[m.key] = g; root.add(g); });
  const quarter = (p, mat, cut) => [lathe(p, mat, 96, 0, Math.PI * 1.5), sectionCut(p.slice(0, -1), cut)];

  // Can: drawn steel tube with a closed negative bottom and a crimped positive end; the printed
  // sleeve on the outside folds over both shoulders.
  const canP = [V2(1.24, -3.42), V2(1.28, -3.42), V2(1.3, -3.38), V2(1.3, 3.06), V2(1.27, 3.14), V2(1.2, 3.2), V2(1.17, 3.17), V2(1.24, 3.1),
    V2(1.24, -3.36), V2(0.0, -3.36), V2(0.0, -3.42), V2(1.24, -3.42)];
  mods.can.add(...quarter(canP, M.can));
  const sleeve = new T.Mesh(new T.CylinderGeometry(1.334, 1.334, 6.3, 120, 1, true, 0, Math.PI * 1.5), M.wrap);
  sleeve.rotation.z = -Math.PI / 2; sleeve.position.x = -0.13; mods.can.add(sleeve);
  mods.can.add(...quarter([V2(1.3, -3.3), V2(1.326, -3.28), V2(1.326, 3.02), V2(1.3, 3.04), V2(1.3, -3.3)], M.wrapEdge));
  mods.can.add(ring(1.3, -3.42), ring(1.33, 3.02));
  // Thermocouple strip lying flat on the sleeve.
  const patch = new T.Mesh(new T.BoxGeometry(2.8, 0.02, 0.22), M.patch);
  patch.position.set(0, -1.345 * Math.sin(TC), 1.345 * Math.cos(TC)); patch.rotation.x = Math.PI / 2 + TC; mods.can.add(patch);
  // Insulator discs above and below the stack.
  [[-3.05, -2.97], [2.86, 2.94]].forEach(([x0, x1]) => mods.can.add(...quarter([V2(0.15, x0), V2(1.2, x0), V2(1.2, x1), V2(0.15, x1), V2(0.15, x0)], M.insul)));

  // Wound electrode stack: one solid with printed section faces (every layer to scale), the separator
  // layers on their own faces so the interface can be tinted separately.
  const stackP = [V2(R0, X0), V2(R1, X0), V2(R1, X1), V2(R0, X1), V2(R0, X0)];
  mods.stack.add(lathe(stackP, M.stack, 96, 0, Math.PI * 1.5), sectionCut(stackP.slice(0, -1), M.stackCut));
  const sepFaces = sectionCut(stackP.slice(0, -1), M.sepCut);
  sepFaces.children.filter((c) => c.isLine).forEach((c) => { c.visible = false; });
  sepFaces.children[0].position.y = 0.003; sepFaces.children[1].position.z = 0.003; // lift off the stack faces (no z-fighting)
  mods.interface.add(sepFaces);
  mods.stack.add(axialCylinder(0.15, -2.95, 2.85, M.mandrel, 24));

  // Electrolyte: a faint fill of the stack volume.
  const fill = new T.Mesh(new T.CylinderGeometry(1.2, 1.2, 5.7, 48, 1, true, 0, Math.PI * 1.5), M.electrolyte);
  fill.rotation.z = Math.PI / 2; fill.position.x = -0.05; mods.electrolyte.add(fill);

  // Terminals: positive button cap with vents over a gasket, tabs from the stack to both ends.
  mods.terminal.add(lathe([V2(0.0, 3.16), V2(1.12, 3.16), V2(1.16, 3.2), V2(1.12, 3.24), V2(0.66, 3.27), V2(0.62, 3.32), V2(0.6, 3.48),
    V2(0.56, 3.52), V2(0.0, 3.52)], M.cap, 72));
  mods.terminal.add(lathe([V2(1.0, 3.1), V2(1.2, 3.1), V2(1.22, 3.18), V2(1.18, 3.26), V2(1.0, 3.26), V2(1.0, 3.1)], M.gasket, 72));
  for (let i = 0; i < 4; i++) {
    const a = (i / 4) * Math.PI * 2 + Math.PI / 4, v = new T.Mesh(new T.CylinderGeometry(0.1, 0.1, 0.02, 20), M.vent);
    v.rotation.z = Math.PI / 2; v.position.set(3.255, 0.88 * Math.cos(a), 0.88 * Math.sin(a)); mods.terminal.add(v);
  }
  mods.terminal.add(ring(0.56, 3.52));
  const tabGeo = new T.BoxGeometry(0.42, 0.03, 0.18);
  const tabP = new T.Mesh(tabGeo, M.tab); tabP.position.set(3.0, 0.62, -0.5); tabP.rotation.x = 0.4; mods.terminal.add(tabP);
  const tabN = new T.Mesh(tabGeo, M.tab); tabN.position.set(-3.18, -0.6, -0.45); tabN.rotation.x = -0.4; mods.terminal.add(tabN);

  // Current trace: particles running out of the stack along the tabs to the terminals.
  const flowMat = new T.PointsMaterial({ color: 0x5fd4f8, size: 0.06, transparent: true, opacity: 0.6, depthWrite: false, blending: T.AdditiveBlending });
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

  // Lithium ions on the two cut faces, crossing a separator from anode to cathode while discharging.
  const pairs = []; // [anode-side radius, cathode-side radius] across each separator
  LAYERS.forEach(([k, a, b], i) => {
    if (k !== 'sep') return;
    const prev = LAYERS[i - 1], next = LAYERS[i + 1];
    if (prev && next) pairs.push(prev[0] === 'anode' ? [a - 0.012, b + 0.012] : [b + 0.012, a - 0.012]);
  });
  const IN = 220, ionPos = new Float32Array(IN * 3), ion = [];
  for (let i = 0; i < IN; i++) ion.push({ p: pairs[i % pairs.length], x: X0 + 0.2 + Math.random() * (X1 - X0 - 0.4), face: i % 2, ph: Math.random(), sp: 0.5 + Math.random() * 0.6 });
  const ionGeo = new T.BufferGeometry(); ionGeo.setAttribute('position', new T.BufferAttribute(ionPos, 3));
  const ionMat = new T.PointsMaterial({ color: 0x8fe6ff, size: 0.035, transparent: true, opacity: 0.85, depthWrite: false, blending: T.AdditiveBlending });
  const ions = new T.Points(ionGeo, ionMat); ions.frustumCulled = false; mods.stack.add(ions);

  // The monitored cell sits at the front of its module (battery_module.js).
  const mod = moduleContext(root, mods, M);

  let rate = 0.15;
  return {
    key: 'battery', root, mods, modules: MODULES, layout: LAYOUT, materials: M,
    // the can and the whole module ghost in the exploded view; the cap (with its + interconnect) slides off
    shells: [M.can, M.wrap, M.wrapEdge, M.insul, M.patch, ...mod.materials],
    introOrder: ['can', 'stack', 'interface', 'electrolyte', 'terminal'],
    panels: { L: 'Capacity and charge', R: 'Resistance, voltage and temperature' },
    view: { target: [0.1, 0.1, -1.6], dir: [0.6, 0.42, 1], twin: [4.6, 2.6], hero: [5.4, 3.0], min: 7 },
    groundY: -1.66,
    labels: { stack: [-0.3, -1.75, 0], terminal: [3.5, -1.75, 0], can: [0, 1.75, 0] },
    apply({ modLevel, z, levels }) {
      const tint = (mats, mod, strength) => {
        const lv = modLevel[mod];
        mats.forEach((m) => {
          if (lv < 0) m.emissive.setRGB(0, 0, 0);
          else { m.emissive.set(levels[lv].color); m.emissiveIntensity = strength[lv]; }
        });
      };
      tint([M.stack, M.stackCut], 'stack', [0.2, 0.13, 0.07]);
      tint([M.sepCut], 'interface', [0.45, 0.3, 0.15]);
      // The can warms with peak-temperature drift.
      const heat = Math.max(0, Math.min(1, (z.temp_max_c || 0) / 4));
      M.can.emissive.setRGB(1.0 * heat, 0.42 * heat, 0.12 * heat); M.can.emissiveIntensity = 0.5;
      mod.setHeat(heat);
      const elv = modLevel.electrolyte;
      M.electrolyte.color.set(elv < 0 ? 0x3fa2ff : levels[elv].color);
      rate = 0.12 + 0.12 * Math.max(0, Math.min(1, -(z.capacity_ah || 0) / 4));
    },
    tick(dt, tsec, { reduced, explode }) {
      mod.tick(dt, explode);
      flowMat.opacity = 0.6 * (1 - explode);
      ionMat.opacity = 0.85 * (1 - explode);
      M.electrolyte.opacity = 0.07 * (1 - explode);
      if (reduced) return;
      for (let i = 0; i < N; i++) {
        phase[i] = (phase[i] + dt * rate) % 1;
        const p = path(phase[i], i);
        pos[i * 3] = p[0]; pos[i * 3 + 1] = p[1]; pos[i * 3 + 2] = p[2];
      }
      flowGeo.attributes.position.needsUpdate = true;
      for (let i = 0; i < IN; i++) {
        const o = ion[i];
        o.ph = (o.ph + dt * o.sp * rate * 2.2) % 1;
        const f = o.ph * o.ph * (3 - 2 * o.ph), r = o.p[0] + (o.p[1] - o.p[0]) * f;
        // face 0 is the +Z cut (y = 0), face 1 the +Y cut (z = 0); sit just in front of the face
        ionPos[i * 3] = o.x;
        ionPos[i * 3 + 1] = o.face ? r : 0.012;
        ionPos[i * 3 + 2] = o.face ? 0.012 : r;
      }
      ionGeo.attributes.position.needsUpdate = true;
    },
    resize() {},
    conditionText(c, i) { return c ? `${Math.round(c.ambient_c[i])} °C ambient  ${c.load_a[i].toFixed(1)} A discharge` : ''; },
    dispose() { mod.dispose(); dispose(root); },
  };
}
