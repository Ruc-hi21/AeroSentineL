/* Hydraulic model: a hydraulic power unit like the ZeMA test rig, laid out along world X on a skid.
 * Reservoir and air-oil cooler (cooling circuit), electric motor and pump with a flow meter, a switching
 * valve on its manifold, and a bladder accumulator, joined by pipes. Oil particles run round the circuit
 * (warm before the cooler, cool after), pressure gauges follow their channels, the cooler fan turns and the
 * valve's indicator steps with the load cycle. Parts take the colour of their predicted condition.
 *
 * Exploded view: the pipes ghost and each unit lifts straight up off the skid; nothing is above them. */
import { T, V2, physical, metal, lathe, cable, canvasTexture, dispose } from './shared.js?v=6.0.0';

const MODULES = [
  { key: 'pump', name: 'Pump and motor', explode: [0, 1.3, 0] },
  { key: 'valve', name: 'Switching valve', explode: [0, 1.7, 0] },
  { key: 'accumulator', name: 'Accumulator', explode: [0, 1.2, 0] },
  { key: 'cooler', name: 'Cooler and tank', explode: [0, 1.0, 0] },
];
const FLOOR = -1.9;
// Stations (world positions) used by the layout and the pipe runs.
const P = {
  tankOut: [-1.6, -1.45, 0.55], pumpIn: [-0.55, -1.25, 0.55], pumpOut: [0.62, -0.95, 0.55], meter: [1.05, -0.55, 0.55],
  valveIn: [1.55, -0.1, 0.5], valveA: [2.2, -0.05, 0.5], acc: [2.95, -1.2, -0.25], ret: [1.7, -0.05, -0.15],
  coolIn: [0.2, -0.2, -1.0], coolOut: [-1.0, -0.2, -1.0], tankIn: [-2.4, -0.25, -0.55],
};
const LAYOUT = {};
const put = (k, mod, pos, side) => { LAYOUT[k] = { mod, pos, side }; };
// Left panel: pump and valve. Right panel: main-flow profile, accumulator and cooling circuit.
put('ps1', 'pump', [0.62, -0.62, 0.95], 'L');
put('eps1', 'pump', [-1.05, -0.62, 0.55], 'L');
put('vs1', 'pump', [0.35, -0.75, 0.95], 'L');
put('se', 'pump', [0.1, -1.0, 1.0], 'L');
put('fs1', 'pump', [1.05, -0.3, 0.85], 'R');
for (let i = 0; i < 6; i++) put(`fs1_w${i}`, 'pump', [0.88 + i * 0.07, -0.15 + (i % 2) * 0.1, 0.8], 'R');
put('ps2', 'valve', [2.25, 0.45, 0.85], 'L');
put('ps3', 'valve', [2.35, 0.05, 0.75], 'L');
for (let i = 0; i < 6; i++) put(`ps2_w${i}`, 'valve', [1.62 + i * 0.12, 0.58 + (i % 2) * 0.1, 0.55], 'L');
put('ps4', 'accumulator', [2.95, -1.45, 0.25], 'R');
put('ps5', 'accumulator', [1.7, -0.2, -0.45], 'R');
put('ps6', 'accumulator', [-1.75, -0.2, -0.55], 'R');
put('fs2', 'cooler', [-0.4, -0.2, -0.8], 'R');
put('ts1', 'cooler', [-2.6, -0.85, 0.6], 'R');
put('ts2', 'cooler', [-1.15, -1.4, 0.75], 'R');
put('ts3', 'cooler', [0.25, 0.25, -0.75], 'R');
put('ts4', 'cooler', [-1.05, 0.25, -0.75], 'R');
put('ce', 'cooler', [-0.4, 0.75, -0.85], 'R');
put('cp', 'cooler', [-0.4, 0.35, -0.85], 'R');

