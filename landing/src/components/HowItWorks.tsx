'use client';

import { useRef } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { useGSAP } from '@gsap/react';
import { FileArrowUp, Cpu, ListChecks, HandPalm } from '@phosphor-icons/react';
import { SectionHead } from './ui';

gsap.registerPlugin(ScrollTrigger, useGSAP);

const STEPS = [
  {
    icon: FileArrowUp,
    t: 'Upload a sensor file',
    d: 'Drop a CSV of readings per unit over time, from any of the five components. Logs up to 4 GB are fine.',
    tag: 'CSV · any column names',
  },
  {
    icon: Cpu,
    t: 'AeroSentinel reads it',
    d: 'It recognises the component from the shape of the data, never from column names, then removes the effect of altitude, load and temperature on every reading.',
    tag: 'Recognise · correct · score',
  },
  {
    icon: ListChecks,
    t: 'Act on the result',
    d: 'Remaining life, risk band, drifting sensors and the reasons for every unit, with a suggested next step. Export to CSV or JSON.',
    tag: 'About 0.1 ms per reading',
  },
];

export default function HowItWorks() {
  const root = useRef<HTMLDivElement>(null);

  useGSAP(
    () => {
      if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
      const tl = gsap.timeline({ scrollTrigger: { trigger: root.current, start: 'top 72%', once: true } });
      tl.from('.track-fill', { scaleX: 0, scaleY: 0, duration: 1.4, ease: 'power3.inOut' })
        .from('.step', { opacity: 0, y: 32, duration: 0.8, stagger: 0.12, ease: 'expo.out' }, 0.1)
        .from('.branch', { opacity: 0, y: 12, duration: 0.6, ease: 'expo.out' }, 0.9);
    },
    { scope: root },
  );

  return (
    <section id="how" aria-labelledby="how-title" className="section border-t border-line">
      <div className="blueprint absolute inset-0 [mask-image:linear-gradient(to_bottom,transparent,black_30%,black_70%,transparent)]" aria-hidden="true" />
      <div className="wrap relative">
        <SectionHead id="how-title" title="From a sensor file to a decision in three steps.">
          No setup and no mapping of columns. The console works out what it is looking at, and stops if it is not sure.
        </SectionHead>

        <div ref={root} className="relative mt-16">
          {/* track: horizontal on desktop, vertical on mobile */}
          <div className="absolute left-[27px] top-0 h-full w-px bg-line lg:left-0 lg:top-[27px] lg:h-px lg:w-full" aria-hidden="true">
            <div className="track-fill absolute inset-0 origin-top bg-accent/60 lg:origin-left" />
            <span className="pulse-rail absolute inset-0"><span className="absolute -left-[3.5px] -top-1 h-2 w-2 rounded-full bg-accent shadow-[0_0_12px_2px_rgb(63_162_255/0.6)]" /></span>
          </div>

          <ol className="relative grid grid-cols-1 gap-12 lg:grid-cols-3 lg:gap-8">
            {STEPS.map((s, i) => {
              const Icon = s.icon;
              return (
                <li key={s.t} className="step relative pl-20 lg:pl-0 lg:pt-20">
                  <span className="absolute left-0 top-0 grid h-14 w-14 place-items-center rounded-xl border border-line-strong bg-surface">
                    <Icon size={24} className="text-accent" aria-hidden="true" />
                  </span>
                  <span className="caption-4 data text-faint">Step {i + 1}</span>
                  <h3 className="heading-6 mt-2 text-ink">{s.t}</h3>
                  <p className="body-6 mt-3 max-w-[340px] text-muted">{s.d}</p>
                  <span className="caption-4 mt-4 inline-block rounded-md border border-line bg-base px-2 py-1 text-muted">{s.tag}</span>

                  {i === 1 && (
                    <div className="branch mt-6 flex max-w-[340px] items-start gap-3 rounded-xl border border-line bg-surface p-4">
                      <HandPalm size={20} className="mt-0.5 shrink-0 text-degrading" aria-hidden="true" />
                      <p className="body-6 text-muted">
                        <span className="text-ink">Less than 80% sure?</span> It stops with “not recognised” and hands the
                        file to a person, so data never reaches a model it does not belong to.
                      </p>
                    </div>
                  )}
                </li>
              );
            })}
          </ol>
        </div>
      </div>
    </section>
  );
}
