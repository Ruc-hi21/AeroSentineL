'use client';

import { useLayoutEffect, useMemo, useRef, useState } from 'react';
import * as THREE from 'three';
import { Canvas, useFrame } from '@react-three/fiber';
import { Environment, Lightformer, Sky } from '@react-three/drei';

/* The hero shot. Golden hour above a sea of cloud: a jet climbs out of the
   cloud tops, rushes the camera and bursts. The title then sits over the same
   sky, and scrolling dives the camera down through the clouds into the page. */

export const FLIGHT = 2.1; // seconds from first frame to the burst
const BURST_LEN = 1.6;

type Clock = { t: number; boomed: boolean };

/** Scene time in seconds. `?introSlow=8` in development plays the shot in slow motion for review. */
const SCENE = {
  now: 0,
  slow:
    process.env.NODE_ENV !== 'production' && typeof window !== 'undefined'
      ? Math.max(1, Number(new URLSearchParams(window.location.search).get('introSlow')) || 1)
      : 1,
};

/* ── Airframe, built along +Z (nose towards the camera) ── */

function wingShape(root: number, tip: number, span: number, sweep: number) {
  const s = new THREE.Shape();
  s.moveTo(0, 0);
  s.lineTo(span, -sweep);
  s.lineTo(span, -sweep - tip);
  s.lineTo(0, -root);
  s.closePath();
  return s;
}

function useWing(root: number, tip: number, span: number, sweep: number, depth: number) {
  return useMemo(() => {
    const g = new THREE.ExtrudeGeometry(wingShape(root, tip, span, sweep), {
      depth,
      bevelEnabled: true,
      bevelThickness: depth * 0.4,
      bevelSize: depth * 0.4,
      bevelSegments: 2,
    });
    g.computeVertexNormals();
    return g;
  }, [root, tip, span, sweep, depth]);
}

function Jet() {
  const wing = useWing(1.7, 0.5, 3.3, 1.35, 0.06);
  const stab = useWing(0.75, 0.3, 1.25, 0.6, 0.04);
  const fin = useMemo(() => {
    const s = new THREE.Shape();
    s.moveTo(0, 0);
    s.lineTo(-0.95, 1.35);
    s.lineTo(-1.45, 1.35);
    s.lineTo(-1.6, 0);
    s.closePath();
    const g = new THREE.ExtrudeGeometry(s, { depth: 0.05, bevelEnabled: true, bevelThickness: 0.02, bevelSize: 0.02, bevelSegments: 2 });
    g.computeVertexNormals();
    return g;
  }, []);

  const skin = <meshStandardMaterial color="#e9edf2" metalness={0.75} roughness={0.28} side={THREE.DoubleSide} />;
  const accent = <meshStandardMaterial color="#0b6fe0" metalness={0.5} roughness={0.35} side={THREE.DoubleSide} />;

  return (
    <group>
      {/* Fuselage */}
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <capsuleGeometry args={[0.34, 4.6, 12, 32]} />
        {skin}
      </mesh>
      {/* Cockpit glass */}
      <mesh position={[0, 0.16, 2.35]} rotation={[0.35, 0, 0]} scale={[1, 0.55, 1.2]}>
        <sphereGeometry args={[0.24, 24, 16, 0, Math.PI * 2, 0, Math.PI / 2]} />
        <meshStandardMaterial color="#0d1726" metalness={0.9} roughness={0.08} />
      </mesh>
      {/* Brand stripe */}
      <mesh rotation={[Math.PI / 2, 0, 0]} position={[0, 0, 0.6]}>
        <cylinderGeometry args={[0.345, 0.345, 0.18, 32, 1, true]} />
        {accent}
      </mesh>

      {/* Wings */}
      <mesh geometry={wing} position={[0.22, -0.12, 0.95]} rotation={[Math.PI / 2, 0, 0]}>{skin}</mesh>
      <mesh geometry={wing} position={[-0.22, -0.12, 0.95]} rotation={[Math.PI / 2, 0, 0]} scale={[-1, 1, 1]}>{skin}</mesh>

      {/* Tailplane */}
      <mesh geometry={stab} position={[0.12, 0.05, -1.9]} rotation={[Math.PI / 2, 0, 0]}>{skin}</mesh>
      <mesh geometry={stab} position={[-0.12, 0.05, -1.9]} rotation={[Math.PI / 2, 0, 0]} scale={[-1, 1, 1]}>{skin}</mesh>
      <mesh geometry={fin} position={[0.025, 0.2, -1.05]} rotation={[0, -Math.PI / 2, 0]}>{accent}</mesh>

      {/* Engines */}
      {[1.25, -1.25].map((x) => (
        <group key={x} position={[x, -0.42, 0.75]}>
          <mesh rotation={[Math.PI / 2, 0, 0]}>
            <cylinderGeometry args={[0.2, 0.17, 0.95, 28]} />
            {skin}
          </mesh>
          <mesh position={[0, 0, 0.48]} rotation={[Math.PI / 2, 0, 0]}>
            <circleGeometry args={[0.18, 24]} />
            <meshStandardMaterial color="#1b1f25" metalness={0.6} roughness={0.5} side={THREE.DoubleSide} />
          </mesh>
          <mesh position={[0, 0, -0.5]}>
            <sphereGeometry args={[0.12, 16, 12]} />
            <meshBasicMaterial color="#8fd0ff" toneMapped={false} />
          </mesh>
        </group>
      ))}
    </group>
  );
}


