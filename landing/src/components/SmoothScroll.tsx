'use client';

import { useEffect } from 'react';
import Lenis from 'lenis';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { useIntroDone } from '@/lib/intro';

gsap.registerPlugin(ScrollTrigger);

/** Inertial scrolling, driven by GSAP's ticker so every ScrollTrigger reads the same frame. */
export default function SmoothScroll() {
  const ready = useIntroDone();

  useEffect(() => {
    if (!ready) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const lenis = new Lenis({ lerp: 0.09, wheelMultiplier: 1, anchors: { offset: -96 } });
    lenis.on('scroll', ScrollTrigger.update);
    const tick = (t: number) => lenis.raf(t * 1000);
    gsap.ticker.add(tick);
    gsap.ticker.lagSmoothing(0);
    document.documentElement.classList.add('lenis-on');
    return () => {
      gsap.ticker.remove(tick);
      lenis.destroy();
      document.documentElement.classList.remove('lenis-on');
    };
  }, [ready]);

  return null;
}
