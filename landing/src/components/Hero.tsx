'use client';

import { Fragment, useEffect, useRef } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { useGSAP } from '@gsap/react';
import { flight, onBoom } from '@/lib/flight';
import { DemoButton } from './ui';

gsap.registerPlugin(ScrollTrigger, useGSAP);

const LINES = [['Know', 'which', 'part'], ['needs', 'attention', 'next,'], ['and', 'why.']];
const WORDMARK = 'AEROSENTINEL'.split('');

/** Small live readouts: they drift like real instruments, written straight to the DOM. */
function useTelemetry(root: React.RefObject<HTMLElement | null>) {
  useEffect(() => {
    const el = root.current;
    if (!el || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const n1 = el.querySelector<HTMLElement>('[data-t="n1"]');
    const egt = el.querySelector<HTMLElement>('[data-t="egt"]');
    const ff = el.querySelector<HTMLElement>('[data-t="ff"]');
    let t = 0;
    const id = window.setInterval(() => {
      t += 0.15;
      if (n1) n1.textContent = (92.4 + Math.sin(t * 0.9) * 0.6 + Math.sin(t * 2.3) * 0.15).toFixed(1);
      if (egt) egt.textContent = String(Math.round(642 + Math.sin(t * 0.7) * 4 + Math.sin(t * 3.1) * 1.5));
      if (ff) ff.textContent = (2.71 + Math.sin(t * 0.5) * 0.04).toFixed(2);
    }, 150);
    return () => window.clearInterval(id);
  }, [root]);
}

export default function Hero() {
  const section = useRef<HTMLElement>(null);
  useTelemetry(section);

  useGSAP(
    () => {
      ScrollTrigger.create({
        trigger: section.current,
        start: 'top top',
        end: 'bottom top',
        onUpdate: (self) => (flight.hero = self.progress),
      });

      const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      const q = gsap.utils.selector(section);
      if (reduce) {
        gsap.set(q('.h-in, .wm > span, .wordmark span'), { opacity: 1, y: 0, clearProps: 'filter' });
        return;
      }

      // Hidden until the sonic boom, then everything arrives out of the shockwave
      gsap.set(q('.wm > span'), { yPercent: 115 });
      gsap.set(q('.h-in'), { opacity: 0, y: 24, filter: 'blur(8px)' });
      gsap.set(q('.wordmark span'), { opacity: 0, yPercent: 40, filter: 'blur(14px)' });
      gsap.set(q('.limb, .limb-sun'), { opacity: 0, y: 80 });

      const tl = gsap.timeline({ paused: true, defaults: { ease: 'expo.out' } });
      tl.to(q('.limb, .limb-sun'), { opacity: 1, y: 0, duration: 2.2, ease: 'power3.out' }, 0)
        .to(q('.wordmark span'), { opacity: 1, yPercent: 0, filter: 'blur(0px)', duration: 1.6, stagger: { each: 0.035, from: 'center' } }, 0.05)
        .to(q('.wm > span'), { yPercent: 0, duration: 1.2, stagger: 0.045 }, 0.12)
        .to(q('.h-in'), { opacity: 1, y: 0, filter: 'blur(0px)', duration: 1.1, stagger: 0.07 }, 0.35);

      const off = onBoom(() => tl.play());

      // Scroll: the text lifts away faster than the planet, the wordmark slowest (parallax depth)
      gsap.to(q('.hero-copy'), { yPercent: -18, opacity: 0, ease: 'none', scrollTrigger: { trigger: section.current, start: 'top top', end: '70% top', scrub: true } });
      gsap.to(q('.wordmark'), { yPercent: 30, ease: 'none', scrollTrigger: { trigger: section.current, start: 'top top', end: 'bottom top', scrub: true } });
      gsap.to(q('.limb-group'), { y: 160, ease: 'none', scrollTrigger: { trigger: section.current, start: 'top top', end: 'bottom top', scrub: true } });

      return () => off();
    },
    { scope: section },
  );

  return (
    <section ref={section} id="top" aria-labelledby="hero-title" className="relative min-h-[100svh] overflow-hidden">
      {/* planet limb at dawn, under the engine */}
      <div className="limb-group pointer-events-none absolute inset-0 [mask-image:linear-gradient(to_bottom,black_62%,transparent_96%)]" aria-hidden="true">
        <div className="limb-sun" />
        <div className="limb" />
      </div>

      <div className="pointer-events-none absolute inset-x-0 bottom-[6%] flex justify-center overflow-hidden [mask-image:linear-gradient(to_bottom,black_40%,transparent)] lg:bottom-[4%]" aria-hidden="true">
        <p className="wordmark">
          {WORDMARK.map((ch, i) => (
            <span key={i}>{ch}</span>
          ))}
        </p>
      </div>

      <div className="hero-copy wrap relative z-10 flex min-h-[100svh] flex-col justify-start pb-24 pt-28 lg:justify-center lg:pb-28 lg:pt-28">
        <div className="max-w-[780px]">
          <span className="h-in eyebrow">
            <span className="live-dot h-1.5 w-1.5 rounded-full bg-healthy shadow-[0_0_10px_2px_rgb(66_190_101/0.7)]" />
            Predictive maintenance · 5 aircraft systems
          </span>

          <h1 id="hero-title" className="display-1 mt-6 lg:mt-8">
            {LINES.map((line, li) => (
              <span key={li} className="block">
                {line.map((w, wi) => (
                  <Fragment key={wi}>
                    <span className="wm">
                      <span className={li === 2 && wi === 1 ? 'burn-ink' : 'hero-ink'}>{w}</span>
                    </span>
                    {wi < line.length - 1 ? ' ' : ''}
                  </Fragment>
                ))}
              </span>
            ))}
          </h1>

          <p className="h-in body-lead mt-6 max-w-[520px] text-muted lg:mt-8">
            AeroSentinel reads a file of sensor readings, recognises the component and forecasts its remaining useful
            life, its risk band and the sensors behind the call.
          </p>

          <div className="h-in mt-8 flex flex-wrap items-center gap-4">
            <DemoButton />
            <span className="caption-2 text-faint">Opens with sample data. No account needed.</span>
          </div>

          <dl className="h-in mt-10 hidden max-w-[520px] grid-cols-2 gap-6 border-t border-line pt-6 sm:grid">
            <div>
              <dt className="hud-label">Risk band correct</dt>
              <dd className="data mt-1 text-xl leading-7 text-ink">90.3 to 93.1%</dd>
            </div>
            <div>
              <dt className="hud-label">Files sent to a wrong model</dt>
              <dd className="data mt-1 text-xl leading-7 text-ink">0 of 960</dd>
            </div>
          </dl>
        </div>
      </div>

      {/* instrument strip, bottom */}
      <div className="h-in pointer-events-none absolute inset-x-0 bottom-6 z-10 hidden lg:block" aria-hidden="true">
        <div className="wrap flex items-end justify-between">
          <div className="glass relative flex items-center gap-6 rounded-xl px-4 py-3">
            <div className="hud-frame" />
            <div>
              <p className="hud-label">N1</p>
              <p className="data text-sm text-ink"><span data-t="n1">92.4</span>%</p>
            </div>
            <div>
              <p className="hud-label">EGT</p>
              <p className="data text-sm text-ink"><span data-t="egt">642</span>°C</p>
            </div>
            <div>
              <p className="hud-label">Fuel flow</p>
              <p className="data text-sm text-ink"><span data-t="ff">2.71</span> kg/s</p>
            </div>
          </div>

          <div className="flex flex-col items-center gap-3">
            <span className="hud-label">Scroll to fly through</span>
            <span className="cue-line" />
          </div>

          <div className="glass relative flex items-center gap-4 rounded-xl px-4 py-3">
            <div className="hud-frame" />
            <span className="caption-4 rounded-md bg-warning/15 px-2 py-0.5 text-warning">Warning</span>
            <span className="body-6 text-muted">
              Sample <span className="data text-ink">Engine 07</span>
            </span>
            <span className="h-4 w-px bg-line" />
            <span className="body-6 text-muted">
              <span className="data text-ink">23</span> cycles left
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}
