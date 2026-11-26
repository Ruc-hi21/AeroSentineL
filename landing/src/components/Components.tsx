'use client';

import Link from 'next/link';
import { ArrowUpRight } from '@phosphor-icons/react';
import { useRef } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { useGSAP } from '@gsap/react';
import { Reveal, SectionHead } from './ui';
import Tilt from './Tilt';

gsap.registerPlugin(ScrollTrigger, useGSAP);

const ITEMS = [
  {
    img: '/brand/turbofan.webp',
    name: 'Turbofan engine',
    unit: 'Life in engine cycles',
    watch: 'Gas path temperatures, pressures and spool speeds, corrected for altitude, Mach and throttle.',
    big: true,
  },
  {
    img: '/brand/battery.webp',
    name: 'Lithium ion battery cell',
    unit: 'Life in discharge cycles',
    watch: 'Capacity fade, charge time and impedance, against the cell’s own first discharges.',
  },
  {
    img: '/brand/bearing.webp',
    name: 'Engine gearbox',
    unit: 'Life in running minutes',
    watch: 'Bearing vibration on two accelerometer axes, at its shaft speed and load.',
  },
  {
    img: '/brand/hydraulic.webp',
    name: 'Hydraulic system',
    unit: 'Remaining condition margin',
    watch: 'Pressures, flows and temperatures, plus a separate call on the cooler, valve and pump.',
  },
  {
    img: '/brand/power.webp',
    name: 'Power electronics switch',
    unit: 'Life in running minutes',
    watch: 'On state voltage, gate voltage and package temperature of the IGBT module.',
  },
];

export default function Components() {
  const plane = useRef<HTMLDivElement>(null);

  // The grid lies back like a tabletop and stands up as it scrolls in
  useGSAP(
    () => {
      if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
      gsap.fromTo(
        '.cards-plane',
        { rotateX: 32, scale: 0.88, y: 60 },
        { rotateX: 0, scale: 1, y: 0, ease: 'none', scrollTrigger: { trigger: plane.current, start: 'top 100%', end: 'top 30%', scrub: 0.8 } },
      );
    },
    { scope: plane },
  );

  return (
    <section id="components" aria-labelledby="components-title" className="section border-t border-line">
      <div className="wrap">
        <SectionHead id="components-title" title="One console for five aircraft systems.">
          Each component keeps its own model, its own units and its own risk limits. You never pick which one; the
          console routes every file to the right model by itself.
        </SectionHead>

        <div ref={plane} className="mt-16 [perspective:1800px]">
        <ul className="cards-plane grid grid-cols-1 gap-4 [transform-origin:50%_0%] [transform-style:preserve-3d] sm:grid-cols-2 lg:grid-cols-4 lg:grid-rows-2">
          {ITEMS.map((it, i) => (
            <Reveal
              as="li"
              key={it.name}
              delay={0.06 * i}
              className={it.big ? 'sm:col-span-2 lg:row-span-2' : ''}
            >
              <Tilt className="h-full" max={7}>
              <Link
                href="/demo/"
                className="lift group flex h-full flex-col overflow-hidden rounded-2xl border border-line bg-surface shadow-[0_24px_48px_-28px_rgb(0_0_0/0.35)]"
              >
                <div className={`relative overflow-hidden bg-[#0e1013] ${it.big ? 'aspect-[16/10] lg:aspect-auto lg:flex-1' : 'aspect-[16/10]'}`}>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={it.img}
                    alt={`${it.name} model in the AeroSentinel console`}
                    loading="lazy"
                    className="zoom-img absolute inset-0 h-full w-full object-cover"
                  />
                </div>
                <div className="flex flex-1 flex-col p-4 sm:p-6">
                  <div className="flex items-start justify-between gap-4">
                    <h3 className={`${it.big ? 'heading-5' : 'title-2'} text-ink`}>{it.name}</h3>
                    <ArrowUpRight size={18} className="mt-1 shrink-0 text-faint transition-colors duration-300 group-hover:text-accent" aria-hidden="true" />
                  </div>
                  <p className="caption-4 mt-2 text-accent">{it.unit}</p>
                  <p className="body-6 mt-3 text-muted">{it.watch}</p>
                </div>
              </Link>
              </Tilt>
            </Reveal>
          ))}
        </ul>
        </div>
      </div>
    </section>
  );
}
