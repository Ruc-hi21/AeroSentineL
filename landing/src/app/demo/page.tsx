import type { Metadata } from 'next';
import DemoRedirect from './DemoRedirect';

export const metadata: Metadata = {
  title: 'Opening the live demo | AeroSentinel',
  robots: { index: false },
};

export default function DemoPage() {
  return <DemoRedirect />;
}