/* ── Flight path: out of the cloud tops, a banking climb, straight at the lens ── */

const START = new THREE.Vector3(-34, -8, -120);
const END = new THREE.Vector3(0.6, 3.9, 8.2);
function pathAt(p: number, out: THREE.Vector3) {
  const e = Math.pow(p, 2.1);
  out.lerpVectors(START, END, e);
  out.x += Math.sin(p * Math.PI) * 12;
  out.y += Math.sin(p * Math.PI * 0.9) * 3.5;
  return out;
}

function Plane({ clock, onBoom }: { clock: Clock; onBoom: (at: THREE.Vector3) => void }) {
  const ref = useRef<THREE.Group>(null);
  const pos = useMemo(() => new THREE.Vector3(), []);
  const ahead = useMemo(() => new THREE.Vector3(), []);
  const tipR = useRef<THREE.Object3D>(null);
  const tipL = useRef<THREE.Object3D>(null);

  useFrame(() => {
    const g = ref.current;
    if (!g) return;
    if (clock.boomed) {
      g.visible = false;
      return;
    }
    const p = Math.min(clock.t / FLIGHT, 1);
    pathAt(p, pos);
    pathAt(Math.min(p + 0.01, 1.001), ahead);
    if (p >= 1) ahead.copy(pos).add(new THREE.Vector3(0, 0, 1));
    g.position.copy(pos);
    g.lookAt(ahead);
    g.rotateZ(-Math.sin(p * Math.PI * 1.3) * 0.7); // bank through the turn
    if (p >= 1) {
      clock.boomed = true;
      onBoom(pos.clone());
    }
  });

  return (
    <>
      <group ref={ref} position={START}>
        <Jet />
        <object3D ref={tipR} position={[3.5, -0.12, -0.6]} />
        <object3D ref={tipL} position={[-3.5, -0.12, -0.6]} />
        <pointLight position={[0, 2, 3]} intensity={12} distance={10} color="#fff1e0" />
        <pointLight position={[0, -0.4, -1.2]} intensity={8} distance={6} color="#6fb8ff" />
      </group>
      <Contrail anchor={tipR} clock={clock} />
      <Contrail anchor={tipL} clock={clock} />
    </>
  );
}

