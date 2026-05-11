import { Code2, Mail, MessageSquareText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import ZeroQwaitLogo from "./ZeroQwaitLogo";

const footerSections = [
  {
    title: "Product",
    links: [
      { label: "Features", href: "#features" },
      { label: "Testimonials", href: "#testimonials" },
      { label: "Highlights", href: "#highlights" },
      { label: "Pricing", href: "#pricing" },
      { label: "FAQ", href: "#faq" },
    ],
  },
  {
    title: "Account",
    links: [
      { label: "Register", href: "/signup" },
      { label: "Sign in", href: "/login" },
      { label: "Search shops", href: "/search" },
    ],
  },
];

function Copyright() {
  return <p className="text-xs text-muted-foreground">Copyright {new Date().getFullYear()} ZeroQwait. All rights reserved.</p>;
}

export default function Footer() {
  return (
    <footer className="bg-muted/30">
      <div className="mx-auto grid max-w-7xl gap-10 px-4 py-12 sm:px-6 lg:grid-cols-[1.2fr_1fr_1fr] lg:px-8">
        <div className="flex flex-col gap-4">
          <ZeroQwaitLogo className="text-lg" />
          <p className="max-w-sm text-sm leading-6 text-muted-foreground">
            AI receptionist and owner operations workspace for practical service businesses.
          </p>
          <div className="flex gap-2">
            <Button variant="outline" size="icon" aria-label="GitHub">
              <Code2 />
            </Button>
            <Button variant="outline" size="icon" aria-label="Email">
              <Mail />
            </Button>
            <Button
              variant="outline"
              size="icon"
              aria-label="Ask ZeroQ"
              onClick={() => window.dispatchEvent(new Event("trigger-zeroq-assistant"))}
            >
              <MessageSquareText />
            </Button>
          </div>
        </div>

        {footerSections.map((section) => (
          <div key={section.title}>
            <p className="font-bold">{section.title}</p>
            <ul className="mt-3 flex flex-col gap-2 text-sm text-muted-foreground">
              {section.links.map((link) => (
                <li key={link.label}>
                  <a href={link.href} className="hover:text-foreground hover:underline">
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        ))}

        <div className="lg:col-span-3">
          <div className="flex flex-col gap-3 rounded-xl border bg-card p-4 sm:flex-row sm:items-center">
            <div className="flex-1">
              <p className="font-bold">Get product updates</p>
              <p className="text-sm text-muted-foreground">Follow the migration from queue SaaS to AI operations workspace.</p>
            </div>
            <div className="flex min-w-0 gap-2 sm:w-[360px]">
              <Input type="email" placeholder="you@example.com" aria-label="Email address" />
              <Button>Subscribe</Button>
            </div>
          </div>
        </div>

        <div className="border-t pt-5 lg:col-span-3">
          <Copyright />
        </div>
      </div>
    </footer>
  );
}
