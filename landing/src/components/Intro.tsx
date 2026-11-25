'use client';

import { useEffect, useRef } from 'react';
import { RUN, flight, introFreeze } from '@/lib/flight';

/**
 * The opening, as a DOM layer over the 3D world.
 *
 *  boot  : black, systems check, while three.js loads (pure CSS, from first paint)
 *  fly   : the backdrop fades away and the 3D supersonic run plays underneath this HUD:
 *          lock-on box tracking the jet, Mach tape, phase readout
 *  sonic : the barrier breaks: MACH 1 stamp, flash, shake
 *  wash  : the shockwave reaches the lens: white-out, the site is revealed behind it
 *
 * INTRO_SCRIPT decides before first paint whether it plays (hard loads only, never with
 * reduced motion). If WebGL never comes up, a plain white-out reveals the site instead.
 */

export const INTRO_SCRIPT = `(function(){try{var d=document.documentElement;if(d.dataset.intro)return;
var r=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
if(r){d.dataset.intro='done';return;}
if('scrollRestoration' in history)history.scrollRestoration='manual';window.scrollTo(0,0);
d.dataset.intro='play';window.__introT0=performance.now();}catch(e){}})();`;

const CHECKS = ['AIRFRAME', 'ENGINES', 'SENSOR BUS', 'FLIGHT MODEL'];
const MIN_BOOT = 0.55; // s: long enough to read the systems check, never longer than loading needs
const MAX_BOOT = 5; // s: give up on the 3D run and white-out straight to the site

