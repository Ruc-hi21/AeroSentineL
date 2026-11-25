'use client';

import { useEffect } from 'react';
import Lenis from 'lenis';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { flight, onIntroDone } from '@/lib/flight';

gsap.registerPlugin(ScrollTrigger);

/**
 * Smooth scrolling (Lenis, on GSAP's ticker so ScrollTrigger and the 3D world share one clock)
 * and the page-wide scroll ranges the world reads: `after` and `cta`.
 * Rendered last on the page so its triggers are created after every pinned section above it.
 */
export default function ScrollDirector() {
  useEffect(() => {
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    let lenis: Lenis | null = null;
    let raf: ((t: number) => void) | null = null;
    let lastY = window.scrollY;
    let onNative: (() => void) | null = null;
    let decay = 0;

    if (!reduce) {
      lenis = new Lenis({ duration: 1.15, easing: (t) => 1 - Math.pow(1 - t, 4), anchors: { offset: -88 }, syncTouch: false });
      lenis.on('scroll', (e: Lenis) => {
        flight.velocity = e.velocity;
        ScrollTrigger.update();
      });
      raf = (t: number) => lenis!.raf(t * 1000);
      gsap.ticker.add(raf);
      gsap.ticker.lagSmoothing(0);
      if (document.documentElement.dataset.intro === 'play') lenis.stop();
    } else {
      onNative = () => {
        flight.velocity = window.scrollY - lastY;
        lastY = window.scrollY;
      };
      window.addEventListener('scroll', onNative, { passive: true });
    }

    // velocity eases back to zero when scrolling stops (Lenis reports the last value)
    const tick = () => {
      flight.velocity *= 0.92;
      if (Math.abs(flight.velocity) < 0.01) flight.velocity = 0;
    };
    gsap.ticker.add(tick);
    decay = 1;

    const offIntro = onIntroDone(() => {
      lenis?.start();
      ScrollTrigger.refresh();
    });

    const triggers = [
      ScrollTrigger.create({
        trigger: '#problem',
        start: 'top bottom',
        endTrigger: '#cta',
        end: 'top bottom',
        onUpdate: (s) => (flight.after = s.progress),
        onLeaveBack: () => (flight.after = 0),
      }),
      ScrollTrigger.create({
        trigger: '#cta',
        start: 'top bottom',
        end: 'center center',
        scrub: true,
        onUpdate: (s) => (flight.cta = s.progress),
        onLeaveBack: () => (flight.cta = 0),
      }),
    ];
    ScrollTrigger.sort();
    // fonts and images change heights after first layout
    const refresh = () => ScrollTrigger.refresh();
    window.addEventListener('load', refresh);
    document.fonts?.ready.then(refresh);

    return () => {
      offIntro();
      triggers.forEach((t) => t.kill());
      window.removeEventListener('load', refresh);
      if (raf) gsap.ticker.remove(raf);
      if (decay) gsap.ticker.remove(tick);
      if (onNative) window.removeEventListener('scroll', onNative);
      lenis?.destroy();
    };
  }, []);

  return null;
}
