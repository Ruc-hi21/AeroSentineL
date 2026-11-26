'use client';

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import * as THREE from 'three';
import { Canvas, useFrame } from '@react-three/fiber';
import { Environment, Html, Lightformer } from '@react-three/drei';
import gsap from 'gsap';

/* A procedurally built two spool turbofan, sectioned to show the gas path.
   Built along +Y, then turned so the inlet faces the viewer's right. */

type Shared = { assemble: { p: number }; scroll: { p: number }; reduce: boolean };

const CUT_START = 0;
const CUT_LENGTH = Math.PI * 1.5; // leaves the upper quadrant facing the camera open

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
    if (group.current) group.current.rotation.y += dt * speed;
  });

  return (
    <group ref={group} position={[0, y, 0]}>
      <instancedMesh ref={ref} args={[undefined, undefined, count]}>
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
function Part({ offset, shared, children }: { offset: number; shared: Shared; children: React.ReactNode }) {
  const ref = useRef<THREE.Group>(null);
  useFrame(() => {
    if (ref.current) ref.current.position.y = (1 - shared.assemble.p) * offset;
  });
  return <group ref={ref}>{children}</group>;
}

type Station = { id: string; label: string; value: string; y: number; r: number; tone: 'healthy' | 'degrading' | 'warning'; down?: boolean };
const STATIONS: Station[] = [
  { id: 'T2', label: 'Fan inlet', value: '+0.2σ', y: 2.78, r: 0.92, tone: 'healthy' },
  { id: 'T24', label: 'LPC outlet', value: '+1.1σ', y: 1.62, r: 0.62, tone: 'degrading', down: true },
  { id: 'T30', label: 'HPC outlet', value: '+2.1σ', y: 0.42, r: 0.58, tone: 'warning' },
  { id: 'T50', label: 'LPT outlet', value: '+2.4σ', y: -1.42, r: 0.56, tone: 'warning', down: true },
];
const TONE: Record<Station['tone'], string> = { healthy: '#198038', degrading: '#9a7200', warning: '#c24e00' };

function Stations({ shared }: { shared: Shared }) {
  // inside the open quadrant: between local -X and +Z
  const dir = useMemo(() => new THREE.Vector2(-0.62, 0.78).normalize(), []);
  const [show, setShow] = useState(false);
  useFrame(() => {
    const s = shared.assemble.p > 0.92;
    if (s !== show) setShow(s);
  });
  return (
    <>
      {STATIONS.map((s) => (
        <group key={s.id} position={[dir.x * s.r, s.y, dir.y * s.r]}>
          <mesh>
            <sphereGeometry args={[0.035, 16, 16]} />
            <meshBasicMaterial color={TONE[s.tone]} toneMapped={false} />
          </mesh>
          <Html center zIndexRange={[20, 0]} style={{ pointerEvents: 'none' }}>
            <div
              className="station"
              data-show={show}
              data-side={s.down ? "down" : "up"}
              style={{ ['--tone' as string]: TONE[s.tone] }}
            >
              <span className="station-dot" />
              <span className="data">{s.id}</span>
              <span className="station-label">{s.label}</span>
              <span className="data station-value">{s.value}</span>
            </div>
          </Html>
        </group>
      ))}
    </>
  );
}

function Engine({ shared }: { shared: Shared }) {
  const root = useRef<THREE.Group>(null);
  const glow = useRef<THREE.MeshStandardMaterial>(null);
  const nacelle = useMemo(() => lathe(NACELLE), []);
  const ghost = useMemo(() => lathe(NACELLE.slice(0, 6), 36, true), []);
  const core = useMemo(() => lathe(CORE), []);
  const spin = shared.reduce ? 0.6 : 1;

  useFrame((state, dt) => {
    const g = root.current;
    if (!g) return;
    const k = 1 - Math.exp(-dt * 2.6); // damped follow: momentum, not a hard lock
    const s = shared.scroll.p;
    const ty = -0.62 + state.pointer.x * 0.28 + s * 0.9;
    const tx = 0.16 - state.pointer.y * 0.1 + s * 0.1;
    g.rotation.y += (ty - g.rotation.y) * k;
    g.rotation.x += (tx - g.rotation.x) * k;
    if (glow.current) glow.current.emissiveIntensity = 1.6 + Math.sin(state.clock.elapsedTime * 2.2) * 0.5;
  });

  return (
    <group ref={root}>
      <group rotation={[0, 0, -Math.PI / 2]} position={[-0.85, 0, 0]}>
        {/* Fan cowl, sectioned */}
        <Part offset={0.7} shared={shared}>
          <mesh geometry={nacelle}>
            <meshStandardMaterial color="#c3c8cf" metalness={0.88} roughness={0.3} side={THREE.DoubleSide} />
          </mesh>
          <mesh geometry={ghost}>
            <meshBasicMaterial color="#3fa2ff" wireframe transparent opacity={0.07} />
          </mesh>
        </Part>

        {/* Fan and spinner */}
        <Part offset={1.7} shared={shared}>
          <BladeRing y={2.56} hub={0.3} tip={1.15} count={22} chord={0.2} twist={0.62} color="#dfe3e8" speed={6 * spin} />
          <mesh position={[0, 2.92, 0]}>
            <coneGeometry args={[0.31, 0.62, 48]} />
            <meshStandardMaterial color="#2a2e34" metalness={0.7} roughness={0.25} />
          </mesh>
        </Part>

        {/* Low pressure compressor */}
        <Part offset={1.1} shared={shared}>
          {[2.16, 1.98, 1.8].map((y, i) => (
            <BladeRing key={y} y={y} hub={0.26} tip={0.64} count={30} chord={0.08} twist={0.5} color="#bcc2ca" speed={6 * spin} phase={i * 0.1} />
          ))}
        </Part>

        {/* High pressure compressor */}
        <Part offset={0.45} shared={shared}>
          {Array.from({ length: 8 }).map((_, i) => {
            const y = 1.48 - i * 0.14;
            return (
              <BladeRing key={y} y={y} hub={0.24} tip={0.6 - i * 0.022} count={36} chord={0.06} twist={0.45} color="#aeb5be" speed={-11 * spin} phase={i * 0.2} />
            );
          })}
        </Part>

        {/* Combustor */}
        <Part offset={0} shared={shared}>
          <mesh position={[0, 0.08, 0]} rotation={[Math.PI / 2, 0, 0]}>
            <torusGeometry args={[0.4, 0.085, 24, 96, CUT_LENGTH]} />
            <meshStandardMaterial ref={glow} color="#3a1d0e" emissive="#ff7a2b" emissiveIntensity={1.6} roughness={0.5} toneMapped={false} />
          </mesh>
          <mesh position={[0, 0.45, 0]}>
            <cylinderGeometry args={[0.05, 0.05, 4.4, 16]} />
            <meshStandardMaterial color="#7a8089" metalness={0.9} roughness={0.3} />
          </mesh>
        </Part>

        {/* High and low pressure turbines */}
        <Part offset={-1.2} shared={shared}>
          {[-0.3, -0.45].map((y, i) => (
            <BladeRing key={y} y={y} hub={0.26} tip={0.5} count={40} chord={0.07} twist={-0.5} color="#a8927e" rough={0.36} speed={-11 * spin} phase={i * 0.15} />
          ))}
          {[-0.72, -0.9, -1.08, -1.26].map((y, i) => (
            <BladeRing key={y} y={y} hub={0.28} tip={0.5 + i * 0.03} count={44} chord={0.08} twist={-0.55} color="#9a8a7c" rough={0.36} speed={6 * spin} phase={i * 0.12} />
          ))}
          <mesh position={[0, -1.98, 0]} rotation={[Math.PI, 0, 0]}>
            <coneGeometry args={[0.3, 0.95, 48]} />
            <meshStandardMaterial color="#4a4f57" metalness={0.8} roughness={0.35} />
          </mesh>
        </Part>

        {/* Core cowl, sectioned */}
        <Part offset={-0.5} shared={shared}>
          <mesh geometry={core}>
            <meshStandardMaterial color="#8d939b" metalness={0.85} roughness={0.38} side={THREE.DoubleSide} />
          </mesh>
        </Part>

        <Stations shared={shared} />
      </group>
    </group>
  );
}

/** Keeps the whole engine in frame on narrow canvases. */
function Rig() {
  useFrame(({ camera, size }) => {
    const aspect = size.width / size.height;
    const z = 10.4 * Math.max(1, 1.25 / aspect);
    if (Math.abs(camera.position.z - z) > 0.01) {
      camera.position.z = z;
      camera.updateProjectionMatrix();
    }
  });
  return null;
}

export default function EngineScene({ scroll, start = true }: { scroll: { p: number }; start?: boolean }) {
  const wrap = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(true);
  const shared = useMemo<Shared>(() => {
    const reduce = typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    return { assemble: { p: reduce ? 1 : 0 }, scroll, reduce };
  }, [scroll]);

  // The hero's one authored moment: the engine assembles from an exploded view.
  useEffect(() => {
    if (shared.reduce || !start) return;
    const t = gsap.to(shared.assemble, { p: 1, duration: 2.6, delay: 0.1, ease: 'expo.out' });
    return () => {
      t.kill();
    };
  }, [shared, start]);

  // Stop rendering when the hero is off screen
  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const io = new IntersectionObserver(([e]) => setVisible(e.isIntersecting), { rootMargin: '120px' });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    <div ref={wrap} className="absolute inset-0">
      <Canvas
        frameloop={visible ? 'always' : 'never'}
        dpr={[1, 1.75]}
        camera={{ position: [0.3, 0.8, 10.4], fov: 30 }}
        gl={{ antialias: true, alpha: true, powerPreference: 'high-performance' }}
      >
        <ambientLight intensity={0.25} />
        <directionalLight position={[3, 5, 6]} intensity={1.6} />
        <directionalLight position={[-6, 2, -4]} intensity={2.2} color="#3fa2ff" />
        <pointLight position={[0, -2, 3]} intensity={6} distance={7} color="#ff7a2b" />
        <Environment resolution={256} frames={1}>
          <Lightformer form="rect" intensity={2.2} position={[0, 4, 2]} scale={[10, 1.6, 1]} />
          <Lightformer form="rect" intensity={1.2} position={[-5, 0, 1]} rotation={[0, Math.PI / 2, 0]} scale={[8, 2, 1]} />
          <Lightformer form="rect" intensity={1.6} color="#3fa2ff" position={[5, -1, -2]} rotation={[0, -Math.PI / 2, 0]} scale={[8, 1, 1]} />
          <Lightformer form="ring" intensity={0.8} position={[0, 0, -6]} scale={4} />
        </Environment>
        <Rig />
        <Engine shared={shared} />
      </Canvas>
    </div>
  );
}
