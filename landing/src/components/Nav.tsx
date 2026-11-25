'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';
import { NAV, EASE } from '@/lib/site';
import { DemoButton, Logo } from './ui';

export default function Nav() {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState<string>('');
  const [scrolled, setScrolled] = useState(false);
  const reduce = useReducedMotion();

  // Current section, from IntersectionObserver (never a raw scroll listener)
  useEffect(() => {
    const els = NAV.map((n) => document.getElementById(n.id)).filter(Boolean) as HTMLElement[];
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) setActive(e.target.id);
        });
      },
      { rootMargin: '-45% 0px -50% 0px' },
    );
    els.forEach((el) => io.observe(el));
    const top = document.getElementById('top');
    const topIo = new IntersectionObserver(([e]) => {
      setScrolled(!e.isIntersecting);
      if (e.isIntersecting) setActive('');
    }, { rootMargin: '-80px 0px 0px 0px' });
    if (top) topIo.observe(top);
    return () => {
      io.disconnect();
      topIo.disconnect();
    };
  }, []);

  useEffect(() => {
    document.documentElement.style.overflow = open ? 'hidden' : '';
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false);
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  return (
    <>
      <div className="nav-shell pointer-events-none fixed inset-x-0 top-3 z-50 flex justify-center px-4 sm:top-4">
        <nav
          aria-label="Main"
          className={`pointer-events-auto flex h-14 w-full max-w-[1104px] items-center justify-between gap-4 rounded-2xl border pl-4 pr-2 backdrop-blur-xl transition-[background-color,border-color] duration-500 ease-[cubic-bezier(0.22,1,0.36,1)] ${
            scrolled || open ? 'border-line bg-base/75' : 'border-transparent bg-base/20'
          }`}
        >
          <Link href="/" aria-label="AeroSentinel home" className="shrink-0 rounded-lg">
            <Logo />
          </Link>

          <ul className="hidden items-center gap-1 lg:flex">
            {NAV.map((n) => {
              const isActive = active === n.id;
              return (
                <li key={n.id}>
                  <a
                    href={n.href}
                    aria-current={isActive ? 'true' : undefined}
                    className={`relative rounded-lg px-3 py-2 title-4 transition-colors duration-300 ${
                      isActive ? 'text-ink' : 'text-muted hover:text-ink'
                    }`}
                  >
                    {isActive && (
                      <motion.span
                        layoutId="nav-active"
                        className="absolute inset-0 -z-10 rounded-lg bg-raised"
                        transition={{ duration: 0.5, ease: EASE }}
                      />
                    )}
                    {n.label}
                  </a>
                </li>
              );
            })}
          </ul>

          <div className="flex items-center gap-2">
            <Link href="/signin/" className="btn btn-quiet button-sm hidden sm:inline-flex">
              Sign in
            </Link>
            <span className="hidden sm:inline-flex">
              <DemoButton size="sm" label="Try the demo" />
            </span>
            <button
              type="button"
              className="relative grid h-10 w-10 place-items-center rounded-lg text-ink lg:hidden"
              aria-label={open ? 'Close menu' : 'Open menu'}
              aria-expanded={open}
              aria-controls="mobile-menu"
              onClick={() => setOpen((v) => !v)}
            >
              <span
                className="absolute h-[1.5px] w-5 bg-current transition-transform duration-500 ease-[cubic-bezier(0.22,1,0.36,1)]"
                style={{ transform: open ? 'rotate(45deg)' : 'translateY(-4px)' }}
              />
              <span
                className="absolute h-[1.5px] w-5 bg-current transition-transform duration-500 ease-[cubic-bezier(0.22,1,0.36,1)]"
                style={{ transform: open ? 'rotate(-45deg)' : 'translateY(4px)' }}
              />
            </button>
          </div>
        </nav>
      </div>

      <AnimatePresence>
        {open && (
          <motion.div
            id="mobile-menu"
            className="fixed inset-0 z-40 bg-base/95 px-4 pt-24 backdrop-blur-2xl lg:hidden"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0, transition: { duration: 0.2 } }}
            transition={{ duration: 0.3, ease: EASE }}
          >
            <ul className="flex flex-col">
              {NAV.map((n, i) => (
                <motion.li
                  key={n.id}
                  initial={reduce ? { opacity: 0 } : { opacity: 0, y: 24 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.5, ease: EASE, delay: Math.min(i * 0.06, 0.36) }}
                  className="border-b border-line"
                >
                  <a href={n.href} onClick={() => setOpen(false)} className="block py-4 heading-5 text-ink">
                    {n.label}
                  </a>
                </motion.li>
              ))}
            </ul>
            <motion.div
              className="mt-8 flex flex-col gap-3"
              initial={{ opacity: 0, y: reduce ? 0 : 24 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, ease: EASE, delay: 0.4 }}
            >
              <DemoButton />
              <Link href="/signin/" className="btn btn-ghost btn-lg button-md">
                Sign in
              </Link>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
