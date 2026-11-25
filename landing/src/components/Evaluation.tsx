'use client';

import { useRef } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { useGSAP } from '@gsap/react';
import { ShieldCheck } from '@phosphor-icons/react';
import { Reveal, SectionHead } from './ui';

gsap.registerPlugin(ScrollTrigger, useGSAP);

type Range = { min: number; max: number; lo: number; hi: number; goal?: number; goalLabel?: string; lowerIsBetter?: boolean };
type Row = { p: string; what: string; result: React.ReactNode; goal?: string; range?: Range };

/** A number that counts up once when it scrolls in. */
function N({ v, d = 0 }: { v: number; d?: number }) {
  return (
    <span className="count" data-v={v} data-d={d}>
      {v.toFixed(d)}
    </span>
  );
}

const ROWS: Row[] = [
  {
    p: 'Remaining life error, RMSE',
    what: 'Typical miss on a turbofan’s remaining life, in engine cycles. Lower is better.',
    goal: 'under 18',
    result: (<><N v={9.6} d={1} /> to <N v={10.7} d={1} /> cycles</>),
    range: { min: 0, max: 20, lo: 9.6, hi: 10.7, goal: 18, goalLabel: 'goal 18', lowerIsBetter: true },
  },
  {
    p: 'Risk band accuracy',
    what: 'Engines placed in the right one of the four risk bands.',
    result: (<><N v={90.3} d={1} /> to <N v={93.1} d={1} />%</>),
    range: { min: 80, max: 100, lo: 90.3, hi: 93.1 },
  },
  {
    p: 'Risk band macro F1',
    what: 'Balance across all four bands, so the rare urgent ones count as much as the common healthy ones.',
    goal: 'above 0.85',
    result: (<><N v={0.82} d={2} /> to <N v={0.89} d={2} /></>),
    range: { min: 0.7, max: 1, lo: 0.82, hi: 0.89, goal: 0.85, goalLabel: 'goal 0.85' },
  },
  {
    p: 'Variance explained, R²',
    what: 'How much of the real spread in remaining life the forecast captures.',
    result: (<><N v={0.82} d={2} /> to <N v={0.93} d={2} /></>),
    range: { min: 0.5, max: 1, lo: 0.815, hi: 0.927 },
  },
  {
    p: 'Component routing',
    what: 'Of 960 files from units the console had never seen: sent to the right model, sent to a wrong one, held back for a person.',
    result: (<><N v={98.9} d={1} />% · <N v={0} />% · <N v={1.1} d={1} />%</>),
  },
  {
    p: 'Unrelated tables rejected',
    what: 'Files that are not from any of the five components are stopped as “not recognised”.',
    result: (<><N v={100} />%</>),
  },
  {
    p: 'Hydraulic part condition',
    what: 'Correct calls on the cooler, the valve and the pump, every load cycle.',
    result: (<><N v={100} />% · <N v={100} />% · <N v={98.0} d={1} />%</>),
  },
  {
    p: 'Scoring speed',
    what: 'Time to score one reading, explanations included, on a laptop.',
    goal: 'under 25 ms',
    result: (<>about <N v={0.1} d={1} /> ms</>),
  },
];

function Bar({ r }: { r: Range }) {
  const pos = (v: number) => ((v - r.min) / (r.max - r.min)) * 100;
  return (
    <div className="relative mt-3 h-6" aria-hidden="true">
      <div className="absolute inset-x-0 top-2.5 h-1 rounded-full bg-raised" />
      <div
        className="range-fill absolute top-1.5 h-3 rounded-sm bg-accent"
        style={{ left: `${pos(r.lo)}%`, width: `${Math.max(pos(r.hi) - pos(r.lo), 1.2)}%` }}
      />
      {r.goal !== undefined && (
        <>
          <div className="absolute -top-0.5 h-7 w-px bg-ink/60" style={{ left: `${pos(r.goal)}%` }} />
          <span className="caption-5 data absolute -top-5 -translate-x-1/2 text-faint" style={{ left: `${pos(r.goal)}%` }}>
            {r.goalLabel}
          </span>
        </>
      )}
    </div>
  );
}

