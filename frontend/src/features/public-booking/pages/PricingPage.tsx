import React from "react";
import { Link } from "react-router-dom";
import { CheckCircle2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const tiers = [
  {
    name: "Free",
    price: "$0",
    period: "forever",
    features: [
      "Up to 1 shop",
      "AI Receptionist for customer chats",
      "Live queue join page",
      "Appointment booking flow",
      "Shared tenant environment",
      "Email support",
      "Mobile-friendly customer pages",
    ],
    cta: "Get Started",
    to: "/signup",
    highlighted: false,
  },
  {
    name: "Premium",
    price: "$29",
    period: "per month",
    features: [
      "Up to 5 shops",
      "Full AI agent team (Receptionist, Finance, HR)",
      "Human-in-the-Loop approvals",
      "Advanced analytics and revenue reports",
      "Custom branding & colors",
      "Priority support",
      "Owner agent inbox workspace",
    ],
    cta: "Start Free Trial",
    to: "/signup",
    highlighted: true,
  },
  {
    name: "Enterprise",
    price: "Custom",
    period: "contact us",
    features: [
      "Unlimited shops",
      "Dedicated onboarding",
      "Custom support SLA",
      "Private deployment planning",
      "Dedicated account manager",
      "Multi-location rollout support",
    ],
    cta: "Contact Us",
    to: "/signup",
    highlighted: false,
  },
];

const PricingPage: React.FC = () => {
  return (
    <main className="mx-auto flex max-w-6xl flex-col gap-10 px-4 py-12 md:px-6 md:py-16">
      <section className="mx-auto max-w-3xl text-center">
        <h1 className="text-4xl font-bold tracking-tight md:text-5xl">Choose Your Plan</h1>
        <p className="mt-4 text-lg text-muted-foreground">
          Start with an AI receptionist, then expand into a full AI operating team for your shop.
        </p>
      </section>

      <section className="grid gap-6 md:grid-cols-3">
        {tiers.map((tier) => (
          <Card
            key={tier.name}
            className={cn("relative flex flex-col transition hover:-translate-y-1", tier.highlighted && "border-primary shadow-lg")}
          >
            {tier.highlighted && <Badge className="absolute right-4 top-4">Most Popular</Badge>}
            <CardHeader>
              <CardTitle className="text-2xl">{tier.name}</CardTitle>
              <div className="pt-3">
                <span className="text-4xl font-bold">{tier.price}</span>
                <span className="text-muted-foreground"> / {tier.period}</span>
              </div>
            </CardHeader>
            <CardContent className="flex flex-1 flex-col gap-6">
              <ul className="flex flex-1 flex-col gap-3">
                {tier.features.map((feature) => (
                  <li key={feature} className="flex gap-3 text-sm">
                    <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-primary" />
                    <span>{feature}</span>
                  </li>
                ))}
              </ul>
              <Button asChild variant={tier.highlighted ? "default" : "outline"} size="lg">
                <Link to={tier.to}>{tier.cta}</Link>
              </Button>
            </CardContent>
          </Card>
        ))}
      </section>

      <section className="flex flex-col items-center gap-4 text-center">
        <h2 className="text-2xl font-semibold">All plans include:</h2>
        <div className="grid w-full gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {[
            "Public shop page",
            "Live queue status",
            "Appointment booking flow",
            "Mobile-friendly customer experience",
            "No setup fees",
            "Cancel anytime",
          ].map((feature) => (
            <div key={feature} className="flex items-center justify-center gap-2 rounded-lg border bg-card p-3">
              <CheckCircle2 className="size-4 text-primary" />
              <span className="text-sm font-medium">{feature}</span>
            </div>
          ))}
        </div>
      </section>

      <p className="text-center text-sm text-muted-foreground">
        Need a custom plan? <Link className="font-medium text-primary hover:underline" to="/signup">Contact us</Link> for enterprise pricing
      </p>
    </main>
  );
};

export default PricingPage;
