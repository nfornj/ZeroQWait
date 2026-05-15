import React from "react";
import { Link as RouterLink } from "react-router-dom";
import {
  Activity,
  ArrowUpRight,
  BarChart3,
  CalendarRange,
  ExternalLink,
  Sparkles,
  UsersRound,
} from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import Header from "../components/Header";
import MainGrid from "../components/MainGrid";

const overviewSections = [
  { href: "#overview-metrics", label: "Snapshot", sub: "Visits and wait times", icon: Activity },
  { href: "#overview-trends", label: "Trends", sub: "Daily and monthly charts", icon: BarChart3 },
  { href: "#recent-visits", label: "Visits", sub: "Completed service history", icon: CalendarRange },
  { href: "#team-context", label: "Team", sub: "Staff and audience context", icon: UsersRound },
];

const ShopDashboardPage: React.FC = () => {
  return (
    <div
      className="flex min-h-full w-full flex-col bg-[#f9fafb] px-3 pb-16 md:px-6"
      style={{
        "--background": "210 20% 98%",
        "--foreground": "222 47% 11%",
        "--card": "0 0% 100%",
        "--card-foreground": "222 47% 11%",
        "--popover": "0 0% 100%",
        "--popover-foreground": "222 47% 11%",
        "--muted": "210 40% 96%",
        "--muted-foreground": "215 16% 47%",
        "--border": "214 32% 91%",
        "--input": "214 32% 91%",
        "--primary": "154 40% 30%",
        "--primary-foreground": "0 0% 100%",
        "--ring": "154 40% 30%",
        "--chart-1": "#2d6a4f",
        "--chart-2": "#0ea5a3",
        "--chart-3": "#38bdf8",
        "--chart-4": "#f59e0b",
        "--chart-5": "#64748b",
      } as React.CSSProperties}
    >
      <Header />

      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Operations overview</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Historic shop performance, service history, and staffing context.
          </p>
        </div>
        <Button asChild className="w-full rounded-xl bg-primary text-primary-foreground shadow-none hover:bg-primary/90 sm:w-auto">
          <RouterLink to="/dashboard">
            Open live dashboard
            <ExternalLink data-icon="inline-end" />
          </RouterLink>
        </Button>
      </div>

      <nav className="mb-6 rounded-2xl border border-border bg-card p-1.5">
        <div className="grid grid-cols-1 gap-1 sm:grid-cols-2 xl:grid-cols-4">
          {overviewSections.map((item, index) => {
            const Icon = item.icon;
            return (
              <a
                key={item.href}
                href={item.href}
                className="relative flex items-center gap-3 rounded-xl px-4 py-3.5 text-left transition-all hover:bg-muted/45"
              >
                <span className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full border border-border bg-background text-muted-foreground">
                  <Icon className="h-4 w-4" />
                </span>
                <span className="min-w-0">
                  <span className="block truncate text-sm font-semibold text-foreground">{item.label}</span>
                  <span className="block truncate text-xs text-muted-foreground">{item.sub}</span>
                </span>
                {index === 0 && <span className="absolute bottom-0 left-4 right-4 h-0.5 rounded-full bg-primary" />}
              </a>
            );
          })}
        </div>
      </nav>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <Card className="rounded-2xl border-border bg-card shadow-none lg:col-span-8">
          <CardContent className="p-6">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div>
                <div className="inline-flex items-center gap-2 rounded-full border border-border bg-background px-3 py-1 text-xs font-semibold text-muted-foreground">
                  <Sparkles className="h-3.5 w-3.5 text-primary" />
                  Analytics workspace
                </div>
                <h2 className="mt-4 text-2xl font-bold tracking-tight text-foreground">Operations Dashboard</h2>
                <p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">
                  Review completed visits, service demand, revenue mix, and team activity in one focused workspace.
                </p>
              </div>
              <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
                <ArrowUpRight className="h-5 w-5" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Alert className="flex h-full items-center rounded-2xl border-border bg-card px-5 py-4 shadow-none lg:col-span-4">
          <AlertDescription className="text-sm leading-6 text-foreground">
            Use the live dashboard for today view, operations summaries, and agent orchestration. This page remains
            the historical analytics workspace.
          </AlertDescription>
        </Alert>
      </div>

      <MainGrid />
    </div>
  );
};

export default ShopDashboardPage;