export default function Evaluation() {
  const root = useRef<HTMLDivElement>(null);

  useGSAP(
    () => {
      if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
      gsap.utils.toArray<HTMLElement>('.count').forEach((el) => {
        const v = Number(el.dataset.v);
        const d = Number(el.dataset.d);
        const o = { n: 0 };
        gsap.to(o, {
          n: v,
          duration: 1.6,
          ease: 'expo.out',
          scrollTrigger: { trigger: el, start: 'top 90%', once: true },
          onUpdate: () => {
            el.textContent = o.n.toFixed(d);
          },
        });
      });
      gsap.from('.range-fill', {
        scaleX: 0,
        transformOrigin: 'left center',
        duration: 1.2,
        ease: 'expo.out',
        stagger: 0.08,
        scrollTrigger: { trigger: root.current, start: 'top 75%', once: true },
      });
    },
    { scope: root },
  );

  return (
    <section id="evaluation" aria-labelledby="evaluation-title" className="section">
      <div className="wrap">
        <div className="grid grid-cols-1 items-end gap-8 lg:grid-cols-12">
          <div className="lg:col-span-7">
            <SectionHead id="evaluation-title" title="Measured, not promised.">
              The parameters we track for every forecast, the target we set and what the console achieves today. Each
              result is scored once, at the last reading of every unit.
            </SectionHead>
          </div>
          <Reveal className="lg:col-span-5" delay={0.1}>
            <div className="flex gap-4 rounded-2xl border border-line bg-surface p-6">
              <ShieldCheck size={28} weight="duotone" className="shrink-0 text-healthy" aria-hidden="true" />
              <p className="body-6 text-muted">
                <span className="body-4 block text-ink">No truly urgent engine was ever called Normal.</span>
                Every risk band miss across the turbofan results landed in the neighbouring band, never two bands away.
              </p>
            </div>
          </Reveal>
        </div>

        <div ref={root} className="mt-16 overflow-hidden rounded-2xl border border-line">
          <table className="w-full border-collapse text-left">
            <caption className="sr-only">Evaluation parameters, targets and results</caption>
            <thead className="hidden bg-surface md:table-header-group">
              <tr className="border-b border-line">
                <th scope="col" className="caption-3 px-6 py-4 text-faint">Parameter</th>
                <th scope="col" className="caption-3 px-6 py-4 text-faint">What it tells you</th>
                <th scope="col" className="caption-3 px-6 py-4 text-faint">Target</th>
                <th scope="col" className="caption-3 w-[30%] px-6 py-4 text-faint">Result</th>
              </tr>
            </thead>
            <tbody>
              {ROWS.map((r) => (
                <tr key={r.p} className="grid grid-cols-1 gap-2 border-b border-line px-4 py-6 last:border-b-0 md:table-row md:px-0 md:py-0">
                  <th scope="row" className="title-3 align-top text-ink md:px-6 md:py-6">{r.p}</th>
                  <td className="body-6 align-top text-muted md:px-6 md:py-6">{r.what}</td>
                  <td className="caption-2 data whitespace-nowrap align-top text-faint md:px-6 md:py-6">
                    <span className="md:hidden">Target: </span>
                    {r.goal ?? '·'}
                  </td>
                  <td className="align-top md:px-6 md:py-6">
                    <span className="data text-lg leading-7 text-ink">{r.result}</span>
                    {r.range && <Bar r={r.range} />}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="caption-5 mt-4 max-w-[720px] text-faint">
          Turbofan figures span the four engine fleets the console supports. Battery, gearbox and power electronics
          forecasts are newer and shown in the console as indicative.
        </p>
      </div>
    </section>
  );
}
