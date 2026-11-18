import Link from 'next/link';
import { Logo } from '@/components/ui';

export default function NotFound() {
  return (
    <main id="main" className="relative grid min-h-[100svh] place-items-center px-4">
      <div className="blueprint absolute inset-0 [mask-image:radial-gradient(ellipse_at_center,black_10%,transparent_60%)]" aria-hidden="true" />
      <div className="relative max-w-[440px] text-center">
        <div className="flex justify-center"><Logo size={40} withName={false} /></div>
        <p className="data mt-6 text-sm text-faint">404 · not recognised</p>
        <h1 className="heading-4 mt-2 text-ink">This page is off the flight plan.</h1>
        <p className="body-6 mt-3 text-muted">The address may have changed. Head back to the site or open the console directly.</p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Link href="/" className="btn btn-ghost button-sm">Back to site</Link>
          <Link href="/demo/" className="btn btn-primary button-sm">Try the live demo</Link>
        </div>
      </div>
    </main>
  );
}
