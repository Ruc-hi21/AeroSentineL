/* Geometry helpers and materials shared by the component models (turbofan, battery, bearing).
 * Every model lies along world X, sectioned so the upper-front quarter is open. */
import * as T from '../vendor/three-bundle.js';

export { T };
export const V2 = (r, x) => new T.Vector2(r, x);
export const metal = (color, rough, metalness = 0.85) => new T.MeshStandardMaterial({ color, roughness: rough, metalness });
// Polished or coated parts: clearcoat gives the crisp second highlight of ground steel and painted cases.
export const physical = (color, rough, metalness = 0.9, extra = {}) => new T.MeshPhysicalMaterial({
  color, roughness: rough, metalness, clearcoat: 0.6, clearcoatRoughness: 0.25, ...extra });

export function canvasTexture(w, h, draw, srgb = true) {
  const c = document.createElement('canvas'); c.width = w; c.height = h;
  draw(c.getContext('2d'), w, h);
  const t = new T.CanvasTexture(c);
  if (srgb) t.colorSpace = T.SRGBColorSpace;
  t.anisotropy = 4;
  return t;
}

// Section faces carry 45-degree hatching, as on an engineering drawing. ShapeGeometry UVs are shape
// coordinates, so the pattern keeps a constant world spacing.
const hatch = canvasTexture(64, 64, (g, w, h) => {
  g.fillStyle = '#3c434c'; g.fillRect(0, 0, w, h);
  g.strokeStyle = '#59626e'; g.lineWidth = 3;
  for (let i = -w; i < w * 2; i += 16) { g.beginPath(); g.moveTo(i, h); g.lineTo(i + h, 0); g.stroke(); }
});
hatch.wrapS = hatch.wrapT = T.RepeatWrapping; hatch.repeat.set(4, 4);
export const CUT = new T.MeshStandardMaterial({ color: 0xffffff, map: hatch, metalness: 0.05, roughness: 0.85, side: T.DoubleSide });
export const EDGE = new T.LineBasicMaterial({ color: 0x6a7480 });

// Lathe a (radius, axial) profile around world X. phi 0..1.5pi leaves the upper-front quarter open.
export function lathe(points, mat, segs = 72, start = 0, len = Math.PI * 2) {
  const m = new T.Mesh(new T.LatheGeometry(points, segs, start, len), mat);
  m.rotation.z = -Math.PI / 2;
  return m;
}
export function axialCylinder(r, x0, x1, mat, segs = 48) {
  const m = new T.Mesh(new T.CylinderGeometry(r, r, x1 - x0, segs, 1), mat);
  m.rotation.z = Math.PI / 2; m.position.x = (x0 + x1) / 2;
  return m;
}
// Section faces and outline where a closed (r, x) profile is cut at phi = 0 (+Z) and phi = 1.5pi (+Y).
export function sectionCut(profile, mat = CUT) {
  const g = new T.Group();
  const shape = new T.Shape(profile.map((p) => new T.Vector2(p.y, p.x)));
  const faceZ = new T.Mesh(new T.ShapeGeometry(shape), mat); faceZ.rotation.x = Math.PI / 2; // (a, r) -> (a, 0, r)
  const faceY = new T.Mesh(new T.ShapeGeometry(shape), mat);                                  // (a, r) -> (a, r, 0)
  faceZ.userData.receive = faceY.userData.receive = false;
  const lineZ = new T.LineLoop(new T.BufferGeometry().setFromPoints(profile.map((p) => new T.Vector3(p.y, 0, p.x + 0.002))), EDGE);
  const lineY = new T.LineLoop(new T.BufferGeometry().setFromPoints(profile.map((p) => new T.Vector3(p.y, p.x + 0.002, 0))), EDGE);
  g.add(faceZ, faceY, lineZ, lineY);
  return g;
}
export function ring(r, x) {
  const pts = []; for (let i = 0; i <= 96; i++) { const a = (i / 96) * Math.PI * 1.5; pts.push(new T.Vector3(x, -r * Math.sin(a), r * Math.cos(a))); }
  return new T.Line(new T.BufferGeometry().setFromPoints(pts), EDGE);
}
// Closed rectangle profile (r0..r1, x0..x1), for tubes and discs cut by sectionCut.
export const rectProfile = (r0, r1, x0, x1) => [V2(r0, x0), V2(r1, x0), V2(r1, x1), V2(r0, x1)];
export function tube(r0, r1, x0, x1, mat, segs = 72) {
  const g = new T.Group();
  const p = [...rectProfile(r0, r1, x0, x1), V2(r0, x0)];
  g.add(lathe(p, mat, segs, 0, Math.PI * 1.5), sectionCut(p.slice(0, -1)));
  return g;
}
// Angle (around X) of a point, using the lathe convention: y = -r sin(phi), z = r cos(phi).
export const atPhi = (r, phi, x = 0) => new T.Vector3(x, -r * Math.sin(phi), r * Math.cos(phi));

// Hex-head bolts on a pitch circle around X, heads facing `facing` (+1 = +X). Only the solid
// three quarters (phi 0..1.5pi) are populated, so the open section stays clear.
export function boltCircle({ r, x, count, size = 0.06, height = 0.05, facing = 1, mat, arc = Math.PI * 1.5, phase = 0 }) {
  const geo = new T.CylinderGeometry(size, size, height, 6);
  geo.rotateZ(Math.PI / 2); geo.translate((facing * height) / 2, 0, 0);
  const n = Math.max(1, Math.round(count * arc / (Math.PI * 2)));
  const mesh = new T.InstancedMesh(geo, mat, n), m = new T.Matrix4(), q = new T.Quaternion(), s = new T.Vector3(1, 1, 1);
  for (let i = 0; i < n; i++) {
    const phi = phase + ((i + 0.5) / n) * arc;
    q.setFromAxisAngle(new T.Vector3(1, 0, 0), phi);
    m.compose(atPhi(r, phi, x), q, s); mesh.setMatrixAt(i, m);
  }
  return mesh;
}

// A cable: tube along a smooth curve through the given points.
export function cable(points, radius, mat, segs = 64) {
  const curve = new T.CatmullRomCurve3(points.map((p) => new T.Vector3(...p)), false, 'centripetal');
  return new T.Mesh(new T.TubeGeometry(curve, segs, radius, 10, false), mat);
}

export function dispose(obj) {
  obj.traverse((o) => {
    if (o.geometry) o.geometry.dispose();
    const mats = Array.isArray(o.material) ? o.material : o.material ? [o.material] : [];
    mats.forEach((m) => { if (m !== CUT && m !== EDGE) { if (m.map && m.map !== hatch) m.map.dispose(); m.dispose(); } });
  });
}