const dialTex = () => canvasTexture(256, 256, (g, w, h) => {
  g.fillStyle = '#e8ebef'; g.beginPath(); g.arc(128, 128, 124, 0, Math.PI * 2); g.fill();
  g.strokeStyle = '#1d2126'; g.lineWidth = 4;
  for (let i = 0; i <= 10; i++) {
    const a = Math.PI * 0.75 + (i / 10) * Math.PI * 1.5;
    g.beginPath(); g.moveTo(128 + Math.cos(a) * 92, 128 + Math.sin(a) * 92); g.lineTo(128 + Math.cos(a) * 112, 128 + Math.sin(a) * 112); g.stroke();
  }
  g.strokeStyle = '#fa4d56'; g.lineWidth = 8; g.beginPath(); g.arc(128, 128, 104, Math.PI * 1.95, Math.PI * 2.25); g.stroke();
  g.fillStyle = '#1d2126'; g.font = '600 26px sans-serif'; g.textAlign = 'center'; g.fillText('bar', 128, 190);
});

function gauge(M, pos, normal) {
  const g = new T.Group();
  const body = new T.Mesh(new T.CylinderGeometry(0.2, 0.2, 0.09, 40), M.chrome); body.rotation.x = Math.PI / 2;
  const face = new T.Mesh(new T.CircleGeometry(0.175, 40), M.dial); face.position.z = 0.047;
  const needle = new T.Mesh(new T.BoxGeometry(0.012, 0.15, 0.008), M.needle); needle.geometry.translate(0, 0.06, 0);
  const pivot = new T.Group(); pivot.position.z = 0.055; pivot.add(needle);
  const stem = new T.Mesh(new T.CylinderGeometry(0.035, 0.035, 0.2, 12), M.brass); stem.position.y = -0.27;
  g.add(body, face, pivot, stem);
  g.position.set(...pos); g.lookAt(g.position.clone().add(new T.Vector3(...normal)));
  return { group: g, needle: pivot };
}

function finnedCylinder(r, len, fins, mat) {
  const g = new T.Group();
  const core = new T.Mesh(new T.CylinderGeometry(r, r, len, 48), mat); core.rotation.z = Math.PI / 2; g.add(core);
  for (let i = 0; i < fins; i++) {
    const a = (i / fins) * Math.PI * 2, f = new T.Mesh(new T.BoxGeometry(len * 0.92, 0.06, 0.02), mat);
    f.position.set(0, (r + 0.025) * Math.cos(a), (r + 0.025) * Math.sin(a)); f.rotation.x = -a; g.add(f);
  }
  return g;
}

