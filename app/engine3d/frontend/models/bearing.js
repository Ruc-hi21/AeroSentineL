/* Bearing model: a sectioned deep-groove ball bearing on a shaft, in a cast pillow block with a
 * horizontal and a vertical accelerometer (as on the PRONOSTIA rig). The shaft turns, the balls orbit
 * at cage speed, parts take the colour of their drifting channels, and each accelerometer radiates
 * rings at a rate and colour set by its measured vibration level. */
import { T, V2, physical, lathe, sectionCut, ring, boltCircle, cable, atPhi, CUT, dispose } from './shared.js?v=5.1.0';

const MODULES = [
  { key: 'shaft', name: 'Shaft', explode: [-2.4, 0, 0], intro: [-6, 0, 0] },
  { key: 'rolling', name: 'Rolling elements', explode: [0, 0, 0], intro: [0, 3.6, 0] },
  { key: 'races', name: 'Races', explode: [0, 0, 0], intro: [0, 0, 3.6] },
  { key: 'housing', name: 'Housing', explode: [0, 2.6, 0], intro: [0, 5, 0] },
];
const RP = 1.2, RB = 0.3; // ball pitch radius and ball radius
const RO = 2.55, RI = 1.8; // housing crown and bore radius
// Horizontal-axis channels sit on the +Z side, vertical-axis channels on the +Y side.
const LAYOUT = {};
const place = (ax, key, mod, pos) => { LAYOUT[`${ax}_${key}`] = { mod, pos, side: ax === 'h' ? 'L' : 'R' }; };
[['rms', 'housing', 0.24], ['peak', 'housing', -0.24]].forEach(([k, m, dx]) => {
  place('h', k, m, [dx, -0.62, 2.92]); place('v', k, m, [dx, 2.92, -0.62]);
});
[['kurt', -0.3], ['crest', -0.1], ['skew', 0.1], ['band4', 0.3]].forEach(([k, dx]) => {
  place('h', k, 'races', [dx, -1.28, 1.28]); place('v', k, 'races', [dx, 1.28, -1.28]);
});
[['band2', -0.18], ['band3', 0.0], ['centroid_khz', 0.18]].forEach(([k, dx]) => {
  place('h', k, 'rolling', [dx, 0.35, RP + 0.05]); place('v', k, 'rolling', [dx, RP + 0.05, 0.35]);
});
place('h', 'band1', 'shaft', [-2.7, 0.0, 0.62]); place('v', 'band1', 'shaft', [-2.7, 0.62, 0.0]);

function groove(r0, sign, half = 0.45) {
  // Race profile (radius, axial): chamfered shoulders, circular ball track facing the balls.
  const pts = [];
  const rr = RB + 0.02;
  for (let i = 0; i <= 18; i++) {
    const x = -0.28 + (0.56 * i) / 18;
    pts.push(V2(RP + sign * Math.sqrt(Math.max(rr * rr - x * x, 0)), x));
  }
  const land = RP + sign * 0.2, c = 0.04;
  return sign < 0
    ? [V2(r0, -half + c), V2(r0 + c, -half), V2(land - c, -half), V2(land, -half + c), ...pts.map((p) => V2(Math.min(p.x, land), p.y)),
      V2(land, half - c), V2(land - c, half), V2(r0 + c, half), V2(r0, half - c), V2(r0, -half + c)]
    : [V2(r0, -half + c), V2(r0 - c, -half), V2(land + c, -half), V2(land, -half + c), ...pts.map((p) => V2(Math.max(p.x, land), p.y)),
      V2(land, half - c), V2(land + c, half), V2(r0 - c, half), V2(r0, half - c), V2(r0, -half + c)];
}

