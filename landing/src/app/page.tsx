import Nav from '@/components/Nav';
import Intro, { INTRO_SCRIPT } from '@/components/Intro';
import WorldMount from '@/components/world/WorldMount';
import Hero from '@/components/Hero';
import Dive from '@/components/Dive';
import Problem from '@/components/Problem';
import Answers from '@/components/Answers';
import Tagline from '@/components/Tagline';
import HowItWorks from '@/components/HowItWorks';
import Components from '@/components/Components';
import ConsoleShowcase from '@/components/ConsoleShowcase';
import Evaluation from '@/components/Evaluation';
import Faq from '@/components/Faq';
import Footer, { FinalCta } from '@/components/Footer';
import Altimeter from '@/components/Altimeter';
import ScrollDirector from '@/components/ScrollDirector';

export default function Home() {
  return (
    <>
      {/* Decides before first paint whether the intro plays (hard loads only, never with reduced motion) */}
      <script dangerouslySetInnerHTML={{ __html: INTRO_SCRIPT }} />
      <Intro />
      <WorldMount />
      <Nav />
      <Altimeter />
      <main id="main">
        <Hero />
        <Dive />
        <Problem />
        <Answers />
        <Tagline />
        <HowItWorks />
        <Components />
        <ConsoleShowcase />
        <Evaluation />
        <Faq />
        <FinalCta />
      </main>
      <Footer />
      <ScrollDirector />
    </>
  );
}
