import { Bot, CalendarDays, ClipboardCheck, Headphones, MessagesSquare, Users } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const items = [
  {
    icon: Headphones,
    title: "AI Receptionist",
    body: "Answers service questions, helps customers join queues, books appointments, and keeps wait-time context close.",
  },
  {
    icon: Bot,
    title: "Supervisor Agent",
    body: "Routes owner requests to receptionist, finance, and HR agents while keeping the shop owner in control.",
  },
  {
    icon: ClipboardCheck,
    title: "Human approvals",
    body: "Queue closures, schedule changes, refunds, and other sensitive actions can require explicit owner approval.",
  },
  {
    icon: CalendarDays,
    title: "Appointments",
    body: "Customers can move from a conversation into booking without leaving the assisted flow.",
  },
  {
    icon: Users,
    title: "Queue awareness",
    body: "The same agent can explain positions, wait estimates, live service state, and next steps.",
  },
  {
    icon: MessagesSquare,
    title: "Owner workspace",
    body: "The dashboard is a working inbox for updates, proposed actions, chat, and operational visibility.",
  },
];

export default function Features({ embedded = false }: { embedded?: boolean }) {
  return (
    <section id="features" className={embedded ? "py-2" : "border-b py-16 sm:py-24"}>
      <div className={embedded ? "flex flex-col gap-5" : "mx-auto flex max-w-7xl flex-col gap-8 px-4 sm:px-6 lg:px-8"}>
        <div className="max-w-3xl">
          <p className="text-sm font-semibold uppercase text-primary">Capabilities</p>
          <h2 className="mt-2 text-3xl font-black sm:text-4xl">The shop runs through agents, not scattered tabs.</h2>
          <p className="mt-3 text-muted-foreground">
            ZeroQwait focuses on concrete shop workflows: reception, queues, appointments, approvals, and owner operations.
          </p>
        </div>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {items.map((item) => (
            <Card key={item.title}>
              <CardHeader className="gap-3">
                <item.icon className="size-5 text-primary" />
                <CardTitle className="text-lg">{item.title}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm leading-6 text-muted-foreground">{item.body}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </section>
  );
}
