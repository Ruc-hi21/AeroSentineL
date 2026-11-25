'use client';

import { useEffect, useRef } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { onIntroDone } from '@/lib/flight';

gsap.registerPlugin(ScrollTrigger);

/** A flight-level tape on the left edge: the page is a climb from the ground to cruise. */
export default function Altimeter() {
  const root = useRef<HTMLDivElement>(null);
  const tape = useRef<HTMLDivElement>(null);
  const fl = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const off = onIntroDone(() => root.current?.setAttribute('data-on', 'true'));
    const st = ScrollTrigger.create({
      start: 0,
      end: 'max',
      onUpdate: (s) => {
        const level = Math.round(s.progress * 410);
        if (fl.current) fl.current.textContent = String(level).padStart(3, '0');
        if (tape.current) tape.current.style.backgroundPositionY = `${(s.progress * 1200).toFixed(1)}px`;
      },
    });
    return () => {
      off();
      st.kill();
    };
  }, []);

  return (
    <div
      ref={root}
      className="pointer-events-none fixed left-5 top-1/2 z-20 hidden -translate-y-1/2 flex-col items-center gap-3 opacity-0 transition-opacity duration-1000 data-[on=true]:opacity-100 xl:flex"
      aria-hidden="true"
    >
      <span className="hud-label">ALT</span>
      <div className="relative h-[180px] w-3 [mask-image:linear-gradient(to_bottom,transparent,black_25%,black_75%,transparent)]">
        <div ref={tape} className="alt-tape absolute inset-0" />
        <span className="absolute left-[-6px] top-1/2 h-px w-6 -translate-y-1/2 bg-accent shadow-[0_0_8px_1px_rgb(63_162_255/0.8)]" />
      </div>
      <span className="data text-[11px] text-ink">
        FL<span ref={fl}>000</span>
      </span>
    </div>
  );
}