/** A camera facing ribbon that remembers where the anchor has been. Starts collapsed at the anchor, so no stray line. */
function Contrail({ anchor, clock, n = 48, width = 0.32 }: { anchor: React.RefObject<THREE.Object3D | null>; clock: Clock; n?: number; width?: number }) {
  const mesh = useRef<THREE.Mesh>(null);
  const hist = useMemo(() => Array.from({ length: n }, () => new THREE.Vector3()), [n]);
  const primed = useRef(false);
  const geo = useMemo(() => {
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(n * 2 * 3), 3));
    g.setAttribute('alpha', new THREE.BufferAttribute(new Float32Array(n * 2), 1));
    const idx: number[] = [];
    for (let i = 0; i < n - 1; i++) {
      const a = i * 2;
      idx.push(a, a + 1, a + 2, a + 1, a + 3, a + 2);
    }
    g.setIndex(idx);
    return g;
  }, [n]);
  const mat = useMemo(
    () =>
      new THREE.ShaderMaterial({
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        side: THREE.DoubleSide,
        uniforms: { uColor: { value: new THREE.Color('#cfe6ff') }, uFade: { value: 1 } },
        vertexShader: `attribute float alpha; varying float vA; void main(){ vA = alpha; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }`,
        fragmentShader: `uniform vec3 uColor; uniform float uFade; varying float vA; void main(){ gl_FragColor = vec4(uColor, vA * uFade * 0.75); }`,
      }),
    [],
  );
  const p = useMemo(() => new THREE.Vector3(), []);
  const side = useMemo(() => new THREE.Vector3(), []);
  const tan = useMemo(() => new THREE.Vector3(), []);
  const view = useMemo(() => new THREE.Vector3(), []);

  useFrame(({ camera }, dt) => {
    const a = anchor.current;
    if (!a) return;
    if (!clock.boomed) {
      a.getWorldPosition(p);
      if (!primed.current) {
        hist.forEach((h) => h.copy(p));
        primed.current = true;
      }
      for (let i = n - 1; i > 0; i--) hist[i].copy(hist[i - 1]);
      hist[0].copy(p);
    } else {
      mat.uniforms.uFade.value = Math.max(0, mat.uniforms.uFade.value - dt * 3);
    }
    const pos = geo.attributes.position.array as Float32Array;
    const al = geo.attributes.alpha.array as Float32Array;
    for (let i = 0; i < n; i++) {
      const h = hist[i];
      tan.subVectors(hist[Math.max(0, i - 1)], hist[Math.min(n - 1, i + 1)]);
      view.subVectors(camera.position, h);
      side.crossVectors(tan, view).normalize();
      const k = 1 - i / (n - 1);
      const w = width * (0.25 + 0.75 * (1 - k)) * (0.4 + h.distanceTo(camera.position) / 40);
      pos.set([h.x + side.x * w, h.y + side.y * w, h.z + side.z * w], i * 6);
      pos.set([h.x - side.x * w, h.y - side.y * w, h.z - side.z * w], i * 6 + 3);
      al[i * 2] = al[i * 2 + 1] = k * k;
    }
    geo.attributes.position.needsUpdate = true;
    geo.attributes.alpha.needsUpdate = true;
    geo.computeBoundingSphere();
  });

  return <mesh ref={mesh} geometry={geo} material={mat} frustumCulled={false} />;
}

/* ── The burst ── */

function rand(min: number, max: number) {
  return min + Math.random() * (max - min);
}
function randDir(out: THREE.Vector3) {
  const u = Math.random() * 2 - 1;
  const th = Math.random() * Math.PI * 2;
  const r = Math.sqrt(1 - u * u);
  return out.set(r * Math.cos(th), r * Math.sin(th), u);
}

