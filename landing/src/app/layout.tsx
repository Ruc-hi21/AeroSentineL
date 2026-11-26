import type { Metadata, Viewport } from 'next';
import { Geist, Geist_Mono } from 'next/font/google';
import './globals.css';

const geist = Geist({ subsets: ['latin'], variable: '--font-geist', display: 'swap' });
const geistMono = Geist_Mono({ subsets: ['latin'], variable: '--font-geist-mono', display: 'swap' });

const title = 'AeroSentinel | Predictive maintenance for aircraft components';
const description =
  'AeroSentinel reads a file of sensor readings, recognises the aircraft component and forecasts its remaining useful life, its risk band and the sensors behind it.';

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL || 'http://localhost:3000'),
  title,
  description,
  applicationName: 'AeroSentinel',
  openGraph: {
    title,
    description,
    type: 'website',
    siteName: 'AeroSentinel',
    images: [{ url: '/shots/status.webp', width: 1440, height: 1400, alt: 'AeroSentinel unit status console' }],
  },
  twitter: { card: 'summary_large_image', title, description, images: ['/shots/status.webp'] },
};

export const viewport: Viewport = { themeColor: '#ffffff', colorScheme: 'light' };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${geist.variable} ${geistMono.variable}`} suppressHydrationWarning>
      <head>
        {/* Before first paint: the opening shot plays on every load of the home page, never for reduced motion */}
        <script
          dangerouslySetInnerHTML={{
            __html: `try{var h=document.documentElement;if(location.pathname==='/'){h.setAttribute('data-intro',matchMedia('(prefers-reduced-motion: reduce)').matches?'skip':'play')}}catch(e){}`,
          }}
        />
      </head>
      <body>
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[100] focus:rounded-lg focus:bg-accent focus:px-3 focus:py-2 focus:text-accent-ink button-sm"
        >
          Skip to content
        </a>
        {children}
      </body>
    </html>
  );
}
