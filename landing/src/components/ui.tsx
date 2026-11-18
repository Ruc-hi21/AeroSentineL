'use client';

import Link from 'next/link';
import { motion, useReducedMotion } from 'motion/react';
import { ArrowRight } from '@phosphor-icons/react';
import { EASE } from '@/lib/site';

export function Logo({ size = 28, withName = true }: { size?: number; withName?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src="/brand/logo-mark.svg" width={size} height={size} alt="" aria-hidden="true" />
      {withName && <span className="title-3 tracking-tight text-ink">AeroSentinel</span>}
    </span>
  );
}

/** The one primary action on every screen. Goes through /demo so a sleeping console can wake. */
export function DemoButton({ size = 'lg', label = 'Try the live demo' }: { size?: 'lg' | 'sm'; label?: string }) {
  return (
    <Link href="/demo/" className={`btn btn-primary ${size === 'lg' ? 'btn-lg button-md' : 'button-sm'}`}>
      {label}
      <ArrowRight size={size === 'lg' ? 18 : 16} weight="bold" className="btn-arrow" aria-hidden="true" />
    </Link>
  );
}

export function SignInButton({ size = 'lg' }: { size?: 'lg' | 'sm' }) {
  return (
    <Link href="/signin/" className={`btn btn-ghost ${size === 'lg' ? 'btn-lg button-md' : 'button-sm'}`}>
      Sign in
    </Link>
  );
}

/** Sections rise 32px and fade in once, on the base curve. */
export function Reveal({
  children,
  delay = 0,
  className,
  as = 'div',
}: {
  children: React.ReactNode;
  delay?: number;
  className?: string;
  as?: 'div' | 'li' | 'header';
}) {
  const reduce = useReducedMotion();
  const Comp = motion[as];
  return (
    <Comp
      className={className}
      initial={reduce ? { opacity: 0 } : { opacity: 0, y: 32 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '0px 0px -12% 0px' }}
      transition={{ duration: reduce ? 0.3 : 0.7, ease: EASE, delay }}
    >
      {children}
    </Comp>
  );
}

export function SectionHead({ title, children, id }: { title: React.ReactNode; children?: React.ReactNode; id?: string }) {
  return (
    <Reveal as="header" className="max-w-[680px]">
      <h2 id={id} className="heading-2 text-ink">
        {title}
      </h2>
      {children && <p className="body-lead mt-6 text-muted">{children}</p>}
    </Reveal>
  );
}
