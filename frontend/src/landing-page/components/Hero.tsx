import { ArrowRight, Bot, CalendarClock, CheckCircle2, MessageSquareText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import FloatingAIOrb from "./FloatingAIOrb";

const stats = [
  { value: "24/7", label: "AI front desk" },
  { value: "10 sec", label: "average answer time" },
  { value: "1 link", label: "queue, booking, updates" },
];

export default function Hero() {
  return (
    <section id="top" className="overflow-hidden border-b">
      <div className="mx-auto grid min-h-[calc(100vh-4rem)] max-w-7xl items-center gap-10 px-4 py-12 sm:px-6 lg:grid-cols-[1fr_0.9fr] lg:px-8 lg:py-16">
        <div className="flex flex-col gap-7">
          <Badge variant="secondary" className="w-fit gap-2 rounded-full px-3 py-1">
            <Bot className="size-3.5" />
            Agent-as-a-Service for service businesses
          </Badge>
          <div className="max-w-3xl">
            <h1 className="text-4xl font-black sm:text-5xl lg:text-6xl">
              ZeroQwait
            </h1>
            <p className="mt-5 text-lg leading-8 text-muted-foreground sm:text-xl">
              An AI receptionist and operations workspace for shops that need queue management, booking, follow-ups, and owner approvals handled from one live agent interface.
            </p>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row">
            <Button size="lg" onClick={() => (window.location.href = "/signup")}>
              Register a shop
              <ArrowRight data-icon="inline-end" />
            </Button>
            <Button
              size="lg"
              variant="outline"
              onClick={() => window.dispatchEvent(new Event("trigger-zeroq-assistant"))}
            >
              <MessageSquareText data-icon="inline-start" />
              Ask ZeroQ
            </Button>
          </div>
          <div className="grid max-w-2xl gap-3 sm:grid-cols-3">
            {stats.map((item) => (
              <div key={item.label} className="rounded-xl border bg-card p-4">
                <p className="text-2xl font-black">{item.value}</p>
                <p className="text-sm text-muted-foreground">{item.label}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="relative">
          <FloatingAIOrb />
          <div className="mt-6 grid gap-4 sm:grid-cols-2">
            <Card>
              <CardContent className="flex flex-col gap-3 p-5">
                <CalendarClock className="size-5 text-primary" />
                <p className="font-bold">Owner approval ready</p>
                <p className="text-sm text-muted-foreground">
                  High-impact changes surface as actions the owner can review before they run.
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="flex flex-col gap-3 p-5">
                <CheckCircle2 className="size-5 text-primary" />
                <p className="font-bold">Customer flow aware</p>
                <p className="text-sm text-muted-foreground">
                  Customers can ask, book, join queues, and check wait times without hunting through screens.
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </section>
  );
}
