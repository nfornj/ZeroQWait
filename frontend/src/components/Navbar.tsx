import React, { useState } from "react";
import { Link as RouterLink, useNavigate } from "react-router-dom";
import { Scissors, Search, Menu, X, User, BookOpen } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "./ui/dropdown-menu";
import { Button } from "./ui/button";
import { Avatar, AvatarFallback } from "./ui/avatar";
import { cn } from "../lib/utils";

const Navbar = () => {
  const [mobileOpen, setMobileOpen] = useState(false);
  const { isAuthenticated, user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/");
    setMobileOpen(false);
  };

  const isEmployee = user?.role === "employee";

  return (
    <header className="sticky top-0 z-50 border-b border-border bg-background/95 backdrop-blur">
      <div className="mx-auto flex max-w-screen-xl items-center px-4 py-0 h-16">
        {/* Logo */}
        <RouterLink
          to="/"
          className="flex items-center gap-2 text-foreground no-underline hover:opacity-80 transition-opacity"
        >
          <Scissors className="h-6 w-6 text-primary" />
          <span className="text-xl font-bold tracking-[-0.02em]">ZeroQwait</span>
        </RouterLink>

        <div className="flex-1" />

        {/* Desktop nav */}
        <nav className="hidden md:flex items-center gap-1">
          {!isEmployee && (
            <>
              <RouterLink
                to="/search"
                className="flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
              >
                <Search className="h-4 w-4" />
                Search
              </RouterLink>
              <RouterLink
                to="/pricing"
                className="rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
              >
                Pricing
              </RouterLink>
              <RouterLink
                to="/docs"
                className="flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
              >
                <BookOpen className="h-4 w-4" />
                Docs
              </RouterLink>
            </>
          )}

          {/* User menu */}
          <div className="ml-3">
            {isAuthenticated ? (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button
                    type="button"
                    className={cn(
                      "flex items-center gap-2 rounded-full border border-border px-3 py-1.5 text-sm",
                      "hover:shadow-sm transition-shadow"
                    )}
                  >
                    <User className="h-4 w-4 text-muted-foreground" />
                    <Avatar className="h-6 w-6">
                      <AvatarFallback className="bg-primary text-primary-foreground text-xs">
                        {user?.username?.charAt(0).toUpperCase() || "U"}
                      </AvatarFallback>
                    </Avatar>
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-40">
                  <DropdownMenuItem onClick={handleLogout} className="cursor-pointer">
                    Logout
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            ) : (
              <div className="flex items-center gap-2">
                <Button variant="ghost" size="sm" asChild>
                  <RouterLink to="/login">Log in</RouterLink>
                </Button>
                <Button
                  size="sm"
                  asChild
                  className="bg-gradient-to-r from-rose-500 to-red-500 hover:from-rose-600 hover:to-red-600 text-white"
                >
                  <RouterLink to="/signup">Sign up</RouterLink>
                </Button>
              </div>
            )}
          </div>
        </nav>

        {/* Mobile hamburger */}
        <button
          type="button"
          className="ml-3 flex h-9 w-9 items-center justify-center rounded-lg border border-border md:hidden"
          onClick={() => setMobileOpen((o) => !o)}
          aria-label="Toggle menu"
        >
          {mobileOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
        </button>
      </div>

      {/* Mobile menu */}
      {mobileOpen && (
        <div className="border-t border-border bg-background px-4 py-3 md:hidden">
          <div className="flex flex-col gap-1">
            {!isEmployee && (
              <>
                <RouterLink
                  to="/search"
                  onClick={() => setMobileOpen(false)}
                  className="flex items-center gap-2 rounded-lg px-3 py-2.5 text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
                >
                  <Search className="h-4 w-4" />
                  Search
                </RouterLink>
                <RouterLink
                  to="/pricing"
                  onClick={() => setMobileOpen(false)}
                  className="rounded-lg px-3 py-2.5 text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
                >
                  Pricing
                </RouterLink>
                <RouterLink
                  to="/docs"
                  onClick={() => setMobileOpen(false)}
                  className="flex items-center gap-2 rounded-lg px-3 py-2.5 text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
                >
                  <BookOpen className="h-4 w-4" />
                  Docs
                </RouterLink>
              </>
            )}
            {!isAuthenticated && (
              <>
                <RouterLink
                  to="/login"
                  onClick={() => setMobileOpen(false)}
                  className="rounded-lg px-3 py-2.5 text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
                >
                  Log in
                </RouterLink>
                <RouterLink
                  to="/signup"
                  onClick={() => setMobileOpen(false)}
                  className="rounded-lg px-3 py-2.5 text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
                >
                  Sign up
                </RouterLink>
              </>
            )}
            {isAuthenticated && (
              <button
                type="button"
                onClick={handleLogout}
                className="rounded-lg border-t border-border px-3 py-2.5 text-left text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
              >
                Logout
              </button>
            )}
          </div>
        </div>
      )}
    </header>
  );
};

export default Navbar;
