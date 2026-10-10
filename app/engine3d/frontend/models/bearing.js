/* Bearing model: a sectioned deep-groove ball bearing on a shaft, in a housing with a horizontal and a
 * vertical accelerometer (as on the PRONOSTIA rig). The shaft turns, the balls orbit at cage speed,
 * parts take the colour of their drifting channels and the housing trembles faintly with vibration level. */
import { T, V2, metal, lathe, axialCylinder, sectionCut, ring, dispose } from './shared.js';

const MODULES = [
  { key: 'shaft', name: 'Shaft', explode: [-2.4, 0, 0] },
  { key: 'rolling', name: 'Rolling elements', explode: [0, 0, 0] },
  { key: 'races', name: 'Races', explode: [0, 0, 0] },
  { key: 'housing', name: 'Housing', explode: [0, 2.6, 0] },
];
const RP = 1.2, RB = 0.3; // ball pitch radius and ball radius
// Horizontal-axis channels sit on the +Z side, vertical-axis channels on the +Y side.
const LAYOUT = {};
const place = (ax, key, mod, pos) => { LAYOUT[`${ax}_${key}`] = { mod, pos, side: ax === 'h' ? 'L' : 'R' }; };
[['rms', 'housing', 0.2], ['peak', 'housing', -0.2]].forEach(([k, m, dx]) => {
  place('h', k, m, [dx, -0.55, 2.78]); place('v', k, m, [dx, 2.78, -0.55]);
});
[['kurt', -0.3], ['crest', -0.1], ['skew', 0.1], ['band4', 0.3]].forEach(([k, dx]) => {
  place('h', k, 'races', [dx, -1.28, 1.28]); place('v', k, 'races', [dx, 1.28, -1.28]);
});
[['band2', -0.18], ['band3', 0.0], ['centroid_khz', 0.18]].forEach(([k, dx]) => {
  place('h', k, 'rolling', [dx, 0.35, RP + 0.05]); place('v', k, 'rolling', [dx, RP + 0.05, 0.35]);
});
place('h', 'band1', 'shaft', [-2.7, 0.0, 0.62]); place('v', 'band1', 'shaft', [-2.7, 0.62, 0.0]);

function groove(r0, sign, half = 0.45) {
  // Race profile (radius, axial): flat sides, circular ball track facing the balls.
  const pts = [];
  const rr = RB + 0.02;
  for (let i = 0; i <= 16; i++) {
    const x = -0.28 + (0.56 * i) / 16;
    pts.push(V2(RP + sign * Math.sqrt(Math.max(rr * rr - x * x, 0)), x));
  }
  return sign < 0
    ? [V2(r0, -half), V2(RP - 0.2, -half), ...pts.map((p) => V2(Math.min(p.x, RP - 0.2), p.y)), V2(RP - 0.2, half), V2(r0, half), V2(r0, -half)]
    : [V2(r0, -half), V2(RP + 0.2, -half), ...pts.map((p) => V2(Math.max(p.x, RP + 0.2), p.y)), V2(RP + 0.2, half), V2(r0, half), V2(r0, -half)];
}