export function build() {
  const M = {
    skid: physical(0x22282f, 0.6, 0.4),
    tank: physical(0x2b3540, 0.5, 0.35, { emissive: 0x000000, clearcoat: 0.35 }),
    motor: physical(0x1f4c8f, 0.45, 0.35, { emissive: 0x000000, clearcoat: 0.5 }),
    pump: physical(0x9aa4af, 0.3, 0.9, { emissive: 0x000000 }),
    valve: physical(0xb5bcc4, 0.28, 0.95, { emissive: 0x000000 }),
    coil: physical(0x15181c, 0.5, 0.2, { emissive: 0x000000 }),
    acc: physical(0xb7392f, 0.38, 0.35, { emissive: 0x000000, clearcoat: 0.6 }),
    cooler: physical(0x3a4652, 0.4, 0.7, { emissive: 0x000000 }),
    fins: metal(0xa9b2bc, 0.35, 0.9),
    pipe: physical(0x7d8792, 0.3, 0.9),
    hose: new T.MeshStandardMaterial({ color: 0x15191e, roughness: 0.6, metalness: 0.05 }),
    chrome: physical(0xc9cfd6, 0.18, 1.0), brass: physical(0xc59b4f, 0.3, 1.0),
    dial: new T.MeshBasicMaterial({ map: dialTex() }), needle: new T.MeshBasicMaterial({ color: 0x15181c }),
    glass: new T.MeshPhysicalMaterial({ color: 0xb8862b, roughness: 0.05, transparent: true, opacity: 0.6 }),
    led: new T.MeshBasicMaterial({ color: 0x5fd4f8, toneMapped: false }),
    fan: physical(0x2a3038, 0.5, 0.5),
  };
  const root = new T.Group();
  const mods = {};
  MODULES.forEach((m) => { const g = new T.Group(); mods[m.key] = g; root.add(g); });
  const box = (w, h, d, mat, x, y, z, r = 0.05) => { const m = new T.Mesh(new T.RoundedBoxGeometry(w, h, d, 3, r), mat); m.position.set(x, y, z); return m; };

  // Skid: the base frame everything bolts to (does not move).
  root.add(box(7.4, 0.14, 3.0, M.skid, 0, FLOOR + 0.07, 0, 0.03));
  [-1.35, 1.35].forEach((z) => root.add(box(7.6, 0.1, 0.16, M.skid, 0, FLOOR + 0.05, z, 0.02)));

  // Cooler and tank: reservoir with filler and sight glass, air-oil cooler panel with a fan behind it.
  const tank = box(1.5, 1.4, 1.9, M.tank, -2.55, FLOOR + 0.84, 0.05, 0.08); mods.cooler.add(tank);
  const filler = lathe([V2(0, 0), V2(0.16, 0), V2(0.16, 0.12), V2(0.2, 0.14), V2(0.2, 0.2), V2(0, 0.2)], M.chrome, 32);
  filler.rotation.z = 0; filler.position.set(-2.9, FLOOR + 1.54, 0.4); mods.cooler.add(filler);
  const sight = new T.Mesh(new T.BoxGeometry(0.06, 0.5, 0.14), M.glass); sight.position.set(-1.79, FLOOR + 0.85, 0.65); mods.cooler.add(sight);
  const core = new T.Group(); core.position.set(-0.4, 0.25, -1.05); mods.cooler.add(core);
  core.add(box(1.9, 1.3, 0.22, M.cooler, 0, 0, 0, 0.04));
  for (let i = 0; i < 22; i++) { const f = new T.Mesh(new T.BoxGeometry(0.012, 1.12, 0.26), M.fins); f.position.set(-0.85 + i * 0.081, 0, 0.0); core.add(f); }
  const shroud = new T.Mesh(new T.TorusGeometry(0.5, 0.05, 10, 48), M.cooler); shroud.position.set(0, 0, -0.2); core.add(shroud);
  const fan = new T.Group(); fan.position.set(0, 0, -0.22); core.add(fan);
  for (let i = 0; i < 6; i++) { const b = new T.Mesh(new T.BoxGeometry(0.1, 0.42, 0.02), M.fan); b.geometry.translate(0, 0.23, 0); b.rotation.z = (i / 6) * Math.PI * 2; b.rotation.y = 0.35; fan.add(b); }
  core.add(...[-0.85, 0.85].map((x) => box(0.12, 0.45, 0.12, M.skid, x, -0.85, 0.05, 0.02)));

  // Pump and motor: motor with cooling fins and a fan cover, bell housing, gear pump, flow meter on the outlet.
  const motor = finnedCylinder(0.42, 1.2, 24, M.motor); motor.position.set(-1.05, -1.05, 0.55); mods.pump.add(motor);
  const cover = lathe([V2(0, -0.62), V2(0.36, -0.62), V2(0.44, -0.55), V2(0.44, -0.45), V2(0, -0.45)], M.motor, 40); cover.position.set(-1.05, -1.05, 0.55); mods.pump.add(cover);
  mods.pump.add(box(0.5, 0.45, 0.62, M.motor, -1.05, -1.35, 0.55, 0.03));
  const bell = lathe([V2(0.42, 0), V2(0.42, 0.06), V2(0.3, 0.35), V2(0.3, 0.42), V2(0.0, 0.42), V2(0, 0)], M.pump, 40); bell.rotation.z = -Math.PI / 2;
  bell.position.set(-0.45, -1.05, 0.55); mods.pump.add(bell);
  mods.pump.add(box(0.48, 0.5, 0.5, M.pump, 0.25, -1.05, 0.55, 0.05));
  const coupling = new T.Mesh(new T.CylinderGeometry(0.16, 0.16, 0.08, 24), M.chrome); coupling.rotation.z = Math.PI / 2; coupling.position.set(-0.2, -1.05, 0.55); mods.pump.add(coupling);
  const meter = new T.Mesh(new T.CylinderGeometry(0.17, 0.17, 0.38, 28), M.valve); meter.position.set(1.05, -0.55, 0.55); mods.pump.add(meter);
  const meterHead = box(0.26, 0.2, 0.22, M.coil, 1.05, -0.28, 0.55, 0.03); mods.pump.add(meterHead);
  const g1 = gauge(M, [0.62, -0.42, 0.62], [0, 0.3, 1]); mods.pump.add(g1.group);

  // Switching valve: manifold block on a stand, solenoid valve with coil and indicator on top.
  mods.valve.add(box(0.12, 1.4, 0.12, M.skid, 1.4, FLOOR + 0.7, 0.5, 0.02), box(0.12, 1.4, 0.12, M.skid, 2.3, FLOOR + 0.7, 0.5, 0.02));
  mods.valve.add(box(1.2, 0.36, 0.6, M.valve, 1.85, -0.15, 0.5, 0.04));
  mods.valve.add(box(0.62, 0.3, 0.42, M.valve, 1.85, 0.18, 0.5, 0.04));
  [1.45, 2.25].forEach((x) => { const c = new T.Mesh(new T.CylinderGeometry(0.13, 0.13, 0.36, 24), M.coil); c.rotation.z = Math.PI / 2; c.position.set(x, 0.18, 0.5); mods.valve.add(c); });
  const led = new T.Mesh(new T.SphereGeometry(0.035, 12, 10), M.led); led.position.set(1.85, 0.36, 0.72); mods.valve.add(led);
  const g2 = gauge(M, [2.2, 0.42, 0.62], [0, 0.3, 1]); mods.valve.add(g2.group);

  // Accumulator: bladder bottle with a gas valve and a pressure gauge at its base.
  const bottle = lathe([V2(0, -1.75), V2(0.28, -1.72), V2(0.38, -1.6), V2(0.38, 0.05), V2(0.32, 0.28), V2(0.16, 0.4), V2(0, 0.42)].map((p) => V2(p.x, p.y)), M.acc, 48);
  bottle.rotation.z = 0; // lathe() lays parts along X; the bottle stands upright on Y
  bottle.position.set(2.95, 0, -0.25); mods.accumulator.add(bottle);
  const gasValve = new T.Mesh(new T.CylinderGeometry(0.06, 0.06, 0.16, 16), M.brass); gasValve.position.set(2.95, 0.5, -0.25); mods.accumulator.add(gasValve);
  mods.accumulator.add(box(0.7, 0.12, 0.7, M.skid, 2.95, FLOOR + 0.2, -0.25, 0.02));
  const g3 = gauge(M, [2.95, -1.25, 0.2], [0, 0.2, 1]); mods.accumulator.add(g3.group);

  // Pipes: pressure line (steel) and suction, return and cooling lines (hose). They ghost in the exploded view.
  const runs = {
    suction: [P.tankOut, [-1.2, -1.45, 0.55], P.pumpIn],
    pressure: [P.pumpOut, [0.85, -0.95, 0.55], [1.05, -0.78, 0.55], P.meter, [1.05, -0.2, 0.55], P.valveIn],
    work: [P.valveA, [2.6, -0.05, 0.4], [2.95, -0.4, 0.05], [2.95, -0.9, -0.1], P.acc],
    ret: [[1.85, -0.15, 0.2], P.ret, [1.0, -0.2, -0.6], P.coolIn],
    cool: [P.coolOut, [-1.6, -0.2, -0.9], [-2.1, -0.25, -0.75], P.tankIn],
  };
  const pipes = new T.Group(); root.add(pipes);
  const curves = {};
  for (const [name, pts] of Object.entries(runs)) {
    const c = new T.CatmullRomCurve3(pts.map((p) => new T.Vector3(...p)), false, 'centripetal', 0.3);
    curves[name] = c;
    pipes.add(new T.Mesh(new T.TubeGeometry(c, 64, name === 'pressure' || name === 'work' ? 0.05 : 0.065, 12, false),
      name === 'pressure' || name === 'work' ? M.pipe : M.hose));
  }

  // Oil: particles running round the circuit, warm (amber) until the cooler, cool (blue) after it.
  const order = ['suction', 'pressure', 'work', 'ret', 'cool'];
  const N = 260, pos = new Float32Array(N * 3), col = new Float32Array(N * 3), ph = new Float32Array(N), run = new Uint8Array(N);
  for (let i = 0; i < N; i++) { ph[i] = Math.random(); run[i] = i % order.length; }
  const oilGeo = new T.BufferGeometry();
  oilGeo.setAttribute('position', new T.BufferAttribute(pos, 3)); oilGeo.setAttribute('color', new T.BufferAttribute(col, 3));
  const oilMat = new T.PointsMaterial({ size: 0.055, vertexColors: true, transparent: true, opacity: 0.85, depthWrite: false, blending: T.AdditiveBlending });
  const oil = new T.Points(oilGeo, oilMat); oil.frustumCulled = false; root.add(oil);
  const warm = new T.Color(0xff9a3c), cool = new T.Color(0x5fd4f8), tmp = new T.Vector3(), c3 = new T.Color();

  let flowRate = 0.3, fanRate = 1, heat = 0, needle = [0, 0, 0];
  return {
    key: 'hydraulic', root, mods, modules: MODULES, layout: LAYOUT, materials: M,
    shells: [M.pipe, M.hose],
    panels: { L: 'Pump and valve', R: 'Flow, accumulator and cooling' },
    view: { target: [0.1, -0.7, 0], dir: [0.45, 0.55, 1], twin: [4.4, 2.0], hero: [4.6, 2.3], min: 7 },
    groundY: FLOOR,
    labels: { pump: [-0.4, 0.4, 0.9], valve: [1.85, 1.3, 0.6], accumulator: [2.95, 1.1, -0.2], cooler: [-1.4, 1.4, -0.6] },
    apply({ modLevel, z, levels }) {
      const tint = (mats, mod, strength) => mats.forEach((mat) => {
        const lv = modLevel[mod];
        if (lv < 0) mat.emissive.setRGB(0, 0, 0); else { mat.emissive.set(levels[lv].color); mat.emissiveIntensity = strength[lv]; }
      });
      tint([M.motor, M.pump], 'pump', [0.28, 0.18, 0.08]);
      tint([M.valve, M.coil], 'valve', [0.3, 0.2, 0.08]);
      tint([M.acc], 'accumulator', [0.25, 0.16, 0.07]);
      tint([M.tank, M.cooler], 'cooler', [0.2, 0.13, 0.06]);
      // Drift moves the gauge needles and sets the oil pace and the cooler's heat.
      needle = [z.ps1 || 0, z.ps2 || 0, z.ps4 || 0];
      flowRate = 0.22 + 0.08 * Math.max(-2, Math.min(2, -(z.fs1 || 0)));
      heat = Math.max(0, Math.min(1, ((z.ts1 || 0) + (z.ts3 || 0)) / 6));
      fanRate = 1 + Math.max(0, Math.min(1, (z.cp || 0) / 4));
    },
    tick(dt, tsec, { reduced, explode }) {
      oilMat.opacity = 0.85 * (1 - explode);
      [g1, g2, g3].forEach((g, i) => { g.needle.rotation.z = -(0.15 + 0.12 * Math.max(-3, Math.min(3, needle[i]))); });
      if (reduced) return;
      fan.rotation.z += dt * 9 * fanRate;
      coupling.rotation.x += dt * 12;
      led.material.color.set(Math.floor(tsec / 3) % 2 ? 0x5fd4f8 : 0x0f2a3a); // valve switches with the load cycle
      for (let i = 0; i < N; i++) {
        ph[i] += dt * flowRate * (run[i] === 1 ? 1.6 : 1);
        if (ph[i] >= 1) { ph[i] -= 1; run[i] = (run[i] + 1) % order.length; }
        curves[order[run[i]]].getPointAt(ph[i], tmp);
        pos[i * 3] = tmp.x; pos[i * 3 + 1] = tmp.y; pos[i * 3 + 2] = tmp.z;
        const r = order[run[i]];
        c3.copy(r === 'cool' ? cool : warm);
        if (r === 'ret') c3.lerp(new T.Color(0xff5a1f), heat * ph[i]);
        col[i * 3] = c3.r; col[i * 3 + 1] = c3.g; col[i * 3 + 2] = c3.b;
      }
      oilGeo.attributes.position.needsUpdate = true; oilGeo.attributes.color.needsUpdate = true;
    },
    resize() {},
    conditionText() { return 'constant 60 s load cycle'; },
    dispose() { dispose(root); },
  };
}
