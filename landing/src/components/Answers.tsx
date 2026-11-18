'use client';

import { useState } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';
import { Clock, Gauge, Waveform, Path } from '@phosphor-icons/react';
import { EASE } from '@/lib/site';
import { Reveal, SectionHead } from './ui';

const QUESTIONS = [
  {
    id: 'life',
    icon: Clock,
    q: 'How long has it got?',
    a: 'Remaining useful life in the component’s own units, with an 80% range and the window it is likely to reach end of life in.',
  },
  {
    id: 'risk',
    icon: Gauge,
    q: 'How worried should I be?',
    a: 'One of four risk bands, from Normal to Failure likely, with the probability of each. Always written as a word, never colour alone.',
  },
  {
    id: 'where',
    icon: Waveform,
    q: 'What is changing, and where?',
    a: 'A health score against healthy units and the drift of every sensor, shaded part by part on the component’s schematic.',
  },
  {
    id: 'why',
    icon: Path,
    q: 'Why does the model think so?',
    a: 'The sensors that pushed this forecast up or down, ranked, so an engineer can check the call against the readings.',
  },
] as const;
type Id = (typeof QUESTIONS)[number]['id'];

function LifePanel() {
  const scale = 125;
  const bands = [
    { to: 15, c: 'bg-critical', l: 'Critical' },
    { to: 30, c: 'bg-warning', l: 'Warning' },
    { to: 60, c: 'bg-degrading', l: 'Degrading' },
    { to: 125, c: 'bg-healthy', l: 'Healthy' },
  ];
  let from = 0;
  return (
    <div>
      <p className="caption-2 text-faint">Remaining useful life</p>
      <p className="mt-2 flex items-baseline gap-2">
        <span className="data text-6xl leading-none text-ink">23</span>
        <span className="body-5 text-muted">engine cycles</span>
      </p>
      <p className="body-6 mt-2 text-muted">
        80% range <span className="data text-ink">17 to 31</span> · end of life between cycles <span className="data text-ink">312 and 326</span>
      </p>
      <div className="relative mt-10">
        <div className="flex h-2 overflow-hidden rounded-full">
          {bands.map((b) => {
            const w = ((b.to - from) / scale) * 100;
            from = b.to;
            return <span key={b.l} className={`${b.c} opacity-70`} style={{ width: `${w}%` }} />;
          })}
        </div>
        <div className="absolute -top-2 h-6 rounded-sm border border-ink/80" style={{ left: `${(17 / scale) * 100}%`, width: `${(14 / scale) * 100}%` }} aria-hidden="true" />
        <div className="absolute -top-4 h-10 w-0.5 bg-ink" style={{ left: `${(23 / scale) * 100}%` }} aria-hidden="true" />
        <div className="mt-3 flex justify-between caption-5 text-faint data">
          <span>0</span><span>30</span><span>60</span><span>125+</span>
        </div>
      </div>
    </div>
  );
}

function RiskPanel() {
  const rows = [
    { l: 'Normal', p: 4, c: 'bg-healthy' },
    { l: 'At risk', p: 21, c: 'bg-degrading' },
    { l: 'High risk', p: 61, c: 'bg-warning' },
    { l: 'Failure likely', p: 14, c: 'bg-critical' },
  ];
  return (
    <div>
      <div className="flex items-center justify-between">
        <p className="caption-2 text-faint">Risk band</p>
        <span className="caption-4 rounded-md bg-warning/15 px-2 py-0.5 text-warning">Warning · High risk</span>
      </div>
      <ul className="mt-6 space-y-4">
        {rows.map((r, i) => (
          <li key={r.l} className="grid grid-cols-[112px_1fr_48px] items-center gap-4">
            <span className="body-6 text-muted">{r.l}</span>
            <span className="h-2 overflow-hidden rounded-full bg-raised">
              <motion.span
                className={`block h-full rounded-full ${r.c}`}
                initial={{ scaleX: 0 }}
                animate={{ scaleX: r.p / 100 }}
                style={{ transformOrigin: 'left' }}
                transition={{ duration: 0.8, ease: EASE, delay: 0.1 + i * 0.06 }}
              />
            </span>
            <span className="data body-6 text-right text-ink">{r.p}%</span>
          </li>
        ))}
      </ul>
      <div className="mt-8 grid grid-cols-5 gap-2">
        {[
          ['Critical', 'text-critical'],
          ['Warning', 'text-warning'],
          ['Degrading', 'text-degrading'],
          ['Healthy', 'text-healthy'],
          ['Too short', 'text-muted'],
        ].map(([l, c]) => (
          <span key={l} className={`caption-4 rounded-md border border-line px-2 py-1 text-center ${c} ${l === 'Warning' ? 'border-warning/50 bg-warning/10' : ''}`}>
            {l}
          </span>
        ))}
      </div>
    </div>
  );
}

