import { PHASE_DEVELOPMENT_SERVER } from 'next/constants.js';

/** @type {(phase: string) => import('next').NextConfig} */
export default function config(phase) {
  return {
    output: 'export',
    trailingSlash: true,
    images: { unoptimized: true },
    reactStrictMode: true,
    // A stray lockfile sits in a parent folder; pin the project root here.
    outputFileTracingRoot: import.meta.dirname,
    // The dev server keeps its own cache, so running `next build` (which uses
    // .next and exports to out/) never breaks a running `next dev`.
    ...(phase === PHASE_DEVELOPMENT_SERVER ? { distDir: process.env.NEXT_DIST_DIR || '.next-dev' } : {}),
  };
}