// Pillow block: a C-shaped crown around the bore on a waisted pedestal, the upper-front quarter cut away.
function pedestal(mat) {
  const s = new T.Shape(), arc = (a0, a1, r, n = 40) => {
    for (let i = 0; i <= n; i++) { const a = a0 + ((a1 - a0) * i) / n; s.lineTo(r * Math.cos(a), r * Math.sin(a)); }
  };
  const deg = Math.PI / 180, ri = RI + 0.05;
  s.moveTo(0, RO);
  arc(90 * deg, 236 * deg, RO);
  s.lineTo(-1.5, -2.5); s.lineTo(-2.7, -2.5); s.lineTo(-2.8, -2.6); s.lineTo(-2.8, -3.0); s.lineTo(2.8, -3.0); s.lineTo(2.8, -2.6);
  s.lineTo(2.7, -2.5); s.lineTo(1.5, -2.5);
  arc(304 * deg, 360 * deg, RO);
  s.lineTo(ri, 0);
  arc(0, -270 * deg, ri, 80);
  s.lineTo(0, RO);
  const depth = 1.36;
  const geo = new T.ExtrudeGeometry(s, { depth, bevelEnabled: true, bevelThickness: 0.07, bevelSize: 0.05, bevelSegments: 3, curveSegments: 8 });
  geo.rotateY(-Math.PI / 2); geo.translate(depth / 2, 0, 0); // shape (Z, Y), extruded along X, centred
  const g = new T.Group();
  g.add(new T.Mesh(geo, mat));
  // hatched section faces where the crown is cut
  // the bevel pushes the cut walls 0.05 into the open quarter, so the hatching sits just outside them
  const fa = new T.Mesh(new T.PlaneGeometry(1.42, RO - RI + 0.02), CUT); fa.rotation.x = -Math.PI / 2; fa.position.set(0, 0.056, (RO + RI) / 2 + 0.02);
  const fb = new T.Mesh(new T.PlaneGeometry(1.42, RO - RI + 0.02), CUT); fb.position.set(0, (RO + RI) / 2 + 0.02, 0.056);
  fa.userData.receive = fb.userData.receive = false;
  g.add(fa, fb);
  return g;
}

// Piezo accelerometer: hex base, body, connector and a cable that runs down to the floor.
function accelerometer(M, phi, cableTo) {
  const g = new T.Group();
  const base = new T.Mesh(new T.CylinderGeometry(0.19, 0.19, 0.07, 6), M.sensorCap); base.position.y = 0.035;
  const body = new T.Mesh(new T.CylinderGeometry(0.15, 0.15, 0.34, 32), M.sensor); body.position.y = 0.24;
  const band = new T.Mesh(new T.CylinderGeometry(0.152, 0.152, 0.03, 32), M.brand); band.position.y = 0.33;
  const conn = new T.Mesh(new T.CylinderGeometry(0.06, 0.07, 0.12, 16), M.sensorCap); conn.position.y = 0.47;
  g.add(base, body, band, conn);
  // place on the crown, pointing along the outward normal at angle phi (lathe convention)
  const n = atPhi(1, phi);
  g.position.copy(atPhi(RO + 0.04, phi));
  g.quaternion.setFromUnitVectors(new T.Vector3(0, 1, 0), n);
  const tip = atPhi(RO + 0.58, phi);
  const c = cable([[tip.x, tip.y, tip.z], [tip.x + n.x * 0.3, tip.y + n.y * 0.3, tip.z + n.z * 0.3], ...cableTo], 0.035, M.cable);
  return { group: g, cable: c, tip, normal: n };
}

