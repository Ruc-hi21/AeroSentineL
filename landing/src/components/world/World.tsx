'use client';

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import * as THREE from 'three';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { Environment, Lightformer, PerformanceMonitor } from '@react-three/drei';
import gsap from 'gsap';
import { flight, onBoom } from '@/lib/flight';
import IntroScene, { intro } from './IntroScene';

/* ────────────────────────────────────────────────────────────────────────────
   The one 3D world behind the whole page.
   A procedurally built, sectioned two-spool turbofan in a wind tunnel of airflow
   streaks, under a starfield. A director reads the shared `flight` store every
   frame and flies the camera: hero → through the engine → cruise → finale.
   Engine-local frame: the axis is +Y (inlet at y≈3, nozzle at y≈-2.4).
   ──────────────────────────────────────────────────────────────────────────── */

const W = {
  assemble: { p: 0 },
  /** 0..1 exploded view, driven by scroll mid-page */
  explode: 0,
  reduce: false,
  spin: 1,
};

const CUT_START = 0;
const CUT_LENGTH = Math.PI * 1.5; // leaves one quadrant open toward OPEN below
/** Direction of the open (cut away) quadrant in the engine's local XZ plane. */
const OPEN = new THREE.Vector3(-0.62, 0, 0.78).normalize();
const SIDE = new THREE.Vector3().crossVectors(new THREE.Vector3(0, 1, 0), OPEN).normalize();

function lathe(points: [number, number][], segments = 96, full = false) {
  const g = new THREE.LatheGeometry(
    points.map(([r, y]) => new THREE.Vector2(r, y)),
    segments,
    full ? 0 : CUT_START,
    full ? Math.PI * 2 : CUT_LENGTH,
  );
  g.computeVertexNormals();
  return g;
}

const NACELLE: [number, number][] = [
  [1.2, 2.96], [1.29, 2.84], [1.34, 2.5], [1.34, 1.7], [1.28, 0.9], [1.15, 0.22],
  [1.1, 0.22], [1.2, 0.9], [1.25, 1.7], [1.24, 2.5], [1.17, 2.82], [1.16, 2.92], [1.2, 2.96],
];
const CORE: [number, number][] = [
  [0.7, 2.02], [0.78, 1.3], [0.76, 0.2], [0.63, -1.1], [0.5, -1.72],
  [0.46, -1.72], [0.59, -1.1], [0.71, 0.2], [0.73, 1.3], [0.66, 2.02], [0.7, 2.02],
];

let glowTex: THREE.Texture | null = null;
function glowTexture() {
  if (glowTex) return glowTex;
  const c = document.createElement('canvas');
  c.width = c.height = 128;
  const g = c.getContext('2d')!;
  const gr = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  gr.addColorStop(0, 'rgba(255,255,255,1)');
  gr.addColorStop(0.18, 'rgba(255,255,255,0.65)');
  gr.addColorStop(0.45, 'rgba(255,255,255,0.14)');
  gr.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = gr;
  g.fillRect(0, 0, 128, 128);
  glowTex = new THREE.CanvasTexture(c);
  glowTex.colorSpace = THREE.SRGBColorSpace;
  return glowTex;
}

/* ── Engine parts ─────────────────────────────────────────────────────────── */

function BladeRing({
  y, hub, tip, count, chord, twist, color, metal = 0.9, rough = 0.28, speed, phase = 0,
}: {
  y: number; hub: number; tip: number; count: number; chord: number; twist: number;
  color: string; metal?: number; rough?: number; speed: number; phase?: number;
}) {
  const ref = useRef<THREE.InstancedMesh>(null);
  const group = useRef<THREE.Group>(null);
  const span = tip - hub;

  useLayoutEffect(() => {
    const m = ref.current;
    if (!m) return;
    const o = new THREE.Object3D();
    for (let i = 0; i < count; i++) {
      const a = (i / count) * Math.PI * 2 + phase;
      const r = hub + span / 2;
      o.position.set(Math.sin(a) * r, 0, Math.cos(a) * r);
      o.rotation.set(0, a, 0);
      o.rotateZ(twist);
      o.updateMatrix();
      m.setMatrixAt(i, o.matrix);
    }
    m.instanceMatrix.needsUpdate = true;
  }, [count, hub, span, twist, phase]);

  useFrame((_, dt) => {
    if (group.current) group.current.rotation.y += Math.min(dt, 0.05) * speed * W.spin;
  });

  return (
    <group ref={group} position={[0, y, 0]}>
      <instancedMesh ref={ref} args={[undefined, undefined, count]} frustumCulled={false}>
        <boxGeometry args={[0.018, chord, span]} />
        <meshStandardMaterial color={color} metalness={metal} roughness={rough} />
      </instancedMesh>
      <mesh>
        <cylinderGeometry args={[hub, hub, chord * 1.1, 40]} />
        <meshStandardMaterial color="#5d636b" metalness={0.85} roughness={0.4} />
      </mesh>
    </group>
  );
}

