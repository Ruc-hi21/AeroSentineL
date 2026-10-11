/* Gearbox model: a two-stage helical reduction gearbox (engine accessory drive), cut away at the front,
 * shafts along world X. Input pinion -> intermediate gear, intermediate pinion -> output gear (14:29 then
 * 15:33). Each pair has opposite-hand helical teeth and stays in mesh while turning. Six ball bearings in
 * the end walls carry the three shafts; the casing has stiffening ribs, bolted bearing caps, an inspection
 * cover, lifting eyes, breather, sight glass, drain plug and a nameplate. The data channels come from a
 * horizontal and a vertical accelerometer on the casing (FEMTO gearbox-bearing data).
 *
 * Motion: GSAP runs a load cycle (speed ramps up and down) that also sets how hard the mesh contacts glow
 * and how much oil the output gear throws. Accelerometers radiate rings at the measured vibration level.
 * Exploded view: the casing ghosts; the gear train slides out of the open front, the stages part along
 * their shafts and the bearings move outward. No part ever passes through another. */
import { T, physical, metal, lathe, V2, boltCircle, cable, canvasTexture, dispose } from './shared.js?v=6.1.0';

const MODULES = [
  { key: 'shaft', name: 'Shafts', explode: [0, 0, 1.6] },
  { key: 'rolling', name: 'Gear mesh', explode: [0, 0, 1.6] },
  { key: 'races', name: 'Bearings', explode: [0, 0, 1.6] },
  { key: 'housing', name: 'Casing', explode: [0, 0, 0] },
];
const GEAR = { p1: { r: 0.42, n: 14 }, g1: { r: 0.88, n: 29 }, p2: { r: 0.46, n: 15 }, g2: { r: 1.0, n: 33 } };
const YA = 1.25, YB = YA - (GEAR.p1.r + GEAR.g1.r), YC = YB - (GEAR.p2.r + GEAR.g2.r); // shaft heights
const X1 = -0.75, X2 = 0.7; // stage stations along the shafts
const XB = 1.65;            // bearing stations in the end walls
const BOX = { x0: -1.85, x1: 1.85, y0: -2.78, y1: 1.98, z0: -1.05, z1: 1.05, t: 0.12 };
const HELIX = (20 * Math.PI) / 180;

const LAYOUT = {};
const put = (ax, k, mod, pos) => { LAYOUT[`${ax}_${k}`] = { mod, pos, side: ax === 'h' ? 'L' : 'R' }; };
[['rms', 0.18], ['peak', -0.18]].forEach(([k, dx]) => { put('h', k, 'housing', [1.3 + dx, -2.2, 1.43]); put('v', k, 'housing', [0.7 + dx, 2.5, -0.5]); });
[['kurt', -1, 0.12], ['crest', -1, -0.12], ['skew', 1, 0.12], ['band4', 1, -0.12]].forEach(([k, side, dy]) => {
  put('h', k, 'races', [side * XB, YC + dy, 0.62]); put('v', k, 'races', [side * XB, YA + dy, 0.5]);
});
[['band2', -0.16], ['band3', 0.0], ['centroid_khz', 0.16]].forEach(([k, dx]) => {
  put('h', k, 'rolling', [X2 + dx, YC + GEAR.g2.r, 0.36]); put('v', k, 'rolling', [X1 + dx, YA - GEAR.p1.r, 0.32]);
});
put('h', 'band1', 'shaft', [2.5, YC, 0.3]); put('v', 'band1', 'shaft', [-2.5, YA, 0.3]);

