'use client';

import { useRef } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { useGSAP } from '@gsap/react';
import { Reveal, SectionHead } from './ui';

gsap.registerPlugin(ScrollTrigger, useGSAP);

// Illustrative drift of one sensor over a unit's life (deterministic noise)
const W = 560, H = 320, PAD_L = 40, PAD_R = 16, PAD_T = 24, PAD_B = 40;
const LIFE = 260, FAIL = 236;
function drift(c: number) {
  const base = 0.12 + 0.88 * Math.pow(c / FAIL, 3.2);
  const noise = Math.sin(c * 0.23) * 0.018 + Math.sin(c * 0.071 + 1.3) * 0.022 + Math.sin(c * 0.53 + 0.4) * 0.008;
  return Math.min(1.05, base + noise);
}
const x = (c: number) => PAD_L + (c / LIFE) * (W - PAD_L - PAD_R);
const y = (v: number) => PAD_T + (1 - v) * (H - PAD_T - PAD_B);
const PATH = Array.from({ length: FAIL + 1 }, (_, c) => `${c === 0 ? 'M' : 'L'}${x(c).toFixed(1)} ${y(drift(c)).toFixed(1)}`).join(' ');
const CHECKS = [100, 200];
const FLAG = FAIL - 30;

const POINTS = [
  { k: 'Too early', v: 'A part with half its life left goes in the bin because the calendar said so.' },
  { k: 'Too late', v: 'Wear that started after the last check turns into an unplanned removal and an aircraft on the ground.' },
  { k: 'Signal buried', v: 'Altitude, load and temperature move the readings as much as wear does, so the trend hides in plain sight.' },
];