/** A group that slides in from an exploded offset as the engine assembles. */
function Part({ offset, children }: { offset: number; children: React.ReactNode }) {
  const ref = useRef<THREE.Group>(null);
  useFrame(() => {
    if (ref.current) ref.current.position.y = (1 - W.assemble.p) * offset + W.explode * offset * 1.5;
  });
  return <group ref={ref}>{children}</group>;
}

type Station = { id: string; y: number; r: number; color: string; at: number };
/** Sensor stations, and the point of the fly-through (0..1) where each one is read. */
export const STATIONS: Station[] = [
  { id: 'T2', y: 2.78, r: 0.92, color: '#42be65', at: 0.3 },
  { id: 'T24', y: 1.62, r: 0.62, color: '#f1c21b', at: 0.5 },
  { id: 'T30', y: 0.42, r: 0.58, color: '#ff832b', at: 0.667 },
  { id: 'T50', y: -1.42, r: 0.56, color: '#ff832b', at: 0.833 },
];

function Beacons() {
  const tex = useMemo(() => glowTexture(), []);
  const sprites = useRef<(THREE.Sprite | null)[]>([]);
  useFrame((state) => {
    const d = flight.dive;
    const t = state.clock.elapsedTime;
    const shown = W.assemble.p > 0.9 ? 1 : 0;
    STATIONS.forEach((s, i) => {
      const sp = sprites.current[i];
      if (!sp) return;
      const focus = d > 0 && d < 1 ? Math.exp(-(((d - s.at) / 0.075) ** 2)) : 0;
      const k = shown * (0.32 + 0.06 * Math.sin(t * 2 + i) + focus * 1.25);
      sp.scale.setScalar(0.18 + k * 0.42);
      (sp.material as THREE.SpriteMaterial).opacity = Math.min(1, k);
    });
  });
  return (
    <>
      {STATIONS.map((s, i) => (
        <group key={s.id} position={[OPEN.x * s.r, s.y, OPEN.z * s.r]}>
          <mesh>
            <sphereGeometry args={[0.03, 16, 16]} />
            <meshBasicMaterial color={s.color} toneMapped={false} />
          </mesh>
          <sprite ref={(el) => { sprites.current[i] = el; }}>
            <spriteMaterial map={tex} color={s.color} transparent depthWrite={false} blending={THREE.AdditiveBlending} toneMapped={false} />
          </sprite>
        </group>
      ))}
    </>
  );
}

/* Exhaust plume with shock diamonds (Mach disks), additive, no lighting */
const plumeVert = /* glsl */ `
  varying vec2 vUv; varying vec3 vN; varying vec3 vV;
  void main(){
    vUv = uv;
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    vN = normalize(normalMatrix * normal);
    vV = normalize(-mv.xyz);
    gl_Position = projectionMatrix * mv;
  }`;
const plumeFrag = /* glsl */ `
  uniform float uTime; uniform float uPower;
  varying vec2 vUv; varying vec3 vN; varying vec3 vV;
  void main(){
    float t = vUv.y;
    float rim = abs(dot(vN, vV));
    float core = pow(rim, 1.6);
    float diamonds = pow(0.5 + 0.5 * cos(t * 30.0 - 0.6), 9.0) * smoothstep(0.8, 0.04, t);
    float flick = 0.86 + 0.14 * sin(uTime * 37.0 + t * 23.0);
    vec3 hot = vec3(1.0, 0.6, 0.3);
    vec3 cool = vec3(0.4, 0.68, 1.0);
    vec3 col = mix(hot, cool, smoothstep(0.0, 0.75, t)) * (1.0 + diamonds * 2.2);
    float a = (1.0 - t) * (1.0 - t) * core * (0.22 + diamonds) * flick * uPower;
    gl_FragColor = vec4(col, a);
  }`;

