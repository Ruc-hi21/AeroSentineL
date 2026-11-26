'use client';

import { useSyncExternalStore } from 'react';

/* A tiny shared flag: has the opening flight finished?
   The hero waits on it so its entrance plays after the flash, not under it. */

let done = false;
const subs = new Set<() => void>();

export function finishIntro() {
  if (done) return;
  done = true;
  subs.forEach((f) => f());
}

export function useIntroDone() {
  return useSyncExternalStore(
    (f) => {
      subs.add(f);
      return () => subs.delete(f);
    },
    () => done,
    () => false,
  );
}
