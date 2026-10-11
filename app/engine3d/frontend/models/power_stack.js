/* The inverter around the monitored IGBT module: a 3-phase stack. Two more half-bridge modules (phases V and
 * W) with their gate-driver boards sit behind it on one long finned heat sink cooled by a fan; a DC-link
 * bank of film capacitors feeds all three through a laminated busbar along the right side; each phase's AC
 * output leaves on the left through a Hall-effect current sensor to the output terminal block.
 *
 * GSAP drives 3-phase PWM: each phase's gate LED and AC bar pulse in turn, 120 degrees apart, and the DC
 * link ripples with them. Cooling air runs through the fin channels every frame, warming as it passes the
 * modules. Everything here is context: it stays put and ghosts in the exploded view. */
import { T, physical, metal, canvasTexture } from './shared.js?v=6.1.0';

const PHASE_Z = [0, -3.4, -6.8]; // U (the monitored module), V, W
const SINK = { x0: -2.3, x1: 2.3, z0: -8.4, z1: 1.6, top: -1.6 };

const capTex = () => canvasTexture(256, 256, (g, w, h) => {
  g.fillStyle = '#3a414a'; g.fillRect(0, 0, w, h);
  g.fillStyle = '#e6e8eb'; g.font = '600 30px "IBM Plex Sans", sans-serif'; g.fillText('DC-LINK', 40, 80);
  g.font = '400 24px "IBM Plex Mono", monospace'; g.fillText('450 uF', 60, 130); g.fillText('900 V DC', 52, 170);
});