function Plume() {
  const mat = useRef<THREE.ShaderMaterial>(null);
  const uniforms = useMemo(() => ({ uTime: { value: 0 }, uPower: { value: 0 } }), []);
  useFrame((state) => {
    if (!mat.current) return;
    uniforms.uTime.value = state.clock.elapsedTime;
    const target = W.assemble.p > 0.95 ? 1 + Math.min(Math.abs(flight.velocity) * 0.03, 0.8) : 0;
    uniforms.uPower.value += (target - uniforms.uPower.value) * 0.06;
  });
  return (
    <mesh position={[0, -3.35, 0]} rotation={[Math.PI, 0, 0]}>
      <coneGeometry args={[0.45, 3.2, 40, 1, true]} />
      <shaderMaterial
        ref={mat}
        vertexShader={plumeVert}
        fragmentShader={plumeFrag}
        uniforms={uniforms}
        transparent
        depthWrite={false}
        blending={THREE.AdditiveBlending}
        side={THREE.DoubleSide}
      />
    </mesh>
  );
}

/* Wind-tunnel streaks: one line segment per particle, animated entirely on the GPU */
const flowVert = /* glsl */ `
  uniform float uFlow; uniform float uLen; uniform float uOpacity;
  attribute vec4 aData; attribute float aEnd;
  varying float vA; varying float vHeat;
  void main(){
    float y = mod(aData.z - uFlow * aData.w + 10.0, 20.0) - 10.0;
    float r = aData.y;
    float inside = smoothstep(3.4, 2.6, y) * smoothstep(-2.4, -1.6, y);
    float rr = r < 1.25 ? mix(r, r * 0.82, inside) : r + inside * 0.12;
    float yy = y + aEnd * uLen * aData.w;
    vec3 p = vec3(sin(aData.x) * rr, yy, cos(aData.x) * rr);
    vA = (1.0 - aEnd) * smoothstep(10.0, 6.0, abs(y)) * uOpacity;
    vHeat = step(r, 0.8) * smoothstep(0.7, -0.3, y) * smoothstep(-7.0, -1.2, y);
    gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.0);
  }`;
const flowFrag = /* glsl */ `
  varying float vA; varying float vHeat;
  void main(){
    vec3 col = mix(vec3(0.55, 0.8, 1.0), vec3(1.0, 0.56, 0.26), vHeat);
    gl_FragColor = vec4(col, vA * 0.6);
  }`;

function Flow({ count }: { count: number }) {
  const geo = useMemo(() => {
    const g = new THREE.BufferGeometry();
    const data = new Float32Array(count * 2 * 4);
    const end = new Float32Array(count * 2);
    const pos = new Float32Array(count * 2 * 3);
    let seed = 7;
    const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
    for (let i = 0; i < count; i++) {
      const u = rnd();
      const r = u < 0.42 ? 0.3 + rnd() * 0.9 : 1.35 + rnd() * 1.25; // through the core, and the bypass just outside the cowl
      const a = rnd() * Math.PI * 2;
      const y0 = rnd() * 20;
      const sp = 0.7 + rnd() * 0.7;
      for (let k = 0; k < 2; k++) {
        data.set([a, r, y0, sp], (i * 2 + k) * 4);
        end[i * 2 + k] = k;
      }
    }
    g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    g.setAttribute('aData', new THREE.BufferAttribute(data, 4));
    g.setAttribute('aEnd', new THREE.BufferAttribute(end, 1));
    g.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 14);
    return g;
  }, [count]);
  const uniforms = useMemo(() => ({ uFlow: { value: 0 }, uLen: { value: 0.3 }, uOpacity: { value: 0 } }), []);

  useFrame((_, dt) => {
    const v = Math.abs(flight.velocity);
    const speed = (W.reduce ? 1.2 : 2.6) + Math.min(v * 0.09, 18) + flight.dive * (1 - flight.dive) * 6;
    uniforms.uFlow.value += Math.min(dt, 0.05) * speed;
    uniforms.uLen.value += (0.22 + speed * 0.07 - uniforms.uLen.value) * 0.15;
    // quiet around the hero, full in the fly-through where speed is the point
    const op = flight.boomed ? (flight.dive > 0.02 && flight.dive < 0.98 ? 1 : 0.42) : 0;
    uniforms.uOpacity.value += (op - uniforms.uOpacity.value) * 0.04;
  });

  return (
    <lineSegments geometry={geo} frustumCulled={false}>
      <shaderMaterial
        vertexShader={flowVert}
        fragmentShader={flowFrag}
        uniforms={uniforms}
        transparent
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </lineSegments>
  );
}

