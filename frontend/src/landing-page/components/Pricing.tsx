import { CheckCircle2, Sparkles } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const tiers = [
  {
    name: "Starter",
    price: "$49",
    period: "month",
    description: "For one location validating AI-assisted reception.",
    features: ["AI receptionist chat", "Queue join flow", "Basic owner dashboard", "Email support"],
  },
  {
    name: "Growth",
    price: "$149",
    period: "month",
    description: "For shops ready to run daily operations through agents.",
    features: ["Everything in Starter", "Appointments", "Owner approvals", "Agent inbox", "Voice-ready customer flow"],
    highlighted: true,
  },
  {
    name: "Operations",
    price: "Custom",
    period: "plan",
    description: "For multi-role service teams that need deeper rollout support.",
    features: ["Custom workflows", "Priority setup", "Advanced analytics", "Policy configuration", "Dedicated support"],
  },
];

export default function Pricing({ embedded = false }: { embedded?: boolean }) {
  return (
    <section id="pricing" className={embedded ? "py-2" : "border-b py-16 sm:py-24"}>
      <div className={embedded ? "flex flex-col gap-6" : "mx-auto flex max-w-7xl flex-col gap-8 px-4 sm:px-6 lg:px-8"}>
        <div className="max-w-3xl">
          <p className="text-sm font-semibold uppercase text-primary">Pricing</p>
          <h2 className="mt-2 text-3xl font-black sm:text-4xl">Start with one shop workflow, then expand.</h2>
          <p className="mt-3 text-muted-foreground">
            Plans are structured around practical service-business operations rather than generic AI seats.
          </p>
        </div>
        <div className="grid gap-4 lg:grid-cols-3">
          {tiers.map((tier) => (
            <Card key={tier.name} className={cn("relative flex flex-col", tier.highlighted && "border-primary shadow-md")}>
              {tier.highlighted && (
                <Badge className="absolute right-4 top-4 gap-1">
                  <Sparkles className="size-3" />
                  Popular
                </Badge>
              )}
              <CardHeader>
                <CardTitle>{tier.name}</CardTitle>
                <p className="text-sm text-muted-foreground">{tier.description}</p>
                <div className="pt-3">
                  <span className="text-4xl font-black">{tier.price}</span>
                  <span className="text-muted-foreground"> / {tier.period}</span>
                </div>
              </CardHeader>
              <CardContent className="flex flex-1 flex-col gap-5">
                <ul className="flex flex-1 flex-col gap-3">
                  {tier.features.map((feature) => (
                    <li key={feature} className="flex gap-2 text-sm">
                      <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-primary" />
                      <span>{feature}</span>
                    </li>
                  ))}
                </ul>
                <Button variant={tier.highlighted ? "default" : "outline"} onClick={() => (window.location.href = "/signup")}>
                  Register a shop
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </section>
  );
}
