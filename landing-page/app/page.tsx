import { ArchitectureMap } from "@/components/landing/ArchitectureMap";
import { CapabilityGrid } from "@/components/landing/CapabilityGrid";
import { FAQSection } from "@/components/landing/FAQSection";
import { FinalCTA } from "@/components/landing/FinalCTA";
import { Footer } from "@/components/landing/Footer";
import { Hero } from "@/components/landing/Hero";
import { Highlights } from "@/components/landing/Highlights";
import { RealityBoundary } from "@/components/landing/RealityBoundary";
import { TechStackBoard } from "@/components/landing/TechStackBoard";
import { WorkflowShowcase } from "@/components/landing/WorkflowShowcase";
import { FullPageSlider } from "@/components/landing/FullPageSlider";

export default function Home() {
  const sections = [
    <Hero key="hero" />,
    <CapabilityGrid key="grid" />,
    <ArchitectureMap key="arch1" part={1} />,
    <ArchitectureMap key="arch2" part={2} />,
    <WorkflowShowcase key="flow1" part={1} />,
    <WorkflowShowcase key="flow2" part={2} />,
    <Highlights key="high" />,
    <TechStackBoard key="tech" />,
    <RealityBoundary key="real" />,
    <FAQSection key="faq" />,
    <div key="final" className="flex flex-col h-full w-full">
      <div className="flex-1 flex flex-col justify-center">
        <FinalCTA />
      </div>
      <Footer />
    </div>
  ];

  return (
    <div className="landing-page relative min-h-screen">
      <div className="pointer-events-none absolute inset-x-0 top-0 z-0 h-full w-full bg-[radial-gradient(circle_at_top,rgba(125,211,252,0.2),transparent_55%),radial-gradient(circle_at_80%_10%,rgba(251,191,36,0.12),transparent_30%)]" />
      <div className="pointer-events-none absolute inset-0 z-0 bg-[linear-gradient(rgba(148,163,184,0.08)_1px,transparent_1px),linear-gradient(90deg,rgba(148,163,184,0.08)_1px,transparent_1px)] bg-[size:32px_32px] [mask-image:linear-gradient(to_bottom,rgba(255,255,255,0.8),transparent_92%)]" />

      <main className="relative z-10 w-full h-full">
        <FullPageSlider sections={sections} />
      </main>
    </div>
  );
}