function WherePanel() {
  const parts = [
    { p: 'Fan', d: 0.2 },
    { p: 'LPC', d: 1.1 },
    { p: 'HPC', d: 2.1 },
    { p: 'Combustor', d: 0.9 },
    { p: 'HPT', d: 1.6 },
    { p: 'LPT', d: 2.4 },
  ];
  const tone = (d: number) => (d >= 2 ? '#c24e00' : d >= 1 ? '#9a7200' : '#198038');
  return (
    <div>
      <div className="flex items-center justify-between">
        <p className="caption-2 text-faint">Sensor drift by part, gas path</p>
        <p className="caption-2 text-faint">Health score <span className="data text-ink">0.41</span></p>
      </div>
      {/* schematic strip: parts in gas path order, shaded by drift */}
      <div className="mt-6 flex h-20 items-center gap-1">
        {parts.map((x, i) => (
          <motion.div
            key={x.p}
            className="relative flex h-full flex-1 items-end justify-center rounded-md border border-line pb-2"
            style={{ height: `${56 + (i === 0 ? 24 : i < 3 ? 12 - i * 4 : 0)}%` }}
            initial={{ backgroundColor: 'rgba(31,31,31,1)' }}
            animate={{ backgroundColor: `${tone(x.d)}${x.d >= 2 ? '33' : x.d >= 1 ? '26' : '1a'}` }}
            transition={{ duration: 0.8, ease: EASE, delay: i * 0.06 }}
          >
            <span className="caption-5 text-muted">{x.p}</span>
          </motion.div>
        ))}
      </div>
      <ul className="mt-6 space-y-2">
        {[
          { s: 'T50', n: 'LPT outlet temperature', d: 2.4 },
          { s: 'T30', n: 'HPC outlet temperature', d: 2.1 },
          { s: 'Ps30', n: 'HPC static pressure', d: 1.8 },
        ].map((r) => (
          <li key={r.s} className="flex items-center justify-between border-b border-line py-2">
            <span className="body-6 text-muted">
              <span className="data mr-2 text-ink">{r.s}</span>
              {r.n}
            </span>
            <span className="data body-6" style={{ color: tone(r.d) }}>+{r.d.toFixed(1)}σ</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function WhyPanel() {
  const rows = [
    { s: 'T50 · LPT outlet temp', v: -7.8 },
    { s: 'T30 · HPC outlet temp', v: -5.9 },
    { s: 'Ps30 · HPC pressure', v: -4.2 },
    { s: 'Nc · core speed', v: -2.1 },
    { s: 'phi · fuel flow ratio', v: 1.6 },
  ];
  const max = 8;
  return (
    <div>
      <p className="caption-2 text-faint">What moved the forecast, in cycles</p>
      <ul className="mt-6 space-y-3">
        {rows.map((r, i) => {
          const w = (Math.abs(r.v) / max) * 50;
          return (
            <li key={r.s} className="grid grid-cols-[1fr_1.4fr_44px] items-center gap-4 sm:grid-cols-[176px_1fr_48px]">
              <span className="body-6 truncate text-muted">{r.s}</span>
              <span className="relative h-3">
                <span className="absolute inset-y-[-4px] left-1/2 w-px bg-line-strong" aria-hidden="true" />
                <motion.span
                  className={`absolute top-0 h-3 rounded-sm ${r.v < 0 ? 'bg-warning/80' : 'bg-accent/80'}`}
                  style={{ [r.v < 0 ? 'right' : 'left']: '50%', width: `${w}%`, transformOrigin: r.v < 0 ? 'right' : 'left' }}
                  initial={{ scaleX: 0 }}
                  animate={{ scaleX: 1 }}
                  transition={{ duration: 0.7, ease: EASE, delay: 0.1 + i * 0.06 }}
                />
              </span>
              <span className="data body-6 text-right text-ink">{r.v > 0 ? '+' : ''}{r.v.toFixed(1)}</span>
            </li>
          );
        })}
      </ul>
      <div className="mt-6 flex gap-6 caption-5 text-faint">
        <span className="inline-flex items-center gap-2"><span className="h-2 w-2 rounded-sm bg-warning/80" />shortens life</span>
        <span className="inline-flex items-center gap-2"><span className="h-2 w-2 rounded-sm bg-accent/80" />extends life</span>
      </div>
    </div>
  );
}

const PANELS: Record<Id, () => React.ReactElement> = { life: LifePanel, risk: RiskPanel, where: WherePanel, why: WhyPanel };

export default function Answers() {
  const [active, setActive] = useState<Id>('life');
  const reduce = useReducedMotion();
  const Panel = PANELS[active];

  return (
    <section id="answers" aria-labelledby="answers-title" className="section border-t border-line">
      <div className="wrap">
        <SectionHead id="answers-title" title="Four answers for every unit in your fleet.">
          Upload once and every engine, cell, gearbox, hydraulic session or power switch gets the same four answers, on
          one screen, in plain words.
        </SectionHead>

        <div className="mt-16 grid grid-cols-1 gap-8 lg:grid-cols-12 lg:gap-12">
          <Reveal className="lg:col-span-5">
            <div role="tablist" aria-label="The four answers" aria-orientation="vertical" className="flex flex-col gap-2">
              {QUESTIONS.map((q) => {
                const on = q.id === active;
                const Icon = q.icon;
                return (
                  <button
                    key={q.id}
                    role="tab"
                    id={`tab-${q.id}`}
                    aria-selected={on}
                    aria-controls="answer-panel"
                    onClick={() => setActive(q.id)}
                    className={`group relative rounded-xl border p-4 text-left transition-[border-color,background-color] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] active:scale-[0.99] ${
                      on ? 'border-line-strong bg-surface' : 'border-transparent hover:bg-surface/60'
                    }`}
                  >
                    <span className="flex items-center gap-3">
                      <Icon size={20} weight={on ? 'fill' : 'regular'} className={on ? 'text-accent' : 'text-faint'} aria-hidden="true" />
                      <span className={`title-2 ${on ? 'text-ink' : 'text-muted group-hover:text-ink'}`}>{q.q}</span>
                    </span>
                    <span
                      className="grid transition-[grid-template-rows,opacity] duration-500 ease-[cubic-bezier(0.22,1,0.36,1)]"
                      style={{ gridTemplateRows: on ? '1fr' : '0fr', opacity: on ? 1 : 0 }}
                    >
                      <span className="overflow-hidden">
                        <span className="body-6 block pl-8 pt-2 text-muted">{q.a}</span>
                      </span>
                    </span>
                  </button>
                );
              })}
            </div>
          </Reveal>

          <Reveal className="lg:col-span-7" delay={0.1}>
            <div
              id="answer-panel"
              role="tabpanel"
              aria-labelledby={`tab-${active}`}
              className="relative min-h-[380px] overflow-hidden rounded-2xl border border-line bg-surface p-6 sm:p-8"
            >
              <div className="mb-8 flex items-center justify-between border-b border-line pb-4">
                <span className="title-4 text-ink">Engine 07</span>
                <span className="caption-5 text-faint">Sample unit, illustrative values</span>
              </div>
              <AnimatePresence mode="wait" initial={false}>
                <motion.div
                  key={active}
                  initial={reduce ? { opacity: 0 } : { opacity: 0, y: 8, filter: 'blur(4px)' }}
                  animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                  exit={reduce ? { opacity: 0 } : { opacity: 0, y: -4, filter: 'blur(4px)', transition: { duration: 0.15 } }}
                  transition={{ duration: 0.35, ease: EASE }}
                >
                  <Panel />
                </motion.div>
              </AnimatePresence>
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
