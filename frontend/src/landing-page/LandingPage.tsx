import AppAppBar from "./components/AppAppBar";
import Hero from "./components/Hero";
import PartnersList from "./components/PartnersList";
import Highlights from "./components/Highlights";
import Pricing from "./components/Pricing";
import Features from "./components/Features";
import Testimonials from "./components/Testimonials";
import FAQ from "./components/FAQ";
import Footer from "./components/Footer";
import MasterAIAgent from "./components/MasterAIAgent";

export default function MarketingPage() {
  return (
    <main className="min-h-screen bg-background text-foreground">
      <AppAppBar />
      <Hero />
      <PartnersList />
      <Features />
      <Testimonials />
      <Highlights />
      <Pricing />
      <FAQ />
      <Footer />
      <MasterAIAgent />
    </main>
  );
}