export function build() {
  const M = {
    race: new T.MeshStandardMaterial({ color: 0xaeb6bf, metalness: 0.9, roughness: 0.25, side: T.DoubleSide, emissive: 0x000000 }),
    ball: new T.MeshStandardMaterial({ color: 0xd4d9df, metalness: 0.95, roughness: 0.15, emissive: 0x000000 }),
    cage: metal(0x9a7b4f, 0.45, 0.7),
    shaft: new T.MeshStandardMaterial({ color: 0x6c7580, metalness: 0.85, roughness: 0.3, side: T.DoubleSide, emissive: 0x000000 }),
    housing: new T.MeshStandardMaterial({ color: 0x2f353d, metalness: 0.4, roughness: 0.6, side: T.DoubleSide, emissive: 0x000000 }),
    sensor: new T.MeshStandardMaterial({ color: 0x3a4250, metalness: 0.5, roughness: 0.5 }),
    arrow: new T.MeshBasicMaterial({ color: 0x7f8790 }),
  };

  const root = new T.Group();
  const mods = {};
  MODULES.forEach((m) => { const g = new T.Group(); mods[m.key] = g; root.add(g); });
  const quarter = (p, mat) => [lathe(p, mat, 96, 0, Math.PI * 1.5), sectionCut(p.slice(0, -1))];

  // Shaft through the inner race, with a coupling flange at the drive end.
  const shaft = new T.Group(); mods.shaft.add(shaft);
  shaft.add(axialCylinder(0.55, -3.3, 2.6, M.shaft, 48), axialCylinder(0.95, -3.4, -3.1, M.shaft, 48));
  const key = new T.Mesh(new T.BoxGeometry(0.9, 0.12, 0.12), M.housing); key.position.set(-2.4, 0.56, 0); shaft.add(key);

  // Races: inner turns with the shaft, outer is pressed into the housing.
  const inner = new T.Group(); mods.races.add(inner);
  inner.add(...quarter(groove(0.55, -1), M.race));
  mods.races.add(...quarter(groove(1.8, +1), M.race));
  mods.races.add(ring(1.8, -0.45), ring(1.8, 0.45));

  // Rolling elements: nine balls held by a cage, orbiting at cage speed.
  const cage = new T.Group(); mods.rolling.add(cage);
  const ballGeo = new T.SphereGeometry(RB, 28, 20);
  for (let i = 0; i < 9; i++) {
    const a = (i / 9) * Math.PI * 2, b = new T.Mesh(ballGeo, M.ball);
    b.position.set(0, RP * Math.cos(a), RP * Math.sin(a)); cage.add(b);
  }
  [-0.24, 0.24].forEach((x) => {
    const band = new T.Mesh(new T.TorusGeometry(RP, 0.035, 8, 72), M.cage);
    band.rotation.y = Math.PI / 2; band.position.x = x; cage.add(band);
  });

  // Housing: a pillow block with a bore for the outer race, two accelerometers and the radial-load point.
  const housing = new T.Group(); mods.housing.add(housing);
  housing.add(...quarter([V2(1.8, -0.75), V2(2.6, -0.75), V2(2.6, 0.75), V2(1.8, 0.75), V2(1.8, -0.75)], M.housing));
  const base = new T.Mesh(new T.BoxGeometry(1.5, 0.5, 5.6), M.housing); base.position.set(0, -2.85, 0); housing.add(base);
  const web = new T.Mesh(new T.BoxGeometry(1.5, 0.6, 2.2), M.housing); web.position.set(0, -2.35, 0); housing.add(web);
  const accH = new T.Mesh(new T.BoxGeometry(0.42, 0.42, 0.3), M.sensor); accH.position.set(0, -0.55, 2.7); housing.add(accH);
  const accV = new T.Mesh(new T.BoxGeometry(0.42, 0.3, 0.42), M.sensor); accV.position.set(0, 2.7, -0.55); housing.add(accV);

  let spin = 1, shake = 0;
  const home = housing.position.clone();
  return {
    key: 'bearing', root, mods, modules: MODULES, layout: LAYOUT, materials: M,
    panels: { L: 'Horizontal accelerometer', R: 'Vertical accelerometer' },
    view: { target: [0, -0.1, 0], dir: [0.75, 0.42, 1], twin: [3.7, 3.3], hero: [4.4, 3.8], min: 7 },
    groundY: -3.15,
    labels: { shaft: [-3.0, -1.4, 0], rolling: [0, -1.65, 0], races: [0, -2.0, 0], housing: [0, 3.0, 0] },
    apply({ modLevel, z, levels }) {
      const tint = (mat, mod, strength) => {
        const lv = modLevel[mod];
        if (lv < 0) mat.emissive.setRGB(0, 0, 0);
        else { mat.emissive.set(levels[lv].color); mat.emissiveIntensity = strength[lv]; }
      };
      // Large flat surfaces take a lighter tint than the races and balls, so the status reads without glare.
      tint(M.race, 'races', [0.24, 0.16, 0.08]);
      tint(M.ball, 'rolling', [0.24, 0.16, 0.08]);
      tint(M.shaft, 'shaft', [0.14, 0.09, 0.05]);
      tint(M.housing, 'housing', [0.1, 0.07, 0.04]);
      const level = Math.max(z.h_rms || 0, z.v_rms || 0);
      shake = Math.max(0, Math.min(1, level / 6)) * 0.018;
    },
    tick(dt, tsec, { reduced }) {
      if (reduced) { housing.position.copy(home); return; }
      shaft.rotation.x += dt * 2.6 * spin;
      inner.rotation.x += dt * 2.6 * spin;
      cage.rotation.x += dt * 1.05 * spin; // cage turns at roughly 0.4 of shaft speed
      housing.position.set(home.x, home.y + shake * Math.sin(tsec * 61), home.z + shake * Math.sin(tsec * 47 + 1));
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
