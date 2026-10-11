/* Gearbox model: an engine accessory gearbox, cut away at the front, shafts along world X.
 * An input pinion drives an output gear (16 : 35 teeth, involute-like profiles that stay in mesh while
 * turning); each shaft runs in two ball bearings in the end walls; oil sits in the sump. A horizontal and
 * a vertical accelerometer on the casing give the vibration channels (FEMTO gearbox-bearing data), and
 * each radiates rings at a rate and colour set by its measured level.
 *
 * Exploded view: the casing and oil ghost; the gear train slides forward out of the open front, the
 * gears separate along their shafts and the bearings move outward. Nothing passes through anything. */
import { T, physical, metal, lathe, V2, boltCircle, cable, dispose } from './shared.js?v=6.0.0';

const MODULES = [
  { key: 'shaft', name: 'Shafts', explode: [0, 0, 1.5] },
  { key: 'rolling', name: 'Gear mesh', explode: [0, 0, 1.5] },
  { key: 'races', name: 'Bearings', explode: [0, 0, 1.5] },
  { key: 'housing', name: 'Casing', explode: [0, 0, 0] },
];
const Y_IN = 0.7, Y_OUT = -0.9; // shaft heights; centre distance 1.6 = pinion 0.5 + gear 1.1 pitch radii
const NP = 16, NG = 35, RP = 0.5, RG = 1.1;
const XB = 1.55; // bearing stations in the end walls
const BOX = { x0: -1.75, x1: 1.75, y0: -2.25, y1: 1.6, z0: -1.05, z1: 1.05, t: 0.12 };

const LAYOUT = {};
const put = (ax, k, mod, pos) => { LAYOUT[`${ax}_${k}`] = { mod, pos, side: ax === 'h' ? 'L' : 'R' }; };
// Casing: overall level, at each accelerometer
[['rms', 0.18], ['peak', -0.18]].forEach(([k, dx]) => { put('h', k, 'housing', [1.2 + dx, -1.45, 1.42]); put('v', k, 'housing', [0.6 + dx, 2.1, -0.45]); });
// Bearings: impulsive features at the output (h) and input (v) shaft bearings
[['kurt', -1, 0.12], ['crest', -1, -0.12], ['skew', 1, 0.12], ['band4', 1, -0.12]].forEach(([k, side, dy]) => {
  put('h', k, 'races', [side * XB, Y_OUT + dy, 0.62]); put('v', k, 'races', [side * XB, Y_IN + dy, 0.5]);
});
// Gear mesh: mid bands and spectral centroid where the teeth engage
[['band2', -0.16], ['band3', 0.0], ['centroid_khz', 0.16]].forEach(([k, dx]) => {
  put('h', k, 'rolling', [dx, -0.25, 0.32]); put('v', k, 'rolling', [dx, -0.05, 0.32]);
});
// Shafts: low band at the shaft ends
put('h', 'band1', 'shaft', [2.3, Y_OUT, 0.3]); put('v', 'band1', 'shaft', [-2.3, Y_IN, 0.3]);

// Spur gear outline: N teeth around pitch radius r (module m = 2r / N), with a bore and optional lightening holes.
function gearGeometry(r, n, width, bore, holes = 0, phase = 0) {
  const m = (2 * r) / n, ra = r + m, rf = r - 1.25 * m, pitch = (Math.PI * 2) / n;
  const s = new T.Shape();
  for (let i = 0; i < n; i++) {
    const c = phase + i * pitch;
    const pts = [[rf, c - 0.5 * pitch], [rf, c - 0.28 * pitch], [r, c - 0.2 * pitch], [ra, c - 0.12 * pitch],
      [ra, c + 0.12 * pitch], [r, c + 0.2 * pitch], [rf, c + 0.28 * pitch]];
    pts.forEach(([rad, a], k) => { const x = rad * Math.cos(a), y = rad * Math.sin(a); (i === 0 && k === 0) ? s.moveTo(x, y) : s.lineTo(x, y); });
  }
  s.closePath();
  const hole = (cx, cy, rr) => { const p = new T.Path(); p.absarc(cx, cy, rr, 0, Math.PI * 2, true); s.holes.push(p); };
  hole(0, 0, bore);
  for (let k = 0; k < holes; k++) { const a = (k / holes) * Math.PI * 2 + 0.4; hole(Math.cos(a) * r * 0.55, Math.sin(a) * r * 0.55, r * 0.17); }
  const g = new T.ExtrudeGeometry(s, { depth: width, bevelEnabled: true, bevelThickness: 0.02, bevelSize: 0.015, bevelSegments: 2, curveSegments: 24 });
  g.translate(0, 0, -width / 2);
  g.rotateY(Math.PI / 2); // shape (x, y) -> world (Y = y, Z = -x); gear axis along world X
  return g;
}

