import { Activity, Clock3, ShieldCheck, Sparkles, Workflow, Zap } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

const highlights = [
  { icon: Activity, title: "Live context", body: "Queue state, shop services, and customer status stay visible to the assistant." },
  { icon: ShieldCheck, title: "Policy-aware", body: "Sensitive operations are designed to pause for owner review before execution." },
  { icon: Workflow, title: "Agent routing", body: "Supervisor routing keeps receptionist, finance, and HR responsibilities clear." },
  { icon: Clock3, title: "Real-time updates", body: "Customers and owners get current queue and wait-time information." },
  { icon: Zap, title: "Fast actions", body: "Common actions are available as buttons but still backed by natural language." },
  { icon: Sparkles, title: "Voice ready", body: "Customer-facing flows can use the existing ASR and Qwen3-TTS voice pipeline." },
];

export default function Highlights() {
  return (
    <section id="highlights" className="border-b bg-muted/30 py-16 sm:py-24">
      <div className="mx-auto flex max-w-7xl flex-col gap-8 px-4 sm:px-6 lg:px-8">
        <div className="max-w-3xl">
          <p className="text-sm font-semibold uppercase text-primary">Operational highlights</p>
          <h2 className="mt-2 text-3xl font-black sm:text-4xl">Designed for one real service business at a time.</h2>
        </div>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {highlights.map((item) => (
            <Card key={item.title}>
              <CardContent className="flex gap-4 p-5">
                <div className="grid size-10 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary">
                  <item.icon className="size-5" />
                </div>
                <div>
                  <p className="font-bold">{item.title}</p>
                  <p className="mt-1 text-sm leading-6 text-muted-foreground">{item.body}</p>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </section>
  );
}
