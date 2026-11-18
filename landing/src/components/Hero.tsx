'use client';

import { useMemo, useRef } from 'react';
import dynamic from 'next/dynamic';
import { motion, useReducedMotion } from 'motion/react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { useGSAP } from '@gsap/react';
import { EASE } from '@/lib/site';
import { DemoButton } from './ui';

gsap.registerPlugin(ScrollTrigger, useGSAP);

const EngineScene = dynamic(() => import('./EngineScene'), {
  ssr: false,
  loading: () => <div className="absolute inset-0" aria-hidden="true" />,
});

export default function Hero() {
  const reduce = useReducedMotion();
  const section = useRef<HTMLElement>(null);
  const scroll = useMemo(() => ({ p: 0 }), []);

  useGSAP(
    () => {
      ScrollTrigger.create({
        trigger: section.current,
        start: 'top top',
        end: 'bottom top',
        scrub: true,
        onUpdate: (self) => {
          scroll.p = self.progress;
        },
      });
    },
    { scope: section },
  );

  const enter = (i: number) => ({
    initial: reduce ? { opacity: 0 } : { opacity: 0, y: 24, filter: 'blur(6px)' },
    animate: { opacity: 1, y: 0, filter: 'blur(0px)' },
    transition: { duration: 0.9, ease: EASE, delay: 0.1 + i * 0.08 },
  });

  return (
    <section ref={section} id="top" aria-labelledby="hero-title" className="relative overflow-hidden">
      <div className="blueprint absolute inset-0 [mask-image:radial-gradient(ellipse_at_70%_45%,black_20%,transparent_70%)]" aria-hidden="true" />

      <div className="wrap relative grid min-h-[100svh] grid-cols-1 items-center gap-8 pb-16 pt-28 lg:grid-cols-12 lg:pb-24 lg:pt-24">
        <div className="relative z-10 lg:col-span-7">
          <motion.h1 {...enter(1)} id="hero-title" className="heading-1 hero-ink max-w-[680px]">
            Know which part
            <br className="hidden sm:block" /> needs attention next,
            <br className="hidden sm:block" /> and why.
          </motion.h1>

          <motion.p {...enter(2)} className="body-lead mt-6 max-w-[560px] text-muted">
            AeroSentinel reads a file of sensor readings, recognises the component and forecasts its remaining
            useful life, its risk band and the sensors behind the call. Engines, battery cells, gearboxes, hydraulics
            and power electronics, in one console.
          </motion.p>

          <motion.div {...enter(3)} className="mt-8 flex flex-wrap items-center gap-4">
            <DemoButton />
            <span className="caption-2 text-faint">Opens with sample data. No account needed.</span>
          </motion.div>

          <motion.dl {...enter(4)} className="mt-12 grid max-w-[560px] grid-cols-2 gap-6 border-t border-line pt-6">
            <div>
              <dt className="caption-2 text-faint">Turbofan risk band correct</dt>
              <dd className="data mt-1 text-xl leading-7 text-ink">90.3 to 93.1%</dd>
            </div>
            <div>
              <dt className="caption-2 text-faint">Files sent to a wrong model</dt>
              <dd className="data mt-1 text-xl leading-7 text-ink">0 of 960</dd>
            </div>
          </motion.dl>
        </div>

        <motion.div
          className="relative h-[380px] sm:h-[480px] lg:col-span-5 lg:-ml-32 lg:-mr-12 lg:h-[640px]"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 1.2, ease: EASE, delay: 0.2 }}
          aria-label="Sectioned 3D turbofan engine with four sensor stations: fan inlet healthy, LPC outlet degrading, HPC outlet and LPT outlet at warning"
          role="img"
        >
          <EngineScene scroll={scroll} />
          <div className="pointer-events-none absolute bottom-2 left-0 right-0 flex justify-center sm:bottom-6">
            <div className="flex items-center gap-4 rounded-xl border border-line bg-white/85 px-4 py-3 shadow-[0_8px_24px_-12px_rgb(0_0_0/0.18)] backdrop-blur-md">
              <span className="caption-4 rounded-md bg-warning/15 px-2 py-0.5 text-warning">Warning</span>
              <span className="body-6 text-muted">
                Sample <span className="data text-ink">Engine 07</span>
              </span>
              <span className="hidden h-4 w-px bg-line sm:block" aria-hidden="true" />
              <span className="hidden body-6 text-muted sm:inline">
                <span className="data text-ink">23</span> cycles left, range <span className="data text-ink">17 to 31</span>
              </span>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