export default function Intro() {
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const d = document.documentElement;
    const el = root.current;
    if (d.dataset.intro !== 'play' || !el) {
      flight.introPhase = 'done';
      flight.boomed = true;
      flight.introDone = true;
      return;
    }
    flight.introPhase = 'boot';
    const t0 = (window as unknown as { __introT0?: number }).__introT0 ?? performance.now();
    const since = () => (performance.now() - t0) / 1000;
    const timers: number[] = [];
    const later = (fn: () => void, s: number) => timers.push(window.setTimeout(fn, Math.max(0, s * 1000)));
    const setPhase = (p: string) => el.setAttribute('data-phase', p);

    let finished = false;
    const reveal = () => {
      if (flight.boomed) return;
      flight.boomed = true;
      window.dispatchEvent(new Event('intro:boom'));
    };
    const finish = () => {
      if (finished) return;
      finished = true;
      reveal();
      flight.introPhase = 'done';
      d.dataset.intro = 'done';
      flight.introDone = true;
      if ('scrollRestoration' in history) history.scrollRestoration = 'auto';
      window.dispatchEvent(new Event('intro:done'));
    };
    /** White-out to the site: used by the run, by skip, and when WebGL never arrives. */
    const washOut = (hold: number) => {
      setPhase('wash');
      later(() => {
        flight.introPhase = 'done';
        reveal();
      }, hold);
      later(finish, hold + 0.55);
    };

    // ── boot → fly once the world has rendered ──
    let flying = false;
    const fly = () => {
      if (flying || finished) return;
      flying = true;
      later(() => {
        flight.introPhase = 'fly';
        setPhase('fly');
      }, MIN_BOOT - since());
    };
    if ((window as unknown as { __worldReady?: boolean }).__worldReady) fly();
    window.addEventListener('world:ready', fly);
    const frozen = introFreeze() !== null;
    if (!frozen) {
      later(() => {
        if (!flying) washOut(0.12);
      }, MAX_BOOT - since());
    }

    // ── beats of the run, fired by the world on its own clock ──
    const onSonic = () => {
      setPhase('sonic');
      d.classList.add('quake');
      later(() => d.classList.remove('quake'), 0.5);
    };
    const onWash = () => {
      washOut(RUN.swap - RUN.wash);
      d.classList.add('quake');
      later(() => d.classList.remove('quake'), 0.5);
    };
    window.addEventListener('intro:sonic', onSonic);
    window.addEventListener('intro:wash', onWash);

    // ── HUD: lock-on box and Mach, written straight to the DOM every frame ──
    const box = el.querySelector<HTMLElement>('.ih-lock');
    const range = el.querySelector<HTMLElement>('[data-h="range"]');
    const mach = el.querySelector<HTMLElement>('[data-h="mach"]');
    const state = el.querySelector<HTMLElement>('[data-h="state"]');
    const tape = el.querySelector<HTMLElement>('.ih-tape');
    let raf = 0;
    let lastState = '';
    const hud = () => {
      raf = requestAnimationFrame(hud);
      if (flight.introPhase !== 'fly') return;
      if (box) {
        const x = (flight.lockX * 0.5 + 0.5) * window.innerWidth;
        const y = (-flight.lockY * 0.5 + 0.5) * window.innerHeight;
        box.style.transform = `translate3d(${x.toFixed(1)}px, ${y.toFixed(1)}px, 0)`;
        box.dataset.on = String(flight.lockOn);
      }
      if (range) range.textContent = (flight.lockRange / 1000).toFixed(2);
      if (mach) mach.textContent = flight.mach.toFixed(2);
      if (tape) tape.style.transform = `translateY(${((flight.mach - 0.8) * 600).toFixed(1)}px)`;
      const st = flight.mach >= 1 ? 'SUPERSONIC' : flight.mach >= 0.95 ? 'TRANSONIC' : 'HIGH SUBSONIC';
      if (state && st !== lastState) {
        lastState = st;
        state.textContent = st;
      }
    };
    raf = requestAnimationFrame(hud);

    // ── skip: click, key or wheel ──
    const skip = () => {
      if (frozen || finished || el.dataset.phase === 'wash') return;
      washOut(0.1);
    };
    const onKey = (e: KeyboardEvent) => {
      if (['Escape', 'Enter', ' '].includes(e.key)) skip();
    };
    el.addEventListener('pointerdown', skip);
    window.addEventListener('keydown', onKey);
    window.addEventListener('wheel', skip, { passive: true });
    window.addEventListener('touchmove', skip, { passive: true });

    return () => {
      timers.forEach((t) => window.clearTimeout(t));
      cancelAnimationFrame(raf);
      window.removeEventListener('world:ready', fly);
      window.removeEventListener('intro:sonic', onSonic);
      window.removeEventListener('intro:wash', onWash);
      el.removeEventListener('pointerdown', skip);
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('wheel', skip);
      window.removeEventListener('touchmove', skip);
    };
  }, []);

  return (
    <div ref={root} className="intro" data-phase="boot" aria-hidden="true">
      <div className="ib-backdrop" />

      {/* boot: systems check while the world loads */}
      <div className="ib-boot">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/brand/logo-mark.svg" width={44} height={44} alt="" className="ib-mark" />
        <p className="ib-word data">AEROSENTINEL</p>
        <ul className="ib-checks data">
          {CHECKS.map((c, i) => (
            <li key={c} style={{ ['--i' as string]: i }}>
              <span>{c}</span>
              <span className="ib-dots" />
              <span className="ib-ok">OK</span>
            </li>
          ))}
        </ul>
        <div className="ib-bar"><span /></div>
      </div>

      {/* fly: head-up display over the 3D run */}
      <div className="ih">
        <div className="ih-brackets" />
        <div className="ih-top data">
          <span>AEROSENTINEL · AS-088</span>
          <span className="ih-dim">SUPERSONIC RUN · FL 350</span>
        </div>

        <div className="ih-ladder">
          {[-2, -1, 1, 2].map((n) => (
            <span key={n} style={{ ['--n' as string]: n }}><i>{Math.abs(n) * 5}</i></span>
          ))}
          <b />
        </div>

        <div className="ih-lock" data-on="false">
          <span className="ih-lock-box" />
          <span className="ih-lock-tag data">
            AS-088 · LOCK<br />
            <span className="ih-dim">RNG <span data-h="range">0.00</span> km</span>
          </span>
        </div>

        <div className="ih-machcol">
          <span className="ih-dim data">MACH</span>
          <div className="ih-tapewin"><div className="ih-tape" /></div>
        </div>

        <div className="ih-readout">
          <span className="ih-mach data" data-h="mach">0.84</span>
          <span className="ih-state data" data-h="state">HIGH SUBSONIC</span>
        </div>
        <span className="ih-skip data">CLICK TO SKIP</span>
      </div>

      <div className="ih-stamp data">
        <span>MACH 1</span>
        <small>SOUND BARRIER BROKEN</small>
      </div>
      <div className="ib-flash" />
    </div>
  );
}
