/* The battery module around the monitored cell: two more 18650 cells in moulded holders, nickel
 * interconnects spot-welded to every terminal, HV terminals with cables, a battery-management board with
 * balancing resistors, status LEDs and sense wires, and a liquid cooling plate with its coolant loop.
 *
 * GSAP drives the module's rhythm: discharge pulses run through the interconnects and HV cables, and the
 * BMS LEDs chase while it balances. Coolant runs through the hoses every frame, warming with the cell.
 * Everything here is context: it stays put and ghosts in the exploded view (the + interconnect moves with
 * the monitored cell's cap, so the cap never slides through it). */
import { T, V2, physical, metal, lathe, cable, canvasTexture } from './shared.js?v=7.0.0';

const PITCH = 2.85;   // cell spacing along Z
const CELLS_Z = [-PITCH, -2 * PITCH];
const R = 1.334;      // sleeve radius
const Y_PLATE = -1.62; // top of the cooling plate is Y_PLATE + 0.22

const bmsTex = () => canvasTexture(1024, 512, (g, w, h) => {
  g.fillStyle = '#0d3a2c'; g.fillRect(0, 0, w, h);
  g.strokeStyle = '#c59b4f'; g.lineWidth = 3;
  for (let i = 0; i < 26; i++) { const x = 30 + i * 38; g.beginPath(); g.moveTo(x, 30); g.lineTo(x, 180 + (i % 4) * 40); g.lineTo(x + 60, h - 30); g.stroke(); }
  g.strokeStyle = '#e6e8eb'; g.lineWidth = 2; g.strokeRect(14, 14, w - 28, h - 28);
  g.fillStyle = '#e6e8eb'; g.font = '600 34px "IBM Plex Sans", sans-serif'; g.fillText('BMS  3S1P', 640, 70);
  g.font = '400 22px "IBM Plex Mono", monospace'; g.fillText('CELL MONITOR  AS-BMU-3', 640, 104); g.fillText('BAL  OVP  UVP  OTP', 640, 136);
});

function cellBody(Mx) {
  // A whole wrapped cell (not sectioned): can, sleeve, positive cap with vents, negative bottom.
  const g = new T.Group();
  const sleeve = new T.Mesh(new T.CylinderGeometry(R, R, 6.3, 72), Mx.wrap); sleeve.rotation.z = -Math.PI / 2; sleeve.position.x = -0.13; g.add(sleeve);
  const cap = lathe([V2(0, 3.16), V2(1.12, 3.16), V2(1.18, 3.2), V2(1.12, 3.26), V2(0.66, 3.28), V2(0.6, 3.48), V2(0.56, 3.52), V2(0, 3.52)], Mx.cap, 48);
  const crimp = lathe([V2(1.12, 3.05), V2(1.3, 3.05), V2(1.31, 3.14), V2(1.2, 3.22), V2(1.12, 3.2), V2(1.12, 3.05)], Mx.can, 48);
  const bottom = lathe([V2(0, -3.42), V2(1.24, -3.42), V2(1.3, -3.38), V2(1.3, -3.28), V2(0, -3.28)], Mx.can, 48);
  g.add(cap, crimp, bottom);
  return g;
}

function holderPlate(mat, x, thick) {
  // Moulded holder: a plate in the Z-Y plane with a bore per cell, ribs between bores.
  const s = new T.Shape();
  s.moveTo(-7.05, -1.4); s.lineTo(1.45, -1.4); s.lineTo(1.45, 1.42); s.lineTo(-7.05, 1.42); s.closePath();
  [0, ...CELLS_Z].forEach((z) => { const h = new T.Path(); h.absarc(z, 0, R + 0.03, 0, Math.PI * 2, true); s.holes.push(h); });
  const geo = new T.ExtrudeGeometry(s, { depth: thick, bevelEnabled: true, bevelThickness: 0.02, bevelSize: 0.02, bevelSegments: 2, curveSegments: 40 });
  geo.rotateY(-Math.PI / 2); // shape (Z, Y) extruded along X
  const m = new T.Mesh(geo, mat); m.position.x = x + thick / 2; return m;
}

