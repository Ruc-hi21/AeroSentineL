import Link from 'next/link';
import { ArrowLeft } from '@phosphor-icons/react/dist/ssr';
import { Logo } from './ui';
import Footer from './Footer';

export default function LegalShell({ title, updated, children }: { title: string; updated: string; children: React.ReactNode }) {
  return (
    <>
      <header className="wrap flex items-center justify-between py-6">
        <Link href="/" aria-label="AeroSentinel home" className="rounded-lg"><Logo /></Link>
        <Link href="/" className="btn btn-quiet button-sm"><ArrowLeft size={16} aria-hidden="true" /> Back to site</Link>
      </header>
      <main id="main" className="wrap pb-24 pt-12">
        <h1 className="heading-3 text-ink">{title}</h1>
        <p className="caption-2 mt-2 text-faint">Last updated {updated}</p>
        <div className="prose-legal mt-8">{children}</div>
      </main>
      <Footer />
    </>
  );
}