function Shards({ count, color, emissive, origin, born }: { count: number; color: string; emissive?: string; origin: THREE.Vector3; born: number }) {
  const ref = useRef<THREE.InstancedMesh>(null);
  const data = useMemo(() => {
    const d = new THREE.Vector3();
    return Array.from({ length: count }, () => ({
      v: randDir(d).clone().multiplyScalar(rand(4, 20)).add(new THREE.Vector3(0, 0, rand(2, 9))),
      w: new THREE.Vector3(rand(-8, 8), rand(-8, 8), rand(-8, 8)),
      s: rand(0.06, 0.32),
    }));
  }, [count]);
  const o = useMemo(() => new THREE.Object3D(), []);

  useFrame(() => {
    const m = ref.current;
    if (!m) return;
    const t = SCENE.now - born;
    const drag = (1 - Math.exp(-t * 2.2)) / 2.2; // integrated, decelerating
    const shrink = Math.max(0, 1 - t / BURST_LEN);
    data.forEach((d, i) => {
      o.position.copy(origin).addScaledVector(d.v, drag);
      o.position.y -= t * t * 1.6;
      o.rotation.set(d.w.x * t, d.w.y * t, d.w.z * t);
      o.scale.setScalar(d.s * shrink);
      o.updateMatrix();
      m.setMatrixAt(i, o.matrix);
    });
    m.instanceMatrix.needsUpdate = true;
  });

  return (
    <instancedMesh ref={ref} args={[undefined, undefined, count]}>
      <tetrahedronGeometry args={[1, 0]} />
      {emissive ? (
        <meshStandardMaterial color={color} emissive={emissive} emissiveIntensity={3} toneMapped={false} />
      ) : (
        <meshStandardMaterial color={color} metalness={0.8} roughness={0.3} />
      )}
    </instancedMesh>
  );
}

function Sparks({ origin, born }: { origin: THREE.Vector3; born: number }) {
  const ref = useRef<THREE.Points>(null);
  const mat = useRef<THREE.PointsMaterial>(null);
  const N = 900;
  const { pos, vel } = useMemo(() => {
    const pos = new Float32Array(N * 3);
    const vel = new Float32Array(N * 3);
    const d = new THREE.Vector3();
    for (let i = 0; i < N; i++) {
      randDir(d).multiplyScalar(rand(3, 30));
      vel.set([d.x, d.y, d.z + rand(0, 6)], i * 3);
    }
    return { pos, vel };
  }, []);

  useFrame(() => {
    const p = ref.current;
    if (!p) return;
    const t = SCENE.now - born;
    const drag = (1 - Math.exp(-t * 2.6)) / 2.6;
    for (let i = 0; i < N; i++) {
      pos[i * 3] = origin.x + vel[i * 3] * drag;
      pos[i * 3 + 1] = origin.y + vel[i * 3 + 1] * drag - t * t * 2;
      pos[i * 3 + 2] = origin.z + vel[i * 3 + 2] * drag;
    }
    p.geometry.attributes.position.needsUpdate = true;
    if (mat.current) mat.current.opacity = Math.max(0, 1 - t / 1.3);
  });

  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[pos, 3]} />
      </bufferGeometry>
      <pointsMaterial ref={mat} size={0.14} color="#ffb36b" transparent blending={THREE.AdditiveBlending} depthWrite={false} toneMapped={false} />
    </points>
  );
}

function Shockwave({ origin, born, delay = 0, color, max }: { origin: THREE.Vector3; born: number; delay?: number; color: string; max: number }) {
  const ref = useRef<THREE.Mesh>(null);
  const mat = useRef<THREE.MeshBasicMaterial>(null);
  useFrame(({ camera }) => {
    const m = ref.current;
    if (!m || !mat.current) return;
    const t = Math.max(0, SCENE.now - born - delay);
    const k = 1 - Math.pow(1 - Math.min(t / 0.7, 1), 3);
    m.scale.setScalar(0.05 + k * max);
    m.quaternion.copy(camera.quaternion);
    mat.current.opacity = t === 0 ? 0 : Math.max(0, 1 - k) * 0.9;
  });
  return (
    <mesh ref={ref} position={origin}>
      <ringGeometry args={[0.82, 1, 96]} />
      <meshBasicMaterial ref={mat} color={color} transparent blending={THREE.AdditiveBlending} depthWrite={false} side={THREE.DoubleSide} toneMapped={false} />
    </mesh>
  );
}

