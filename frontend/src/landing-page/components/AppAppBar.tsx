import * as React from "react";
import { Bot, Menu } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { useAuth } from "../../contexts/AuthContext";
import ZeroQwaitLogo from "./ZeroQwaitLogo";

const navItems = [
  { label: "Features", id: "features" },
  { label: "Testimonials", id: "testimonials" },
  { label: "Highlights", id: "highlights" },
  { label: "Pricing", id: "pricing" },
  { label: "FAQ", id: "faq" },
];

export default function AppAppBar() {
  const { user } = useAuth();

  const scrollToSection = (id: string) => {
    const element = document.getElementById(id);
    element?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const openAssistant = () => {
    window.dispatchEvent(new Event("trigger-zeroq-assistant"));
  };

  const handleSignIn = () => {
    window.location.href = user ? "/dashboard" : "/login";
  };

  const handleSignUp = () => {
    window.location.href = "/signup";
  };

  return (
    <header className="sticky top-0 z-40 border-b bg-background/80 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <button type="button" onClick={() => scrollToSection("top")} className="text-left">
          <ZeroQwaitLogo className="text-lg" />
        </button>

        <nav className="hidden items-center gap-1 md:flex">
          {navItems.map((item) => (
            <Button key={item.id} variant="ghost" size="sm" onClick={() => scrollToSection(item.id)}>
              {item.label}
            </Button>
          ))}
        </nav>

        <div className="hidden items-center gap-2 md:flex">
          <Button variant="outline" size="sm" onClick={openAssistant}>
            <Bot data-icon="inline-start" />
            Ask ZeroQ
          </Button>
          <Button variant="ghost" size="sm" onClick={handleSignIn}>
            Sign in
          </Button>
          <Button size="sm" onClick={handleSignUp}>
            Register a shop
          </Button>
        </div>

        <div className="md:hidden">
          <Sheet>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon" aria-label="Open menu">
                <Menu />
              </Button>
            </SheetTrigger>
            <SheetContent className="w-[300px]">
              <SheetHeader>
                <SheetTitle className="sr-only">ZeroQwait navigation</SheetTitle>
              </SheetHeader>
              <div className="mt-8 flex flex-col gap-2">
                {navItems.map((item) => (
                  <SheetClose asChild key={item.id}>
                    <Button variant="ghost" className="justify-start" onClick={() => scrollToSection(item.id)}>
                      {item.label}
                    </Button>
                  </SheetClose>
                ))}
                <div className="my-3 h-px bg-border" />
                <SheetClose asChild>
                  <Button variant="outline" onClick={openAssistant}>
                    <Bot data-icon="inline-start" />
                    Ask ZeroQ
                  </Button>
                </SheetClose>
                <SheetClose asChild>
                  <Button variant="ghost" onClick={handleSignIn}>
                    Sign in
                  </Button>
                </SheetClose>
                <SheetClose asChild>
                  <Button onClick={handleSignUp}>Register a shop</Button>
                </SheetClose>
              </div>
            </SheetContent>
          </Sheet>
        </div>
      </div>
    </header>
  );
}
