/* The working side of the hydraulic test rig, around the monitored power unit: a double-acting cylinder
 * that strokes a load sled along two rails, a control cabinet with a live HMI screen and indicator lamps,
 * a pressure filter, a return filter on the tank, a relief valve on the manifold, the motor's terminal box
 * and conduit, and hex fittings at the hose ends.
 *
 * GSAP runs the rig's load cycle (the 60 s cycle of the test rig, compressed to 6 s): the valve shifts, the
 * rod extends against the load while pressure and flow rise, holds, then the valve shifts back and the rod
 * retracts. The power unit reads the cycle state to set its gauges and oil flow. */
import { T, V2, physical, metal, lathe, cable, canvasTexture } from './shared.js?v=7.0.0';

const CYL = { x0: 1.05, x1: 2.55, y: -1.4, z: 1.18, r: 0.2 };
const STROKE = 0.95;

export function rigContext(root, mods, M0) {
  const gsap = window.gsap;
  const REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const M = {
    barrel: physical(0x2f5e9e, 0.4, 0.4, { clearcoat: 0.6, emissive: 0x000000 }),
    chrome: physical(0xd4d9df, 0.1, 1.0, { clearcoat: 0.6 }),
    steel: physical(0x7d8792, 0.35, 0.9),
    rail: physical(0xa9b2bc, 0.25, 1.0),
    sled: physical(0x3a4652, 0.45, 0.6),
    cabinet: physical(0xc9ced3, 0.45, 0.2, { clearcoat: 0.3 }),
    door: physical(0xb9c0c8, 0.45, 0.2, { clearcoat: 0.3 }),
    dark: physical(0x15181c, 0.5, 0.2),
    filter: physical(0xd9a441, 0.4, 0.4, { clearcoat: 0.4 }),
    fitting: physical(0xc59b4f, 0.3, 1.0),
    conduit: new T.MeshStandardMaterial({ color: 0x2a3038, roughness: 0.6 }),
    hose: new T.MeshStandardMaterial({ color: 0x15191e, roughness: 0.6 }),
  };
  const box = (w, h, d, mat, x, y, z, r = 0.04) => { const m = new T.Mesh(new T.RoundedBoxGeometry(w, h, d, 2, r), mat); m.position.set(x, y, z); return m; };
  const ctx = new T.Group(); root.add(ctx);

  // ---- working cylinder (part of the valve module: the valve drives it) with clevis mounts and a load sled
  const cyl = new T.Group(); mods.valve.add(cyl);
  const barrel = new T.Mesh(new T.CylinderGeometry(CYL.r, CYL.r, CYL.x1 - CYL.x0, 40), M.barrel);
  barrel.rotation.z = Math.PI / 2; barrel.position.set((CYL.x0 + CYL.x1) / 2, CYL.y, CYL.z); cyl.add(barrel);
  [CYL.x0, CYL.x1].forEach((x) => cyl.add(box(0.16, 0.5, 0.5, M.steel, x, CYL.y, CYL.z, 0.03)));
  for (let i = 0; i < 4; i++) { // tie rods
    const a = Math.PI / 4 + (i * Math.PI) / 2, rod = new T.Mesh(new T.CylinderGeometry(0.025, 0.025, CYL.x1 - CYL.x0 + 0.2, 8), M.chrome);
    rod.rotation.z = Math.PI / 2; rod.position.set((CYL.x0 + CYL.x1) / 2, CYL.y + 0.2 * Math.sin(a), CYL.z + 0.2 * Math.cos(a)); cyl.add(rod);
  }
  cyl.add(box(0.25, 0.42, 0.35, M.steel, CYL.x0 - 0.2, CYL.y - 0.08, CYL.z, 0.03)); // rear clevis mount
  const rod = new T.Group(); cyl.add(rod);
  const shaft = new T.Mesh(new T.CylinderGeometry(0.07, 0.07, 1.25, 24), M.chrome); shaft.rotation.z = Math.PI / 2; shaft.position.set(CYL.x1 + 0.45, CYL.y, CYL.z); rod.add(shaft);
  rod.add(box(0.18, 0.26, 0.26, M.steel, CYL.x1 + 1.1, CYL.y, CYL.z, 0.03)); // rod eye
  const sled = box(0.6, 0.42, 0.7, M.sled, CYL.x1 + 1.45, CYL.y - 0.02, CYL.z, 0.04); rod.add(sled);
  rod.add(box(0.5, 0.06, 0.5, M.filter, CYL.x1 + 1.45, CYL.y + 0.22, CYL.z, 0.02)); // load mass marker
  [-0.22, 0.22].forEach((dz) => cyl.add(box(2.8, 0.06, 0.08, M.rail, CYL.x1 + 1.6, -1.72, CYL.z + dz, 0.02)));
  cyl.add(box(0.12, 0.4, 0.9, M.steel, CYL.x1 + 3.1, -1.55, CYL.z, 0.02)); // end stop, beyond the sled's full stroke
  ctx.add(box(2.3, 0.14, 1.4, M.sled, 4.75, -1.83, CYL.z - 0.05, 0.03)); // skid extension under the rails

  // ---- control cabinet with HMI and lamps (behind the valve)
  const hmi = document.createElement('canvas'); hmi.width = 512; hmi.height = 320;
  const hmiTex = new T.CanvasTexture(hmi); hmiTex.colorSpace = T.SRGBColorSpace;
  const drawHmi = (phase, p, q) => {
    const g = hmi.getContext('2d');
    g.fillStyle = '#081018'; g.fillRect(0, 0, 512, 320);
    g.fillStyle = '#1683f2'; g.fillRect(0, 0, 512, 44);
    g.fillStyle = '#e6e8eb'; g.font = '600 26px "IBM Plex Sans", sans-serif'; g.fillText('HPU  LOAD CYCLE', 16, 31);
    g.font = '500 30px "IBM Plex Mono", monospace';
    g.fillStyle = '#9fb8d8'; g.fillText('PHASE', 16, 92); g.fillStyle = '#5fd4f8'; g.fillText(phase, 190, 92);
    g.fillStyle = '#9fb8d8'; g.fillText('PS2', 16, 142); g.fillStyle = '#e6e8eb'; g.fillText(`${p.toFixed(0)} bar`, 190, 142);
    g.fillStyle = '#9fb8d8'; g.fillText('FS1', 16, 192); g.fillStyle = '#e6e8eb'; g.fillText(`${q.toFixed(1)} l/min`, 190, 192);
    g.fillStyle = '#20252b'; g.fillRect(16, 236, 480, 26); g.fillStyle = '#3fa2ff'; g.fillRect(16, 236, 480 * Math.min(1, p / 180), 26);
    hmiTex.needsUpdate = true;
  };
  drawHmi('IDLE', 0, 0);
  const cab = new T.Group(); ctx.add(cab);
  cab.add(box(1.1, 2.4, 0.5, M.cabinet, 1.6, -0.62, -1.15, 0.05));
  cab.add(box(1.0, 2.25, 0.04, M.door, 1.6, -0.62, -0.88, 0.02));
  const screen = new T.Mesh(new T.PlaneGeometry(0.72, 0.45), new T.MeshBasicMaterial({ map: hmiTex, toneMapped: false }));
  screen.position.set(1.6, -0.05, -0.855); cab.add(screen);
  const lamps = [0x42be65, 0xf1c21b, 0xfa4d56].map((c, i) => {
    const mat = new T.MeshBasicMaterial({ color: c, toneMapped: false });
    const l = new T.Mesh(new T.CylinderGeometry(0.06, 0.06, 0.05, 16), mat); l.rotation.x = Math.PI / 2; l.position.set(1.35 + i * 0.25, -0.62, -0.84); cab.add(l);
    return { mat, base: new T.Color(c) };
  });
  const estop = new T.Mesh(new T.CylinderGeometry(0.1, 0.1, 0.08, 24), new T.MeshStandardMaterial({ color: 0xc92a2a, roughness: 0.4 }));
  estop.rotation.x = Math.PI / 2; estop.position.set(1.6, -1.0, -0.83); cab.add(estop);
  cab.add(box(0.8, 0.12, 0.12, M.dark, 1.6, -1.86, -1.0, 0.02)); // cable gland strip
  ctx.add(cable([[1.4, -1.85, -1.0], [0.6, -1.75, -0.3], [-0.2, -1.6, 0.2], [-1.05, -0.55, 0.55]], 0.05, M.conduit)); // conduit to the motor

  // ---- motor terminal box, filters, relief valve
  mods.pump.add(box(0.36, 0.22, 0.32, M.steel, -1.05, -0.5, 0.55, 0.03));
  const pf = lathe([V2(0, 0), V2(0.16, 0), V2(0.16, 0.5), V2(0.2, 0.52), V2(0.2, 0.62), V2(0, 0.62)], M.filter, 32);
  pf.rotation.z = 0; pf.position.set(0.55, -1.9 + 0.14, 1.15); mods.pump.add(pf); // pressure filter
  const rf = lathe([V2(0, 0), V2(0.2, 0), V2(0.2, 0.32), V2(0.24, 0.34), V2(0.24, 0.42), V2(0, 0.42)], M.filter, 32);
  rf.rotation.z = 0; rf.position.set(-2.2, -1.9 + 1.54, -0.45); mods.cooler.add(rf); // return filter on the tank
  const rv = lathe([V2(0, 0), V2(0.09, 0), V2(0.09, 0.28), V2(0.06, 0.32), V2(0.06, 0.45), V2(0, 0.47)], M.fitting, 24);
  rv.rotation.z = 0; rv.position.set(2.3, -0.33, 0.5); mods.valve.add(rv); // relief valve
  // hoses from the valve's A and B ports to the cylinder, hex fittings at every hose end
  const portA = [[2.0, -0.33, 0.78], [2.1, -0.9, 1.0], [CYL.x0 + 0.1, -1.15, CYL.z]];
  const portB = [[1.7, -0.33, 0.78], [1.5, -0.95, 1.1], [CYL.x1 - 0.12, -1.15, CYL.z]];
  [portA, portB].forEach((pts) => {
    mods.valve.add(cable(pts, 0.055, M.hose));
    [pts[0], pts[pts.length - 1]].forEach((p) => { const f = new T.Mesh(new T.CylinderGeometry(0.08, 0.08, 0.12, 6), M.fitting); f.position.set(...p); mods.valve.add(f); });
  });

  // ---- GSAP load cycle (6 s): shift, extend under load, hold, shift back, retract, rest
  const cyc = { rod: 0, flow: 0.6, press: 0.2, spool: 0, phase: 'IDLE' };
  const set = (phase) => () => { cyc.phase = phase; };
  const tl = gsap.timeline({ repeat: -1, paused: REDUCED })
    .call(set('SHIFT A'))
    .to(cyc, { spool: 1, duration: 0.35, ease: 'power2.out' })
    .call(set('EXTEND'))
    .to(cyc, { rod: 1, flow: 2.2, press: 1, duration: 2.0, ease: 'power2.inOut' })
    .call(set('HOLD'))
    .to(cyc, { flow: 0.4, duration: 0.5, ease: 'power1.out' })
    .call(set('SHIFT B'))
    .to(cyc, { spool: -1, duration: 0.35, ease: 'power2.out' })
    .call(set('RETRACT'))
    .to(cyc, { rod: 0, flow: 1.6, press: 0.45, duration: 1.7, ease: 'power2.inOut' })
    .call(set('IDLE'))
    .to(cyc, { spool: 0, flow: 0.6, press: 0.2, duration: 0.6, ease: 'power1.out' });

  let hmiT = 0;
  return {
    cyc,
    materials: [M.cabinet, M.door, M.dark, M.conduit],
    tick(dt, explode) {
      rod.position.x = cyc.rod * STROKE;
      lamps[0].mat.color.copy(lamps[0].base).multiplyScalar(cyc.phase === 'IDLE' ? 0.35 : 1.6);
      lamps[1].mat.color.copy(lamps[1].base).multiplyScalar(cyc.phase.startsWith('SHIFT') ? 1.6 : 0.3);
      lamps[2].mat.color.copy(lamps[2].base).multiplyScalar(0.25);
      hmiT += dt;
      if (hmiT > 0.2) { hmiT = 0; drawHmi(cyc.phase, 60 + 110 * cyc.press, 4 + 6 * cyc.flow); }
    },
    dispose() { tl.kill(); hmiTex.dispose(); },
  };
}
