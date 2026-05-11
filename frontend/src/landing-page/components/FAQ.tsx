import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";

const faqs = [
  {
    question: "Is ZeroQwait only for barbers?",
    answer: "No. The product is built for service businesses where customers need orientation, queues, appointments, and live updates.",
  },
  {
    question: "Does the assistant take actions automatically?",
    answer: "Routine low-risk interactions can be automated, while high-impact operational changes can require owner approval.",
  },
  {
    question: "Can customers join a queue from chat?",
    answer: "Yes. The customer-facing AI receptionist can collect queue details and guide customers through service selection.",
  },
  {
    question: "Does this replace my dashboard?",
    answer: "The goal is to make the dashboard feel like an AI operations workspace, not to remove visibility or owner control.",
  },
];

export default function FAQ({ embedded = false }: { embedded?: boolean }) {
  return (
    <section id="faq" className={embedded ? "py-2" : "border-b py-16 sm:py-24"}>
      <div className={embedded ? "flex flex-col gap-5" : "mx-auto flex max-w-4xl flex-col gap-8 px-4 sm:px-6 lg:px-8"}>
        <div>
          <p className="text-sm font-semibold uppercase text-primary">FAQ</p>
          <h2 className="mt-2 text-3xl font-black sm:text-4xl">Common questions</h2>
        </div>
        <Accordion type="single" collapsible className="w-full">
          {faqs.map((faq, index) => (
            <AccordionItem key={faq.question} value={`item-${index}`}>
              <AccordionTrigger>{faq.question}</AccordionTrigger>
              <AccordionContent>{faq.answer}</AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </div>
    </section>
  );
}
