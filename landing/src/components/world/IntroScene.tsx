'use client';

import { useMemo, useRef } from 'react';
import * as THREE from 'three';
import { useFrame, useThree } from '@react-three/fiber';
import { flight, introFreeze, RUN } from '@/lib/flight';

/* ────────────────────────────────────────────────────────────────────────────
   The opening run, in 3D. Sunset over a sea of cloud; a twin-engine delta comes in
   low and fast, banks across, pulls up right in front of the camera and goes
   supersonic: vapour cone, boom, and a shockwave that washes over the lens.
   Original airframe, built from primitives. Nose is +Z in the jet's own space.
   ──────────────────────────────────────────────────────────────────────────── */

export const intro = {
  /** the run owns the camera */
  active: false,
  /** the world has swapped to the site */
  swapped: false,
  start: -1,
  sonicFired: false,
  washFired: false,
};

const ss = (a: number, b: number, x: number) => {
  const t = Math.min(1, Math.max(0, (x - a) / (b - a)));
  return t * t * (3 - 2 * t);
};

/* Flight path: keyframe positions and the run time at which the jet passes each. */
const PATH = new THREE.CatmullRomCurve3(
  [
    new THREE.Vector3(26, -5.5, -260),
    new THREE.Vector3(12, -3.2, -125),
    new THREE.Vector3(3.2, -1.2, -46),
    new THREE.Vector3(-0.8, 0.2, -16),
    new THREE.Vector3(-0.6, 2.6, -7.2),
    new THREE.Vector3(0.6, 11, -7.8),
    new THREE.Vector3(2.4, 60, -9),
  ],
  false,
  'centripetal',
);
const TIMES = [0, 0.72, 1.18, 1.46, 1.66, 1.88, 2.3];
function pathParam(T: number) {
  const n = TIMES.length - 1;
  if (T <= 0) return 0;
  if (T >= TIMES[n]) return 1;
  let i = 0;
  while (T > TIMES[i + 1]) i++;
  const f = (T - TIMES[i]) / (TIMES[i + 1] - TIMES[i]);
  return (i + f) / n;
}
const CAM_START = new THREE.Vector3(0, -0.6, 14);

