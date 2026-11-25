'use client';

import dynamic from 'next/dynamic';

/** three.js loads in its own chunk, in parallel with the intro, and never on the server. */
const World = dynamic(() => import('./World'), { ssr: false, loading: () => null });

export default function WorldMount() {
  return <World />;
}
