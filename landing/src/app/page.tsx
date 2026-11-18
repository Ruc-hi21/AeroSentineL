import Nav from '@/components/Nav';
import Hero from '@/components/Hero';
import Problem from '@/components/Problem';
import Answers from '@/components/Answers';
import Tagline from '@/components/Tagline';
import HowItWorks from '@/components/HowItWorks';
import Components from '@/components/Components';
import ConsoleShowcase from '@/components/ConsoleShowcase';
import Evaluation from '@/components/Evaluation';
import Faq from '@/components/Faq';
import Footer, { FinalCta } from '@/components/Footer';

export default function Home() {
  return (
    <>
      <Nav />
      <main id="main">
        <Hero />
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
    </>
  );
}
