/**
 * One mutable store shared by the DOM (scroll, pointer, intro) and the 3D world.
 * Written by ScrollTriggers and listeners, read every frame inside useFrame.
 * Plain object on purpose: no React state, so nothing re-renders at 60 fps.
 */
export const flight = {
  /** 0..1 while the hero scrolls out of view */
  hero: 0,
  /** 0..1 across the pinned fly-through chapter */
  dive: 0,
  /** 0..1 from the end of the fly-through to the final call to action */
  after: 0,
  /** 0..1 as the final call to action arrives */
  cta: 0,
  /** smoothed scroll velocity in px per frame (signed) */
  velocity: 0,
  /** pointer, -1..1 on both axes */
  px: 0,
  py: 0,

  /* ── intro ── */
  /** boot: overlay up, world loading · fly: the 3D supersonic run · done: site live */
  introPhase: 'done' as 'boot' | 'fly' | 'done',
  /** seconds into the 3D run (written by the world) */
  introT: 0,
  /** Mach number shown on the HUD */
  mach: 0.84,
  /** jet position on screen for the HUD lock-on box: NDC x/y, range in metres, on screen */
  lockX: 0,
  lockY: 0,
  lockRange: 0,
  lockOn: false,
  /** set when the shockwave reveals the site (or at once when the intro does not play) */
  boomed: false,
  /** set once the intro overlay is gone */
  introDone: false,
};

export type Flight = typeof flight;

/** The 3D run's clock, in seconds from the start of the flight. */
export const RUN = {
  /** the jet breaks the sound barrier: vapour cone pops, boom */
  sonic: 1.62,
  /** the shockwave reaches the camera: white-out */
  wash: 1.96,
  /** under the white-out the world swaps to the site */
  swap: 2.02,
  /** overlay fully gone */
  end: 2.6,
};

/** Dev only: `?introAt=1.4` freezes the 3D run at that second, for inspecting each beat. */
export function introFreeze(): number | null {
  if (typeof window === 'undefined' || process.env.NODE_ENV === 'production') return null;
  const v = new URLSearchParams(window.location.search).get('introAt');
  return v === null ? null : Number(v);
}

/** Runs when the site is revealed (immediately if it already happened or the intro never played). */
export function onBoom(cb: () => void): () => void {
  if (typeof window === 'undefined') return () => {};
  if (flight.boomed || document.documentElement.dataset.intro !== 'play') {
    cb();
    return () => {};
  }
  const h = () => cb();
  window.addEventListener('intro:boom', h, { once: true });
  return () => window.removeEventListener('intro:boom', h);
}

/** Resolves when the intro has finished (immediately if it never played). */
export function onIntroDone(cb: () => void): () => void {
  if (typeof window === 'undefined') return () => {};
  if (document.documentElement.dataset.intro !== 'play') {
    cb();
    return () => {};
  }
  const h = () => cb();
  window.addEventListener('intro:done', h, { once: true });
  return () => window.removeEventListener('intro:done', h);
}

if (typeof window !== 'undefined' && process.env.NODE_ENV !== 'production') {
  (window as unknown as { __flight: Flight }).__flight = flight;
}