export function moduleContext(root, mods, Mcell) {
  const gsap = window.gsap;
  const REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const M = {
    can: physical(0x8a929c, 0.32, 0.95), cap: physical(0xb3bac2, 0.34, 1.0),
    wrap: Mcell.wrap.clone(),
    holder: physical(0x2a2f37, 0.55, 0.15, { clearcoat: 0.25 }),
    nickel: physical(0xc9ced3, 0.28, 1.0, { emissive: 0x000000 }),
    weld: metal(0x8d949c, 0.5, 0.9),
    plate: physical(0x8a939e, 0.62, 0.6, { clearcoat: 0 }),
    pad: new T.MeshStandardMaterial({ color: 0x3a4048, roughness: 0.9 }),
    endplate: physical(0x5c6671, 0.55, 0.6, { clearcoat: 0.1 }),
    bolt: physical(0xa3abb4, 0.3, 0.95),
    pcb: new T.MeshStandardMaterial({ map: bmsTex(), roughness: 0.55, metalness: 0.1 }),
    chip: physical(0x15181c, 0.45, 0.2), res: physical(0x2b3038, 0.5, 0.3), conn: physical(0xe6e8eb, 0.5, 0.1),
    wire: new T.MeshStandardMaterial({ color: 0x1b1f24, roughness: 0.6 }),
    sense: new T.MeshStandardMaterial({ color: 0xd9a441, roughness: 0.5 }),
    hv: new T.MeshStandardMaterial({ color: 0xff7a1a, roughness: 0.45, emissive: 0xff5a00, emissiveIntensity: 0 }),
    hose: new T.MeshStandardMaterial({ color: 0x15191e, roughness: 0.6 }),
    lug: physical(0xc47a3c, 0.25, 1.0),
  };
  const ctx = new T.Group(); root.add(ctx);
  const box = (w, h, d, mat, x, y, z, r = 0.03) => { const m = new T.Mesh(new T.RoundedBoxGeometry(w, h, d, 2, r), mat); m.position.set(x, y, z); return m; };

  // Two more cells in the module, same orientation (parallel group).
  CELLS_Z.forEach((z) => { const c = cellBody(M); c.position.z = z; ctx.add(c); });
  // Holders at both ends, thermal pads and the cooling plate under every cell.
  ctx.add(holderPlate(M.holder, -3.12, 0.24), holderPlate(M.holder, 2.82, 0.24));
  [0, ...CELLS_Z].forEach((z) => ctx.add(box(5.4, 0.08, 1.1, M.pad, -0.05, -R - 0.04, z, 0.02)));
  ctx.add(box(8.0, 0.22, 8.9, M.plate, 0.0, Y_PLATE + 0.11, -2.85, 0.04));
  for (let i = 0; i < 9; i++) ctx.add(box(7.6, 0.035, 0.08, M.weld, 0, Y_PLATE + 0.005, 1.3 - i * 1.02, 0.01)); // channel ribs underneath
  // End plates and compression straps behind the monitored cell (the front stays open to see it).
  [-4.05, 3.95].forEach((x) => {
    ctx.add(box(0.18, 3.1, 5.9, M.endplate, x, 0.0, -4.25, 0.04));
    for (let k = 0; k < 4; k++) { const b = new T.Mesh(new T.CylinderGeometry(0.08, 0.08, 0.08, 6), M.bolt); b.rotation.z = Math.PI / 2; b.position.set(x + Math.sign(x) * 0.12, k < 2 ? 1.25 : -1.25, k % 2 ? -1.65 : -6.85); ctx.add(b); }
  });
  [0.85, -0.85].forEach((y) => ctx.add(box(8.2, 0.12, 0.05, M.weld, 0, y, -7.2, 0.01)));

  // Nickel interconnects spot-welded to every terminal; the + one belongs to the monitored cell's terminal module.
  const stripNeg = box(0.04, 0.9, 7.0, M.nickel, -3.47, 0, -2.7, 0.01); ctx.add(stripNeg);
  const stripPos = box(0.04, 0.9, 7.0, M.nickel, 3.56, 0, -2.7, 0.01); mods.terminal.add(stripPos);
  [0, ...CELLS_Z].forEach((z) => [-1, 1].forEach((dy) => {
    const wn = new T.Mesh(new T.CylinderGeometry(0.05, 0.05, 0.02, 10), M.weld); wn.rotation.z = Math.PI / 2; wn.position.set(-3.5, dy * 0.18, z); ctx.add(wn);
    const wp = wn.clone(); wp.position.x = 3.59; mods.terminal.add(wp);
  }));
  // HV terminals: tabs up from each interconnect, copper lugs, orange HV cables leaving the module.
  const tabs = [[-3.47, -6.2], [3.56, -6.2]];
  tabs.forEach(([x, z], i) => {
    const tab = box(0.04, 1.4, 0.5, M.nickel, x, 1.1, z, 0.01);
    const lug = box(0.12, 0.3, 0.5, M.lug, x + (i ? 0.05 : -0.05), 1.85, z, 0.03);
    (i ? mods.terminal : ctx).add(tab); ctx.add(lug);
    ctx.add(cable([[x, 1.95, z], [x + (i ? 0.6 : -0.6), 2.4, z - 0.4], [x + (i ? 1.6 : -1.6), 2.2, z - 1.6], [x + (i ? 2.6 : -2.6), 0.5, z - 2.4]], 0.11, M.hv));
  });

  // Battery-management board on stand-offs above the rear cells.
  const bms = new T.Group(); ctx.add(bms);
  bms.add(box(5.6, 0.06, 4.6, M.pcb, -0.1, 1.72, -4.3, 0.01));
  [[-2.6, -2.2], [2.4, -2.2], [-2.6, -6.4], [2.4, -6.4]].forEach(([x, z]) => bms.add(box(0.1, 0.36, 0.1, M.weld, x, 1.52, z, 0.02)));
  [[-1.6, -3.4, 0.7, 0.55], [-0.4, -3.6, 0.45, 0.45], [0.8, -3.3, 0.55, 0.4]].forEach(([x, z, w, d]) => bms.add(box(w, 0.08, d, M.chip, x, 1.79, z, 0.01)));
  for (let i = 0; i < 12; i++) bms.add(box(0.22, 0.06, 0.1, M.res, -2.2 + (i % 6) * 0.3, 1.78, -5.4 - Math.floor(i / 6) * 0.3, 0.01));
  bms.add(box(1.0, 0.22, 0.35, M.conn, 1.6, 1.86, -6.2, 0.02));
  const leds = [];
  for (let i = 0; i < 6; i++) {
    const mat = new T.MeshBasicMaterial({ color: 0x0f2a3a, toneMapped: false });
    const led = new T.Mesh(new T.SphereGeometry(0.045, 12, 10), mat); led.position.set(-2.0 + i * 0.32, 1.79, -2.2); bms.add(led); leds.push(mat);
  }
  // Sense wires from the board to both interconnects, thermistor leads to every cell.
  ctx.add(cable([[2.3, 1.75, -2.4], [3.3, 1.6, -1.8], [3.58, 0.5, -1.2]], 0.025, M.sense));
  ctx.add(cable([[-2.5, 1.75, -2.4], [-3.3, 1.6, -1.8], [-3.5, 0.5, -1.2]], 0.025, M.sense));
  [0, ...CELLS_Z].forEach((z, i) => ctx.add(cable([[-1.2 + i * 0.5, 1.75, -2.5 - i * 0.6], [-1.0 + i * 0.4, 1.5, z + 0.4], [-0.8 + i * 0.4, R + 0.03, z + 0.15]], 0.018, M.wire)));

  // Coolant loop: fittings on the plate's -X end, hoses out of the module; particles run in and out.
  const hoseIn = new T.CatmullRomCurve3([[-5.8, -1.48, 0.9], [-4.8, -1.5, 0.45], [-4.1, -1.51, 0.2]].map((p) => new T.Vector3(...p)));
  const hoseOut = new T.CatmullRomCurve3([[-4.1, -1.51, -1.4], [-4.8, -1.5, -1.65], [-5.8, -1.48, -2.1]].map((p) => new T.Vector3(...p)));
  [hoseIn, hoseOut].forEach((c) => ctx.add(new T.Mesh(new T.TubeGeometry(c, 32, 0.13, 12, false), M.hose)));
  [0.2, -1.4].forEach((z) => { const f = new T.Mesh(new T.CylinderGeometry(0.17, 0.17, 0.25, 6), M.lug); f.rotation.z = Math.PI / 2; f.position.set(-4.05, -1.51, z); ctx.add(f); });
  const N = 70, pos = new Float32Array(N * 3), col = new Float32Array(N * 3), ph = new Float32Array(N);
  for (let i = 0; i < N; i++) ph[i] = Math.random();
  const geo = new T.BufferGeometry(); geo.setAttribute('position', new T.BufferAttribute(pos, 3)); geo.setAttribute('color', new T.BufferAttribute(col, 3));
  const pmat = new T.PointsMaterial({ size: 0.07, vertexColors: true, transparent: true, opacity: 0.85, depthWrite: false, blending: T.AdditiveBlending });
  const coolant = new T.Points(geo, pmat); coolant.frustumCulled = false; ctx.add(coolant);
  const cold = new T.Color(0x3fa2ff), tmp = new T.Vector3(), c3 = new T.Color();

  // GSAP: discharge pulses through the interconnects and HV cables; BMS LEDs chase while balancing.
  const pulse = { k: 0 };
  const tl = gsap.timeline({ repeat: -1, repeatDelay: 0.9, paused: REDUCED })
    .to(pulse, { k: 1, duration: 0.35, ease: 'power2.out' })
    .to(pulse, { k: 0.15, duration: 1.4, ease: 'power2.inOut' })
    .to(pulse, { k: 0, duration: 0.4 });
  const chase = gsap.timeline({ repeat: -1, paused: REDUCED });
  leds.forEach((m, i) => {
    const on = { r: 0.37, g: 0.83, b: 0.97 }, off = { r: 0.06, g: 0.16, b: 0.23 };
    chase.to(m.color, { ...on, duration: 0.12 }, i * 0.14).to(m.color, { ...off, duration: 0.35 }, i * 0.14 + 0.16);
  });

  let heat = 0;
  return {
    materials: Object.values(M),
    setHeat(h) { heat = h; },
    tick(dt, explode) {
      const k = pulse.k * (1 - explode);
      M.nickel.emissive.setRGB(0.25 * k, 0.6 * k, 1.0 * k); M.nickel.emissiveIntensity = 0.9;
      M.hv.emissiveIntensity = 0.5 * k;
      pmat.opacity = 0.85 * (1 - explode);
      if (REDUCED) return;
      const warm = new T.Color(0xff9a3c);
      for (let i = 0; i < N; i++) {
        ph[i] = (ph[i] + dt * 0.35) % 1;
        const inbound = i % 2 === 0;
        (inbound ? hoseIn : hoseOut).getPointAt(ph[i], tmp);
        pos[i * 3] = tmp.x; pos[i * 3 + 1] = tmp.y; pos[i * 3 + 2] = tmp.z;
        c3.copy(cold); if (!inbound) c3.lerp(warm, 0.25 + heat * 0.6);
        col[i * 3] = c3.r; col[i * 3 + 1] = c3.g; col[i * 3 + 2] = c3.b;
      }
      geo.attributes.position.needsUpdate = true; geo.attributes.color.needsUpdate = true;
    },
    dispose() { tl.kill(); chase.kill(); },
  };
}