/* Stars: static points on a far shell, twinkling in the shader */
const starVert = /* glsl */ `
  uniform float uTime; uniform float uPx;
  attribute float aSize; attribute float aPhase;
  varying float vA;
  void main(){
    vA = 0.55 + 0.45 * sin(uTime * (0.6 + aPhase) + aPhase * 12.0);
    gl_PointSize = aSize * uPx;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }`;
const starFrag = /* glsl */ `
  varying float vA;
  void main(){
    vec2 c = gl_PointCoord - 0.5;
    float d = length(c);
    float a = smoothstep(0.5, 0.0, d);
    gl_FragColor = vec4(vec3(0.85, 0.92, 1.0), a * vA * 0.9);
  }`;

function Stars({ count }: { count: number }) {
  const ref = useRef<THREE.Points>(null);
  const { gl } = useThree();
  const geo = useMemo(() => {
    const g = new THREE.BufferGeometry();
    const p = new Float32Array(count * 3);
    const s = new Float32Array(count);
    const ph = new Float32Array(count);
    let seed = 11;
    const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
    for (let i = 0; i < count; i++) {
      const u = rnd() * 2 - 1;
      const th = rnd() * Math.PI * 2;
      const r = 45 + rnd() * 40;
      const q = Math.sqrt(1 - u * u);
      p.set([q * Math.cos(th) * r, u * r * 0.7 + 6, q * Math.sin(th) * r], i * 3);
      s[i] = rnd() < 0.08 ? 2.6 : 1 + rnd() * 1.2;
      ph[i] = rnd();
    }
    g.setAttribute('position', new THREE.BufferAttribute(p, 3));
    g.setAttribute('aSize', new THREE.BufferAttribute(s, 1));
    g.setAttribute('aPhase', new THREE.BufferAttribute(ph, 1));
    return g;
  }, [count]);
  const uniforms = useMemo(() => ({ uTime: { value: 0 }, uPx: { value: 1 } }), []);
  useFrame((state, dt) => {
    uniforms.uTime.value = state.clock.elapsedTime;
    uniforms.uPx.value = gl.getPixelRatio();
    if (ref.current) ref.current.rotation.y += Math.min(dt, 0.05) * 0.004;
  });
  return (
    <points ref={ref} geometry={geo} frustumCulled={false}>
      <shaderMaterial vertexShader={starVert} fragmentShader={starFrag} uniforms={uniforms} transparent depthWrite={false} blending={THREE.AdditiveBlending} />
    </points>
  );
}

/* ── The engine ───────────────────────────────────────────────────────────── */

