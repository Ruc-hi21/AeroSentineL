'use client';

import { useRef } from 'react';
import { motion, useMotionValue, useSpring, useTransform, useReducedMotion, useMotionTemplate } from 'motion/react';

/** A card that leans towards the pointer in 3D, with a soft glare that follows it. */
export default function Tilt({
  children,
  className,
  max = 8,
  glare = true,
}: {
  children: React.ReactNode;
  className?: string;
  max?: number;
  glare?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();
  const px = useMotionValue(0.5);
  const py = useMotionValue(0.5);
  const spring = { stiffness: 220, damping: 22, mass: 0.6 };
  const rx = useSpring(useTransform(py, [0, 1], [max, -max]), spring);
  const ry = useSpring(useTransform(px, [0, 1], [-max, max]), spring);
  const gx = useTransform(px, (v) => `${v * 100}%`);
  const gy = useTransform(py, (v) => `${v * 100}%`);
  const bg = useMotionTemplate`radial-gradient(420px circle at ${gx} ${gy}, rgb(255 255 255 / 0.55), transparent 55%)`;
  const glareOpacity = useSpring(0, spring);

  if (reduce) return <div className={className}>{children}</div>;

  return (
    <div className={`[perspective:1200px] ${className ?? ''}`}>
      <motion.div
        ref={ref}
        className="relative h-full [transform-style:preserve-3d]"
        style={{ rotateX: rx, rotateY: ry }}
        onPointerMove={(e) => {
          if (e.pointerType !== 'mouse') return;
          const r = ref.current!.getBoundingClientRect();
          px.set((e.clientX - r.left) / r.width);
          py.set((e.clientY - r.top) / r.height);
          glareOpacity.set(1);
        }}
        onPointerLeave={() => {
          px.set(0.5);
          py.set(0.5);
          glareOpacity.set(0);
        }}
      >
        {children}
        {glare && (
          <motion.span
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 z-10 rounded-2xl mix-blend-soft-light"
            style={{ background: bg, opacity: glareOpacity }}
          />
        )}
      </motion.div>
    </div>
  );
}