export function build() {
  const M = {
    race: physical(0xc3cad2, 0.16, 1.0, { emissive: 0x000000 }),
    ball: physical(0xe6e9ee, 0.07, 1.0, { emissive: 0x000000 }),
    cage: physical(0xb38d55, 0.32, 0.9),
    shaft: physical(0x8c95a0, 0.24, 0.95, { emissive: 0x000000, side: T.DoubleSide }),
    housing: physical(0x2b3540, 0.55, 0.35, { emissive: 0x000000, clearcoat: 0.35, clearcoatRoughness: 0.4, side: T.DoubleSide }),
    bolt: physical(0xa3abb4, 0.3, 0.95),
    sensor: physical(0x1c2128, 0.32, 0.7),
    sensorCap: physical(0xb9c0c8, 0.22, 1.0),
    brand: new T.MeshStandardMaterial({ color: 0x1683f2, emissive: 0x1683f2, emissiveIntensity: 0.6, roughness: 0.4 }),
    cable: new T.MeshStandardMaterial({ color: 0x14181d, roughness: 0.55, metalness: 0.1 }),
    brass: physical(0xc59b4f, 0.3, 1.0),
  };

  const root = new T.Group();
  const mods = {};
  MODULES.forEach((m) => { const g = new T.Group(); mods[m.key] = g; root.add(g); });
  const quarter = (p, mat) => [lathe(p, mat, 120, 0, Math.PI * 1.5), sectionCut(p.slice(0, -1))];

  // Shaft: chamfered ends, a shoulder against the inner race, a lock nut on the free side and a
  // bolted coupling flange at the drive end. The whole assembly turns.
  const shaft = new T.Group(); mods.shaft.add(shaft);
  shaft.add(lathe([V2(0, -3.12), V2(0.5, -3.12), V2(0.55, -3.07), V2(0.55, -0.98), V2(0.7, -0.95), V2(0.72, -0.5),
    V2(0.55, -0.47), V2(0.55, 2.55), V2(0.5, 2.6), V2(0, 2.6)], M.shaft, 64));
  shaft.add(lathe([V2(0.3, -3.42), V2(0.92, -3.42), V2(0.98, -3.36), V2(0.98, -3.18), V2(0.92, -3.12), V2(0.3, -3.12), V2(0.3, -3.42)], M.shaft, 64));
  shaft.add(boltCircle({ r: 0.74, x: -3.12, count: 8, size: 0.07, height: 0.07, facing: 1, mat: M.bolt, arc: Math.PI * 2 }));
  const nut = lathe([V2(0.55, 0.5), V2(0.86, 0.5), V2(0.9, 0.54), V2(0.9, 0.71), V2(0.86, 0.75), V2(0.55, 0.75), V2(0.55, 0.5)], M.bolt, 48);
  shaft.add(nut);
  for (let i = 0; i < 4; i++) {
    const slot = new T.Mesh(new T.BoxGeometry(0.26, 0.12, 0.1), M.cable), a = (i / 4) * Math.PI * 2;
    slot.position.set(0.625, 0.88 * Math.cos(a), 0.88 * Math.sin(a)); slot.rotation.x = a; shaft.add(slot);
  }
  const key = new T.Mesh(new T.BoxGeometry(0.9, 0.12, 0.14), M.bolt); key.position.set(-2.4, 0.56, 0); shaft.add(key);

  // Races: inner on the shaft, outer pressed into the housing. Both are sectioned and do not turn on
  // screen (they are rotationally symmetric; turning them would only move the cut).
  mods.races.add(...quarter(groove(0.55, -1), M.race));
  mods.races.add(...quarter(groove(RI, +1), M.race));
  mods.races.add(ring(RI, -0.45), ring(RI, 0.45));

  // Rolling elements: nine balls in a riveted brass cage, orbiting at cage speed.
  const cage = new T.Group(); mods.rolling.add(cage);
  const ballGeo = new T.SphereGeometry(RB, 40, 28);
  for (let i = 0; i < 9; i++) {
    const a = (i / 9) * Math.PI * 2, b = new T.Mesh(ballGeo, M.ball);
    b.position.set(0, RP * Math.cos(a), RP * Math.sin(a)); cage.add(b);
  }
  [-0.25, 0.25].forEach((x) => {
    const band = new T.Mesh(new T.TorusGeometry(RP, 0.04, 10, 120), M.cage);
    band.rotation.y = Math.PI / 2; band.position.x = x; cage.add(band);
  });
  const rivetGeo = new T.CylinderGeometry(0.035, 0.035, 0.58, 10); rivetGeo.rotateZ(Math.PI / 2);
  for (let i = 0; i < 9; i++) {
    const a = ((i + 0.5) / 9) * Math.PI * 2, r = new T.Mesh(rivetGeo, M.cage);
    r.position.set(0, RP * Math.cos(a), RP * Math.sin(a)); cage.add(r);
  }

  // Housing: cast pillow block, hold-down bolts, grease nipple and the two accelerometers.
  const housing = new T.Group(); mods.housing.add(housing);
  housing.add(pedestal(M.housing));
  [-2.15, 2.15].forEach((z) => {
    const washer = new T.Mesh(new T.CylinderGeometry(0.26, 0.26, 0.04, 28), M.bolt); washer.position.set(0, -2.53, z);
    const head = new T.Mesh(new T.CylinderGeometry(0.19, 0.19, 0.16, 6), M.bolt); head.position.set(0, -2.43, z);
    housing.add(washer, head);
  });
  {
    const phi = (222 * Math.PI) / 180; // on the crown, toward the back
    const n = atPhi(1, phi), at = atPhi(RO + 0.04, phi);
    const nip = new T.Group();
    const hex = new T.Mesh(new T.CylinderGeometry(0.1, 0.1, 0.12, 6), M.brass); hex.position.y = 0.06;
    const neck = new T.Mesh(new T.CylinderGeometry(0.045, 0.06, 0.14, 12), M.brass); neck.position.y = 0.19;
    const ball = new T.Mesh(new T.SphereGeometry(0.065, 16, 12), M.brass); ball.position.y = 0.29;
    nip.add(hex, neck, ball); nip.position.copy(at); nip.quaternion.setFromUnitVectors(new T.Vector3(0, 1, 0), n);
    housing.add(nip);
  }
  const deg = Math.PI / 180;
  const accH = accelerometer(M, 12 * deg, [[0.25, -1.5, 3.75], [0.9, -2.75, 4.2], [1.7, -3.0, 4.8]]);
  const accV = accelerometer(M, 258 * deg, [[0.35, 3.75, -0.95], [1.3, 3.5, -1.6], [2.2, -0.8, -2.7], [2.7, -3.0, -3.1]]);
  housing.add(accH.group, accV.group, accH.cable, accV.cable);

  // Vibration rings: each accelerometer radiates rings at a rate and colour set by its RMS drift.
  const waveMat = () => new T.MeshBasicMaterial({ color: 0x5fd4f8, transparent: true, opacity: 0, depthWrite: false,
    blending: T.AdditiveBlending, side: T.DoubleSide, toneMapped: false });
  const waves = [accH, accV].map((acc) => [0, 1, 2].map(() => {
    const w = new T.Mesh(new T.RingGeometry(0.9, 1.0, 64), waveMat());
    w.position.copy(acc.tip); w.quaternion.setFromUnitVectors(new T.Vector3(0, 0, 1), acc.normal); housing.add(w); return w;
  }));
  const vib = [{ level: 0, color: new T.Color(0x5fd4f8) }, { level: 0, color: new T.Color(0x5fd4f8) }];

  let spin = 1, shake = 0;
  const home = housing.position.clone();
  return {
    key: 'bearing', root, mods, modules: MODULES, layout: LAYOUT, materials: M,
    introOrder: ['housing', 'races', 'rolling', 'shaft'],
    panels: { L: 'Horizontal accelerometer', R: 'Vertical accelerometer' },
    view: { target: [0, -0.3, 0], dir: [0.75, 0.42, 1], twin: [3.8, 3.5], hero: [4.6, 3.9], min: 7 },
    groundY: -3.05,
    labels: { shaft: [-3.0, -1.4, 0], rolling: [0, -1.65, 0], races: [0, -2.0, 0], housing: [0, 3.3, 0] },
    apply({ modLevel, z, levels }) {
      const tint = (mat, mod, strength) => {
        const lv = modLevel[mod];
        if (lv < 0) mat.emissive.setRGB(0, 0, 0);
        else { mat.emissive.set(levels[lv].color); mat.emissiveIntensity = strength[lv]; }
      };
      // Large flat surfaces take a lighter tint than the races and balls, so the status reads without glare.
      tint(M.race, 'races', [0.2, 0.13, 0.06]);
      tint(M.ball, 'rolling', [0.2, 0.13, 0.06]);
      tint(M.shaft, 'shaft', [0.09, 0.06, 0.03]);
      tint(M.housing, 'housing', [0.06, 0.04, 0.02]);
      const level = Math.max(z.h_rms || 0, z.v_rms || 0);
      shake = Math.max(0, Math.min(1, level / 6)) * 0.018;
      [z.h_rms || 0, z.v_rms || 0].forEach((v, i) => {
        vib[i].level = Math.max(0, Math.min(1, v / 4));
        const lv = levels.findIndex((l) => v >= l.at);
        vib[i].color.set(lv < 0 ? 0x5fd4f8 : levels[lv].color);
      });
    },
    tick(dt, tsec, { reduced, explode }) {
      waves.forEach((set, i) => set.forEach((w, j) => {
        if (reduced || explode > 0.5) { w.visible = false; return; }
        const rate = 0.35 + vib[i].level * 0.9, ph = (tsec * rate + j / 3) % 1;
        w.visible = true;
        w.scale.setScalar(0.12 + ph * (0.45 + vib[i].level * 0.5));
        w.material.color.copy(vib[i].color);
        w.material.opacity = (1 - ph) * (0.18 + vib[i].level * 0.45);
      }));
      if (reduced) { housing.position.copy(home); return; }
      shaft.rotation.x += dt * 2.6 * spin;
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