function Fireball({ origin, born }: { origin: THREE.Vector3; born: number }) {
  const ref = useRef<THREE.Mesh>(null);
  const mat = useRef<THREE.MeshBasicMaterial>(null);
  useFrame(() => {
    const t = SCENE.now - born;
    if (!ref.current || !mat.current) return;
    ref.current.scale.setScalar(0.4 + (1 - Math.exp(-t * 9)) * 3.4);
    mat.current.opacity = Math.max(0, 1 - t / 0.55);
  });
  return (
    <mesh ref={ref} position={origin}>
      <sphereGeometry args={[1, 32, 24]} />
      <meshBasicMaterial ref={mat} color="#ffd9a8" transparent blending={THREE.AdditiveBlending} depthWrite={false} toneMapped={false} />
    </mesh>
  );
}

function Burst({ origin, born }: { origin: THREE.Vector3; born: number }) {
  return (
    <>
      <Fireball origin={origin} born={born} />
      <Shockwave origin={origin} born={born} color="#cfe6ff" max={26} />
      <Shockwave origin={origin} born={born} delay={0.09} color="#ff9a4a" max={16} />
      <Shards count={170} color="#dfe4ea" origin={origin} born={born} />
      <Shards count={50} color="#0b6fe0" origin={origin} born={born} />
      <Shards count={70} color="#3a1d0e" emissive="#ff7a2b" origin={origin} born={born} />
      <Sparks origin={origin} born={born} />
      <pointLight position={origin} intensity={60} distance={30} color="#ffb36b" />
    </>
  );
}


/* ── Sky, sun and the cloud sea ── */

/** Soft puff texture drawn at runtime, so the clouds need no network fetch. */
function usePuffTexture() {
  return useMemo(() => {
    const c = document.createElement('canvas');
    c.width = c.height = 128;
    const g = c.getContext('2d')!;
    let s = 7;
    const r = () => (s = (s * 16807) % 2147483647) / 2147483647;
    for (let i = 0; i < 40; i++) {
      const a = r() * Math.PI * 2;
      const d = Math.pow(r(), 0.7) * 34;
      const x = 64 + Math.cos(a) * d;
      const y = 64 + Math.sin(a) * d * 0.75;
      const rad = 14 + r() * 24;
      const grd = g.createRadialGradient(x, y, 0, x, y, rad);
      grd.addColorStop(0, 'rgba(255,255,255,0.26)');
      grd.addColorStop(1, 'rgba(255,255,255,0)');
      g.fillStyle = grd;
      g.beginPath();
      g.arc(x, y, rad, 0, Math.PI * 2);
      g.fill();
    }
    // feather the edge so a square never shows
    g.globalCompositeOperation = 'destination-in';
    const m = g.createRadialGradient(64, 64, 26, 64, 64, 64);
    m.addColorStop(0, 'rgba(0,0,0,1)');
    m.addColorStop(1, 'rgba(0,0,0,0)');
    g.fillStyle = m;
    g.fillRect(0, 0, 128, 128);
    return new THREE.CanvasTexture(c);
  }, []);
}

function useGlowTexture() {
  return useMemo(() => {
    const c = document.createElement('canvas');
    c.width = c.height = 256;
    const g = c.getContext('2d')!;
    const grd = g.createRadialGradient(128, 128, 0, 128, 128, 128);
    grd.addColorStop(0, 'rgba(255,248,230,1)');
    grd.addColorStop(0.12, 'rgba(255,224,170,0.85)');
    grd.addColorStop(0.4, 'rgba(255,170,100,0.25)');
    grd.addColorStop(1, 'rgba(255,140,80,0)');
    g.fillStyle = grd;
    g.fillRect(0, 0, 256, 256);
    const t = new THREE.CanvasTexture(c);
    t.colorSpace = THREE.SRGBColorSpace;
    return t;
  }, []);
}

const SUN = new THREE.Vector3(0, 9, -160);