/* ── shared look-up textures ── */
function cloudTexture() {
  const c = document.createElement('canvas');
  c.width = c.height = 128;
  const g = c.getContext('2d')!;
  let seed = 3;
  const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
  for (let i = 0; i < 26; i++) {
    const x = 64 + (rnd() - 0.5) * 60;
    const y = 64 + (rnd() - 0.5) * 34;
    const r = 18 + rnd() * 26;
    const gr = g.createRadialGradient(x, y, 0, x, y, r);
    gr.addColorStop(0, 'rgba(255,255,255,0.22)');
    gr.addColorStop(1, 'rgba(255,255,255,0)');
    g.fillStyle = gr;
    g.fillRect(0, 0, 128, 128);
  }
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

/* ── Sky dome: dusk gradient with the sun on the horizon ── */
const skyVert = /* glsl */ `
  varying vec3 vDir;
  void main(){
    vDir = normalize(position);
    vec4 p = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    gl_Position = p.xyww;
  }`;
const skyFrag = /* glsl */ `
  uniform float uOpacity; uniform vec3 uSun;
  varying vec3 vDir;
  void main(){
    vec3 d = normalize(vDir);
    float h = d.y;
    vec3 zenith = vec3(0.012, 0.028, 0.07);
    vec3 mid = vec3(0.06, 0.08, 0.2);
    vec3 horizon = vec3(1.0, 0.46, 0.22);
    vec3 below = vec3(0.03, 0.025, 0.05);
    vec3 col = mix(horizon, mid, smoothstep(0.0, 0.16, h));
    col = mix(col, zenith, smoothstep(0.14, 0.6, h));
    col = mix(col, below, smoothstep(0.0, -0.12, h));
    float s = max(dot(d, normalize(uSun)), 0.0);
    col += vec3(1.0, 0.62, 0.32) * (pow(s, 900.0) * 6.0 + pow(s, 40.0) * 0.6 + pow(s, 6.0) * 0.18);
    gl_FragColor = vec4(col, uOpacity);
  }`;

function Sky({ fade }: { fade: { v: number } }) {
  const mesh = useRef<THREE.Mesh>(null);
  const uniforms = useMemo(() => ({ uOpacity: { value: 1 }, uSun: { value: new THREE.Vector3(-0.35, 0.025, -1) } }), []);
  useFrame(({ camera }) => {
    if (mesh.current) mesh.current.position.copy(camera.position);
    uniforms.uOpacity.value = fade.v;
  });
  return (
    <mesh ref={mesh} renderOrder={-10} frustumCulled={false}>
      <sphereGeometry args={[150, 48, 24]} />
      <shaderMaterial vertexShader={skyVert} fragmentShader={skyFrag} uniforms={uniforms} side={THREE.BackSide} depthWrite={false} transparent />
    </mesh>
  );
}

/* ── Cloud sea: instanced billboards, lit by the low sun, streaming past ── */
const cloudVert = /* glsl */ `
  uniform float uTime; uniform float uSpeed;
  attribute vec3 aOffset; attribute float aSize; attribute float aSeed;
  varying vec2 vUv; varying float vFog; varying float vSeed; varying float vRim;
  void main(){
    vec3 o = aOffset;
    o.z = mod(o.z + uTime * uSpeed * (0.85 + aSeed * 0.3) + 330.0, 360.0) - 330.0;
    vec4 mv = modelViewMatrix * vec4(o, 1.0);
    mv.xy += position.xy * vec2(aSize * 1.9, aSize);
    vUv = uv; vSeed = aSeed;
    float dist = -mv.z;
    vFog = smoothstep(320.0, 120.0, dist) * smoothstep(1.5, 9.0, dist);
    vRim = clamp((o.x + 120.0) / 240.0, 0.0, 1.0);
    gl_Position = projectionMatrix * mv;
  }`;
const cloudFrag = /* glsl */ `
  uniform sampler2D uMap; uniform float uOpacity;
  varying vec2 vUv; varying float vFog; varying float vSeed; varying float vRim;
  void main(){
    vec4 t = texture2D(uMap, vUv);
    vec3 dark = vec3(0.07, 0.08, 0.16);
    vec3 lit = mix(vec3(1.0, 0.55, 0.32), vec3(0.75, 0.5, 0.55), vRim);
    vec3 col = mix(dark, lit, smoothstep(0.25, 0.95, vUv.y) * (0.55 + vSeed * 0.45));
    gl_FragColor = vec4(col, t.a * vFog * uOpacity * 1.6);
  }`;

function Clouds({ count, fade }: { count: number; fade: { v: number } }) {
  const geo = useMemo(() => {
    const base = new THREE.PlaneGeometry(1, 1);
    const g = new THREE.InstancedBufferGeometry();
    g.index = base.index;
    g.setAttribute('position', base.getAttribute('position'));
    g.setAttribute('uv', base.getAttribute('uv'));
    const off = new Float32Array(count * 3);
    const size = new Float32Array(count);
    const seed = new Float32Array(count);
    let s = 17;
    const rnd = () => ((s = (s * 16807) % 2147483647) / 2147483647);
    for (let i = 0; i < count; i++) {
      off.set([(rnd() - 0.5) * 240, -8 - rnd() * 5, -330 + rnd() * 360], i * 3);
      size[i] = 9 + rnd() * 18;
      seed[i] = rnd();
    }
    g.setAttribute('aOffset', new THREE.InstancedBufferAttribute(off, 3));
    g.setAttribute('aSize', new THREE.InstancedBufferAttribute(size, 1));
    g.setAttribute('aSeed', new THREE.InstancedBufferAttribute(seed, 1));
    g.instanceCount = count;
    return g;
  }, [count]);
  const uniforms = useMemo(() => ({ uTime: { value: 0 }, uSpeed: { value: 70 }, uMap: { value: cloudTexture() }, uOpacity: { value: 1 } }), []);
  useFrame(() => {
    uniforms.uTime.value = Math.max(0, flight.introT);
    uniforms.uOpacity.value = fade.v;
  });
  return (
    <mesh geometry={geo} frustumCulled={false} renderOrder={-5}>
      <shaderMaterial vertexShader={cloudVert} fragmentShader={cloudFrag} uniforms={uniforms} transparent depthWrite={false} />
    </mesh>
  );
}

/* ── Afterburner: shock diamonds, additive ── */
const burnVert = /* glsl */ `
  varying vec2 vUv; varying vec3 vN; varying vec3 vV;
  void main(){
    vUv = uv;
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    vN = normalize(normalMatrix * normal); vV = normalize(-mv.xyz);
    gl_Position = projectionMatrix * mv;
  }`;
const burnFrag = /* glsl */ `
  uniform float uTime; uniform float uPower;
  varying vec2 vUv; varying vec3 vN; varying vec3 vV;
  void main(){
    float t = vUv.y;
    float core = pow(abs(dot(vN, vV)), 1.3);
    float dia = pow(0.5 + 0.5 * cos(t * 26.0 - uTime * 3.0), 8.0) * smoothstep(0.85, 0.05, t);
    float flick = 0.82 + 0.18 * sin(uTime * 53.0 + t * 31.0);
    vec3 col = mix(vec3(1.0, 0.85, 0.6), vec3(1.0, 0.42, 0.15), smoothstep(0.0, 0.35, t));
    col = mix(col, vec3(0.35, 0.6, 1.0), smoothstep(0.35, 0.9, t)) * (1.2 + dia * 2.5);
    float a = pow(1.0 - t, 1.6) * core * (0.4 + dia) * flick * uPower;
    gl_FragColor = vec4(col, a);
  }`;

/* ── Vapour cone (Prandtl–Glauert condensation) ── */
const coneFrag = /* glsl */ `
  uniform float uTime; uniform float uAmount;
  varying vec2 vUv; varying vec3 vN; varying vec3 vV;
  float hash(vec2 p){ return fract(sin(dot(p, vec2(41.3, 289.1))) * 43758.5453); }
  float noise(vec2 p){ vec2 i = floor(p), f = fract(p); f = f*f*(3.0-2.0*f);
    return mix(mix(hash(i), hash(i+vec2(1,0)), f.x), mix(hash(i+vec2(0,1)), hash(i+vec2(1,1)), f.x), f.y); }
  void main(){
    float edge = 1.0 - abs(dot(vN, vV));
    float n = noise(vec2(vUv.x * 40.0, vUv.y * 6.0 - uTime * 4.0)) * 0.6 + noise(vec2(vUv.x * 90.0, vUv.y * 14.0)) * 0.4;
    float body = smoothstep(1.0, 0.25, vUv.y) * smoothstep(0.0, 0.18, vUv.y);
    float a = (0.25 + edge * 0.9) * body * (0.35 + n) * uAmount;
    gl_FragColor = vec4(vec3(0.93, 0.96, 1.0), a * 0.85);
  }`;

/* ── Shockwave shell ── */
const shockFrag = /* glsl */ `
  uniform float uFade;
  varying vec2 vUv; varying vec3 vN; varying vec3 vV;
  void main(){
    float e = 1.0 - abs(dot(vN, vV));
    float ring = pow(e, 5.0) * 1.6 + pow(e, 1.5) * 0.12;
    vec3 col = mix(vec3(0.75, 0.88, 1.0), vec3(1.0, 0.7, 0.45), pow(e, 8.0));
    gl_FragColor = vec4(col, ring * uFade);
  }`;

/* ── Wingtip vortex trails ── */
const trailFrag = /* glsl */ `
  uniform float uAmount;
  varying vec2 vUv;
  void main(){
    float across = 1.0 - abs(vUv.x - 0.5) * 2.0;
    float a = pow(across, 2.0) * pow(1.0 - vUv.y, 1.4) * uAmount;
    gl_FragColor = vec4(vec3(0.92, 0.95, 1.0), a * 0.7);
  }`;
const trailVert = /* glsl */ `
  varying vec2 vUv;
  void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;

function makeShape(pts: [number, number][]) {
  const s = new THREE.Shape();
  pts.forEach(([x, y], i) => (i ? s.lineTo(x, y) : s.moveTo(x, y)));
  s.closePath();
  return s;
}

function useAirframe() {
  return useMemo(() => {
    const fus = new THREE.LatheGeometry(
      ([[0, 5.3], [0.13, 4.9], [0.32, 4.1], [0.48, 3.2], [0.6, 2.0], [0.66, 0.5], [0.68, -1.5], [0.66, -3.4], [0.6, -4.5], [0.56, -4.9]] as [number, number][]).map(
        ([r, y]) => new THREE.Vector2(r, y),
      ),
      48,
    );
    fus.rotateX(Math.PI / 2);
    fus.scale(1.2, 0.82, 1);
    fus.computeVertexNormals();

    const ext = { depth: 0.07, bevelEnabled: true, bevelThickness: 0.025, bevelSize: 0.03, bevelSegments: 1 };
    // shape y becomes +Z after rotateX(+90°), thickness goes to -Y
    const wing = new THREE.ExtrudeGeometry(makeShape([[0.55, 1.4], [4.7, -2.7], [4.75, -3.35], [0.55, -3.7]]), ext);
    wing.rotateX(Math.PI / 2);
    wing.translate(0, 0.03, 0);
    const stab = new THREE.ExtrudeGeometry(makeShape([[0.5, -3.5], [2.35, -4.75], [2.4, -5.15], [0.5, -5.0]]), ext);
    stab.rotateX(Math.PI / 2);
    // fin: shape x → world z, shape y → world y, thickness → x
    const fin = new THREE.ExtrudeGeometry(makeShape([[-2.85, 0], [-4.3, 2.1], [-4.85, 2.1], [-4.75, 0]]), { ...ext, depth: 0.06 });
    fin.rotateY(-Math.PI / 2);
    const intake = new THREE.BoxGeometry(0.42, 0.55, 2.4);
    const nozzle = new THREE.CylinderGeometry(0.33, 0.38, 0.9, 32, 1, true);
    nozzle.rotateX(Math.PI / 2);
    const canopy = new THREE.SphereGeometry(0.42, 32, 16);
    canopy.scale(0.78, 0.62, 2.3);
    const burn = new THREE.ConeGeometry(0.3, 4.2, 32, 1, true);
    burn.rotateX(-Math.PI / 2); // tip downstream (-Z)
    const cone = new THREE.ConeGeometry(2.5, 3.4, 64, 1, true);
    cone.rotateX(Math.PI / 2); // apex forward (+Z)
    const trail = new THREE.PlaneGeometry(0.22, 9, 1, 1);
    trail.rotateX(-Math.PI / 2);
    trail.translate(0, 0, -4.5);
    return { fus, wing, stab, fin, intake, nozzle, canopy, burn, cone, trail };
  }, []);
}

function Jet({ jet }: { jet: React.RefObject<THREE.Group | null> }) {
  const g = useAirframe();
  const burnU = useMemo(() => ({ uTime: { value: 0 }, uPower: { value: 1 } }), []);
  const coneU = useMemo(() => ({ uTime: { value: 0 }, uAmount: { value: 0 } }), []);
  const trailU = useMemo(() => ({ uAmount: { value: 0 } }), []);
  const strobe = useRef<THREE.Sprite>(null);
  const coneMesh = useRef<THREE.Mesh>(null);
  const glow = useMemo(() => {
    const c = document.createElement('canvas');
    c.width = c.height = 64;
    const x = c.getContext('2d')!;
    const gr = x.createRadialGradient(32, 32, 0, 32, 32, 32);
    gr.addColorStop(0, 'rgba(255,255,255,1)');
    gr.addColorStop(0.25, 'rgba(255,255,255,0.5)');
    gr.addColorStop(1, 'rgba(255,255,255,0)');
    x.fillStyle = gr;
    x.fillRect(0, 0, 64, 64);
    const t = new THREE.CanvasTexture(c);
    t.colorSpace = THREE.SRGBColorSpace;
    return t;
  }, []);

  useFrame(() => {
    const T = flight.introT;
    burnU.uTime.value = T;
    coneU.uTime.value = T;
    burnU.uPower.value = 0.9 + ss(1.2, 1.62, T) * 0.8;
    // vapour cone builds through the transonic band and blows away at Mach 1
    const build = ss(1.18, RUN.sonic, T);
    const pop = ss(RUN.sonic, RUN.sonic + 0.22, T);
    coneU.uAmount.value = build * (1 - pop);
    if (coneMesh.current) coneMesh.current.scale.setScalar(0.85 + build * 0.2 + pop * 0.9);
    trailU.uAmount.value = ss(1.25, 1.55, T) * (1 - ss(1.95, 2.25, T));
    if (strobe.current) (strobe.current.material as THREE.SpriteMaterial).opacity = (T * 2.6) % 1 < 0.12 ? 1 : 0;
  });

  const skin = <meshStandardMaterial color="#5a6472" metalness={0.78} roughness={0.3} />;
  return (
    <group ref={jet}>
      <mesh geometry={g.fus}>{skin}</mesh>
      <mesh geometry={g.canopy} position={[0, 0.42, 2.55]}>
        <meshStandardMaterial color="#0b1a2e" metalness={1} roughness={0.06} emissive="#0a2a55" emissiveIntensity={0.4} />
      </mesh>
      {/* spine light: the AeroSentinel blue */}
      <mesh position={[0, 0.56, -0.8]}>
        <boxGeometry args={[0.05, 0.03, 4.6]} />
        <meshBasicMaterial color="#3fa2ff" toneMapped={false} />
      </mesh>
      <mesh geometry={g.wing} position={[0, -0.12, 0]}>{skin}</mesh>
      <mesh geometry={g.wing} position={[0, -0.12, 0]} scale={[-1, 1, 1]}>
        <meshStandardMaterial color="#5a6472" metalness={0.78} roughness={0.3} side={THREE.DoubleSide} />
      </mesh>
      <mesh geometry={g.stab} position={[0, -0.05, 0]}>{skin}</mesh>
      <mesh geometry={g.stab} position={[0, -0.05, 0]} scale={[-1, 1, 1]}>
        <meshStandardMaterial color="#5a6472" metalness={0.78} roughness={0.3} side={THREE.DoubleSide} />
      </mesh>
      <mesh geometry={g.fin} position={[0.5, 0.35, 0]} rotation={[0, 0, -0.32]}>{skin}</mesh>
      <mesh geometry={g.fin} position={[-0.5, 0.35, 0]} rotation={[0, 0, 0.32]}>{skin}</mesh>
      {[-1, 1].map((sx) => (
        <group key={sx}>
          <mesh geometry={g.intake} position={[sx * 0.78, -0.18, 0.9]}>{skin}</mesh>
          <mesh geometry={g.nozzle} position={[sx * 0.4, -0.05, -5.15]}>
            <meshStandardMaterial color="#2c3138" metalness={0.9} roughness={0.4} side={THREE.DoubleSide} />
          </mesh>
          <mesh position={[sx * 0.4, -0.05, -5.0]}>
            <circleGeometry args={[0.32, 24]} />
            <meshBasicMaterial color="#ffb070" toneMapped={false} side={THREE.DoubleSide} />
          </mesh>
          <mesh geometry={g.burn} position={[sx * 0.4, -0.05, -5.6 - 2.1]}>
            <shaderMaterial vertexShader={burnVert} fragmentShader={burnFrag} uniforms={burnU} transparent depthWrite={false} blending={THREE.AdditiveBlending} side={THREE.DoubleSide} />
          </mesh>
          <sprite position={[sx * 0.4, -0.05, -5.3]} scale={[2.2, 2.2, 1]}>
            <spriteMaterial map={glow} color="#ff8a3d" transparent opacity={0.9} depthWrite={false} blending={THREE.AdditiveBlending} toneMapped={false} />
          </sprite>
          {/* wingtip vortex */}
          <mesh geometry={g.trail} position={[sx * 4.72, -0.1, -3.1]}>
            <shaderMaterial vertexShader={trailVert} fragmentShader={trailFrag} uniforms={trailU} transparent depthWrite={false} blending={THREE.AdditiveBlending} side={THREE.DoubleSide} />
          </mesh>
        </group>
      ))}
      {/* nav lights: red on the left wing (+X when nose is +Z), green on the right */}
      <sprite position={[4.74, -0.1, -2.9]} scale={[0.9, 0.9, 1]}>
        <spriteMaterial map={glow} color="#ff3b4a" transparent depthWrite={false} blending={THREE.AdditiveBlending} toneMapped={false} />
      </sprite>
      <sprite position={[-4.74, -0.1, -2.9]} scale={[0.9, 0.9, 1]}>
        <spriteMaterial map={glow} color="#22e07a" transparent depthWrite={false} blending={THREE.AdditiveBlending} toneMapped={false} />
      </sprite>
      <sprite ref={strobe} position={[0, 2.55, -4.6]} scale={[1.6, 1.6, 1]}>
        <spriteMaterial map={glow} color="#ffffff" transparent depthWrite={false} blending={THREE.AdditiveBlending} toneMapped={false} />
      </sprite>
      <mesh ref={coneMesh} geometry={g.cone} position={[0, 0, -0.4]}>
        <shaderMaterial vertexShader={burnVert} fragmentShader={coneFrag} uniforms={coneU} transparent depthWrite={false} side={THREE.DoubleSide} />
      </mesh>
    </group>
  );
}

function Shock({ shock }: { shock: React.RefObject<THREE.Mesh | null> }) {
  const u = useMemo(() => ({ uFade: { value: 0 } }), []);
  return (
    <mesh ref={shock} visible={false} userData={{ u }}>
      <sphereGeometry args={[1, 64, 32]} />
      <shaderMaterial vertexShader={burnVert} fragmentShader={shockFrag} uniforms={u} transparent depthWrite={false} blending={THREE.AdditiveBlending} side={THREE.DoubleSide} />
    </mesh>
  );
}

/* ── The run: drives the jet, the camera and the HUD numbers from the intro clock ── */
export default function IntroScene({ small }: { small: boolean }) {
  const root = useRef<THREE.Group>(null);
  const jet = useRef<THREE.Group>(null);
  const shock = useRef<THREE.Mesh>(null);
  const fade = useMemo(() => ({ v: 1 }), []);
  const { camera, size } = useThree();
  const cam = camera as THREE.PerspectiveCamera;
  const tmp = useMemo(
    () => ({ p: new THREE.Vector3(), q: new THREE.Vector3(), look: new THREE.Vector3(0, -1, -60), boom: new THREE.Vector3(), up: new THREE.Vector3(), ndc: new THREE.Vector3(), shake: 0 }),
    [],
  );

  useFrame((state) => {
    const R = root.current, J = jet.current;
    if (!R || !J) return;
    const phase = flight.introPhase;
    intro.active = phase !== 'done' && !intro.swapped;
    if (phase === 'fly' && intro.start < 0) intro.start = state.clock.elapsedTime;
    if (phase === 'done' && !intro.swapped) intro.swapped = true;
    const frozen = introFreeze();
    const T = phase === 'fly' ? (frozen ?? state.clock.elapsedTime - intro.start) : phase === 'boot' ? 0 : RUN.end;
    flight.introT = T;

    if (frozen !== null) {
      // inspecting: no events, never swap
    } else if (phase === 'fly' && !intro.sonicFired && T >= RUN.sonic) {
      intro.sonicFired = true;
      tmp.shake = 1;
      window.dispatchEvent(new Event('intro:sonic'));
    }
    if (frozen === null && phase === 'fly' && !intro.washFired && T >= RUN.wash) {
      intro.washFired = true;
      tmp.shake = Math.max(tmp.shake, 0.8);
      window.dispatchEvent(new Event('intro:wash'));
    }
    if (frozen === null && phase === 'fly' && T >= RUN.swap) intro.swapped = true;

    R.visible = !intro.swapped;
    fade.v = intro.swapped ? 0 : 1;
    if (!R.visible) {
      flight.lockOn = false;
      return;
    }

    // ── jet along its path, nose along the tangent, banking into the turn ──
    const u = pathParam(T);
    PATH.getPoint(u, tmp.p);
    PATH.getPoint(Math.min(1, u + 0.004), tmp.q);
    J.position.copy(tmp.p);
    J.lookAt(tmp.q);
    const bank = Math.sin(Math.min(1, T / 1.3) * Math.PI) * 0.75 - ss(1.4, 1.75, T) * 0.25;
    J.rotateZ(bank);

    // ── Mach on the HUD ──
    flight.mach = T < RUN.sonic ? 0.84 + 0.16 * ss(0, RUN.sonic, T) * (2 - ss(0, RUN.sonic, T)) : 1 + (T - RUN.sonic) * 0.35;

    // ── shockwave from where the barrier broke ──
    const S = shock.current;
    if (S) {
      if (T < RUN.sonic) tmp.boom.copy(tmp.p);
      const age = T - RUN.sonic;
      S.visible = age > 0;
      if (age > 0) {
        S.position.copy(tmp.boom);
        const dist = tmp.boom.distanceTo(cam.position);
        S.scale.setScalar(Math.max(0.01, (age / (RUN.wash - RUN.sonic)) * dist * 1.04));
        (S.userData.u as { uFade: { value: number } }).uFade.value = Math.min(1, age * 8) * (1 - ss(RUN.wash, RUN.swap + 0.1, T));
      }
    }

    // ── camera: low over the cloud tops, tracking with lag, a slow push in, then the hit ──
    const k = 0.09;
    tmp.q.copy(tmp.p);
    tmp.q.z = Math.min(tmp.q.z, CAM_START.z - 6);
    tmp.look.lerp(tmp.q.lerp(new THREE.Vector3(0, 1.2, -8), ss(1.3, 1.7, T) * 0.35), k);
    const push = ss(0.6, 1.62, T);
    cam.position.set(CAM_START.x + Math.sin(T * 0.8) * 0.15, CAM_START.y + push * 0.4, CAM_START.z - push * 1.6);
    tmp.shake *= 0.9;
    if (tmp.shake > 0.01) {
      cam.position.x += (Math.random() - 0.5) * tmp.shake * 0.5;
      cam.position.y += (Math.random() - 0.5) * tmp.shake * 0.5;
    }
    cam.up.set(Math.sin(T * 0.5) * 0.03, 1, 0);
    cam.lookAt(tmp.look);
    const fov = (size.width / size.height < 1 ? 52 : 36) + ss(1.4, RUN.sonic, T) * 6 - ss(RUN.sonic, RUN.wash, T) * 2;
    if (Math.abs(cam.fov - fov) > 0.01) {
      cam.fov = fov;
      cam.updateProjectionMatrix();
    }

    // ── lock-on box: where the jet is on screen ──
    tmp.ndc.copy(tmp.p).project(cam);
    flight.lockX = tmp.ndc.x;
    flight.lockY = tmp.ndc.y;
    flight.lockRange = tmp.p.distanceTo(cam.position) * 1.5;
    flight.lockOn = tmp.ndc.z < 1 && Math.abs(tmp.ndc.x) < 0.92 && Math.abs(tmp.ndc.y) < 0.9 && T < RUN.sonic + 0.1;
  }, -1);

  return (
    <group ref={root}>
      <Sky fade={fade} />
      <Clouds count={small ? 150 : 300} fade={fade} />
      <Jet jet={jet} />
      <Shock shock={shock} />
    </group>
  );
}
