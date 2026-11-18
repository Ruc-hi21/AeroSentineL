import type { Metadata } from 'next';
import LegalShell from '@/components/LegalShell';

export const metadata: Metadata = { title: 'Privacy | AeroSentinel', description: 'How AeroSentinel handles your information.' };

export default function Privacy() {
  return (
    <LegalShell title="Privacy notice" updated="13 November 2026">
      <p>AeroSentinel is a capstone project by Group 88. This notice explains what the website and the console do with information.</p>
      <h2>This website</h2>
      <p>The site sets no advertising or analytics cookies. If you sign in, your email is kept only in your own browser so the console can greet you; it is not sent to us.</p>
      <h2>Files you upload to the console</h2>
      <p>Sensor files are processed in memory to produce forecasts and are not used for anything else. Do not upload data you are not allowed to share.</p>
      <h2>Contact</h2>
      <p>Questions about privacy can be raised on the project’s GitHub repository.</p>
    </LegalShell>
  );
}