function Engine({ inner, flowCount }: { inner: React.RefObject<THREE.Group | null>; flowCount: number }) {
  const glow = useRef<THREE.MeshStandardMaterial>(null);
  const combustor = useRef<THREE.Sprite>(null);
  const tex = useMemo(() => glowTexture(), []);
  const nacelle = useMemo(() => lathe(NACELLE), []);
  const ghost = useMemo(() => lathe(NACELLE.slice(0, 6), 36, true), []);
  const core = useMemo(() => lathe(CORE), []);

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    const heat = 1.7 + Math.sin(t * 2.2) * 0.45 + Math.exp(-(((flight.dive - 0.667) / 0.1) ** 2)) * 1.6;
    if (glow.current) glow.current.emissiveIntensity = heat;
    if (combustor.current) {
      combustor.current.scale.setScalar(1.4 + heat * 0.25);
      (combustor.current.material as THREE.SpriteMaterial).opacity = 0.35 * W.assemble.p;
    }
  });

  return (
    <group ref={inner} rotation={[0, 0, -Math.PI / 2]} position={[-0.85, 0, 0]}>
      <Part offset={0.7}>
        <mesh geometry={nacelle}>
          <meshStandardMaterial color="#c3c8cf" metalness={0.88} roughness={0.3} side={THREE.DoubleSide} />
        </mesh>
        <mesh geometry={ghost}>
          <meshBasicMaterial color="#3fa2ff" wireframe transparent opacity={0.08} />
        </mesh>
      </Part>

      <Part offset={1.7}>
        <BladeRing y={2.56} hub={0.3} tip={1.15} count={22} chord={0.2} twist={0.62} color="#dfe3e8" speed={6} />
        <mesh position={[0, 2.92, 0]}>
          <coneGeometry args={[0.31, 0.62, 48]} />
          <meshStandardMaterial color="#2a2e34" metalness={0.7} roughness={0.25} />
        </mesh>
      </Part>

      <Part offset={1.1}>
        {[2.16, 1.98, 1.8].map((y, i) => (
          <BladeRing key={y} y={y} hub={0.26} tip={0.64} count={30} chord={0.08} twist={0.5} color="#bcc2ca" speed={6} phase={i * 0.1} />
        ))}
      </Part>

      <Part offset={0.45}>
        {Array.from({ length: 8 }).map((_, i) => {
          const y = 1.48 - i * 0.14;
          return <BladeRing key={y} y={y} hub={0.24} tip={0.6 - i * 0.022} count={36} chord={0.06} twist={0.45} color="#aeb5be" speed={-11} phase={i * 0.2} />;
        })}
      </Part>

      <Part offset={0}>
        <mesh position={[0, 0.08, 0]} rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.4, 0.085, 24, 96, CUT_LENGTH]} />
          <meshStandardMaterial ref={glow} color="#3a1d0e" emissive="#ff7a2b" emissiveIntensity={1.6} roughness={0.5} toneMapped={false} />
        </mesh>
        <sprite ref={combustor} position={[OPEN.x * 0.4, 0.08, OPEN.z * 0.4]}>
          <spriteMaterial map={tex} color="#ff8a3d" transparent opacity={0} depthWrite={false} blending={THREE.AdditiveBlending} toneMapped={false} />
        </sprite>
        <mesh position={[0, 0.45, 0]}>
          <cylinderGeometry args={[0.05, 0.05, 4.4, 16]} />
          <meshStandardMaterial color="#7a8089" metalness={0.9} roughness={0.3} />
        </mesh>
      </Part>

      <Part offset={-1.2}>
        {[-0.3, -0.45].map((y, i) => (
          <BladeRing key={y} y={y} hub={0.26} tip={0.5} count={40} chord={0.07} twist={-0.5} color="#a8927e" rough={0.36} speed={-11} phase={i * 0.15} />
        ))}
        {[-0.72, -0.9, -1.08, -1.26].map((y, i) => (
          <BladeRing key={y} y={y} hub={0.28} tip={0.5 + i * 0.03} count={44} chord={0.08} twist={-0.55} color="#9a8a7c" rough={0.36} speed={6} phase={i * 0.12} />
        ))}
        <mesh position={[0, -1.98, 0]} rotation={[Math.PI, 0, 0]}>
          <coneGeometry args={[0.3, 0.95, 48]} />
          <meshStandardMaterial color="#4a4f57" metalness={0.8} roughness={0.35} />
        </mesh>
      </Part>

      <Part offset={-0.5}>
        <mesh geometry={core}>
          <meshStandardMaterial color="#8d939b" metalness={0.85} roughness={0.38} side={THREE.DoubleSide} />
        </mesh>
      </Part>

      <Beacons />
      <Plume />
      <Flow count={flowCount} />
    </group>
  );
}

/* ── Director: flies the camera from the shared scroll state ──────────────── */

