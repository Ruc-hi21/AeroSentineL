'use client';

import { useRef } from 'react';
import Link from 'next/link';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { useGSAP } from '@gsap/react';
import { ArrowUpRight } from '@phosphor-icons/react';
import { SectionHead } from './ui';

gsap.registerPlugin(ScrollTrigger, useGSAP);

const ITEMS = [
  {
    img: '/brand/turbofan.webp',
    name: 'Turbofan engine',
    unit: 'Life in engine cycles',
    watch: 'Gas path temperatures, pressures and spool speeds, corrected for altitude, Mach and throttle.',
    stat: '4 profiles · FD001 to FD004',
  },
  {
    img: '/brand/battery.webp',
    name: 'Lithium ion battery cell',
    unit: 'Life in discharge cycles',
    watch: 'Capacity fade, charge time and impedance, against the cell’s own first discharges.',
    stat: 'NASA PCoE cells',
  },
  {
    img: '/brand/bearing.webp',
    name: 'Engine gearbox',
    unit: 'Life in running minutes',
    watch: 'Bearing vibration on two accelerometer axes, at its shaft speed and load.',
    stat: 'FEMTO bearings',
  },
  {
    img: '/brand/hydraulic.webp',
    name: 'Hydraulic system',
    unit: 'Remaining condition margin',
    watch: 'Pressures, flows and temperatures, plus a separate call on the cooler, valve and pump.',
    stat: 'UCI hydraulic rig',
  },
  {
    img: '/brand/power.webp',
    name: 'Power electronics switch',
    unit: 'Life in running minutes',
    watch: 'On state voltage, gate voltage and package temperature of the IGBT module.',
    stat: 'NASA PCoE IGBTs',
  },
];

export default function Components() {
  const root = useRef<HTMLElement>(null);
  const track = useRef<HTMLUListElement>(null);

  useGSAP(
    () => {
      if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
      const mm = gsap.matchMedia();
      // Pinned horizontal flight on wide screens; on phones the cards stack and rise in
      mm.add('(min-width: 1024px)', () => {
        const el = track.current!;
        const distance = () => el.scrollWidth - window.innerWidth + 96;
        const tween = gsap.to(el, {
          x: () => -distance(),
          ease: 'none',
          scrollTrigger: {
            trigger: root.current,
            start: 'top top',
            end: () => `+=${distance()}`,
            pin: true,
            scrub: 0.6,
            invalidateOnRefresh: true,
            anticipatePin: 1,
          },
        });
        // each card banks into view as it crosses the screen
        gsap.utils.toArray<HTMLElement>('.cmp-card', el).forEach((card) => {
          gsap.fromTo(
            card,
            { rotateY: -18, z: -120, opacity: 0.35 },
            {
              rotateY: 0, z: 0, opacity: 1, ease: 'power2.out',
              scrollTrigger: { trigger: card, containerAnimation: tween, start: 'left 100%', end: 'left 45%', scrub: true },
            },
          );
          const img = card.querySelector('.cmp-img');
          if (img) {
            gsap.fromTo(img, { xPercent: -8 }, {
              xPercent: 8, ease: 'none',
              scrollTrigger: { trigger: card, containerAnimation: tween, start: 'left right', end: 'right left', scrub: true },
            });
          }
        });
      });
      mm.add('(max-width: 1023px)', () => {
        gsap.utils.toArray<HTMLElement>('.cmp-card', track.current).forEach((card) => {
          gsap.from(card, { y: 60, opacity: 0, duration: 0.9, ease: 'expo.out', scrollTrigger: { trigger: card, start: 'top 88%', once: true } });
        });
      });
      return () => mm.revert();
    },
    { scope: root },
  );

  return (
    <section ref={root} id="components" aria-labelledby="components-title" className="relative overflow-hidden py-28 lg:flex lg:h-[100svh] lg:flex-col lg:justify-center lg:py-0">
      <div className="wrap">
        <SectionHead id="components-title" title="One console for five aircraft systems.">
          Each component keeps its own model, its own units and its own risk limits. You never pick which one; the
          console routes every file to the right model by itself.
        </SectionHead>
      </div>

      <ul
        ref={track}
        className="mt-12 flex flex-col gap-4 px-4 sm:px-8 lg:mt-14 lg:w-max lg:flex-row lg:gap-6 lg:pl-12 lg:pr-12 lg:[perspective:1400px]"
      >
        {ITEMS.map((it, i) => (
          <li key={it.name} className="cmp-card lg:w-[min(520px,40vw,64vh)] lg:shrink-0 lg:[transform-style:preserve-3d]">
            <Link href="/demo/" className="panel lift group flex h-full flex-col overflow-hidden rounded-2xl">
              <div className="relative aspect-[16/10] overflow-hidden bg-[#0e1013]">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={it.img}
                  alt={`${it.name} model in the AeroSentinel console`}
                  loading="lazy"
                  className="cmp-img zoom-img absolute inset-[-8%] h-[116%] w-[116%] max-w-none object-cover"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-[#0a0e15] via-transparent to-transparent" />
                <span className="hud-label absolute left-4 top-4 rounded-md bg-black/50 px-2 py-1 text-[#a9d3ff]">
                  {String(i + 1).padStart(2, '0')} / 05
                </span>
              </div>
              <div className="flex flex-1 flex-col p-5 sm:p-6">
                <div className="flex items-start justify-between gap-4">
                  <h3 className="heading-6 text-ink">{it.name}</h3>
                  <ArrowUpRight size={18} className="mt-1 shrink-0 text-faint transition-colors duration-300 group-hover:text-accent" aria-hidden="true" />
                </div>
                <p className="caption-4 mt-2 text-accent">{it.unit}</p>
                <p className="body-6 mt-3 text-muted">{it.watch}</p>
                <p className="hud-label mt-auto pt-5">{it.stat}</p>
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