// development switches for isolating render problems: ?off=sky,clouds,env,glow
const OFF = new Set(process.env.NODE_ENV !== 'production' && typeof window !== 'undefined' ? (new URLSearchParams(window.location.search).get('off') || '').split(',') : []);

/* ── Cloud field: soft camera facing puffs in one instanced draw, sorted far to near ── */

type Puff = { p: THREE.Vector3; size: number; rot: number; shade: number };

// Deterministic layout: puffy clusters on a deck below the camera, a long bank at the horizon, a solid floor beneath
const PUFFS: Puff[] = (() => {
  let s = 11;
  const r = () => (s = (s * 16807) % 2147483647) / 2147483647;
  const out: Puff[] = [];
  const cluster = (cx: number, cy: number, cz: number, bx: number, by: number, bz: number, n: number, size: number) => {
    for (let i = 0; i < n; i++) {
      // denser and taller in the middle, so each cluster domes like a cumulus
      const u = r() * 2 - 1, v = r() * 2 - 1;
      const dome = 1 - Math.min(1, u * u + v * v);
      out.push({
        p: new THREE.Vector3(cx + u * bx, cy + (r() * 0.4 + dome * 0.9) * by, cz + v * bz),
        size: size * (0.6 + r() * 0.7) * (0.7 + dome * 0.5),
        rot: r() * Math.PI * 2,
        shade: 0.35 + dome * 0.5 + r() * 0.15,
      });
    }
  };
  for (let i = 0; i < 26; i++) cluster((r() - 0.5) * 90, -6.5 + r() * 1.2, -6 - r() * 85, 7 + r() * 6, 2.6 + r() * 1.6, 4 + r() * 3, 16, 7.5);
  for (let i = 0; i < 14; i++) cluster((r() - 0.5) * 220, -6 + r(), -110 - r() * 70, 18, 3.5, 8, 14, 16);
  for (let i = 0; i < 90; i++) out.push({ p: new THREE.Vector3((r() - 0.5) * 120, -10 + r() * 1.5, 14 - r() * 110), size: 18 + r() * 10, rot: r() * 6.28, shade: 0.4 + r() * 0.2 });
  return out;
})();

const cloudVert = /* glsl */ `
  attribute vec3 aOffset;
  attribute vec3 aData; // size, rotation, shade
  uniform float uTime;
  varying vec2 vUv;
  varying float vShade;
  varying float vDepth;
  void main() {
    vUv = uv;
    vShade = aData.z;
    vec3 o = aOffset;
    o.x += uTime * 0.35; // slow drift
    vec4 mv = modelViewMatrix * vec4(o, 1.0);
    float c = cos(aData.y), s = sin(aData.y);
    vec2 q = mat2(c, -s, s, c) * position.xy;
    mv.xy += q * aData.x;
    vDepth = -mv.z;
    gl_Position = projectionMatrix * mv;
  }
`;
const cloudFrag = /* glsl */ `
  uniform sampler2D uMap;
  uniform vec3 uLit;
  uniform vec3 uShadow;
  uniform vec3 uFogColor;
  uniform float uFogNear;
  uniform float uFogFar;
  varying vec2 vUv;
  varying float vShade;
  varying float vDepth;
  void main() {
    float a = texture2D(uMap, vUv).a;
    // lit from above and from the low sun ahead: tops bright, bellies shaded
    float l = clamp(vShade * 0.75 + (vUv.y - 0.35) * 0.7, 0.0, 1.0);
    vec3 col = mix(uShadow, uLit, l);
    float f = smoothstep(uFogNear, uFogFar, vDepth);
    col = mix(col, uFogColor, f);
    // puffs right at the lens dissolve instead of filling the frame
    a *= smoothstep(0.6, 5.0, vDepth);
    gl_FragColor = vec4(col, a * 0.95);
  }
`;

