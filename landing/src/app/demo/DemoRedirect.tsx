'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { ArrowRight } from '@phosphor-icons/react';
import { DASHBOARD_URL } from '@/lib/site';
import { Logo } from '@/components/ui';

export default function DemoRedirect() {
  useEffect(() => {
    const t = window.setTimeout(() => window.location.replace(DASHBOARD_URL), 1400);
    return () => window.clearTimeout(t);
  }, []);

  return (
    <main id="main" className="relative grid min-h-[100svh] place-items-center px-4">
      <div className="blueprint absolute inset-0 [mask-image:radial-gradient(ellipse_at_center,black_10%,transparent_60%)]" aria-hidden="true" />
      <div className="relative w-full max-w-[440px] text-center">
        <div className="flex justify-center">
          <Logo size={40} withName={false} />
        </div>
        <h1 className="heading-5 mt-6 text-ink">Opening the live console</h1>
        <p className="body-6 mt-2 text-muted" role="status">
          Loading the sample fleet. If the console has been idle it can take up to a minute to wake up.
        </p>
        <div className="mt-8 h-1 overflow-hidden rounded-full bg-raised" aria-hidden="true">
          <div className="demo-bar h-full rounded-full bg-accent" />
        </div>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <a href={DASHBOARD_URL} className="btn btn-primary button-sm">
            Open it now <ArrowRight size={16} weight="bold" className="btn-arrow" aria-hidden="true" />
          </a>
          <Link href="/" className="btn btn-ghost button-sm">Back to site</Link>
        </div>
        <p className="caption-5 data mt-6 truncate text-faint">{DASHBOARD_URL.replace(/^https?:\/\//, '')}</p>
      </div>
    </main>
  );
}
