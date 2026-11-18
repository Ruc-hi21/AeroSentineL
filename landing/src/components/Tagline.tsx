'use client';

import { useRef } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { useGSAP } from '@gsap/react';

gsap.registerPlugin(ScrollTrigger, useGSAP);

const LINES = ['Every unit gets a number, a risk band', 'and a reason. The next removal becomes', 'a plan instead of a surprise.'];

export default function Tagline() {
  const root = useRef<HTMLElement>(null);

  useGSAP(
    () => {
      const words = gsap.utils.toArray<HTMLElement>('.tw', root.current);
      const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      if (reduce) {
        words.forEach((w) => w.classList.add('on'));
        return;
      }
      // Words activate one at a time as they cross the trigger line (GSAP throttles to rAF)
      ScrollTrigger.create({
        trigger: root.current,
        start: 'top 65%',
        end: 'bottom 55%',
        onUpdate: (self) => {
          const n = Math.round(self.progress * words.length);
          words.forEach((w, i) => w.classList.toggle('on', i < n));
        },
        onLeave: () => words.forEach((w) => w.classList.add('on')),
      });
    },
    { scope: root },
  );

  const words = LINES.join(' ').split(' ');
  return (
    <section ref={root} aria-label="What AeroSentinel changes" className="section border-t border-line">
      <div className="wrap">
        <p className="heading-1 mx-auto max-w-[920px] text-center [text-wrap:balance]">
          {words.map((w, i) => (
            <span key={i} className="tw">
              {w}{i < words.length - 1 ? ' ' : ''}
            </span>
          ))}
        </p>
      </div>
    </section>
  );
}