function CloudField() {
  const map = usePuffTexture();
  const n = PUFFS.length;
  const { geo, mat } = useMemo(() => {
    const base = new THREE.PlaneGeometry(1, 1);
    const g = new THREE.InstancedBufferGeometry();
    g.index = base.index;
    g.setAttribute('position', base.getAttribute('position'));
    g.setAttribute('uv', base.getAttribute('uv'));
    g.setAttribute('aOffset', new THREE.InstancedBufferAttribute(new Float32Array(n * 3), 3));
    g.setAttribute('aData', new THREE.InstancedBufferAttribute(new Float32Array(n * 3), 3));
    g.instanceCount = n;
    const m = new THREE.ShaderMaterial({
      vertexShader: cloudVert,
      fragmentShader: cloudFrag,
      transparent: true,
      depthWrite: false,
      uniforms: {
        uMap: { value: map },
        uTime: { value: 0 },
        uLit: { value: new THREE.Color('#fff6ec') },
        uShadow: { value: new THREE.Color("#c9a2a4") },
        uFogColor: { value: new THREE.Color('#f6c9a2') },
        uFogNear: { value: 30 },
        uFogFar: { value: 190 },
      },
    });
    return { geo: g, mat: m };
  }, [map, n]);

  const order = useMemo(() => PUFFS.map((_, i) => i), []);
  const dist = useMemo(() => new Float32Array(n), [n]);

  useFrame(({ camera, scene }) => {
    mat.uniforms.uTime.value = SCENE.now;
    const fog = scene.fog as THREE.Fog | null;
    if (fog) {
      mat.uniforms.uFogColor.value.copy(fog.color);
      mat.uniforms.uFogNear.value = fog.near;
      mat.uniforms.uFogFar.value = fog.far;
    }
    // far to near, so the soft edges blend correctly
    const drift = SCENE.now * 0.35;
    for (let i = 0; i < n; i++) {
      const p = PUFFS[i].p;
      const dx = p.x + drift - camera.position.x, dy = p.y - camera.position.y, dz = p.z - camera.position.z;
      dist[i] = dx * dx + dy * dy + dz * dz;
    }
    order.sort((a, b) => dist[b] - dist[a]);
    const off = geo.getAttribute('aOffset') as THREE.InstancedBufferAttribute;
    const dat = geo.getAttribute('aData') as THREE.InstancedBufferAttribute;
    const oa = off.array as Float32Array, da = dat.array as Float32Array;
    for (let k = 0; k < n; k++) {
      const q = PUFFS[order[k]];
      oa[k * 3] = q.p.x; oa[k * 3 + 1] = q.p.y; oa[k * 3 + 2] = q.p.z;
      da[k * 3] = q.size; da[k * 3 + 1] = q.rot; da[k * 3 + 2] = q.shade;
    }
    off.needsUpdate = true;
    dat.needsUpdate = true;
  });

  return <mesh geometry={geo} material={mat} frustumCulled={false} renderOrder={1} />;
}

function CloudSea() {
  const glow = useGlowTexture();
  return (
    <>
      {!OFF.has('sky') && <Sky distance={4500} sunPosition={[0, 0.045, -1]} turbidity={9} rayleigh={2.6} mieCoefficient={0.008} mieDirectionalG={0.88} />}
      {!OFF.has('glow') && (
        <sprite position={SUN} scale={[64, 64, 1]}>
          <spriteMaterial map={glow} transparent blending={THREE.AdditiveBlending} depthWrite={false} fog={false} toneMapped={false} />
        </sprite>
      )}
      {!OFF.has('clouds') && <CloudField />}
    </>
  );
}

/* ── Director: one clock for the intro, the camera, the scroll dive and the burst ── */

const FOG_WARM = new THREE.Color('#f6c9a2');
const FOG_WHITE = new THREE.Color('#ffffff');

