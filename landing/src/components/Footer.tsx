import Link from 'next/link';
import { GithubLogo } from '@phosphor-icons/react/dist/ssr';
import { NAV, REPO_URL } from '@/lib/site';
import { DemoButton, Logo, Reveal, SignInButton, SplitWords } from './ui';

export function FinalCta() {
  return (
    <section id="cta" aria-labelledby="cta-title" className="relative flex min-h-[100svh] items-start pt-32 lg:pt-40">
      <div className="wrap relative flex flex-col items-center text-center">
        <span className="eyebrow">Cleared for departure</span>
        <h2 id="cta-title" className="display-1 mx-auto mt-6 max-w-[900px]">
          <SplitWords text="See which unit needs attention first." wordClass="hero-ink" />
        </h2>
        <Reveal delay={0.2}>
          <p className="body-lead mx-auto mt-6 max-w-[520px] text-muted">
            The demo opens on a fleet of sample units, with the most urgent one already at the top.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <DemoButton />
            <SignInButton />
          </div>
          <p className="caption-2 mt-4 text-faint">No account needed for the demo.</p>
        </Reveal>
      </div>
    </section>
  );
}

export default function Footer() {
  return (
    <footer className="site-footer border-t border-line bg-base/90">
      <div className="wrap grid grid-cols-1 gap-12 py-16 md:grid-cols-12">
        <div className="md:col-span-5">
          <Logo />
          <p className="body-6 mt-4 max-w-[360px] text-muted">
            Predictive maintenance for aircraft components. Built by Group 88: Aarohi Ruchita and Prem Singh.
          </p>
          <a href={REPO_URL} target="_blank" rel="noreferrer" className="btn btn-ghost button-sm mt-6">
            <GithubLogo size={16} aria-hidden="true" /> Source on GitHub
          </a>
        </div>
        <nav aria-label="Footer" className="grid grid-cols-2 gap-8 md:col-span-7 md:grid-cols-3">
          <div>
            <p className="caption-3 text-faint">Product</p>
            <ul className="mt-4 space-y-3">
              {NAV.slice(0, 5).map((n) => (
                <li key={n.id}>
                  <a href={`/${n.href}`} className="body-6 text-muted transition-colors duration-300 hover:text-ink">{n.label}</a>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <p className="caption-3 text-faint">Console</p>
            <ul className="mt-4 space-y-3">
              <li><Link href="/demo/" className="body-6 text-muted transition-colors duration-300 hover:text-ink">Live demo</Link></li>
              <li><Link href="/signin/" className="body-6 text-muted transition-colors duration-300 hover:text-ink">Sign in</Link></li>
              <li><a href="/#faq" className="body-6 text-muted transition-colors duration-300 hover:text-ink">FAQ</a></li>
            </ul>
          </div>
          <div>
            <p className="caption-3 text-faint">Legal</p>
            <ul className="mt-4 space-y-3">
              <li><Link href="/privacy/" className="body-6 text-muted transition-colors duration-300 hover:text-ink">Privacy</Link></li>
              <li><Link href="/terms/" className="body-6 text-muted transition-colors duration-300 hover:text-ink">Terms</Link></li>
            </ul>
          </div>
        </nav>
      </div>
      <div className="wrap flex flex-col gap-2 border-t border-line py-6 md:flex-row md:items-center md:justify-between">
        <p className="caption-5 text-faint">© 2026 AeroSentinel · MIT License</p>
        <p className="caption-5 max-w-[640px] text-faint">
          Decision support only. Not a certified airworthiness determination and not a replacement for certified
          maintenance procedures.
        </p>
      </div>
    </footer>
  );
}
