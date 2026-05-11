import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";

const userTestimonials = [
  {
    name: "Nadia R.",
    role: "Salon owner",
    quote: "The value is not another dashboard. It is having the front desk questions handled before they become interruptions.",
    outcome: "Fewer walk-in questions",
  },
  {
    name: "Marcus T.",
    role: "Barber shop operator",
    quote: "Customers understand where they are in line, and staff can stay focused on the chair.",
    outcome: "Clearer queue flow",
  },
  {
    name: "Elena P.",
    role: "Clinic manager",
    quote: "The approval flow is the part that matters. The assistant can suggest, but we still decide.",
    outcome: "Controlled automation",
  },
];

export default function Testimonials({ embedded = false }: { embedded?: boolean }) {
  return (
    <section id="testimonials" className={embedded ? "py-2" : "border-b py-16 sm:py-24"}>
      <div className={embedded ? "flex flex-col gap-5" : "mx-auto flex max-w-7xl flex-col gap-8 px-4 sm:px-6 lg:px-8"}>
        <div className="max-w-3xl">
          <p className="text-sm font-semibold uppercase text-primary">Testimonials</p>
          <h2 className="mt-2 text-3xl font-black sm:text-4xl">A calmer operating rhythm for busy service teams.</h2>
        </div>
        <div className="grid gap-4 lg:grid-cols-3">
          {userTestimonials.map((testimonial) => (
            <Card key={testimonial.name}>
              <CardHeader className="flex-row items-center gap-3">
                <Avatar>
                  <AvatarFallback>{testimonial.name.split(" ").map((part) => part[0]).join("").slice(0, 2)}</AvatarFallback>
                </Avatar>
                <div>
                  <p className="font-bold">{testimonial.name}</p>
                  <p className="text-sm text-muted-foreground">{testimonial.role}</p>
                </div>
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                <p className="text-sm leading-6 text-muted-foreground">"{testimonial.quote}"</p>
                <Badge variant="secondary" className="w-fit">{testimonial.outcome}</Badge>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </section>
  );
}
