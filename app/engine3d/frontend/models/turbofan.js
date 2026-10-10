/* Turbofan model: a sectioned two-spool turbofan with every C-MAPSS sensor at its station.
 * Rotors and airflow show a running engine; the hot section glows with LPT outlet temperature drift. */
import { T, V2, metal, physical, lathe, axialCylinder, sectionCut, ring, boltCircle, canvasTexture, dispose } from './shared.js?v=5.1.0';

const MODULES = [
  { key: 'fan', name: 'Fan', explode: [-2.6, 0, 0], intro: [-7, 0, 0] }, { key: 'lpc', name: 'LPC', explode: [-1.6, 0, 0], intro: [-6, 0, 0] },
  { key: 'hpc', name: 'HPC', explode: [-0.55, 0, 0], intro: [0, -5, 0] }, { key: 'comb', name: 'Combustor', explode: [0.45, 0, 0], intro: [0, -5, 0] },
  { key: 'hpt', name: 'HPT', explode: [1.25, 0, 0], intro: [0, -5, 0] }, { key: 'lpt', name: 'LPT', explode: [2.15, 0, 0], intro: [6, 0, 0] },
  { key: 'noz', name: 'Nozzle', explode: [3.2, 0, 0], intro: [7, 0, 0] }, { key: 'byp', name: 'Bypass', explode: [0, 2.8, 0], intro: [0, 6, 0] },
];
const LAYOUT = {
  sensor_1: { mod: 'fan', pos: [-4.7, 1.5, 0.6], side: 'L' }, sensor_5: { mod: 'fan', pos: [-4.7, -1.4, 0.7], side: 'L' },
  sensor_2: { mod: 'lpc', pos: [-2.45, 0.95, 0.35], side: 'L' }, sensor_6: { mod: 'byp', pos: [-1.6, 1.72, 0.65], side: 'L' },
  sensor_17: { mod: 'hpc', pos: [-1.2, 1.08, 0.35], side: 'L' }, sensor_11: { mod: 'hpc', pos: [-0.65, 0.55, 0.6], side: 'L' },
  sensor_3: { mod: 'hpc', pos: [-0.25, 0.8, 0.25], side: 'L' }, sensor_7: { mod: 'hpc', pos: [-0.25, -0.72, 0.4], side: 'L' },
  sensor_4: { mod: 'lpt', pos: [2.75, 1.05, 0.4], side: 'L' }, sensor_10: { mod: 'noz', pos: [3.55, 0.85, 0.4], side: 'L' },
  sensor_18: { mod: 'fan', pos: [-4.45, 0.1, 0.05], side: 'R' }, sensor_19: { mod: 'fan', pos: [-4.25, -0.18, 0.15], side: 'R' },
  sensor_8: { mod: 'fan', pos: [-3.95, 0.35, 0.3], side: 'R' }, sensor_13: { mod: 'fan', pos: [-3.6, -0.45, 0.35], side: 'R' },
  sensor_15: { mod: 'byp', pos: [-0.4, -1.72, 0.55], side: 'R' }, sensor_9: { mod: 'hpc', pos: [-1.1, 0.2, 0.22], side: 'R' },
  sensor_14: { mod: 'hpc', pos: [-1.6, -0.3, 0.32], side: 'R' }, sensor_12: { mod: 'comb', pos: [0.45, 1.0, 0.3], side: 'R' },
  sensor_16: { mod: 'comb', pos: [0.45, -0.95, 0.3], side: 'R' }, sensor_20: { mod: 'hpt', pos: [1.15, 0.95, 0.3], side: 'R' },
  sensor_21: { mod: 'lpt', pos: [2.1, 1.2, 0.3], side: 'R' },
};

