'use client';

import { useRef, useState } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { useGSAP } from '@gsap/react';
import { flight } from '@/lib/flight';
import { DemoButton } from './ui';

gsap.registerPlugin(ScrollTrigger, useGSAP);

/* The fly-through: the section pins while the camera travels the gas path from the fan to the
   exhaust. Station timing matches STATIONS[].at in world/World.tsx. */
const BEATS = [
  {
    id: 'T2', label: 'Fan inlet', value: '+0.2σ', tone: 'Healthy', color: '#42be65', from: 0.2,
    text: 'Clean air at the fan face. The baseline every station behind it is measured against.',
  },
  {
    id: 'T24', label: 'LPC outlet', value: '+1.1σ', tone: 'Degrading', color: '#f1c21b', from: 0.4,
    text: 'The low pressure compressor runs a little hot. On its own, easy to miss.',
  },
  {
    id: 'T30', label: 'HPC outlet', value: '+2.1σ', tone: 'Warning', color: '#ff832b', from: 0.585,
    text: 'Corrected for altitude, Mach and throttle, the creep is real: the compressor is wearing.',
  },
  {
    id: 'T50', label: 'LPT outlet', value: '+2.4σ', tone: 'Warning', color: '#ff832b', from: 0.75,
    text: 'The turbines confirm it. Four stations, one story, read together instead of one gauge at a time.',
  },
] as const;
const VERDICT_AT = 0.92;
const AXIAL_M = 5.4; // fan face to nozzle, for the readout

export default function Dive() {
  const root = useRef<HTMLElement>(null);
  const fill = useRef<HTMLSpanElement>(null);
  const axial = useRef<HTMLSpanElement>(null);
  const [beat, setBeat] = useState(-1);
  const beatRef = useRef(-1);

  useGSAP(
    () => {
      const st = ScrollTrigger.create({
        trigger: root.current,
        start: 'top top',
        end: () => `+=${Math.round(window.innerHeight * 3.8)}`,
        pin: true,
        pinSpacing: true,
        anticipatePin: 1,
        invalidateOnRefresh: true,
        onUpdate: (self) => {
          const p = self.progress;
          flight.dive = p;
          if (fill.current) fill.current.style.transform = `scaleY(${Math.min(1, Math.max(0, (p - 0.15) / 0.75))})`;
          if (axial.current) axial.current.textContent = (Math.min(1, Math.max(0, (p - 0.12) / 0.8)) * AXIAL_M).toFixed(2);
          let b = -1;
          BEATS.forEach((x, i) => {
            if (p >= x.from) b = i;
          });
          if (p >= VERDICT_AT) b = BEATS.length;
          if (b !== beatRef.current) {
            beatRef.current = b;
            setBeat(b);
          }
        },
        onLeaveBack: () => (flight.dive = 0),
        onLeave: () => (flight.dive = 1),
      });
      // the chapter's shading and copy arrive with the scroll, so there is no hard edge as it slides in
      const fade = gsap.fromTo(
        gsap.utils.toArray('.dive-fade', root.current),
        { opacity: 0 },
        { opacity: 1, ease: 'none', scrollTrigger: { trigger: root.current, start: 'top 80%', end: 'top 5%', scrub: true } },
      );
      return () => {
        st.kill();
        fade.scrollTrigger?.kill();
        fade.kill();
      };
    },
    { scope: root },
  );

  return (
    <section ref={root} id="inside" aria-labelledby="inside-title" className="relative h-[100svh] overflow-hidden">
      <div className="dive-vignette dive-fade" aria-hidden="true" />

      {/* HUD, top right */}
      <div className="dive-fade pointer-events-none absolute right-4 top-24 z-10 text-right sm:right-8 lg:right-12 lg:top-28" aria-hidden="true">
        <p className="hud-label">Axial position</p>
        <p className="data text-2xl text-ink sm:text-3xl">
          <span ref={axial}>0.00</span>
          <span className="ml-1 text-base text-faint">m</span>
        </p>
        <p className="hud-label mt-3">Station</p>
        <p className="data text-sm text-accent-strong">{beat >= 0 && beat < BEATS.length ? BEATS[beat].id : beat === BEATS.length ? 'EXIT' : 'INLET'}</p>
      </div>

      <div className="dive-fade wrap relative z-10 flex h-full flex-col justify-end pb-10 lg:justify-center lg:pb-0">
        <div className="relative max-w-[460px]">
          <span className="eyebrow">Inside the engine</span>
          <h2 id="inside-title" className="heading-2 mt-5 text-ink">
            Every sensor, read where it sits.
          </h2>

          <div className="relative mt-8 h-[230px] sm:h-[210px]" aria-live="polite">
            <div className="beat" data-on={beat === -1}>
              <p className="body-lead text-muted">
                Keep scrolling. The camera flies the gas path from the fan to the exhaust and stops at each station
                AeroSentinel reads.
              </p>
            </div>

            {BEATS.map((b, i) => (
              <div key={b.id} className="beat" data-on={beat === i}>
                <p className="flex items-center gap-3">
                  <span className="h-2 w-2 rounded-full" style={{ background: b.color, boxShadow: `0 0 14px 2px ${b.color}` }} />
                  <span className="data title-4 text-ink">{b.id}</span>
                  <span className="body-6 text-muted">{b.label}</span>
                </p>
                <p className="mt-3 flex items-baseline gap-3">
                  <span className="data text-5xl leading-none sm:text-6xl" style={{ color: b.color }}>{b.value}</span>
                  <span className="caption-4 rounded-md px-2 py-0.5" style={{ color: b.color, background: `${b.color}22` }}>
                    {b.tone}
                  </span>
                </p>
                <p className="body-3 mt-4 text-muted">{b.text}</p>
              </div>
            ))}

            <div className="beat" data-on={beat === BEATS.length}>
              <p className="flex items-center gap-3">
                <span className="caption-4 rounded-md bg-warning/15 px-2 py-0.5 text-warning">Warning</span>
                <span className="body-6 text-muted">
                  Sample <span className="data text-ink">Engine 07</span>
                </span>
              </p>
              <p className="mt-3 flex items-baseline gap-3">
                <span className="data text-6xl leading-none text-ink">23</span>
                <span className="body-5 text-muted">cycles left · range 17 to 31</span>
              </p>
              <p className="body-6 mt-4 text-muted">Drivers, ranked: T50, T30, T24. A plan, not a surprise.</p>
              <div className="mt-5">
                <DemoButton size="sm" label="Open Engine 07 in the console" />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* station rail, right edge on desktop */}
      <ol className="dive-fade pointer-events-none absolute bottom-0 right-12 top-0 z-10 my-auto hidden h-[300px] flex-col justify-between lg:flex" aria-hidden="true">
        <span className="absolute right-[3px] top-0 h-full w-px bg-line">
          <span ref={fill} className="absolute inset-0 origin-top bg-gradient-to-b from-healthy via-degrading to-warning" style={{ transform: 'scaleY(0)' }} />
        </span>
        {BEATS.map((b, i) => (
          <li key={b.id} className="rail-tick relative flex items-center gap-3 pr-0 text-faint" data-on={beat >= i} style={{ ['--tone' as string]: b.color }}>
            <span className="data caption-4">{b.id}</span>
            <span className="rail-dot h-[7px] w-[7px] rounded-full bg-line-strong" />
          </li>
        ))}
      </ol>
    </section>
  );
}