function Director({ onBoom, scroll, skipIntro }: { onBoom: () => void; scroll: { p: number }; skipIntro: boolean }) {
  const clock = useMemo<Clock>(() => ({ t: skipIntro ? FLIGHT + 2 : 0, boomed: skipIntro }), [skipIntro]);
  const [burst, setBurst] = useState<{ at: THREE.Vector3; born: number } | null>(null);
  const shake = useRef(0);
  const t0 = useRef<number | null>(null);
  const look = useMemo(() => new THREE.Vector3(), []);
  const dive = useRef(0);

  // Runs before every other frame callback (negative priority keeps automatic rendering)
  useFrame(({ camera, clock: c, scene, pointer }, dt) => {
    if (t0.current === null) t0.current = c.elapsedTime;
    SCENE.now = (c.elapsedTime - t0.current) / SCENE.slow;
    if (!skipIntro) clock.t = SCENE.now;
    shake.current *= Math.exp(-(dt / SCENE.slow) * 5);
    const s = shake.current;

    // intro: a slow glide forward over the cloud tops
    const k = skipIntro ? 1 : Math.min(SCENE.now / (FLIGHT + 0.4), 1);
    const ease = 1 - Math.pow(1 - k, 3);
    // scroll: dive down through the deck (damped, so it carries momentum)
    dive.current += (scroll.p - dive.current) * (1 - Math.exp(-dt * 6));
    const d = dive.current;
    const dd = d * d * (3 - 2 * d);

    const x = pointer.x * 0.6 * (1 - d);
    const y = 6.2 - ease * 1.6 - dd * 14;
    const z = 19 - ease * 4 - dd * 7;
    camera.position.set(x + (Math.random() - 0.5) * s, y + (Math.random() - 0.5) * s, z);
    look.set(pointer.x * 1.2 * (1 - d), 2.6 - dd * 16 + pointer.y * 0.6 * (1 - d), -24 + dd * 8);
    camera.lookAt(look);

    const fog = scene.fog as THREE.Fog | null;
    if (fog) {
      fog.near = 30 - dd * 28;
      fog.far = 190 - dd * 172;
      fog.color.copy(FOG_WARM).lerp(FOG_WHITE, Math.min(1, dd * 1.4));
    }
  }, -1);

  return (
    <>
      {!skipIntro && (
        <Plane
          clock={clock}
          onBoom={(at) => {
            shake.current = 0.9;
            setBurst({ at, born: SCENE.now });
            onBoom();
          }}
        />
      )}
      {burst && <Burst origin={burst.at} born={burst.born} />}
    </>
  );
}

export default function SkyScene({
  onBoom,
  onReady,
  scroll,
  skipIntro,
  active,
}: {
  onBoom: () => void;
  onReady: () => void;
  scroll: { p: number };
  skipIntro: boolean;
  active: boolean;
}) {
  const ready = useRef(onReady);
  useLayoutEffect(() => {
    ready.current = onReady;
  });
  return (
    <Canvas
      frameloop={active ? 'always' : 'never'}
      dpr={[1, 1.6]}
      camera={{ position: [0, 6.2, 19], fov: 48, near: 0.1, far: 6000 }}
      gl={{ antialias: true, powerPreference: 'high-performance' }}
      onCreated={(state) => {
        state.gl.toneMappingExposure = 0.62;
        if (process.env.NODE_ENV !== 'production') (window as unknown as { __sky: unknown }).__sky = state;
        ready.current();
      }}
    >
      <fog attach="fog" args={['#f6c9a2', 30, 190]} />
      <hemisphereLight args={['#ffd8b0', '#7a6a9a', 0.9]} />
      <directionalLight position={[0, 12, -100]} intensity={2.2} color="#ffb877" />
      <directionalLight position={[8, 20, 30]} intensity={0.8} color="#ffe9d6" />
      {!OFF.has('env') && <Environment resolution={64} frames={1}>
        <Lightformer form="rect" intensity={3} color="#ffd2a0" position={[0, 2, -10]} scale={[20, 4, 1]} />
        <Lightformer form="rect" intensity={1.4} color="#9fb6ff" position={[0, 10, 6]} rotation={[Math.PI / 2, 0, 0]} scale={[20, 20, 1]} />
      </Environment>}
      <CloudSea />
      <Director onBoom={onBoom} scroll={scroll} skipIntro={skipIntro} />
    </Canvas>
  );
}