function bladeGeometry({ hub, tip, chordHub, chordTip, thick, twistHub, twistTip, sweep = 0 }) {
  const g = new T.BoxGeometry(1, 1, 1, 2, 10, 1);
  const p = g.attributes.position;
  for (let i = 0; i < p.count; i++) {
    const x = p.getX(i), y = p.getY(i), z = p.getZ(i), t = y + 0.5;
    const r = hub + (tip - hub) * t, chord = chordHub + (chordTip - chordHub) * t;
    const cx = x * chord;
    let cz = z * thick * (1 - 1.4 * x * x);
    cz += (0.25 - x * x) * chord * 0.22;
    const tw = twistHub + (twistTip - twistHub) * t, c = Math.cos(tw), s = Math.sin(tw);
    p.setXYZ(i, cx * c - cz * s + sweep * t * t, r, cx * s + cz * c);
  }
  g.computeVertexNormals();
  return g;
}
function bladeRing(geo, mat, count, x, phase = 0) {
  const mesh = new T.InstancedMesh(geo, mat, count), m = new T.Matrix4();
  for (let i = 0; i < count; i++) { m.makeRotationX(phase + (i / count) * Math.PI * 2); mesh.setMatrixAt(i, m); }
  mesh.position.x = x;
  return mesh;
}

// Spinner swirl: the painted spiral that tells ground crew the fan is turning.
function spinnerTexture() {
  const t = canvasTexture(512, 512, (g, w, h) => {
    g.fillStyle = '#9aa3ad'; g.fillRect(0, 0, w, h);
    g.strokeStyle = '#f2f4f7'; g.lineWidth = 46;
    g.beginPath(); g.moveTo(-w * 0.2, h); g.bezierCurveTo(w * 0.3, h * 0.7, w * 0.5, h * 0.35, w * 1.2, 0); g.stroke();
  });
  return t;
}
// Saw-tooth trailing edge (chevrons) round an exit at radius r, axial station x, over the solid 270 degrees.
function chevrons(r, x, count, len, mat) {
  const shape = new T.Shape(); shape.moveTo(-0.5, 0); shape.lineTo(0.5, 0); shape.lineTo(0, 1); shape.lineTo(-0.5, 0);
  const geo = new T.ShapeGeometry(shape); geo.rotateZ(-Math.PI / 2); // tip points +X, base along the tangent (Y at phi 0)
  const mesh = new T.InstancedMesh(geo, mat, count), m = new T.Matrix4(), q = new T.Quaternion(), sc = new T.Vector3();
  const width = (2 * Math.PI * r * 0.75) / count;
  for (let i = 0; i < count; i++) {
    const phi = ((i + 0.5) / count) * Math.PI * 1.5;
    q.setFromAxisAngle(new T.Vector3(1, 0, 0), phi);
    sc.set(len, width * 0.98, 1);
    m.compose(new T.Vector3(x, -r * Math.sin(phi), r * Math.cos(phi)), q, sc); mesh.setMatrixAt(i, m);
  }
  return mesh;
}

