import type { Metadata } from 'next';
import LegalShell from '@/components/LegalShell';

export const metadata: Metadata = { title: 'Terms | AeroSentinel', description: 'Terms of use for AeroSentinel.' };

export default function Terms() {
  return (
    <LegalShell title="Terms of use" updated="13 November 2026">
      <p>AeroSentinel is released under the MIT License and provided as is, without warranty of any kind.</p>
      <h2>Decision support only</h2>
      <ul>
        <li>AeroSentinel is not a certified airworthiness determination.</li>
        <li>It must not be used for real time, in flight safety decisions.</li>
        <li>It does not replace certified maintenance procedures. Forecasts inform human review and never trigger maintenance action on their own.</li>
      </ul>
      <h2>Results</h2>
      <p>Forecasts come from simulations and laboratory test rigs, not aircraft in service. Risk band limits are a design choice, not a regulatory standard. Suggested actions in the console are guidance built on the model’s outputs.</p>
    </LegalShell>
  );
}