export default function Problem() {
  const root = useRef<HTMLDivElement>(null);

  useGSAP(
    () => {
      const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      const line = root.current!.querySelector<SVGPathElement>('.drift-line')!;
      const len = line.getTotalLength();
      if (reduce) return;
      gsap.set(line, { strokeDasharray: len, strokeDashoffset: len });
      gsap.set('.flag-zone', { scaleX: 0, transformOrigin: 'left center' });
      gsap.set('.late-mark, .flag-label, .fail-mark', { opacity: 0, y: 6 });
      const tl = gsap.timeline({
        scrollTrigger: { trigger: root.current, start: 'top 70%', once: true },
        defaults: { ease: 'expo.out' },
      });
      tl.to(line, { strokeDashoffset: 0, duration: 2.2, ease: 'power2.inOut' })
        .to('.flag-zone', { scaleX: 1, duration: 0.9 }, '-=0.7')
        .to('.flag-label', { opacity: 1, y: 0, duration: 0.6 }, '-=0.5')
        .to('.fail-mark', { opacity: 1, y: 0, duration: 0.6 }, '-=0.3')
        .to('.late-mark', { opacity: 1, y: 0, duration: 0.6 }, '-=0.4');
    },
    { scope: root },
  );

  return (
    <section id="problem" aria-labelledby="problem-title" className="section border-t border-line">
      <div className="wrap grid grid-cols-1 items-center gap-16 lg:grid-cols-12">
        <div className="lg:col-span-5">
          <SectionHead id="problem-title" title="Fixed intervals miss the failures that happen between them.">
            Engines, battery cells, gearboxes, hydraulics and power electronics rarely fail without warning. The signs
            are spread across many sensors and look different on every component. A maintenance calendar ignores all
            of it.
          </SectionHead>
          <ul className="mt-10 border-t border-line">
            {POINTS.map((p, i) => (
              <Reveal as="li" key={p.k} delay={0.08 * i} className="grid grid-cols-[120px_1fr] gap-4 border-b border-line py-4">
                <span className="title-4 text-ink">{p.k}</span>
                <span className="body-6 text-muted">{p.v}</span>
              </Reveal>
            ))}
          </ul>
        </div>

        <Reveal className="lg:col-span-7" delay={0.1}>
          <div ref={root} className="rounded-2xl border border-line bg-surface p-4 sm:p-6">
            <div className="flex flex-wrap items-center justify-between gap-2 px-2 pb-4">
              <span className="title-4 text-ink">HPC outlet temperature, drift from healthy</span>
              <span className="caption-5 text-faint">Illustrative unit</span>
            </div>
            <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label="Sensor drift rises slowly then sharply. Scheduled checks at cycle 100 and 200 see little; the unit fails at cycle 236. AeroSentinel flags it 30 cycles before failure.">
              {/* bands */}
              {[
                { from: 0.62, to: 1.1, c: '#da1e28', o: 0.05 },
                { from: 0.4, to: 0.62, c: '#ff832b', o: 0.06 },
              ].map((b) => (
                <rect key={b.c} x={PAD_L} width={W - PAD_L - PAD_R} y={y(Math.min(b.to, 1.05))} height={y(b.from) - y(Math.min(b.to, 1.05))} fill={b.c} opacity={b.o} />
              ))}
              {/* grid */}
              {[0, 0.25, 0.5, 0.75, 1].map((v) => (
                <line key={v} x1={PAD_L} x2={W - PAD_R} y1={y(v)} y2={y(v)} stroke="#e4e4e7" strokeWidth={1} />
              ))}
              {[0, 50, 100, 150, 200, 250].map((c) => (
                <text key={c} x={x(c)} y={H - 16} fill="#6b6b74" fontSize={11} textAnchor="middle" fontFamily="var(--font-geist-mono)">{c}</text>
              ))}
              <text x={W - PAD_R} y={H - 2} fill="#6b6b74" fontSize={11} textAnchor="end">cycles</text>
              <text x={PAD_L - 8} y={y(1) + 4} fill="#6b6b74" fontSize={11} textAnchor="end" fontFamily="var(--font-geist-mono)">3σ</text>
              <text x={PAD_L - 8} y={y(0) + 4} fill="#6b6b74" fontSize={11} textAnchor="end" fontFamily="var(--font-geist-mono)">0</text>

              {/* AeroSentinel flag window */}
              <rect className="flag-zone" x={x(FLAG)} y={PAD_T} width={x(FAIL) - x(FLAG)} height={H - PAD_T - PAD_B} fill="#0b6fe0" opacity={0.1} />
              <line x1={x(FLAG)} x2={x(FLAG)} y1={PAD_T} y2={H - PAD_B} stroke="#0b6fe0" strokeWidth={1.5} className="flag-label" />
              <g className="flag-label">
                <rect x={x(FLAG) - 158} y={PAD_T + 6} width={150} height={40} rx={6} fill="#ffffff" stroke="#0b6fe0" strokeOpacity={0.6} />
                <text x={x(FLAG) - 148} y={PAD_T + 22} fill="#0b6fe0" fontSize={11} fontWeight={600}>AeroSentinel flags it</text>
                <text x={x(FLAG) - 148} y={PAD_T + 38} fill="#52525b" fontSize={11}>30 cycles before failure</text>
              </g>

              {/* scheduled checks */}
              {CHECKS.map((c) => (
                <g key={c}>
                  <line x1={x(c)} x2={x(c)} y1={PAD_T} y2={H - PAD_B} stroke="#52525b" strokeDasharray="3 4" strokeWidth={1} />
                  <text x={x(c) + 6} y={H - PAD_B - 8} fill="#52525b" fontSize={11}>Scheduled check</text>
                </g>
              ))}

              <path className="drift-line" d={PATH} fill="none" stroke="#0a0a0a" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />

              <g className="fail-mark">
                <circle cx={x(FAIL)} cy={y(drift(FAIL))} r={5} fill="#da1e28" />
                <text x={x(FAIL) + 4} y={y(drift(FAIL)) - 12} fill="#da1e28" fontSize={11} fontWeight={600} textAnchor="middle">Failure</text>
              </g>
              <g className="late-mark">
                <text x={W - PAD_R - 4} y={y(0.3)} fill="#52525b" fontSize={11} textAnchor="end">Next check, cycle 300:</text>
                <text x={W - PAD_R - 4} y={y(0.3) + 16} fill="#52525b" fontSize={11} textAnchor="end">too late</text>
              </g>
            </svg>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