// Helical gear: tooth outline extruded along X, then each slice turned about X (helix), with a bore and
// optional lightening holes and hub boss.
function gearGeometry(r, n, width, bore, hand, holes = 0, phase = 0) {
  const m = (2 * r) / n, ra = r + m, rf = r - 1.25 * m, pitch = (Math.PI * 2) / n;
  const s = new T.Shape();
  for (let i = 0; i < n; i++) {
    const c = phase + i * pitch;
    const pts = [[rf, c - 0.5 * pitch], [rf, c - 0.3 * pitch], [r - 0.3 * m, c - 0.24 * pitch], [r, c - 0.2 * pitch], [ra - 0.25 * m, c - 0.14 * pitch],
      [ra, c - 0.09 * pitch], [ra, c + 0.09 * pitch], [ra - 0.25 * m, c + 0.14 * pitch], [r, c + 0.2 * pitch], [r - 0.3 * m, c + 0.24 * pitch], [rf, c + 0.3 * pitch]];
    pts.forEach(([rad, a], k) => { const x = rad * Math.cos(a), y = rad * Math.sin(a); (i === 0 && k === 0) ? s.moveTo(x, y) : s.lineTo(x, y); });
  }
  s.closePath();
  const hole = (cx, cy, rr) => { const p = new T.Path(); p.absarc(cx, cy, rr, 0, Math.PI * 2, true); s.holes.push(p); };
  hole(0, 0, bore);
  for (let k = 0; k < holes; k++) { const a = (k / holes) * Math.PI * 2 + 0.3; hole(Math.cos(a) * r * 0.58, Math.sin(a) * r * 0.58, r * 0.16); }
  const g = new T.ExtrudeGeometry(s, { depth: width, steps: 6, bevelEnabled: true, bevelThickness: 0.015, bevelSize: 0.012, bevelSegments: 2, curveSegments: 24 });
  g.translate(0, 0, -width / 2);
  g.rotateY(Math.PI / 2); // shape (x, y) -> world (Y = y, Z = -x); gear axis along X
  // helix: turn each slice by x * tan(helix) / r about X (opposite hands on mating gears)
  const p = g.attributes.position, v = new T.Vector3();
  for (let i = 0; i < p.count; i++) {
    v.fromBufferAttribute(p, i);
    const a = (hand * v.x * Math.tan(HELIX)) / r, c = Math.cos(a), sn = Math.sin(a);
    p.setXYZ(i, v.x, v.y * c - v.z * sn, v.y * sn + v.z * c);
  }
  g.computeVertexNormals();
  return g;
}

function bearing(M, rOut, rIn, width) {
  const g = new T.Group(), mid = (rOut + rIn) / 2, ball = (rOut - rIn) * 0.3;
  const ringP = (a, b) => [V2(a, -width / 2), V2(b, -width / 2), V2(b, width / 2), V2(a, width / 2), V2(a, -width / 2)];
  g.add(lathe(ringP(mid + ball * 0.75, rOut), M.race, 64), lathe(ringP(rIn, mid - ball * 0.75), M.race, 64));
  // rubber seal on the outboard face
  g.add(lathe([V2(mid - ball * 0.8, width / 2 - 0.01), V2(mid + ball * 0.8, width / 2 - 0.01), V2(mid + ball * 0.8, width / 2 + 0.005), V2(mid - ball * 0.8, width / 2 + 0.005), V2(mid - ball * 0.8, width / 2 - 0.01)], M.seal, 64));
  const cage = new T.Group(); g.add(cage);
  const geo = new T.SphereGeometry(ball, 18, 12), n = 10;
  for (let i = 0; i < n; i++) { const a = (i / n) * Math.PI * 2, b = new T.Mesh(geo, M.ball); b.position.set(0, mid * Math.cos(a), mid * Math.sin(a)); cage.add(b); }
  const band = new T.Mesh(new T.TorusGeometry(mid, ball * 0.25, 8, 64), M.cage); band.rotation.y = Math.PI / 2; cage.add(band);
  return { group: g, cage };
}

const plate = (w, h, d, mat, x, y, z, r = 0.04) => {
  const m = new T.Mesh(new T.RoundedBoxGeometry(w, h, d, 2, Math.min(r, w / 3, h / 3, d / 3)), mat); m.position.set(x, y, z); return m;
};

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