const ss = (a: number, b: number, x: number) => {
  const t = Math.min(1, Math.max(0, (x - a) / (b - a)));
  return t * t * (3 - 2 * t);
};
const lerp = THREE.MathUtils.lerp;

/** Camera keyframes in the engine's local frame, one per beat of the fly-through. */
const L = (open: number, y: number, side = 0) =>
  new THREE.Vector3().addScaledVector(OPEN, open).addScaledVector(SIDE, side).setY(y);
const DIVE_POS = [
  L(0.9, 7.6, 0.4), // head-on, in front of the inlet
  L(1.7, 4.3, 0.25), // closing on the fan
  L(2.35, 1.95, 0), // along the low pressure compressor
  L(2.1, 0.4, -0.1), // combustor
  L(2.1, -1.15, -0.1), // turbines
  L(1.9, -6.2, 0.9), // behind the nozzle, looking back up the plume
];
const DIVE_LOOK = [
  L(0, 2.4), L(0.2, 2.3), L(0.25, 1.7), L(0.2, 0.15), L(0.2, -1.15), L(0.1, -0.9),
];
const DIVE_FOV = [30, 32, 40, 44, 44, 44, 40];

function Director({
  anchor, pose, inner, wrap,
}: {
  anchor: React.RefObject<THREE.Group | null>;
  pose: React.RefObject<THREE.Group | null>;
  inner: React.RefObject<THREE.Group | null>;
  wrap: React.RefObject<HTMLDivElement | null>;
}) {
  const { camera, size } = useThree();
  const cam = camera as THREE.PerspectiveCamera;
  const tmp = useMemo(
    () => ({
      p: new THREE.Vector3(), l: new THREE.Vector3(), a: new THREE.Vector3(), b: new THREE.Vector3(),
      look: new THREE.Vector3(0, 0, 0), curP: new THREE.CatmullRomCurve3(Array.from({ length: 7 }, () => new THREE.Vector3())),
      curL: new THREE.CatmullRomCurve3(Array.from({ length: 7 }, () => new THREE.Vector3())),
      px: 0, py: 0, cruiseSpin: 0, opacity: 1,
    }),
    [],
  );

  useFrame((state, rawDt) => {
    const A = anchor.current, P = pose.current, I = inner.current;
    if (!A || !P || !I) return;
    // during the supersonic run the engine waits off stage (visible while booting so its shaders compile)
    A.visible = !(intro.active && flight.introPhase === 'fly');
    const dt = Math.min(rawDt, 0.05);
    const aspect = size.width / size.height;
    const desk = aspect > 1.05;
    const fit = Math.max(1, 1.3 / aspect);
    const t = state.clock.elapsedTime;

    // damped pointer: momentum, not a hard lock
    const kp = 1 - Math.exp(-dt * 2.6);
    tmp.px += (flight.px - tmp.px) * kp;
    tmp.py += (flight.py - tmp.py) * kp;

    const h = flight.hero;
    const dRaw = flight.dive;
    const after = flight.after;
    const cta = flight.cta;
    const b = ss(0, 0.1, after); // dive → cruise
    const c = ss(0, 1, cta); // cruise → finale

    // ── engine placement ──
    const heroZ = 10.4 * fit * (1 - 0.16 * h);
    const half = Math.tan(THREE.MathUtils.degToRad(15)) * heroZ;
    const heroAnchor = tmp.a.set(desk ? Math.min(2.9, half * aspect * 0.5) : 0, desk ? -0.1 : -half * 0.4, 0);
    const toCenter = ss(0, 0.14, dRaw);
    const cruiseAnchor = tmp.b.set(desk ? 2.6 : 0, desk ? -0.2 : -1.6, desk ? -1.5 : -3);
    const finaleAnchor = new THREE.Vector3(0, desk ? -0.9 : -half * 0.32, 0);
    A.position.copy(heroAnchor).lerp(new THREE.Vector3(0, 0, 0), toCenter);
    if (b > 0) A.position.lerp(cruiseAnchor, b);
    if (c > 0) A.position.lerp(finaleAnchor, c);
    const heroScale = desk ? Math.min(0.7, 0.42 + aspect * 0.17) : 1.05;
    const s = lerp(heroScale, desk ? 1 : 1.12, toCenter) * (1 - b * 0.12 + c * (desk ? 0.05 : 0));
    A.scale.setScalar(s);

    // ── engine pose ──
    const pf = 1 - ss(0, 0.1, dRaw);
    let ry = -0.62 + tmp.px * 0.28 * pf + h * 0.45;
    let rx = 0.16 - tmp.py * 0.1 * pf + h * 0.08;
    if (b > 0) {
      tmp.cruiseSpin += dt * 0.07 * b;
      ry = lerp(ry, ry + after * Math.PI * 2.2 + tmp.cruiseSpin, b);
      rx = lerp(rx, 0.22 + Math.sin(after * 7) * 0.14, b);
    }
    if (c > 0) {
      const target = -0.5 + Math.PI * 2 * Math.round((ry + 0.5) / (Math.PI * 2));
      ry = lerp(ry, target, c);
      rx = lerp(rx, 0.2, c);
    }
    P.rotation.set(rx, ry, 0);
    A.updateMatrixWorld(true);

    // exploded view mid-page: the engine comes apart along its axis, then reassembles
    W.explode = ss(0.2, 0.3, after) * (1 - ss(0.46, 0.58, after)) * (1 - c);

    if (intro.active) return; // the run owns the camera

    // ── camera ──
    const heroPos = tmp.p.set(0.3, 0.6 + h * 0.25, heroZ);
    const heroLook = tmp.l.set(0.3, 0.6 + h * 0.1, 0);
    let fov = 30 * (desk ? 1 : 1.1);

    if (dRaw <= 0.0001 || dRaw >= 0.9999) {
      // outside the dive: hero before, keyframe 6 after
      if (dRaw >= 0.9999) {
        heroPos.copy(I.localToWorld(DIVE_POS[5].clone()));
        heroLook.copy(I.localToWorld(DIVE_LOOK[5].clone()));
        fov = DIVE_FOV[6] * (desk ? 1 : 1.3);
      }
    } else {
      // segment easing: linger a little at every station
      const n = 6;
      const x = dRaw * n;
      const i = Math.min(n - 1, Math.floor(x));
      const f = x - i;
      const eased = (i + lerp(f, f * f * (3 - 2 * f), 0.55)) / n;
      tmp.curP.points[0].copy(heroPos);
      tmp.curL.points[0].copy(heroLook);
      for (let k = 0; k < 6; k++) {
        tmp.curP.points[k + 1].copy(DIVE_POS[k]);
        I.localToWorld(tmp.curP.points[k + 1]);
        tmp.curL.points[k + 1].copy(DIVE_LOOK[k]);
        I.localToWorld(tmp.curL.points[k + 1]);
      }
      tmp.curP.getPoint(eased, heroPos);
      tmp.curL.getPoint(eased, heroLook);
      const fx = eased * n;
      const fi = Math.min(n - 1, Math.floor(fx));
      fov = lerp(DIVE_FOV[fi], DIVE_FOV[fi + 1], fx - fi) * (desk ? 1 : 1.3);
    }

    if (b > 0) {
      const cruisePos = new THREE.Vector3(0.3, 0.6 + Math.sin(after * Math.PI * 2) * 0.5, 12.5 * fit);
      const cruiseLook = new THREE.Vector3(0.3, 0.4, 0);
      heroPos.lerp(cruisePos, b);
      heroLook.lerp(cruiseLook, b);
      fov = lerp(fov, 30 * (desk ? 1 : 1.1), b);
    }
    if (c > 0) {
      heroPos.lerp(new THREE.Vector3(0, 0.5, 10.8 * fit), c);
      heroLook.lerp(new THREE.Vector3(0, 0.1, 0), c);
    }

    // a touch of camera life
    heroPos.y += Math.sin(t * 0.6) * 0.03;
    cam.position.copy(heroPos);
    tmp.look.copy(heroLook);
    cam.lookAt(tmp.look);
    if (Math.abs(cam.fov - fov) > 0.01) {
      cam.fov = fov;
      cam.updateProjectionMatrix();
    }

    // world dims behind reading sections, returns for the finale
    const op = 1 - 0.58 * b * (1 - W.explode * 0.75) + 0.5 * c;
    if (wrap.current && Math.abs(op - tmp.opacity) > 0.002) {
      tmp.opacity = op;
      wrap.current.style.opacity = op.toFixed(3);
    }

    // blades spool up with scroll speed
    W.spin = (W.reduce ? 0.5 : 1) * (1 + Math.min(Math.abs(flight.velocity) * 0.02, 1.5));
  });

  return null;
}

