import type { Metadata } from 'next';
import Link from 'next/link';
import { ArrowLeft } from '@phosphor-icons/react/dist/ssr';
import { Logo } from '@/components/ui';
import SignInForm from './SignInForm';

export const metadata: Metadata = {
  title: 'Sign in | AeroSentinel',
  description: 'Sign in to the AeroSentinel predictive maintenance console.',
  robots: { index: false },
};

export default function SignInPage() {
  return (
    <main id="main" className="grid min-h-[100svh] grid-cols-1 lg:grid-cols-2">
      <div className="flex flex-col px-4 py-6 sm:px-8 lg:px-12">
        <div className="flex items-center justify-between">
          <Link href="/" aria-label="AeroSentinel home" className="rounded-lg">
            <Logo />
          </Link>
          <Link href="/" className="btn btn-quiet button-sm">
            <ArrowLeft size={16} aria-hidden="true" /> Back to site
          </Link>
        </div>

        <div className="mx-auto flex w-full max-w-[400px] flex-1 flex-col justify-center py-16">
          <h1 className="heading-4 text-ink">Sign in to AeroSentinel</h1>
          <p className="body-6 mt-2 text-muted">Pick up where your fleet left off.</p>
          <SignInForm />
        </div>

        <p className="caption-5 text-faint">
          By signing in you agree to the <Link href="/terms/" className="underline hover:text-ink">Terms</Link> and the{' '}
          <Link href="/privacy/" className="underline hover:text-ink">Privacy notice</Link>.
        </p>
      </div>

      <aside className="relative hidden overflow-hidden border-l border-line bg-surface lg:block" aria-label="Console preview">
        <div className="blueprint absolute inset-0" aria-hidden="true" />
        <div className="relative flex h-full flex-col justify-center p-12">
          <p className="heading-5 max-w-[440px] text-ink">
            Remaining life, risk band and the sensors behind the call, for every unit.
          </p>
          <div className="mt-10 overflow-hidden rounded-2xl border border-line-strong bg-[#0e1013] shadow-[0_40px_80px_-20px_rgb(0_0_0/0.25)]">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/shots/status.webp" alt="AeroSentinel unit status page" className="aspect-[16/11] w-full object-cover object-top" />
          </div>
          <dl className="mt-8 grid grid-cols-3 gap-6">
            {[
              ['5', 'component models'],
              ['0%', 'files sent to a wrong model'],
              ['0.1 ms', 'to score a reading'],
            ].map(([v, l]) => (
              <div key={l}>
                <dt className="caption-5 text-faint">{l}</dt>
                <dd className="data mt-1 text-xl leading-7 text-ink">{v}</dd>
              </div>
            ))}
          </dl>
        </div>
      </aside>
    </main>
  );
}
