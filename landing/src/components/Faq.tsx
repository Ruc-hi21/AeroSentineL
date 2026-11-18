'use client';

import { useState } from 'react';
import { Plus } from '@phosphor-icons/react';
import { Reveal, SectionHead } from './ui';

const FAQ = [
  {
    q: 'Is AeroSentinel a certified airworthiness tool?',
    a: 'No. It is decision support. It does not make airworthiness determinations, it is not for in flight safety decisions and it does not replace certified maintenance procedures. Its forecasts inform an engineer’s review; they never trigger work on their own.',
  },
  {
    q: 'Which components can it read?',
    a: 'Turbofan engines, lithium ion battery cells, engine gearboxes, hydraulic systems and power electronics switches. Anything else is rejected rather than scored by the nearest model.',
  },
  {
    q: 'What file do I need?',
    a: 'A table of numeric sensor readings per unit over time, as a CSV with a header row. Column names do not have to match anything; the console reads the shape of the data. Files up to 4 GB are accepted.',
  },
  {
    q: 'What happens when it does not recognise my data?',
    a: 'Below 80% confidence it stops with “not recognised” and shows you why. You can still choose a model by hand from the data check page if you know what the file is.',
  },
  {
    q: 'How does it handle different flight and operating conditions?',
    a: 'Each reading is mapped to its value at a reference condition, so altitude, Mach, throttle, temperature or load do not pass for wear. Readings from a condition the model has never met are flagged rather than trusted.',
  },
  {
    q: 'Can I see why it made a forecast?',
    a: 'Yes. Every remaining life and risk call lists the sensors that pushed it up or down, ranked, next to each sensor’s own drift so you can see where the model and the measurements agree.',
  },
  {
    q: 'Can I take the results into our own systems?',
    a: 'Yes. Unit results and reading history export as CSV, and the full result (component, recognition, model, conditions and timings) as JSON.',
  },
  {
    q: 'Do I need an account to try it?',
    a: 'No. The live demo opens with sample engines, cells, gearboxes, hydraulic sessions and power switches already loaded. Sign in when you want to work with your own files.',
  },
];

export default function Faq() {
  const [open, setOpen] = useState<number | null>(0);
  return (
    <section id="faq" aria-labelledby="faq-title" className="section border-t border-line">
      <div className="wrap grid grid-cols-1 gap-12 lg:grid-cols-12">
        <div className="lg:col-span-4">
          <SectionHead id="faq-title" title="Questions engineers ask first.">
            Something else on your mind? Open the demo and try it on the samples.
          </SectionHead>
        </div>
        <Reveal className="lg:col-span-8">
          <ul className="border-t border-line">
            {FAQ.map((f, i) => {
              const on = open === i;
              return (
                <li key={f.q} className="border-b border-line">
                  <h3>
                    <button
                      type="button"
                      aria-expanded={on}
                      aria-controls={`faq-${i}`}
                      id={`faq-q-${i}`}
                      onClick={() => setOpen(on ? null : i)}
                      className="flex w-full items-center justify-between gap-6 rounded-lg py-6 text-left"
                    >
                      <span className={`title-2 transition-colors duration-300 ${on ? 'text-ink' : 'text-muted hover:text-ink'}`}>{f.q}</span>
                      <Plus
                        size={18}
                        className="shrink-0 text-faint transition-transform duration-500 ease-[cubic-bezier(0.22,1,0.36,1)]"
                        style={{ transform: on ? 'rotate(45deg)' : 'none' }}
                        aria-hidden="true"
                      />
                    </button>
                  </h3>
                  <div
                    id={`faq-${i}`}
                    role="region"
                    aria-labelledby={`faq-q-${i}`}
                    className="grid transition-[grid-template-rows,opacity] duration-500 ease-[cubic-bezier(0.22,1,0.36,1)]"
                    style={{ gridTemplateRows: on ? '1fr' : '0fr', opacity: on ? 1 : 0 }}
                  >
                    <div className="overflow-hidden">
                      <p className="body-3 max-w-[640px] pb-6 text-muted">{f.a}</p>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        </Reveal>
      </div>
    </section>
  );
}
