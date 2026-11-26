'use client';

import { useRef, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { useGSAP } from '@gsap/react';
import { EASE } from '@/lib/site';
import { DemoButton, SectionHead } from './ui';

gsap.registerPlugin(ScrollTrigger, useGSAP);

const SHOTS = [
  { id: 'status', label: 'Unit status', src: '/shots/status.webp', w: 1440, h: 1400, path: 'unit status', alt: 'Unit status page: condition, remaining life on a banded scale, end of life window and the engine schematic shaded by sensor drift' },
  { id: 'twin', label: 'Engine in 3D', src: '/shots/twin.webp', w: 1440, h: 1400, path: '3d model', alt: 'Sectioned 3D turbofan with every sensor placed at its station and leader lines to drifting sensors' },
  { id: 'gearbox', label: 'Gearbox', src: '/shots/gearbox3d.webp', w: 1117, h: 802, path: '3d model · gearbox', alt: 'Cut away accessory gearbox in 3D with leader lines from drifting vibration channels' },
  { id: 'hydraulic', label: 'Hydraulic rig', src: '/shots/hydraulic3d.webp', w: 1117, h: 802, path: '3d model · hydraulics', alt: 'Hydraulic circuit in 3D: reservoir, pump, valves, accumulator, cooler and working cylinder' },
  { id: 'battery', label: 'Battery cell', src: '/shots/battery3d.webp', w: 1117, h: 802, path: '3d model · battery', alt: 'Lithium ion cell cut open to show every electrode layer, at the front of its module' },
  { id: 'power', label: 'Inverter', src: '/shots/power3d.webp', w: 1117, h: 802, path: '3d model · power', alt: 'Three phase inverter stack with the monitored IGBT module cut open' },
] as const;

export default function ConsoleShowcase() {
  const [active, setActive] = useState(0);
  const stage = useRef<HTMLDivElement>(null);
  const shot = SHOTS[active];

  // Scroll moment: the console frame tilts up from the desk and settles flat
  useGSAP(
    () => {
      if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
      gsap.fromTo(
        '.console-frame',
        { rotateX: 52, scale: 0.78, y: 120 },
        {
          rotateX: 0,
          scale: 1,
          y: 0,
          ease: 'power1.out',
          scrollTrigger: { trigger: stage.current, start: 'top 105%', end: 'top 20%', scrub: 0.8 },
        },
      );
      gsap.fromTo(
        '.console-glow',
        { opacity: 0 },
        { opacity: 1, ease: 'none', scrollTrigger: { trigger: stage.current, start: 'top 80%', end: 'top 30%', scrub: true } },
      );
    },
    { scope: stage },
  );

  return (
    <section id="console" aria-labelledby="console-title" className="section border-t border-line">
      <div className="wrap">
        <div className="flex flex-col items-start justify-between gap-8 lg:flex-row lg:items-end">
          <SectionHead id="console-title" title="See the console before you sign in.">
            The same engineering console your team would use: status, forecasts, explanations and a sectioned 3D model of
            every component, with each drifting sensor tied to its station.
          </SectionHead>
          <DemoButton label="Open it live" />
        </div>

        <div className="mt-12 flex gap-2 overflow-x-auto pb-2" role="tablist" aria-label="Console views">
          {SHOTS.map((s, i) => (
            <button
              key={s.id}
              role="tab"
              aria-selected={i === active}
              aria-controls="console-view"
              onClick={() => setActive(i)}
              className={`btn button-sm shrink-0 border ${
                i === active ? 'border-line-strong bg-raised text-ink' : 'border-line text-muted hover:text-ink'
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>

        <div ref={stage} className="relative mt-6 [perspective:1600px]">
          <div className="console-glow pointer-events-none absolute -inset-x-8 -bottom-8 top-1/3 -z-10 rounded-[48px] bg-accent/10 blur-3xl" aria-hidden="true" />
          <div className="console-frame overflow-hidden rounded-2xl border border-line-strong bg-surface shadow-[0_40px_80px_-20px_rgb(0_0_0/0.22)] [transform-origin:50%_100%] will-change-transform">
            <div className="flex items-center gap-4 border-b border-line px-4 py-3">
              <span className="flex gap-2" aria-hidden="true">
                <span className="h-2.5 w-2.5 rounded-full bg-line-strong" />
                <span className="h-2.5 w-2.5 rounded-full bg-line-strong" />
                <span className="h-2.5 w-2.5 rounded-full bg-line-strong" />
              </span>
              <span className="caption-5 data truncate rounded-md bg-base px-3 py-1 text-faint">aerosentinel / {shot.path}</span>
            </div>
            <div id="console-view" role="tabpanel" className="relative aspect-[16/10] bg-[#0e1013]">
              <AnimatePresence initial={false}>
                <motion.img
                  key={shot.id}
                  src={shot.src}
                  width={shot.w}
                  height={shot.h}
                  alt={shot.alt}
                  className="absolute inset-0 h-full w-full object-cover object-top"
                  initial={{ opacity: 0, filter: 'blur(6px)', scale: 1.01 }}
                  animate={{ opacity: 1, filter: 'blur(0px)', scale: 1 }}
                  exit={{ opacity: 0, transition: { duration: 0.25 } }}
                  transition={{ duration: 0.5, ease: EASE }}
                />
              </AnimatePresence>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
