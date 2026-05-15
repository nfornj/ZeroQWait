import { cn } from "@/lib/utils";

export default function Copyright({ className }: { className?: string }) {
  return (
    <p className={cn("text-center text-sm text-muted-foreground", className)}>
      Copyright ©{" "}
      <a href="https://zeroqwait.com" className="underline-offset-4 hover:underline">
        ZeroQwait
      </a>{" "}
      {new Date().getFullYear()}.
    </p>
  );
}