// A deep-groove ball bearing around X: outer and inner ring sections plus a ring of balls in a cage.
function bearing(M, rOut, rIn, width) {
  const g = new T.Group(), mid = (rOut + rIn) / 2, ball = (rOut - rIn) * 0.32;
  const ringP = (a, b) => [V2(a, -width / 2), V2(b, -width / 2), V2(b, width / 2), V2(a, width / 2), V2(a, -width / 2)];
  g.add(lathe(ringP(mid + ball * 0.75, rOut), M.race, 64), lathe(ringP(rIn, mid - ball * 0.75), M.race, 64));
  const cage = new T.Group(); g.add(cage);
  const geo = new T.SphereGeometry(ball, 20, 14), n = 9;
  for (let i = 0; i < n; i++) { const a = (i / n) * Math.PI * 2, b = new T.Mesh(geo, M.ball); b.position.set(0, mid * Math.cos(a), mid * Math.sin(a)); cage.add(b); }
  const band = new T.Mesh(new T.TorusGeometry(mid, ball * 0.25, 8, 64), M.cage); band.rotation.y = Math.PI / 2; cage.add(band);
  return { group: g, cage };
}

function plate(w, h, d, mat, x, y, z) {
  const m = new T.Mesh(new T.RoundedBoxGeometry(w, h, d, 2, Math.min(0.04, w / 3, h / 3, d / 3)), mat);
  m.position.set(x, y, z); return m;
}

function accelerometer(M, at, normal, cableTo) {
  const g = new T.Group();
  const base = new T.Mesh(new T.CylinderGeometry(0.17, 0.17, 0.06, 6), M.sensorCap); base.position.y = 0.03;
  const body = new T.Mesh(new T.CylinderGeometry(0.13, 0.13, 0.3, 32), M.sensor); body.position.y = 0.21;
  const band = new T.Mesh(new T.CylinderGeometry(0.132, 0.132, 0.025, 32), M.brand); band.position.y = 0.29;
  const conn = new T.Mesh(new T.CylinderGeometry(0.05, 0.06, 0.1, 16), M.sensorCap); conn.position.y = 0.41;
  g.add(base, body, band, conn);
  const n = new T.Vector3(...normal).normalize();
  g.position.set(...at); g.quaternion.setFromUnitVectors(new T.Vector3(0, 1, 0), n);
  const tip = new T.Vector3(...at).addScaledVector(n, 0.46);
  const c = cable([[tip.x, tip.y, tip.z], [tip.x + n.x * 0.25, tip.y + n.y * 0.25, tip.z + n.z * 0.25], ...cableTo], 0.03, M.cable);
  return { group: g, cable: c, tip, normal: n };
}