const nameplate = () => canvasTexture(512, 192, (g, w, h) => {
  g.fillStyle = '#c9cfd6'; g.fillRect(0, 0, w, h); g.strokeStyle = '#2b3038'; g.lineWidth = 6; g.strokeRect(6, 6, w - 12, h - 12);
  g.fillStyle = '#15181c'; g.font = '600 40px "IBM Plex Sans", sans-serif'; g.fillText('ACCESSORY GEARBOX', 26, 62);
  g.font = '400 28px "IBM Plex Mono", monospace'; g.fillText('RATIO 4.56:1   2 STAGE', 26, 110); g.fillText('S/N AS-AGB-0113', 26, 152);
});

export function build() {
  const gsap = window.gsap;
  const REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const M = {
    casing: physical(0x2b3540, 0.55, 0.35, { emissive: 0x000000, clearcoat: 0.35, clearcoatRoughness: 0.4 }),
    flange: physical(0x3a4652, 0.4, 0.6, { emissive: 0x000000 }),
    gear: physical(0xb9c1ca, 0.26, 1.0, { emissive: 0x000000, clearcoat: 0.2 }),
    pinion: physical(0xc9a46a, 0.28, 1.0, { emissive: 0x000000, clearcoat: 0.2 }),
    shaft: physical(0x8c95a0, 0.26, 0.95, { emissive: 0x000000 }),
    race: physical(0xb3bac2, 0.32, 1.0, { emissive: 0x000000, side: T.DoubleSide, clearcoat: 0.2 }),
    ball: physical(0xd4d9df, 0.18, 1.0, { emissive: 0x000000, clearcoat: 0.3 }),
    seal: new T.MeshStandardMaterial({ color: 0x8a2f2a, roughness: 0.7 }),
    cage: physical(0xb38d55, 0.32, 0.9),
    bolt: physical(0xa3abb4, 0.3, 0.95),
    oil: new T.MeshPhysicalMaterial({ color: 0xb8862b, roughness: 0.1, metalness: 0, transparent: true, opacity: 0.38, depthWrite: false }),
    sensor: physical(0x1c2128, 0.32, 0.7), sensorCap: physical(0xb9c0c8, 0.22, 1.0),
    brand: new T.MeshStandardMaterial({ color: 0x1683f2, emissive: 0x1683f2, emissiveIntensity: 0.6, roughness: 0.4 }),
    cable: new T.MeshStandardMaterial({ color: 0x14181d, roughness: 0.55, metalness: 0.1 }),
    glass: new T.MeshPhysicalMaterial({ color: 0xb8862b, roughness: 0.05, metalness: 0, transparent: true, opacity: 0.55 }),
    plateTag: new T.MeshStandardMaterial({ map: nameplate(), roughness: 0.4, metalness: 0.5 }),
    contact: new T.MeshBasicMaterial({ color: 0xffb35c, transparent: true, opacity: 0, blending: T.AdditiveBlending, depthWrite: false, toneMapped: false }),
  };

  const root = new T.Group();
  const mods = {};
  MODULES.forEach((m) => { const g = new T.Group(); mods[m.key] = g; root.add(g); });

  // ---- casing: back wall with ribs, floor, back half of the top with an inspection cover, end walls
  // (back half, so the gear train can leave through the open front), feet, lifting eyes and fittings.
  const { x0, x1, y0, y1, z0, z1, t } = BOX, W = x1 - x0, H = y1 - y0;
  const casing = new T.Group(); mods.housing.add(casing);
  casing.add(plate(W + 2 * t, H + 2 * t, t, M.casing, 0, (y0 + y1) / 2, z0 - t / 2));
  for (let i = 0; i < 5; i++) casing.add(plate(0.1, H, 0.22, M.casing, x0 + 0.4 + i * (W - 0.8) / 4, (y0 + y1) / 2, z0 - t - 0.11, 0.03)); // ribs
  casing.add(plate(W + 2 * t, t, z1 - z0 + t, M.casing, 0, y0 - t / 2, (z0 + z1) / 2 - t / 2));
  casing.add(plate(W + 2 * t, t, (z1 - z0) / 2, M.casing, 0, y1 + t / 2, z0 + (z1 - z0) / 4));
  casing.add(plate(1.6, 0.06, 0.75, M.flange, -0.2, y1 + t + 0.03, -0.55, 0.02)); // inspection cover
  for (let i = 0; i < 8; i++) { const b = new T.Mesh(new T.CylinderGeometry(0.04, 0.04, 0.05, 6), M.bolt); b.position.set(-0.9 + (i % 4) * 0.47, y1 + t + 0.08, i < 4 ? -0.25 : -0.85); casing.add(b); }
  [x0 - t / 2, x1 + t / 2].forEach((x) => casing.add(plate(t, H + 2 * t, (z1 - z0) / 2 + t, M.casing, x, (y0 + y1) / 2, z0 + (z1 - z0) / 4 - t / 2)));
  casing.add(plate(W + 2 * t, 0.08, 0.12, M.flange, 0, y1 + t + 0.04, 0.0));
  [x0 - t / 2, x1 + t / 2].forEach((x) => casing.add(plate(0.16, H + 2 * t, 0.08, M.flange, x, (y0 + y1) / 2, 0.02)));
  casing.add(plate(W + 2 * t + 0.2, 0.2, 0.12, M.flange, 0, y0 + 0.02, z1 + 0.04)); // front lip of the sump
  const tag = new T.Mesh(new T.PlaneGeometry(1.15, 0.43), M.plateTag); tag.position.set(-0.9, y0 + 0.02, z1 + 0.105); casing.add(tag);
  [-1, 1].forEach((sd) => casing.add(plate(0.95, 0.2, z1 - z0 + 0.7, M.casing, sd * (W / 2 - 0.15), y0 - t - 0.1, (z0 + z1) / 2)));
  [-1, 1].forEach((sd) => { const eye = new T.Mesh(new T.TorusGeometry(0.16, 0.05, 10, 24), M.bolt); eye.position.set(sd * (W / 2 - 0.25), y1 + t + 0.2, -0.55); casing.add(eye); });
  const breather = lathe([V2(0, 0), V2(0.1, 0), V2(0.1, 0.12), V2(0.14, 0.14), V2(0.14, 0.22), V2(0, 0.24)], M.bolt, 24);
  breather.rotation.z = 0; breather.position.set(1.15, y1 + t, -0.55); casing.add(breather);
  const sight = new T.Mesh(new T.CylinderGeometry(0.16, 0.16, 0.04, 32), M.glass); sight.rotation.z = Math.PI / 2; sight.position.set(x1 + t + 0.01, y0 + 0.5, -0.5); casing.add(sight);
  const drain = new T.Mesh(new T.CylinderGeometry(0.09, 0.09, 0.08, 6), M.bolt); drain.rotation.z = Math.PI / 2; drain.position.set(x0 - t - 0.03, y0 + 0.15, -0.5); casing.add(drain);
  // bolted bearing caps on the outside of both end walls (back half)
  [[YA, 0.42], [YB, 0.5], [YC, 0.6]].forEach(([y, r]) => [-1, 1].forEach((sd) => {
    const cap = lathe([V2(0.0, 0), V2(r, 0), V2(r + 0.05, 0.05), V2(r + 0.05, 0.14), V2(0, 0.14)], M.flange, 48, Math.PI * 0.5, Math.PI);
    cap.rotation.z = sd > 0 ? -Math.PI / 2 : Math.PI / 2; cap.position.set(sd * (x1 + t), y, 0); casing.add(cap);
    for (let k = 0; k < 3; k++) { // three bolts round the back half of the cap
      const a = Math.PI * (0.68 + k * 0.32), b = new T.Mesh(new T.CylinderGeometry(0.035, 0.035, 0.05, 6), M.bolt);
      b.rotation.z = Math.PI / 2; b.position.set(sd * (x1 + t + 0.17), y - (r - 0.08) * Math.sin(a), (r - 0.08) * Math.cos(a)); casing.add(b); }
  }));
  const oil = new T.Mesh(new T.BoxGeometry(W - 0.04, 0.75, z1 - z0 - 0.04), M.oil); oil.position.set(0, y0 + 0.375, 0); oil.userData.receive = false; casing.add(oil);

  // ---- shafts with couplings
  const shaftA = new T.Group(), shaftB = new T.Group(), shaftC = new T.Group();
  shaftA.position.y = YA; shaftB.position.y = YB; shaftC.position.y = YC;
  mods.shaft.add(shaftA, shaftB, shaftC);
  shaftA.add(lathe([V2(0, -3.1), V2(0.16, -3.1), V2(0.19, -3.07), V2(0.19, -1.3), V2(0.22, -1.25), V2(0.22, 1.25), V2(0.19, 1.3), V2(0.19, 2.05), V2(0, 2.08)], M.shaft, 40));
  shaftA.add(lathe([V2(0.19, -3.15), V2(0.44, -3.15), V2(0.48, -3.1), V2(0.48, -2.7), V2(0.44, -2.66), V2(0.19, -2.66), V2(0.19, -3.15)], M.flange, 40));
  shaftA.add(boltCircle({ r: 0.34, x: -2.66, count: 6, size: 0.04, height: 0.04, facing: 1, mat: M.bolt, arc: Math.PI * 2 }));
  shaftB.add(lathe([V2(0, -2.08), V2(0.22, -2.08), V2(0.25, -2.05), V2(0.25, 2.05), V2(0.22, 2.08), V2(0, 2.08)], M.shaft, 40));
  shaftC.add(lathe([V2(0, -2.08), V2(0.26, -2.08), V2(0.3, -2.04), V2(0.3, -1.3), V2(0.33, -1.25), V2(0.33, 1.25), V2(0.3, 1.3), V2(0.3, 3.1), V2(0.26, 3.13), V2(0, 3.13)], M.shaft, 40));
  shaftC.add(lathe([V2(0.3, 2.7), V2(0.66, 2.7), V2(0.7, 2.74), V2(0.7, 2.96), V2(0.66, 3.0), V2(0.3, 3.0), V2(0.3, 2.7)], M.flange, 48));
  shaftC.add(boltCircle({ r: 0.52, x: 3.0, count: 8, size: 0.045, height: 0.05, facing: 1, mat: M.bolt, arc: Math.PI * 2 }));

  // ---- gears: P1 (driver) and P2 present a tooth to the gear below; G1 and G2 a gap, so both stages mesh.
  const mk = (gd, w, bore, hand, holes, phase, mat) => new T.Mesh(gearGeometry(gd.r, gd.n, w, bore, hand, holes, phase), mat);
  const P1 = mk(GEAR.p1, 0.52, 0.22, 1, 0, -Math.PI / 2, M.pinion);
  const G1 = mk(GEAR.g1, 0.48, 0.25, -1, 5, Math.PI / 2 + Math.PI / GEAR.g1.n, M.gear);
  const P2 = mk(GEAR.p2, 0.56, 0.25, 1, 0, -Math.PI / 2, M.pinion);
  const G2 = mk(GEAR.g2, 0.52, 0.33, -1, 6, Math.PI / 2 + Math.PI / GEAR.g2.n, M.gear);
  const st1 = new T.Group(), st2 = new T.Group(); mods.rolling.add(st1, st2);
  const gA = new T.Group(), gB1 = new T.Group(), gB2 = new T.Group(), gC = new T.Group();
  gA.position.set(X1, YA, 0); gB1.position.set(X1, YB, 0); gB2.position.set(X2, YB, 0); gC.position.set(X2, YC, 0);
  gA.add(P1); gB1.add(G1); gB2.add(P2); gC.add(G2);
  gB1.add(lathe([V2(0.25, -0.32), V2(0.42, -0.32), V2(0.42, 0.32), V2(0.25, 0.32), V2(0.25, -0.32)], M.gear, 40));
  gC.add(lathe([V2(0.33, -0.34), V2(0.52, -0.34), V2(0.52, 0.34), V2(0.33, 0.34), V2(0.33, -0.34)], M.gear, 40));
  st1.add(gA, gB1); st2.add(gB2, gC);
  // mesh contact lines: glow with load (GSAP)
  const contact1 = new T.Mesh(new T.BoxGeometry(0.5, 0.025, 0.05), M.contact); contact1.position.set(X1, YA - GEAR.p1.r, 0.0); st1.add(contact1);
  const contact2 = new T.Mesh(new T.BoxGeometry(0.54, 0.025, 0.05), M.contact); contact2.position.set(X2, YB - GEAR.p2.r, 0.0); st2.add(contact2);

  // ---- bearings: two per shaft in the end walls
  const bear = [];
  [[YA, 0.38, 0.22, 'A'], [YB, 0.45, 0.25, 'B'], [YC, 0.55, 0.3, 'C']].forEach(([y, ro, ri, s]) => [-1, 1].forEach((sd) => {
    const b = bearing(M, ro, ri, 0.26); b.group.position.set(sd * XB, y, 0); b.side = sd; b.shaft = s;
    mods.races.add(b.group); bear.push(b);
  }));

  // ---- accelerometers: horizontal on the sump lip by the output bearing, vertical on top
  const accH = accelerometer(M, [1.3, -2.2, z1 + 0.06], [0, 0, 1], [[1.6, -2.5, 1.9], [2.0, -3.0, 2.4]]);
  const accV = accelerometer(M, [0.7, y1 + t, -0.5], [0, 1, 0], [[1.0, 2.9, -0.9], [2.1, 1.8, -1.4], [2.7, -3.0, -1.8]]);
  mods.housing.add(accH.group, accV.group, accH.cable, accV.cable);
  const waveMat = () => new T.MeshBasicMaterial({ color: 0x5fd4f8, transparent: true, opacity: 0, depthWrite: false, blending: T.AdditiveBlending, side: T.DoubleSide, toneMapped: false });
  const waves = [accH, accV].map((acc) => [0, 1, 2].map(() => {
    const w = new T.Mesh(new T.RingGeometry(0.9, 1.0, 64), waveMat());
    w.position.copy(acc.tip); w.quaternion.setFromUnitVectors(new T.Vector3(0, 0, 1), acc.normal); mods.housing.add(w); return w;
  }));
  const vib = [{ level: 0, color: new T.Color(0x5fd4f8) }, { level: 0, color: new T.Color(0x5fd4f8) }];

  // ---- oil thrown by the output gear where it dips into the sump, falling back under gravity
  const ON = 140, opos = new Float32Array(ON * 3), ovel = new Float32Array(ON * 3), olife = new Float32Array(ON);
  const ogeo = new T.BufferGeometry(); ogeo.setAttribute('position', new T.BufferAttribute(opos, 3));
  const omat = new T.PointsMaterial({ color: 0xd9a441, size: 0.045, transparent: true, opacity: 0.85, depthWrite: false });
  const splash = new T.Points(ogeo, omat); splash.frustumCulled = false; mods.rolling.add(splash);
  const spawn = (i) => {
    const a = Math.PI * (1.05 + Math.random() * 0.35); // lower-front quadrant of G2, flung tangentially
    opos[i * 3] = X2 + (Math.random() - 0.5) * 0.5; opos[i * 3 + 1] = YC + Math.sin(a) * GEAR.g2.r; opos[i * 3 + 2] = Math.cos(a) * GEAR.g2.r * 0.4;
    ovel[i * 3] = (Math.random() - 0.5) * 0.3; ovel[i * 3 + 1] = 1.2 + Math.random() * 1.4; ovel[i * 3 + 2] = (Math.random() - 0.3) * 0.6;
    olife[i] = 0;
  };
  for (let i = 0; i < ON; i++) { spawn(i); olife[i] = Math.random() * 1.2; }

  // ---- GSAP load cycle: the drive speeds up and eases off; contacts glow and oil flies harder at load
  const load = { k: 0.6 };
  const cycle = gsap.timeline({ repeat: -1, yoyo: true, paused: REDUCED })
    .to(load, { k: 1.25, duration: 4.5, ease: 'sine.inOut' })
    .to(load, { k: 0.9, duration: 2.0, ease: 'sine.inOut' });

  let angle = 0, base = 1, shake = 0;
  const home = casing.position.clone();
  return {
    key: 'bearing', root, mods, modules: MODULES, layout: LAYOUT, materials: M,
    shells: [M.casing, M.flange, M.oil, M.glass, M.plateTag],
    panels: { L: 'Horizontal accelerometer', R: 'Vertical accelerometer' },
    view: { target: [0, -0.45, 0], dir: [0.55, 0.36, 1], twin: [3.9, 3.0], hero: [4.4, 3.5], min: 7 },
    groundY: y0 - t - 0.2,
    labels: { shaft: [-2.7, YA + 0.6, 1.6], rolling: [0, y1 + 0.4, 1.6], races: [XB + 0.6, YC - 0.9, 1.6], housing: [0, y1 + 0.75, -0.5] },
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
      // Exploded view: the two stages part along their shafts, bearings move outward, all in their own lanes.
      st1.position.x = -0.5 * explode; st2.position.x = 0.5 * explode;
      bear.forEach((b) => { b.group.position.x = b.side * (XB + 0.4 * explode); });
      M.contact.opacity = (reduced ? 0.3 : 0.15 + 0.55 * (load.k - 0.6)) * (1 - explode);
      omat.opacity = 0.85 * (1 - explode);
      waves.forEach((set, i) => set.forEach((w, j) => {
        if (reduced || explode > 0.5) { w.visible = false; return; }
        const rate = 0.35 + vib[i].level * 0.9, ph = (tsec * rate + j / 3) % 1;
        w.visible = true; w.scale.setScalar(0.1 + ph * (0.42 + vib[i].level * 0.45));
        w.material.color.copy(vib[i].color); w.material.opacity = (1 - ph) * (0.16 + vib[i].level * 0.42);
      }));
      if (reduced) { casing.position.copy(home); return; }
      angle += dt * 2.6 * base * load.k;
      const aB = -angle * (GEAR.p1.n / GEAR.g1.n), aC = -aB * (GEAR.p2.n / GEAR.g2.n);
      shaftA.rotation.x = gA.rotation.x = angle;
      shaftB.rotation.x = gB1.rotation.x = gB2.rotation.x = aB;
      shaftC.rotation.x = gC.rotation.x = aC;
      bear.forEach((b) => { b.cage.rotation.x = (b.shaft === 'A' ? angle : b.shaft === 'B' ? aB : aC) * 0.4; });
      for (let i = 0; i < ON; i++) {
        olife[i] += dt;
        ovel[i * 3 + 1] -= 6.5 * dt;
        opos[i * 3] += ovel[i * 3] * dt; opos[i * 3 + 1] += ovel[i * 3 + 1] * dt * load.k; opos[i * 3 + 2] += ovel[i * 3 + 2] * dt;
        if (opos[i * 3 + 1] < y0 + 0.7 || olife[i] > 1.4) spawn(i);
      }
      ogeo.attributes.position.needsUpdate = true;
      casing.position.set(home.x, home.y + shake * Math.sin(tsec * 61), home.z + shake * Math.sin(tsec * 47 + 1));
    },
    resize() {},
    conditionText(c, i) {
      if (!c) return '';
      base = Math.max(0.4, c.speed_rpm[i] / 1800);
      return `${Math.round(c.speed_rpm[i])} rpm  ${c.load_kn[i].toFixed(1)} kN radial load`;
    },
    dispose() { cycle.kill(); dispose(root); },
  };
}
