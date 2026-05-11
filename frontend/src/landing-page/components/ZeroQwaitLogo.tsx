import { Bot } from "lucide-react";

export default function ZeroQwaitLogo({ className = "" }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2 font-extrabold ${className}`}>
      <span className="inline-flex size-9 items-center justify-center rounded-xl bg-primary text-primary-foreground">
        <Bot className="size-5" aria-hidden="true" />
      </span>
      <span>ZeroQwait</span>
    </span>
  );
}