/** Tells the intro the world is live once a few frames have rendered (shaders compiled). */
function Ready() {
  const n = useRef(0);
  useFrame(() => {
    n.current++;
    if (n.current === 4) {
      (window as unknown as { __worldReady?: boolean }).__worldReady = true;
      window.dispatchEvent(new Event('world:ready'));
    }
  });
  return null;
}

/* ── Canvas ───────────────────────────────────────────────────────────────── */

export default function World() {
  const wrap = useRef<HTMLDivElement>(null);
  const anchor = useRef<THREE.Group>(null);
  const pose = useRef<THREE.Group>(null);
  const inner = useRef<THREE.Group>(null);
  const [dpr, setDpr] = useState(1.5);
  const [small] = useState(() => typeof window !== 'undefined' && window.innerWidth < 768);

  useEffect(() => {
    W.reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (W.reduce) {
      W.assemble.p = 1;
      return;
    }
    W.assemble.p = 0;
    let tween: gsap.core.Tween | undefined;
    // The engine assembles out of the shockwave
    const off = onBoom(() => {
      tween = gsap.to(W.assemble, { p: 1, duration: 2.6, delay: 0.05, ease: 'expo.out' });
    });
    return () => {
      off();
      tween?.kill();
    };
  }, []);

  // pointer for parallax (the canvas itself never takes events)
  useEffect(() => {
    const onMove = (e: PointerEvent) => {
      flight.px = (e.clientX / window.innerWidth) * 2 - 1;
      flight.py = -((e.clientY / window.innerHeight) * 2 - 1);
    };
    window.addEventListener('pointermove', onMove, { passive: true });
    return () => window.removeEventListener('pointermove', onMove);
  }, []);

  return (
    <div ref={wrap} className="world" aria-hidden="true">
      <Canvas
        dpr={[1, dpr]}
        camera={{ position: [0.3, 0.6, 10.4], fov: 30, near: 0.05, far: 220 }}
        gl={{ antialias: true, alpha: true, powerPreference: 'high-performance', stencil: false }}
      >
        <PerformanceMonitor onDecline={() => setDpr(1)} onIncline={() => setDpr(small ? 1.5 : 1.75)} flipflops={3} />
        <ambientLight intensity={0.22} />
        <directionalLight position={[3, 5, 6]} intensity={1.5} />
        <directionalLight position={[-6, 2, -4]} intensity={2.4} color="#3fa2ff" />
        <pointLight position={[0, -2, 3]} intensity={6} distance={8} color="#ff7a2b" />
        <Environment resolution={256} frames={1}>
          <Lightformer form="rect" intensity={2.2} position={[0, 4, 2]} scale={[10, 1.6, 1]} />
          <Lightformer form="rect" intensity={1.1} position={[-5, 0, 1]} rotation={[0, Math.PI / 2, 0]} scale={[8, 2, 1]} />
          <Lightformer form="rect" intensity={1.8} color="#3fa2ff" position={[5, -1, -2]} rotation={[0, -Math.PI / 2, 0]} scale={[8, 1, 1]} />
          <Lightformer form="rect" intensity={1.2} color="#ff7a2b" position={[0, -5, 0]} rotation={[Math.PI / 2, 0, 0]} scale={[10, 2, 1]} />
          <Lightformer form="ring" intensity={0.8} position={[0, 0, -6]} scale={4} />
        </Environment>

        <Stars count={small ? 900 : 1800} />
        <group ref={anchor}>
          <group ref={pose}>
            <Engine inner={inner} flowCount={small ? 1100 : 2600} />
          </group>
        </group>
        <IntroScene small={small} />
        <Director anchor={anchor} pose={pose} inner={inner} wrap={wrap} />
        <Ready />
      </Canvas>
    </div>
  );
}