export function build() {
  const M = {
    shell: new T.MeshStandardMaterial({ color: 0x2b3139, metalness: 0.35, roughness: 0.62, side: T.DoubleSide }),
    core: new T.MeshStandardMaterial({ color: 0x23282f, metalness: 0.4, roughness: 0.58, side: T.DoubleSide }),
    fan: physical(0xb3bcc6, 0.24, 0.95, { clearcoat: 0.3 }),
    spinner: new T.MeshPhysicalMaterial({ map: spinnerTexture(), roughness: 0.3, metalness: 0.6, clearcoat: 0.9, clearcoatRoughness: 0.15 }),
    lip: physical(0xc7ced6, 0.18, 1.0), bolt: physical(0x9aa2ab, 0.3, 0.95),
    disk: metal(0x4c5560, 0.45, 0.8),
    stator: metal(0x6a737e, 0.45, 0.75), lpc: metal(0x9aa4af, 0.32), hpc: metal(0x9aa4af, 0.32),
    comb: new T.MeshStandardMaterial({ color: 0x6d625a, metalness: 0.5, roughness: 0.5, emissive: 0xff6a1f, emissiveIntensity: 1.6 }),
    hpt: new T.MeshStandardMaterial({ color: 0x857a72, metalness: 0.75, roughness: 0.4, emissive: 0xff5a1a, emissiveIntensity: 0.25 }),
    lpt: new T.MeshStandardMaterial({ color: 0x8b847f, metalness: 0.78, roughness: 0.38, emissive: 0xff6a20, emissiveIntensity: 0.1 }),
    plug: metal(0x7d8792, 0.35), shaft: metal(0x56606b, 0.35, 0.9),
  };
  [M.spinner, M.disk, M.plug, M.shaft].forEach((m) => { m.side = T.DoubleSide; });

  const root = new T.Group();
  const mods = {};
  MODULES.forEach((m) => { const g = new T.Group(); mods[m.key] = g; root.add(g); });
  const lpRotors = [], hpRotors = [];
  const combLight = new T.PointLight(0xff7a30, 2.4, 3.2, 2); combLight.position.set(0.45, 0, 0); root.add(combLight);

  const nacelleProfile = [V2(2.12, -4.95), V2(2.13, -4.3), V2(2.15, -3.4), V2(2.14, -1.0), V2(2.08, 0.6), V2(1.98, 1.6),
    V2(2.04, 1.68), V2(2.2, 1.55), V2(2.42, 0.2), V2(2.53, -1.6), V2(2.5, -3.3), V2(2.4, -4.5), V2(2.28, -4.98), V2(2.12, -4.95)];
  mods.byp.add(lathe(nacelleProfile, M.shell, 96, 0, Math.PI * 1.5), sectionCut(nacelleProfile.slice(0, -1)));
  mods.byp.add(ring(2.29, -4.97), ring(2.06, 1.66));
  // Polished inlet lip, as on a real nacelle, and chevrons on the bypass and core exits.
  mods.byp.add(lathe([V2(2.12, -4.95), V2(2.13, -4.6), V2(2.37, -4.6), V2(2.4, -4.5), V2(2.28, -4.98), V2(2.12, -4.95)].map((p) => V2(p.x + 0.004, p.y)), M.lip, 96, 0, Math.PI * 1.5));
  mods.byp.add(chevrons(2.08, 1.66, 24, 0.2, M.shell));
  mods.byp.add(chevrons(0.99, 3.84, 14, 0.15, M.core));
  // Bolted case flanges at the fan frame, the combustor case and the turbine case.
  [[-3.3, 1.17], [0.62, 1.33], [2.02, 1.3]].forEach(([x, r]) => mods.byp.add(boltCircle({ r, x, count: 64, size: 0.028, height: 0.04, facing: -1, mat: M.bolt })));
  mods.byp.add(bladeRing(bladeGeometry({ hub: 1.2, tip: 2.12, chordHub: 0.22, chordTip: 0.26, thick: 0.02, twistHub: 0.25, twistTip: 0.2 }), M.stator, 44, -3.05));

  const coreProfile = [V2(1.08, -3.3), V2(1.13, -3.32), V2(1.24, -2.6), V2(1.31, -1.0), V2(1.31, 0.8), V2(1.27, 2.0), V2(1.2, 2.9), V2(1.0, 3.85),
    V2(0.96, 3.84), V2(1.15, 2.9), V2(1.22, 2.0), V2(1.26, 0.8), V2(1.26, -1.0), V2(1.19, -2.6), V2(1.08, -3.3)];
  mods.byp.add(lathe(coreProfile, M.core, 80, 0, Math.PI * 1.5), sectionCut(coreProfile.slice(0, -1)));

  const spinnerPts = []; for (let i = 0; i <= 24; i++) { const t = i / 24; spinnerPts.push(V2(0.52 * Math.pow(Math.sin((t * Math.PI) / 2), 0.75), -4.75 + t * 0.85)); }
  const fanRotor = new T.Group(); mods.fan.add(fanRotor); lpRotors.push(fanRotor);
  fanRotor.add(lathe(spinnerPts, M.spinner, 64));
  fanRotor.add(bladeRing(bladeGeometry({ hub: 0.48, tip: 2.08, chordHub: 0.42, chordTip: 0.66, thick: 0.05, twistHub: 1.05, twistTip: 0.32, sweep: -0.12 }), M.fan, 22, -3.9));
  fanRotor.add(axialCylinder(0.53, -3.95, -3.45, M.disk));

  const lpcRotor = new T.Group(); mods.lpc.add(lpcRotor); lpRotors.push(lpcRotor);
  [-3.05, -2.8, -2.55].forEach((x, i) => {
    lpcRotor.add(bladeRing(bladeGeometry({ hub: 0.55, tip: 1.0 - i * 0.02, chordHub: 0.12, chordTip: 0.14, thick: 0.02, twistHub: 0.8, twistTip: 0.5 }), M.lpc, 30, x, i * 0.1));
    mods.lpc.add(bladeRing(bladeGeometry({ hub: 0.56, tip: 1.0 - i * 0.02, chordHub: 0.08, chordTip: 0.09, thick: 0.015, twistHub: -0.5, twistTip: -0.4 }), M.stator, 36, x + 0.12));
  });
  lpcRotor.add(axialCylinder(0.55, -3.15, -2.45, M.disk));

  const hpcRotor = new T.Group(); mods.hpc.add(hpcRotor); hpRotors.push(hpcRotor);
  for (let i = 0; i < 9; i++) {
    const x = -2.15 + i * 0.235, hub = 0.56 + i * 0.007, tip = 0.96 - i * 0.026;
    hpcRotor.add(bladeRing(bladeGeometry({ hub, tip, chordHub: 0.1, chordTip: 0.1, thick: 0.016, twistHub: 0.75, twistTip: 0.55 }), M.hpc, 34 + i * 3, x, i * 0.2));
    mods.hpc.add(bladeRing(bladeGeometry({ hub: hub + 0.01, tip: tip + 0.01, chordHub: 0.06, chordTip: 0.06, thick: 0.012, twistHub: -0.5, twistTip: -0.4 }), M.stator, 40 + i * 3, x + 0.11));
  }
  hpcRotor.add(lathe([V2(0.5, -2.25), V2(0.57, -2.2), V2(0.63, -0.1), V2(0.5, -0.05)], M.disk, 48));

  {
    const pts = []; for (let i = 0; i <= 40; i++) { const a = (i / 40) * Math.PI * 2; pts.push(V2(0.76 + 0.13 * Math.cos(a), 0.45 + 0.36 * Math.sin(a))); }
    mods.comb.add(lathe(pts, M.comb, 96));
    const nozzleGeo = new T.SphereGeometry(0.03, 10, 8);
    for (let i = 0; i < 20; i++) { const a = (i / 20) * Math.PI * 2, n = new T.Mesh(nozzleGeo, M.disk); n.position.set(0.08, 0.76 * Math.cos(a), 0.76 * Math.sin(a)); mods.comb.add(n); }
  }

  const hptRotor = new T.Group(); mods.hpt.add(hptRotor); hpRotors.push(hptRotor);
  [0.98, 1.24].forEach((x, i) => {
    hptRotor.add(bladeRing(bladeGeometry({ hub: 0.6, tip: 0.86 + i * 0.02, chordHub: 0.12, chordTip: 0.11, thick: 0.03, twistHub: -0.9, twistTip: -0.6 }), M.hpt, 40, x));
    mods.hpt.add(bladeRing(bladeGeometry({ hub: 0.6, tip: 0.87 + i * 0.02, chordHub: 0.08, chordTip: 0.08, thick: 0.02, twistHub: 0.7, twistTip: 0.5 }), M.stator, 30, x - 0.12));
  });
  hptRotor.add(axialCylinder(0.6, 0.9, 1.32, M.disk));
  const lptRotor = new T.Group(); mods.lpt.add(lptRotor); lpRotors.push(lptRotor);
  for (let i = 0; i < 5; i++) {
    const x = 1.55 + i * 0.29;
    lptRotor.add(bladeRing(bladeGeometry({ hub: 0.6, tip: 0.9 + i * 0.055, chordHub: 0.13, chordTip: 0.12, thick: 0.025, twistHub: -0.85, twistTip: -0.55 }), M.lpt, 46 + i * 4, x, i * 0.13));
    mods.lpt.add(bladeRing(bladeGeometry({ hub: 0.6, tip: 0.92 + i * 0.055, chordHub: 0.08, chordTip: 0.08, thick: 0.018, twistHub: 0.6, twistTip: 0.45 }), M.stator, 40 + i * 4, x - 0.13));
  }
  lptRotor.add(lathe([V2(0.45, 1.4), V2(0.6, 1.45), V2(0.6, 2.85), V2(0.45, 2.9)], M.disk, 48));
  mods.noz.add(lathe([V2(0.6, 2.85), V2(0.58, 3.2), V2(0.48, 3.7), V2(0.3, 4.15), V2(0.0, 4.55)], M.plug, 64));
  const lpShaft = axialCylinder(0.12, -3.9, 2.9, M.shaft, 24); lpRotors.push(lpShaft); mods.lpc.add(lpShaft);

  // Airflow: the gas path, cool bypass and core heating after the combustor.
  const flowMat = new T.ShaderMaterial({
    transparent: true, depthWrite: false, blending: T.AdditiveBlending,
    uniforms: { uTime: { value: 0 }, uHeat: { value: 0 }, uPix: { value: 300 }, uFade: { value: 1 } },
    vertexShader: `
      attribute float aR; attribute float aAng; attribute float aPh; attribute float aSp; attribute float aType; attribute float aSize;
      uniform float uTime; uniform float uHeat; uniform float uPix; uniform float uFade;
      varying vec3 vCol; varying float vA;
      const float CX[11] = float[11](-7.0,-3.9,-3.2,-2.2,-0.1,0.9,1.5,2.8,3.9,4.4,7.5);
      const float CH[11] = float[11](0.15,0.5,0.55,0.57,0.63,0.63,0.62,0.6,0.32,0.05,0.05);
      const float CT[11] = float[11](0.95,1.0,1.0,0.95,0.74,0.86,0.9,1.1,0.95,0.92,1.4);
      const float BX[11] = float[11](-7.0,-5.0,-3.9,-3.2,-1.0,0.8,1.6,2.9,3.9,6.0,7.5);
      const float BH[11] = float[11](1.1,1.1,1.12,1.2,1.34,1.34,1.29,1.22,1.04,1.0,1.0);
      const float BT[11] = float[11](2.0,2.04,2.05,2.08,2.1,2.05,1.96,2.02,2.12,2.3,2.5);
      float pw(float x, float xs[11], float ys[11]){
        if (x <= xs[0]) return ys[0];
        for (int i = 0; i < 10; i++){ if (x <= xs[i+1]) return mix(ys[i], ys[i+1], (x - xs[i])/(xs[i+1]-xs[i])); }
        return ys[10];
      }
      void main(){
        float s = fract(aPh + uTime*aSp);
        float x = mix(-7.0, 7.5, s);
        float r; vec3 c;
        if (aType < 0.5) {
          r = mix(pw(x, BX, BH), pw(x, BX, BT), aR);
          c = vec3(0.42, 0.55, 0.72);
        } else {
          r = mix(pw(x, CX, CH), pw(x, CX, CT), aR);
          c = mix(vec3(0.45, 0.6, 0.78), vec3(0.85, 0.85, 0.85), smoothstep(-3.5, -0.3, x));
          c = mix(c, vec3(1.0, 0.62, 0.32) * (1.0 + uHeat * 0.5), smoothstep(-0.1, 0.6, x));
          c = mix(c, vec3(0.75, 0.42, 0.28), smoothstep(2.0, 6.0, x));
        }
        float ang = aAng + x*0.18;
        vec4 mv = modelViewMatrix*vec4(x, r*cos(ang), r*sin(ang), 1.0);
        gl_Position = projectionMatrix*mv;
        gl_PointSize = aSize*uPix/(-mv.z);
        vCol = c;
        vA = smoothstep(0.0, 0.06, s)*(1.0 - smoothstep(0.75, 1.0, s))*uFade;
      }`,
    fragmentShader: `varying vec3 vCol; varying float vA;
      void main(){ float d = length(gl_PointCoord - 0.5); gl_FragColor = vec4(vCol, vA*smoothstep(0.5, 0.15, d)*0.32); }`,
  });
  {
    const N = 2200, g = new T.BufferGeometry(), at = (n) => new Float32Array(n);
    const aR = at(N), aAng = at(N), aPh = at(N), aSp = at(N), aType = at(N), aSize = at(N);
    for (let i = 0; i < N; i++) {
      const core = i % 2 === 0;
      aR[i] = Math.random(); aAng[i] = Math.random() * Math.PI * 2; aPh[i] = Math.random();
      aSp[i] = core ? 0.06 + Math.random() * 0.02 : 0.05 + Math.random() * 0.02;
      aType[i] = core ? 1 : 0; aSize[i] = 0.035 + Math.random() * 0.03;
    }
    g.setAttribute('position', new T.BufferAttribute(at(N * 3), 3));
    [['aR', aR], ['aAng', aAng], ['aPh', aPh], ['aSp', aSp], ['aType', aType], ['aSize', aSize]].forEach(([k, v]) => g.setAttribute(k, new T.BufferAttribute(v, 1)));
    const flow = new T.Points(g, flowMat); flow.frustumCulled = false; root.add(flow);
  }

  return {
    key: 'turbofan', root, mods, modules: MODULES, layout: LAYOUT, materials: M,
    panels: { L: 'Temperature and pressure', R: 'Speed and flow' },
    view: { target: [-0.2, 0, 0], dir: [0.55, 0.34, 1], twin: [4.5, 2.8], hero: [5.9, 3.2], min: 7 },
    groundY: -2.9,
    labels: { fan: [-3.9, -2.35, 0], lpc: [-2.8, -2.35, 0], hpc: [-1.1, -2.35, 0], comb: [0.45, -2.35, 0],
              hpt: [1.1, -2.35, 0], lpt: [2.2, -2.35, 0], noz: [3.7, -2.35, 0] },
    // Module tint: a degrading module takes on its status colour. The hot section glows with EGT (T50)
    // drift; a gentle flicker reads as combustion, not alarm.
    apply({ modLevel, z, tsec, levels, reduced }) {
      const tint = (mat, mod) => {
        const lv = modLevel[mod];
        if (lv < 0) { mat.emissive.setRGB(0, 0, 0); return; }
        mat.emissive.set(levels[lv].color); mat.emissiveIntensity = [0.32, 0.2, 0.1][lv];
      };
      tint(M.fan, 'fan'); tint(M.lpc, 'lpc'); tint(M.hpc, 'hpc');
      const heat = Math.max(0, Math.min(1, (z.sensor_4 || 0) / 4));
      M.comb.emissiveIntensity = 1.6 + heat * 1.2 + (reduced ? 0 : 0.12 * Math.sin(tsec * 13) + 0.06 * Math.sin(tsec * 31));
      M.hpt.emissiveIntensity = 0.3 + heat * 0.6;
      M.lpt.emissiveIntensity = 0.08 + heat * 0.3;
      combLight.intensity = 2.2 + heat * 2;
      flowMat.uniforms.uHeat.value = heat;
    },
    tick(dt, tsec, { reduced, explode }) {
      flowMat.uniforms.uFade.value = 1 - explode;
      if (reduced) return;
      lpRotors.forEach((r) => { r.rotation.x += dt * 2.2; });
      hpRotors.forEach((r) => { r.rotation.x += dt * 4.4; });
      flowMat.uniforms.uTime.value = tsec;
    },
    resize(H, pixelRatio) { flowMat.uniforms.uPix.value = H * pixelRatio * 0.9; },
    conditionText(c, i) {
      return c ? `${Math.round(c.setting_1[i])} kft  M${c.setting_2[i].toFixed(2)}  TRA ${Math.round(c.setting_3[i])}` : '';
    },
    dispose() { dispose(root); },
  };
}
