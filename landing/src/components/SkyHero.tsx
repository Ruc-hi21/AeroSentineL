'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import dynamic from 'next/dynamic';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { useGSAP } from '@gsap/react';
import { finishIntro } from '@/lib/intro';
import { DemoButton } from './ui';

gsap.registerPlugin(ScrollTrigger, useGSAP);

const SkyScene = dynamic(() => import('./SkyScene'), { ssr: false });

// Development review aid: ?introSlow=8 slows the whole shot (the scene reads the same value)
const slow = () =>
  process.env.NODE_ENV !== 'production'
    ? Math.max(1, Number(new URLSearchParams(window.location.search).get('introSlow')) || 1)
    : 1;

type Phase = 'intro' | 'boom' | 'shown';

const KICKER = 'Predictive maintenance for aircraft';

/* The opening and the hero are one shot: it plays on every load (about 3 s),
   then the title rests over the clouds and scrolling dives through them. */
export default function SkyHero() {
  const section = useRef<HTMLElement>(null);
  const scroll = useMemo(() => ({ p: 0 }), []);
  const [phase, setPhase] = useState<Phase>('intro');
  const [skip, setSkip] = useState(false);
  const [active, setActive] = useState(true);
  const timers = useRef<number[]>([]);

  const later = (fn: () => void, ms: number) => {
    timers.current.push(window.setTimeout(fn, ms * slow()));
  };

  const reveal = useCallback(() => {
    setPhase('shown');
    finishIntro();
    document.documentElement.setAttribute('data-intro', 'done');
  }, []);

  const skipNow = useCallback(() => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
    setSkip(true);
    reveal();
  }, [reveal]);

  // Every load starts at the top with the shot; reduced motion goes straight to the title
  useEffect(() => {
    if ('scrollRestoration' in history) history.scrollRestoration = 'manual';
    window.scrollTo(0, 0);
    const html = document.documentElement;
    if (html.getAttribute('data-intro') === 'skip') {
      setSkip(true);
      reveal();
      return;
    }
    html.setAttribute('data-intro', 'play');
    later(skipNow, 6500); // if WebGL never starts, never trap the visitor
    const onKey = (e: KeyboardEvent) => {
      if (['Escape', 'Enter', ' ', 'ArrowDown', 'PageDown'].includes(e.key)) skipNow();
    };
    const onWheel = () => skipNow();
    window.addEventListener('keydown', onKey);
    window.addEventListener('wheel', onWheel, { passive: true, once: true });
    return () => {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('wheel', onWheel);
      timers.current.forEach(clearTimeout);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onBoom = useCallback(() => {
    setPhase('boom');
    later(reveal, 180);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reveal]);

  // Stop rendering the sky once it has scrolled away
  useEffect(() => {
    const el = section.current;
    if (!el) return;
    const io = new IntersectionObserver(([e]) => setActive(e.isIntersecting), { rootMargin: '200px' });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  // The dive: copy lifts away, a second line passes, the clouds whiten into the page
  useGSAP(
    () => {
      ScrollTrigger.create({
        trigger: section.current,
        start: 'top top',
        end: 'bottom bottom',
        scrub: true,
        onUpdate: (self) => {
          scroll.p = self.progress;
        },
      });
      if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
      const tl = gsap.timeline({
        scrollTrigger: { trigger: section.current, start: 'top top', end: 'bottom bottom', scrub: 0.6 },
        defaults: { ease: 'none' },
      });
      tl.to('.sky-copy', { yPercent: -60, scale: 0.92, opacity: 0, filter: 'blur(10px)', duration: 0.32 }, 0)
        .to('.sky-hint', { opacity: 0, duration: 0.08 }, 0)
        .fromTo('.sky-line', { opacity: 0, y: 60, filter: 'blur(10px)' }, { opacity: 1, y: 0, filter: 'blur(0px)', duration: 0.18 }, 0.34)
        .to('.sky-line', { opacity: 0, y: -60, filter: 'blur(10px)', duration: 0.18 }, 0.62)
        .fromTo('.sky-white', { opacity: 0 }, { opacity: 1, duration: 0.16 }, 0.84);
    },
    { scope: section },
  );

  return (
    <section ref={section} id="top" aria-labelledby="sky-title" className="sky-hero relative h-[280vh]" data-phase={phase}>
      <div className="sticky top-0 h-[100svh] overflow-hidden bg-[#2a2440]">
        <div className="sky-canvas absolute inset-0" aria-hidden="true">
          <SkyScene onBoom={onBoom} onReady={() => {}} scroll={scroll} skipIntro={skip} active={active} />
        </div>
        <div className="sky-shaft pointer-events-none absolute inset-0" aria-hidden="true" />
        <div className="sky-vignette pointer-events-none absolute inset-0" aria-hidden="true" />

        {/* Title over the clouds */}
        <div className="sky-copy absolute inset-0 flex flex-col items-center justify-center px-4 text-center">
          <p className="sky-kicker data" aria-label={KICKER}>
            {KICKER.split('').map((ch, i) => (
              <span key={i} style={{ transitionDelay: `${0.25 + i * 0.018}s` }} aria-hidden="true">
                {ch === ' ' ? ' ' : ch}
              </span>
            ))}
          </p>
          <h1 id="sky-title" className="sky-title">
            {'AEROSENTINEL'.split('').map((ch, i) => (
              <span key={i} style={{ transitionDelay: `${0.05 + i * 0.045}s` }}>
                {ch}
              </span>
            ))}
          </h1>
          <p className="sky-sub body-lead">Remaining life, risk and the reason, for every aircraft component.</p>
          <div className="sky-cta mt-8 flex flex-wrap items-center justify-center gap-3">
            <DemoButton />
            <a href="#overview" className="btn btn-lg button-md sky-ghost">
              See how it works
            </a>
          </div>
        </div>

        {/* Passed on the way down */}
        <div className="sky-line pointer-events-none absolute inset-0 flex items-center justify-center px-6 opacity-0">
          <p className="max-w-[880px] text-center text-[clamp(2rem,5vw,4.25rem)] font-semibold leading-[1.05] tracking-[-0.035em] text-white [text-shadow:0_4px_40px_rgb(120_60_20/0.35)]">
            Five aircraft systems.
            <br />
            One forecast for every unit.
          </p>
        </div>

        <div className="sky-hint pointer-events-none absolute inset-x-0 bottom-8 flex flex-col items-center gap-2">
          <span className="caption-4 data tracking-[0.3em] text-white/80">SCROLL TO DESCEND</span>
          <span className="sky-hint-line" />
        </div>

        <div className="sky-white pointer-events-none absolute inset-0 bg-white opacity-0" aria-hidden="true" />
        <div className="sky-flash pointer-events-none absolute inset-0" aria-hidden="true" />

        {phase === 'intro' && (
          <button type="button" className="sky-skip button-sm" onClick={skipNow}>
            Skip intro
          </button>
        )}
      </div>
    </section>
  );
}