export function build() {
  const M = {
    casing: physical(0x2b3540, 0.55, 0.35, { emissive: 0x000000, clearcoat: 0.35, clearcoatRoughness: 0.4 }),
    flange: physical(0x3a4652, 0.4, 0.6, { emissive: 0x000000 }),
    gear: physical(0xb9c1ca, 0.22, 1.0, { emissive: 0x000000 }),
    pinion: physical(0xc9a46a, 0.25, 1.0, { emissive: 0x000000 }),
    shaft: physical(0x8c95a0, 0.24, 0.95, { emissive: 0x000000 }),
    race: physical(0xb3bac2, 0.32, 1.0, { emissive: 0x000000, side: T.DoubleSide, clearcoat: 0.2 }),
    ball: physical(0xd4d9df, 0.18, 1.0, { emissive: 0x000000, clearcoat: 0.3 }),
    cage: physical(0xb38d55, 0.32, 0.9),
    bolt: physical(0xa3abb4, 0.3, 0.95),
    oil: new T.MeshPhysicalMaterial({ color: 0xb8862b, roughness: 0.1, metalness: 0, transmission: 0, transparent: true, opacity: 0.38, depthWrite: false }),
    sensor: physical(0x1c2128, 0.32, 0.7), sensorCap: physical(0xb9c0c8, 0.22, 1.0),
    brand: new T.MeshStandardMaterial({ color: 0x1683f2, emissive: 0x1683f2, emissiveIntensity: 0.6, roughness: 0.4 }),
    cable: new T.MeshStandardMaterial({ color: 0x14181d, roughness: 0.55, metalness: 0.1 }),
    glass: new T.MeshPhysicalMaterial({ color: 0xb8862b, roughness: 0.05, metalness: 0, transparent: true, opacity: 0.55 }),
  };

  const root = new T.Group();
  const mods = {};
  MODULES.forEach((m) => { const g = new T.Group(); mods[m.key] = g; root.add(g); });

  // Casing: back wall, floor, back half of the top and of both end walls (the front is cut away), feet, bolted
  // split-line flange along the cut, a breather and an oil sight glass.
  const { x0, x1, y0, y1, z0, z1, t } = BOX, W = x1 - x0, Hh = y1 - y0;
  const casing = new T.Group(); mods.housing.add(casing);
  casing.add(plate(W + 2 * t, Hh + 2 * t, t, M.casing, 0, (y0 + y1) / 2, z0 - t / 2));        // back wall
  casing.add(plate(W + 2 * t, t, z1 - z0 + t, M.casing, 0, y0 - t / 2, (z0 + z1) / 2 - t / 2)); // floor
  casing.add(plate(W + 2 * t, t, (z1 - z0) / 2, M.casing, 0, y1 + t / 2, z0 + (z1 - z0) / 4)); // top, back half
  [x0 - t / 2, x1 + t / 2].forEach((x) => casing.add(plate(t, Hh + 2 * t, (z1 - z0) / 2 + t, M.casing, x, (y0 + y1) / 2, z0 + (z1 - z0) / 4 - t / 2)));
  casing.add(plate(W + 2 * t, 0.08, 0.12, M.flange, 0, y1 + t + 0.04, 0.0));                 // flange on the top cut
  [x0 - t / 2, x1 + t / 2].forEach((x) => casing.add(plate(0.16, Hh + 2 * t, 0.08, M.flange, x, (y0 + y1) / 2, 0.02)));
  for (let i = 0; i < 6; i++) { const b = new T.Mesh(new T.CylinderGeometry(0.05, 0.05, 0.05, 6), M.bolt); b.position.set(x0 + 0.25 + i * (W - 0.5) / 5, y1 + t + 0.105, 0); casing.add(b); }
  [-1, 1].forEach((sd) => casing.add(plate(0.9, 0.18, z1 - z0 + 0.6, M.casing, sd * (W / 2 - 0.2), y0 - t - 0.09, (z0 + z1) / 2)));
  const breather = lathe([V2(0, 0), V2(0.1, 0), V2(0.1, 0.12), V2(0.14, 0.14), V2(0.14, 0.22), V2(0, 0.24)], M.bolt, 24);
  breather.rotation.set(0, 0, 0); breather.position.set(-0.9, y1 + t, -0.5); casing.add(breather);
  const sight = new T.Mesh(new T.CylinderGeometry(0.16, 0.16, 0.04, 32), M.glass); sight.rotation.z = Math.PI / 2; sight.position.set(x1 + t + 0.01, y0 + 0.45, -0.45); casing.add(sight);
  // Bearing seats in the end walls (bosses round each bore)
  [[Y_IN, 0.5], [Y_OUT, 0.66]].forEach(([y, r]) => [-1, 1].forEach((sd) => {
    const boss = lathe([V2(r * 0.86, -0.16), V2(r, -0.16), V2(r, 0.16), V2(r * 0.86, 0.16), V2(r * 0.86, -0.16)], M.casing, 48, Math.PI * 0.5, Math.PI);
    boss.position.set(sd * (x1 + t / 2), y, 0); casing.add(boss);
  }));
  // Oil in the sump; the gear dips into it.
  const oil = new T.Mesh(new T.BoxGeometry(W - 0.04, 0.62, z1 - z0 - 0.04), M.oil); oil.position.set(0, y0 + 0.31, 0); oil.userData.receive = false; casing.add(oil);

  // Shafts: input (left coupling) and output (right flange), each turning with its gear.
  const inShaft = new T.Group(), outShaft = new T.Group(); inShaft.position.y = Y_IN; outShaft.position.y = Y_OUT;
  mods.shaft.add(inShaft, outShaft);
  inShaft.add(lathe([V2(0, -3.0), V2(0.17, -3.0), V2(0.2, -2.97), V2(0.2, -1.2), V2(0.24, -1.15), V2(0.24, 1.2), V2(0.2, 1.25), V2(0.2, 2.0), V2(0.17, 2.03), V2(0, 2.03)], M.shaft, 40));
  inShaft.add(lathe([V2(0.2, -3.05), V2(0.46, -3.05), V2(0.5, -3.0), V2(0.5, -2.62), V2(0.46, -2.58), V2(0.2, -2.58), V2(0.2, -3.05)], M.flange, 40));
  inShaft.add(boltCircle({ r: 0.36, x: -2.58, count: 6, size: 0.04, height: 0.04, facing: 1, mat: M.bolt, arc: Math.PI * 2 }));
  outShaft.add(lathe([V2(0, -2.03), V2(0.24, -2.03), V2(0.28, -2.0), V2(0.28, -1.2), V2(0.32, -1.15), V2(0.32, 1.2), V2(0.28, 1.25), V2(0.28, 3.0), V2(0.24, 3.03), V2(0, 3.03)], M.shaft, 40));
  outShaft.add(lathe([V2(0.28, 2.62), V2(0.64, 2.62), V2(0.68, 2.66), V2(0.68, 2.86), V2(0.64, 2.9), V2(0.28, 2.9), V2(0.28, 2.62)], M.flange, 48));
  outShaft.add(boltCircle({ r: 0.5, x: 2.9, count: 8, size: 0.045, height: 0.05, facing: 1, mat: M.bolt, arc: Math.PI * 2 }));
  [inShaft, outShaft].forEach((s) => { const key = new T.Mesh(new T.BoxGeometry(0.5, 0.07, 0.07), M.bolt); key.position.set(0, s === inShaft ? 0.25 : 0.33, 0); s.add(key); });

  // Gears: pinion tooth faces the gear (-Y), the gear presents a gap to the pinion (+Y), so they mesh.
  const pinion = new T.Mesh(gearGeometry(RP, NP, 0.5, 0.24, 0, -Math.PI / 2), M.pinion);
  const gear = new T.Mesh(gearGeometry(RG, NG, 0.46, 0.32, 5, Math.PI / 2 + Math.PI / NG), M.gear);
  const pinionG = new T.Group(), gearG = new T.Group(); pinionG.position.y = Y_IN; gearG.position.y = Y_OUT;
  pinionG.add(pinion); gearG.add(gear);
  gearG.add(lathe([V2(0.32, -0.33), V2(0.5, -0.33), V2(0.5, 0.33), V2(0.32, 0.33), V2(0.32, -0.33)], M.gear, 48)); // hub
  mods.rolling.add(pinionG, gearG);

  // Bearings: two per shaft, in the end-wall seats.
  const bear = [];
  [[Y_IN, 0.43, 0.24], [Y_OUT, 0.57, 0.32]].forEach(([y, ro, ri]) => [-1, 1].forEach((sd) => {
    const b = bearing(M, ro, ri, 0.26); b.group.position.set(sd * XB, y, 0); b.side = sd; b.input = y === Y_IN;
    mods.races.add(b.group); bear.push(b);
  }));

  // Accelerometers on the casing: horizontal on the front flange by the output bearing, vertical on the top.
  const accH = accelerometer(M, [1.2, -1.45, z1 + 0.06], [0, 0, 1], [[1.5, -1.9, 1.9], [1.9, -2.55, 2.4]]);
  const accV = accelerometer(M, [0.6, y1 + t, -0.45], [0, 1, 0], [[0.9, 2.5, -0.9], [2.0, 1.4, -1.4], [2.6, -2.55, -1.8]]);
  mods.housing.add(accH.group, accV.group, accH.cable, accV.cable);

  const waveMat = () => new T.MeshBasicMaterial({ color: 0x5fd4f8, transparent: true, opacity: 0, depthWrite: false,
    blending: T.AdditiveBlending, side: T.DoubleSide, toneMapped: false });
  const waves = [accH, accV].map((acc) => [0, 1, 2].map(() => {
    const w = new T.Mesh(new T.RingGeometry(0.9, 1.0, 64), waveMat());
    w.position.copy(acc.tip); w.quaternion.setFromUnitVectors(new T.Vector3(0, 0, 1), acc.normal); mods.housing.add(w); return w;
  }));
  const vib = [{ level: 0, color: new T.Color(0x5fd4f8) }, { level: 0, color: new T.Color(0x5fd4f8) }];

  let angle = 0, spin = 1, shake = 0;
  const home = casing.position.clone();
  return {
    key: 'bearing', root, mods, modules: MODULES, layout: LAYOUT, materials: M,
    shells: [M.casing, M.flange, M.oil, M.glass],
    panels: { L: 'Horizontal accelerometer', R: 'Vertical accelerometer' },
    view: { target: [0, -0.35, 0], dir: [0.55, 0.38, 1], twin: [3.7, 3.0], hero: [4.3, 3.4], min: 7 },
    groundY: y0 - t - 0.18,
    labels: { shaft: [-2.6, Y_IN + 0.75, 1.5], rolling: [0, 2.0, 1.5], races: [XB + 0.5, Y_OUT - 0.9, 1.5], housing: [0, y1 + 0.6, -0.4] },
    apply({ modLevel, z, levels }) {
      const tint = (mats, mod, strength) => mats.forEach((mat) => {
        const lv = modLevel[mod];
        if (lv < 0) mat.emissive.setRGB(0, 0, 0); else { mat.emissive.set(levels[lv].color); mat.emissiveIntensity = strength[lv]; }
      });
      tint([M.race, M.ball], 'races', [0.22, 0.14, 0.06]);
      tint([M.gear, M.pinion], 'rolling', [0.2, 0.13, 0.06]);
      tint([M.shaft], 'shaft', [0.12, 0.08, 0.04]);
      tint([M.casing, M.flange], 'housing', [0.06, 0.04, 0.02]);
      const level = Math.max(z.h_rms || 0, z.v_rms || 0);
      shake = Math.max(0, Math.min(1, level / 6)) * 0.012;
      [z.h_rms || 0, z.v_rms || 0].forEach((v, i) => {
        vib[i].level = Math.max(0, Math.min(1, v / 4));
        const lv = levels.findIndex((l) => v >= l.at);
        vib[i].color.set(lv < 0 ? 0x5fd4f8 : levels[lv].color);
      });
    },
    tick(dt, tsec, { reduced, explode }) {
      // Exploded view: gears part along their shafts, bearings move outward (all inside their own lanes).
      pinionG.position.x = -0.55 * explode; gearG.position.x = 0.55 * explode;
      bear.forEach((b) => { b.group.position.x = b.side * (XB + 0.45 * explode); });
      waves.forEach((set, i) => set.forEach((w, j) => {
        if (reduced || explode > 0.5) { w.visible = false; return; }
        const rate = 0.35 + vib[i].level * 0.9, ph = (tsec * rate + j / 3) % 1;
        w.visible = true;
        w.scale.setScalar(0.1 + ph * (0.42 + vib[i].level * 0.45));
        w.material.color.copy(vib[i].color);
        w.material.opacity = (1 - ph) * (0.16 + vib[i].level * 0.42);
      }));
      if (reduced) { casing.position.copy(home); return; }
      angle += dt * 2.4 * spin;
      inShaft.rotation.x = pinionG.rotation.x = angle;
      outShaft.rotation.x = gearG.rotation.x = -angle * (NP / NG);
      bear.forEach((b) => { b.cage.rotation.x = (b.input ? angle : -angle * (NP / NG)) * 0.4; });
      casing.position.set(home.x, home.y + shake * Math.sin(tsec * 61), home.z + shake * Math.sin(tsec * 47 + 1));
    },
    resize() {},
    conditionText(c, i) {
      if (!c) return '';
      spin = Math.max(0.4, c.speed_rpm[i] / 1800);
      return `${Math.round(c.speed_rpm[i])} rpm  ${c.load_kn[i].toFixed(1)} kN radial load`;
    },
    dispose() { dispose(root); },
  };
}
