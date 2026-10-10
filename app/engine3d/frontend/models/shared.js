/* Geometry helpers and materials shared by the component models (turbofan, battery, bearing).
 * Every model lies along world X, sectioned so the upper-front quarter is open. */
import * as T from '../vendor/three-bundle.js';

export { T };
export const V2 = (r, x) => new T.Vector2(r, x);
export const metal = (color, rough, metalness = 0.85) => new T.MeshStandardMaterial({ color, roughness: rough, metalness });
export const CUT = new T.MeshStandardMaterial({ color: 0x48505a, metalness: 0.05, roughness: 0.9, side: T.DoubleSide });
export const EDGE = new T.LineBasicMaterial({ color: 0x5c646e });

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
export function dispose(obj) {
  obj.traverse((o) => {
    if (o.geometry) o.geometry.dispose();
    const mats = Array.isArray(o.material) ? o.material : o.material ? [o.material] : [];
    mats.forEach((m) => { if (m !== CUT && m !== EDGE) m.dispose(); });
  });
}
