import { Badge } from "@/components/ui/badge";

const sectors = [
  { name: "Barber shops", metric: "queues + walk-ins" },
  { name: "Salons", metric: "booking + follow-up" },
  { name: "Clinics", metric: "front desk triage" },
  { name: "Auto shops", metric: "service updates" },
];

export default function PartnersList() {
  return (
    <section className="border-b bg-muted/30 py-10">
      <div className="mx-auto flex max-w-7xl flex-col gap-5 px-4 sm:px-6 lg:px-8">
        <div className="max-w-2xl">
          <p className="text-sm font-semibold uppercase text-muted-foreground">Built for local service operators</p>
          <h2 className="mt-2 text-2xl font-bold">One AI operating layer for the day-to-day work.</h2>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {sectors.map((sector) => (
            <div key={sector.name} className="rounded-xl border bg-card p-4">
              <p className="font-bold">{sector.name}</p>
              <Badge variant="secondary" className="mt-3">{sector.metric}</Badge>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