export function stackContext(root, sinkLayer, M0) {
  const gsap = window.gsap;
  const REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const M = {
    sink: metal(0xa7b0ba, 0.4, 0.85),
    frame: physical(0x1d2127, 0.55, 0.1), lid: physical(0x262b31, 0.5, 0.1),
    pcb: M0.pcb, chip: M0.chip, pin: M0.pin,
    copper: physical(0xc47a3c, 0.25, 1.0, { emissive: 0x000000 }),
    insul: new T.MeshStandardMaterial({ color: 0xe0b14a, roughness: 0.6 }),
    cap: new T.MeshStandardMaterial({ map: capTex(), roughness: 0.5, metalness: 0.2, emissive: 0x000000 }),
    capTop: physical(0x8d949c, 0.35, 0.8),
    bracket: physical(0x4c5560, 0.45, 0.7),
    sensor: physical(0x15181c, 0.45, 0.2),
    block: physical(0x2f5e9e, 0.5, 0.2),
    fanFrame: physical(0x22282f, 0.5, 0.3), blade: physical(0x2a3038, 0.4, 0.3),
    bolt: physical(0xa3abb4, 0.3, 0.95),
  };
  const box = (w, h, d, mat, x, y, z, r = 0.02) => { const m = new T.Mesh(new T.RoundedBoxGeometry(w, h, d, 2, r), mat); m.position.set(x, y, z); return m; };
  const ctx = new T.Group(); root.add(ctx);

  // One long heat sink under all three modules (part of the monitored module's bottom layer: it never moves).
  const L = SINK.z1 - SINK.z0, zc = (SINK.z0 + SINK.z1) / 2;
  sinkLayer.add(box(SINK.x1 - SINK.x0 + 0.3, 0.3, L, M.sink, 0, SINK.top - 0.15, zc, 0.03));
  for (let i = 0; i < 15; i++) sinkLayer.add(box(0.07, 0.75, L - 0.1, M.sink, -2.2 + i * 0.314, SINK.top - 0.68, zc, 0.015));

  // Phases V and W: closed modules with lids, terminals and their own gate-driver boards.
  const leds = [];
  PHASE_Z.slice(1).forEach((z) => {
    ctx.add(box(4.0, 0.17, 2.5, M.copper, 0, -1.485, z, 0.02));
    ctx.add(box(4.0, 0.95, 2.5, M.frame, 0, -0.93, z, 0.03));
    ctx.add(box(4.0, 0.08, 2.5, M.lid, 0, -0.41, z, 0.02));
    [-1.3, 0, 1.3].forEach((x) => ctx.add(box(0.36, 0.05, 0.5, M.copper, x, -0.35, z - 0.9, 0.01)));
    ctx.add(box(3.4, 0.05, 1.3, M.pcb, -0.1, 0.15, z - 0.5, 0.01));
    [[-1.6, -1.0], [1.4, -1.0], [-1.6, 0.0], [1.4, 0.0]].forEach(([x, dz]) => ctx.add(box(0.08, 0.55, 0.08, M.pin, x, -0.13, z + dz, 0.01)));
    [[-0.9, -0.6, 0.5, 0.4], [0.2, -0.4, 0.35, 0.35], [1.0, -0.7, 0.3, 0.25]].forEach(([x, dz, w, d]) => ctx.add(box(w, 0.06, d, M.chip, x, 0.2, z + dz, 0.01)));
    const mat = new T.MeshBasicMaterial({ color: 0x0f2a3a, toneMapped: false });
    const led = new T.Mesh(new T.SphereGeometry(0.04, 12, 10), mat); led.position.set(1.3, 0.2, z + 0.05); ctx.add(led); leds.push(mat);
  });

  // Laminated DC busbar along the right side (DC+ and DC- plates with insulation between), straps to every module.
  ctx.add(box(0.06, 0.9, 9.0, M.copper, 2.45, -0.75, -3.4, 0.01), box(0.03, 1.0, 9.1, M.insul, 2.52, -0.75, -3.4, 0.005),
          box(0.06, 0.9, 9.0, M.copper, 2.59, -0.75, -3.4, 0.01));
  PHASE_Z.forEach((z) => ctx.add(box(0.42, 0.04, 0.3, M.copper, 2.24, -0.33, z - 1.0, 0.01))); // outside each module's lid
  // DC-link capacitor bank on its bracket to the right.
  ctx.add(box(1.9, 0.12, 9.2, M.bracket, 3.75, SINK.top + 0.06, -3.4, 0.02));
  for (let i = 0; i < 3; i++) for (let j = 0; j < 4; j++) {
    const z = 0.6 - j * 2.3 - (i % 2) * 0.4, x = 3.2 + i * 0.55;
    const c = new T.Mesh(new T.CylinderGeometry(0.25, 0.25, 1.15, 28), M.cap); c.position.set(x, SINK.top + 0.7, z); ctx.add(c);
    const top = new T.Mesh(new T.CylinderGeometry(0.2, 0.25, 0.08, 28), M.capTop); top.position.set(x, SINK.top + 1.31, z); ctx.add(top);
  }
  ctx.add(box(0.8, 0.04, 9.0, M.copper, 3.0, -0.25, -3.4, 0.01)); // link from the bank to the laminated bar

  // AC outputs on the left: a bar per phase through a Hall current sensor to the terminal block.
  const acBars = [];
  PHASE_Z.forEach((z) => {
    const mat = M.copper.clone(); acBars.push(mat);
    ctx.add(box(1.3, 0.05, 0.36, mat, -2.72, -0.33, z - 0.9, 0.01)); // starts outside the module's lid
    const s = box(0.4, 0.5, 0.5, M.sensor, -2.75, -0.33, z - 0.9, 0.05); ctx.add(s);
    ctx.add(box(0.45, 0.5, 0.6, M.block, -3.45, -0.4, z - 0.9, 0.04));
    for (let k = 0; k < 2; k++) { const b = new T.Mesh(new T.CylinderGeometry(0.06, 0.06, 0.06, 6), M.bolt); b.position.set(-3.45, -0.12, z - 1.05 + k * 0.3); ctx.add(b); }
  });

  // Cooling fan behind the sink, blowing along the fin channels.
  const fanZ = SINK.z0 - 0.35;
  ctx.add(box(3.2, 1.3, 0.25, M.fanFrame, 0, SINK.top - 0.55, fanZ, 0.06));
  const shroud = new T.Mesh(new T.TorusGeometry(0.55, 0.05, 10, 48), M.fanFrame); shroud.position.set(0, SINK.top - 0.55, fanZ + 0.13); ctx.add(shroud);
  const fan = new T.Group(); fan.position.set(0, SINK.top - 0.55, fanZ + 0.15); ctx.add(fan);
  for (let i = 0; i < 7; i++) { const b = new T.Mesh(new T.BoxGeometry(0.14, 0.48, 0.02), M.blade); b.geometry.translate(0, 0.26, 0); b.rotation.z = (i / 7) * Math.PI * 2; b.rotation.y = 0.4; fan.add(b); }

  // Air through the fin channels, from the fan to the open front, warming past each module.
  const N = 220, pos = new Float32Array(N * 3), col = new Float32Array(N * 3), ph = new Float32Array(N), lane = new Float32Array(N);
  for (let i = 0; i < N; i++) { ph[i] = Math.random(); lane[i] = -2.05 + (i % 14) * 0.314 + 0.157; }
  const geo = new T.BufferGeometry(); geo.setAttribute('position', new T.BufferAttribute(pos, 3)); geo.setAttribute('color', new T.BufferAttribute(col, 3));
  const pmat = new T.PointsMaterial({ size: 0.05, vertexColors: true, transparent: true, opacity: 0.7, depthWrite: false, blending: T.AdditiveBlending });
  const air = new T.Points(geo, pmat); air.frustumCulled = false; ctx.add(air);
  const cool = new T.Color(0x5fd4f8), warm = new T.Color(0xff9a3c), c3 = new T.Color();

  // GSAP: 3-phase PWM, 120 degrees apart; the DC link ripples with the switching.
  const pwm = { u: 0, v: 0, w: 0, ripple: 0 };
  const period = 1.2;
  const tl = gsap.timeline({ repeat: -1, paused: REDUCED });
  ['u', 'v', 'w'].forEach((k, i) => {
    tl.to(pwm, { [k]: 1, duration: period * 0.18, ease: 'power2.out' }, (i * period) / 3)
      .to(pwm, { [k]: 0, duration: period * 0.3, ease: 'power2.in' }, (i * period) / 3 + period * 0.22)
      .to(pwm, { ripple: 1, duration: 0.08, yoyo: true, repeat: 1 }, (i * period) / 3);
  });
  tl.to({}, { duration: 0.01 }, period); // close the loop at exactly one period

  let heat = 0, fanRate = 1;
  return {
    pwm,
    materials: [M.frame, M.lid, M.copper, M.insul, M.cap, M.capTop, M.bracket, M.sensor, M.block, M.fanFrame, M.blade, ...acBars],
    setHeat(h) { heat = h; fanRate = 1 + h * 1.2; },
    tick(dt, explode, reduced) {
      const k = 1 - explode;
      acBars.forEach((m, i) => { const v = [pwm.u, pwm.v, pwm.w][i] * k; m.emissive.setRGB(0.25 * v, 0.6 * v, 1.0 * v); m.emissiveIntensity = 0.9; });
      leds.forEach((m, i) => m.color.set([pwm.v, pwm.w][i] > 0.5 ? 0x5fd4f8 : 0x0f2a3a));
      M.cap.emissive.setRGB(0.1 * pwm.ripple * k, 0.25 * pwm.ripple * k, 0.4 * pwm.ripple * k);
      pmat.opacity = 0.7 * k;
      if (reduced) return;
      fan.rotation.z += dt * 14 * fanRate;
      for (let i = 0; i < N; i++) {
        ph[i] = (ph[i] + dt * 0.18 * fanRate) % 1;
        const z = SINK.z0 + ph[i] * (L + 0.6);
        pos[i * 3] = lane[i]; pos[i * 3 + 1] = SINK.top - 0.35 - ((i * 7) % 5) * 0.11; pos[i * 3 + 2] = z;
        c3.copy(cool).lerp(warm, Math.min(1, ph[i] * (0.4 + heat)));
        col[i * 3] = c3.r; col[i * 3 + 1] = c3.g; col[i * 3 + 2] = c3.b;
      }
      geo.attributes.position.needsUpdate = true; geo.attributes.color.needsUpdate = true;
    },
    dispose() { tl.kill(); },
  };
}
