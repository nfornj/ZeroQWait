import React, { useEffect, useState } from "react";
import { Link as RouterLink } from "react-router-dom";
import type { LucideIcon } from "lucide-react";
import {
  ArrowRight,
  Bot,
  Building2,
  CheckCircle2,
  ChevronDown,
  Cpu,
  Database,
  LayoutDashboard,
  LockKeyhole,
  MessageSquareText,
  Rocket,
  ServerCog,
  ShieldCheck,
  Sparkles,
  Waves,
  Workflow,
} from "lucide-react";

type DemoAccount = {
  title: string;
  username?: string;
  email?: string;
  password?: string;
  route: string;
  accent: string;
  summary: string;
  details: string[];
};

type WalkthroughStep = {
  title: string;
  eyebrow: string;
  accent: string;
  description: string;
  bullets: string[];
  statLabel: string;
  statValue: string;
  icon: LucideIcon;
  screenTitle: string;
  screenSubtitle: string;
  primaryMetric: string;
  secondaryMetric: string;
  timeline: string[];
  sidebar: string[];
};

type TechPillar = {
  title: string;
  icon: LucideIcon;
  summary: string;
  items: string[];
};

const demoAccounts: DemoAccount[] = [
  {
    title: "Customer exploration",
    route: "/",
    accent: "from-amber-400/30 via-orange-400/20 to-transparent",
    summary:
      "Start here if you want to experience the AI receptionist, public shop discovery, service search, and voice-first customer flow without logging in.",
    details: [
      "Use the landing page chat to ask about services, pricing, and product capabilities.",
      "Open Search to discover shops and public booking flows.",
      "This mirrors the front-desk experience rather than the owner workspace.",
    ],
  },
  {
    title: "Free-tier owner demo",
    username: "demo_owner_free",
    email: "demo_owner_free@example.com",
    password: "Test123!",
    route: "/login",
    accent: "from-emerald-400/30 via-teal-400/20 to-transparent",
    summary:
      "Use this account to explore the core owner workflow: login, dashboard visibility, queue management, and baseline AI-assisted operations.",
    details: [
      "Represents the shared-runtime experience for a standard service business.",
      "Best for showing the owner dashboard, operational overview, and day-to-day queue flows.",
      "Login accepts either the username or the email shown here.",
    ],
  },
  {
    title: "Premium owner demo",
    username: "demo_owner_premium",
    email: "demo_owner_premium@example.com",
    password: "Test123!",
    route: "/login",
    accent: "from-sky-400/30 via-indigo-400/20 to-transparent",
    summary:
      "Use this account to showcase the richer AI workspace: agent inbox, approval flow, finance and HR-style orchestration, and premium operating posture.",
    details: [
      "Best account for demonstrating the supervisor agent and the operations cockpit story.",
      "Use it when you want to present the system as an AI-managed business workspace.",
      "Login accepts either the username or the email shown here.",
    ],
  },
];

const walkthroughSteps: WalkthroughStep[] = [
  {
    eyebrow: "Step 1",
    title: "Log in as the shop owner",
    accent: "from-rose-500 to-orange-400",
    description:
      "The demo starts at the owner login. Use the free or premium demo account and enter the operations workspace rather than a generic admin panel.",
    bullets: [
      "Open /login and use either the username or email.",
      "The owner session routes into the protected workspace.",
      "This separates public customer surfaces from internal business operations.",
    ],
    statLabel: "Entry point",
    statValue: "/login",
    icon: LockKeyhole,
    screenTitle: "Owner authentication",
    screenSubtitle: "Secure entry into the operations workspace",
    primaryMetric: "2 demo accounts",
    secondaryMetric: "Username or email accepted",
    timeline: ["Open /login", "Enter demo credentials", "Protected owner session starts"],
    sidebar: ["Public receptionist", "Search shops", "Owner login", "Protected routes"],
  },
  {
    eyebrow: "Step 2",
    title: "Read the day from the dashboard",
    accent: "from-orange-400 to-amber-300",
    description:
      "After login, the owner sees the live state of the shop: queues, staffing, revenue context, and operational readiness.",
    bullets: [
      "Use this view to frame the product as an AI operations system.",
      "Show how the interface reduces the need to jump across disconnected tools.",
      "This is the best place to explain the shop context before opening agent flows.",
    ],
    statLabel: "Best story",
    statValue: "Operations cockpit",
    icon: LayoutDashboard,
    screenTitle: "Operational dashboard",
    screenSubtitle: "Queues, revenue posture, staff readiness, and shop context",
    primaryMetric: "Daily overview",
    secondaryMetric: "One operational surface",
    timeline: ["Queue pressure", "Revenue snapshot", "Team readiness"],
    sidebar: ["Overview", "Queues", "Appointments", "Inventory"],
  },
  {
    eyebrow: "Step 3",
    title: "Open the Agent Inbox",
    accent: "from-amber-300 to-lime-300",
    description:
      "The Agent Inbox is where the system becomes visibly differentiated. The owner talks to a supervisor agent that can route work across specialist domains.",
    bullets: [
      "Ask queue, finance, HR, or CRM-style questions.",
      "Use this view to explain LangGraph routing and specialist execution.",
      "The inbox is where AI feels operational instead of purely conversational.",
    ],
    statLabel: "Core UX",
    statValue: "Supervisor + specialists",
    icon: MessageSquareText,
    screenTitle: "Agent Inbox",
    screenSubtitle: "Supervisor-led orchestration with specialist routing",
    primaryMetric: "4 specialist domains",
    secondaryMetric: "Streaming + actions",
    timeline: ["Owner prompt", "Intent classification", "Specialist execution"],
    sidebar: ["Inbox", "Approvals", "Feed", "History"],
  },
  {
    eyebrow: "Step 4",
    title: "Show approval-driven execution",
    accent: "from-lime-300 to-cyan-300",
    description:
      "High-impact actions are intentionally gated. The system pauses, saves state, asks for approval, and resumes from a checkpoint.",
    bullets: [
      "This is the strongest proof that the product is engineered for safe operations.",
      "Approvals are runtime checkpoints, not fake UI toggles.",
      "Use this step to talk about trust, control, and resumability.",
    ],
    statLabel: "Control model",
    statValue: "Human in the loop",
    icon: ShieldCheck,
    screenTitle: "Approval checkpoint",
    screenSubtitle: "Execution pauses, saves state, and resumes safely",
    primaryMetric: "Checkpoint saved",
    secondaryMetric: "Approval required",
    timeline: ["Action proposed", "Checkpoint persisted", "Approve or reject"],
    sidebar: ["Pending approvals", "Decision state", "Resume graph", "Audit trail"],
  },
  {
    eyebrow: "Step 5",
    title: "Present the Agent Brain",
    accent: "from-cyan-300 to-sky-400",
    description:
      "The Agent Brain visualizes how the platform goes beyond chat: learned business patterns, commitments, and recurring schedules become visible operating context.",
    bullets: [
      "Use it to explain SOUL, commitments, and natural-language schedules.",
      "This is a strong differentiator for portfolio conversations.",
      "It shows persistence and follow-through rather than one-shot chat replies.",
    ],
    statLabel: "Brain layer",
    statValue: "Patterns + commitments + schedules",
    icon: Bot,
    screenTitle: "Agent Brain",
    screenSubtitle: "Persistent business context beyond one-shot chat",
    primaryMetric: "SOUL + commitments",
    secondaryMetric: "Recurring schedules",
    timeline: ["Pattern learned", "Commitment tracked", "Schedule registered"],
    sidebar: ["Brain graph", "SOUL", "Commitments", "Schedules"],
  },
  {
    eyebrow: "Step 6",
    title: "Connect the system to real operations",
    accent: "from-sky-400 to-indigo-400",
    description:
      "Finish by showing how voice, notifications, MCP integrations, Odoo, and infrastructure all connect to the product experience.",
    bullets: [
      "Voice, SMS, Telegram, and workflow automation extend the system beyond the browser.",
      "This is the right moment to switch from product demo to technical architecture.",
      "It proves the platform is built as a system, not as a single page demo.",
    ],
    statLabel: "System view",
    statValue: "End-to-end product architecture",
    icon: Rocket,
    screenTitle: "Connected platform",
    screenSubtitle: "Voice, notifications, MCP services, CRM, and infra all converge",
    primaryMetric: "Integrated runtime",
    secondaryMetric: "Product + platform",
    timeline: ["Voice path", "External integrations", "Production deployment"],
    sidebar: ["Voice", "Telegram", "SMS", "Infrastructure"],
  },
];

const technicalPillars: TechPillar[] = [
  {
    title: "Frontend experience layer",
    icon: Sparkles,
    summary:
      "Public customer flows and owner operations use different surfaces so the product can feel focused for each audience.",
    items: [
      "React 18 + TypeScript",
      "MUI, Radix UI, and rich dashboard surfaces",
      "Protected owner workspace, public shop flows, and AI receptionist entry points",
    ],
  },
  {
    title: "Agent orchestration layer",
    icon: Cpu,
    summary:
      "Owner operations are handled by a LangGraph supervisor that routes work across specialist domains and approval checkpoints.",
    items: [
      "Supervisor + receptionist + finance + HR + CRM specialists",
      "Checkpointed execution and resumable approvals",
      "SOUL, commitments, and schedule-driven agent brain workflows",
    ],
  },
  {
    title: "Data and workflow backbone",
    icon: Database,
    summary:
      "State, persistence, and delayed work are handled as real platform concerns rather than temporary UI state.",
    items: [
      "PostgreSQL for business data and checkpoints",
      "Redis for session and cache surfaces",
      "Temporal for recurring and deferred operational workflows",
    ],
  },
  {
    title: "Platform and integrations",
    icon: ServerCog,
    summary:
      "The product connects to external systems through service boundaries that keep execution clearer and safer.",
    items: [
      "Booking, Finance, HR, Odoo, Postgres, and Voice MCP services",
      "NVIDIA NIM as primary LLM provider with local compatibility paths",
      "Whisper ASR, Qwen3-TTS, Odoo CRM, Telegram, and AWS SNS",
    ],
  },
];

const infrastructureHighlights = [
  {
    title: "Local and demo runtime",
    body:
      "A single Docker Compose stack keeps the full demo environment fast to run and easy to validate locally. Frontend, backend, Redis, PostgreSQL, MCP services, Odoo, and optional Temporal all work together under one non-prod path.",
  },
  {
    title: "Production runtime",
    body:
      "Production runs on K3s behind Traefik at zeroqwait.com. Voice services, workflow services, business integrations, and application APIs are separated into operational service boundaries instead of being packed into one process.",
  },
  {
    title: "Tier-aware platform design",
    body:
      "The system is designed for shared free-tier runtime and stronger premium isolation without forking the product codebase. That makes the architecture easier to evolve from startup constraints into a more robust multi-tenant platform.",
  },
];

const quickStart = [
  "Open the AI receptionist on the landing page to see the customer experience.",
  "Use the premium demo account to log into the owner workspace.",
  "Open the dashboard first, then the Agent Inbox, then the Agent Brain.",
  "Use the free-tier demo account to contrast shared-tier operations behavior.",
  "Finish with the infrastructure section below to explain how the product is implemented.",
];

export default function DocsShowcasePage() {
  const [activeStep, setActiveStep] = useState(0);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      setActiveStep((current) => (current + 1) % walkthroughSteps.length);
    }, 4200);

    return () => window.clearInterval(intervalId);
  }, []);

  const currentStep = walkthroughSteps[activeStep];
  const CurrentStepIcon = currentStep.icon;

  return (
    <div className="min-h-screen bg-[#07111f] text-slate-100">
      <div className="relative overflow-hidden border-b border-white/10 bg-[radial-gradient(circle_at_top_left,_rgba(56,189,248,0.22),_transparent_30%),radial-gradient(circle_at_top_right,_rgba(251,146,60,0.16),_transparent_28%),linear-gradient(180deg,#08101d_0%,#0b1322_48%,#07111f_100%)]">
        <div className="absolute inset-0 opacity-30">
          <div className="absolute -left-16 top-20 h-56 w-56 rounded-full bg-cyan-400/20 blur-3xl animate-pulse" />
          <div className="absolute right-0 top-0 h-72 w-72 rounded-full bg-orange-400/15 blur-3xl animate-pulse" />
          <div className="absolute bottom-0 left-1/3 h-60 w-60 rounded-full bg-indigo-400/15 blur-3xl animate-pulse" />
        </div>

        <section className="relative mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8 lg:py-24">
          <div className="grid gap-10 lg:grid-cols-[1.2fr_0.8fr] lg:items-end">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-4 py-2 text-sm text-cyan-100 backdrop-blur">
                <Sparkles className="h-4 w-4 text-cyan-300" />
                Interactive product docs for the live demo application
              </div>

              <h1 className="mt-6 max-w-4xl text-4xl font-semibold leading-tight tracking-[-0.04em] text-white sm:text-5xl lg:text-6xl">
                A guided demo and architecture tour built directly into
                <span className="bg-gradient-to-r from-cyan-300 via-sky-300 to-orange-300 bg-clip-text text-transparent"> ZeroQwait</span>
              </h1>

              <p className="mt-6 max-w-3xl text-lg leading-8 text-slate-300 sm:text-xl">
                This page is designed for live product walkthroughs. It explains what the demo application does, how to log in, what to show after login, how the shop experience works, and how the platform is engineered underneath.
              </p>

              <div className="mt-8 flex flex-wrap gap-3">
                <RouterLink
                  to="/login"
                  className="inline-flex items-center gap-2 rounded-full bg-white px-5 py-3 text-sm font-semibold text-slate-900 transition-transform hover:-translate-y-0.5"
                >
                  Open demo login
                  <ArrowRight className="h-4 w-4" />
                </RouterLink>
                <a
                  href="#walkthrough"
                  className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-5 py-3 text-sm font-semibold text-slate-100 backdrop-blur transition-colors hover:bg-white/10"
                >
                  Watch the login walkthrough
                  <ChevronDown className="h-4 w-4" />
                </a>
                <RouterLink
                  to="/docs/architecture"
                  className="inline-flex items-center gap-2 rounded-full border border-cyan-300/20 bg-cyan-300/10 px-5 py-3 text-sm font-semibold text-cyan-100 transition-colors hover:bg-cyan-300/15"
                >
                  Open deep architecture UI
                  <Workflow className="h-4 w-4" />
                </RouterLink>
              </div>

              <div className="mt-10 grid gap-4 sm:grid-cols-3">
                <div className="rounded-3xl border border-white/10 bg-white/5 p-5 backdrop-blur">
                  <p className="text-sm uppercase tracking-[0.24em] text-slate-400">Public</p>
                  <p className="mt-3 text-2xl font-semibold text-white">AI receptionist</p>
                  <p className="mt-2 text-sm leading-6 text-slate-300">Customer-facing discovery, voice, public shop search, and queue flow.</p>
                </div>
                <div className="rounded-3xl border border-white/10 bg-white/5 p-5 backdrop-blur">
                  <p className="text-sm uppercase tracking-[0.24em] text-slate-400">Owner</p>
                  <p className="mt-3 text-2xl font-semibold text-white">Operations cockpit</p>
                  <p className="mt-2 text-sm leading-6 text-slate-300">Dashboard, agent inbox, approvals, and agent-brain visibility.</p>
                </div>
                <div className="rounded-3xl border border-white/10 bg-white/5 p-5 backdrop-blur">
                  <p className="text-sm uppercase tracking-[0.24em] text-slate-400">Platform</p>
                  <p className="mt-3 text-2xl font-semibold text-white">System architecture</p>
                  <p className="mt-2 text-sm leading-6 text-slate-300">LangGraph, Temporal, MCP services, PostgreSQL, Redis, voice, and K3s.</p>
                </div>
              </div>
            </div>

            <div className="rounded-[2rem] border border-white/10 bg-white/5 p-6 backdrop-blur-xl">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm uppercase tracking-[0.3em] text-slate-400">Demo shop focus</p>
                  <h2 className="mt-2 text-2xl font-semibold text-white">ZeroQ Demo Cuts</h2>
                </div>
                <div className="rounded-full border border-emerald-400/30 bg-emerald-400/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-emerald-200">
                  Demo-ready
                </div>
              </div>

              <p className="mt-5 text-sm leading-7 text-slate-300">
                Use this demo story to frame the application as an AI-first operating system for a service business: customers engage a smart receptionist, owners supervise an AI team, and the platform handles real operational workflows under the hood.
              </p>

              <div className="mt-6 grid gap-3">
                {[
                  "Customer flow: ask questions, search shops, join queues, use voice.",
                  "Owner flow: log in, review operations, use the Agent Inbox, inspect the Agent Brain.",
                  "Architecture flow: explain orchestration, approvals, integrations, and infrastructure.",
                ].map((item) => (
                  <div key={item} className="flex items-start gap-3 rounded-2xl border border-white/10 bg-slate-950/40 p-4">
                    <CheckCircle2 className="mt-0.5 h-5 w-5 text-cyan-300" />
                    <p className="text-sm leading-6 text-slate-200">{item}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>
      </div>

      <section id="access" className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.28em] text-cyan-300">Demo access</p>
            <h2 className="mt-3 text-3xl font-semibold tracking-[-0.03em] text-white">How to enter the application</h2>
          </div>
          <p className="max-w-2xl text-sm leading-7 text-slate-300">
            These are the recommended starting points for live demos. Only demo-safe application credentials are shown here. Production secrets and infrastructure credentials are intentionally not exposed on the public docs page.
          </p>
        </div>

        <div className="mt-8 grid gap-6 lg:grid-cols-3">
          {demoAccounts.map((account) => (
            <div
              key={account.title}
              className="group overflow-hidden rounded-[2rem] border border-white/10 bg-slate-900/70 shadow-[0_20px_80px_rgba(0,0,0,0.25)]"
            >
              <div className={`h-2 bg-gradient-to-r ${account.accent}`} />
              <div className="p-6">
                <h3 className="text-xl font-semibold text-white">{account.title}</h3>
                <p className="mt-3 text-sm leading-7 text-slate-300">{account.summary}</p>

                {(account.username || account.email || account.password) && (
                  <div className="mt-6 rounded-3xl border border-white/10 bg-black/20 p-4">
                    {account.username && (
                      <div className="flex items-center justify-between gap-4 border-b border-white/10 py-2 text-sm text-slate-200">
                        <span className="text-slate-400">Username</span>
                        <span className="font-medium text-white">{account.username}</span>
                      </div>
                    )}
                    {account.email && (
                      <div className="flex items-center justify-between gap-4 border-b border-white/10 py-2 text-sm text-slate-200">
                        <span className="text-slate-400">Email</span>
                        <span className="font-medium text-white">{account.email}</span>
                      </div>
                    )}
                    {account.password && (
                      <div className="flex items-center justify-between gap-4 py-2 text-sm text-slate-200">
                        <span className="text-slate-400">Password</span>
                        <span className="font-medium text-white">{account.password}</span>
                      </div>
                    )}
                  </div>
                )}

                <div className="mt-6 space-y-3">
                  {account.details.map((detail) => (
                    <div key={detail} className="flex items-start gap-3 text-sm leading-6 text-slate-300">
                      <div className="mt-1 h-2.5 w-2.5 rounded-full bg-cyan-300" />
                      <p>{detail}</p>
                    </div>
                  ))}
                </div>

                <RouterLink
                  to={account.route}
                  className="mt-8 inline-flex items-center gap-2 rounded-full border border-white/15 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-white/10"
                >
                  Open {account.route}
                  <ArrowRight className="h-4 w-4" />
                </RouterLink>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section id="walkthrough" className="border-y border-white/10 bg-white/[0.03] py-16">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-sm uppercase tracking-[0.28em] text-cyan-300">Animated walkthrough</p>
              <h2 className="mt-3 text-3xl font-semibold tracking-[-0.03em] text-white">What to show after they log in</h2>
            </div>
            <p className="max-w-2xl text-sm leading-7 text-slate-300">
              This section auto-advances through the ideal live demo sequence. Use it as your talk track while presenting the owner experience.
            </p>
          </div>

          <div className="mt-10 grid gap-8 2xl:grid-cols-[0.9fr_1.1fr] 2xl:items-start">
            <div className="space-y-4">
              {walkthroughSteps.map((step, index) => {
                const StepIcon = step.icon;
                const isActive = index === activeStep;

                return (
                  <button
                    key={step.title}
                    type="button"
                    onClick={() => setActiveStep(index)}
                    className={`w-full rounded-[1.75rem] border p-5 text-left transition-all duration-500 ${
                      isActive
                        ? "border-cyan-300/40 bg-slate-900 shadow-[0_16px_60px_rgba(34,211,238,0.12)]"
                        : "border-white/10 bg-slate-900/50 hover:border-white/20 hover:bg-slate-900/70"
                    }`}
                  >
                    <div className="flex items-start gap-4">
                      <div
                        className={`rounded-2xl p-3 ${
                          isActive ? "bg-cyan-300/15 text-cyan-200" : "bg-white/5 text-slate-300"
                        }`}
                      >
                        <StepIcon className="h-5 w-5" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="text-xs font-semibold uppercase tracking-[0.28em] text-slate-400">{step.eyebrow}</p>
                        <h3 className="mt-2 text-lg font-semibold text-white">{step.title}</h3>
                        <p className="mt-2 text-sm leading-7 text-slate-300">{step.description}</p>
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>

            <div className="relative overflow-hidden rounded-[2rem] border border-white/10 bg-[#081424] p-6 shadow-[0_30px_100px_rgba(0,0,0,0.35)]">
              <div className="absolute inset-x-0 top-0 h-1 bg-white/5">
                <div
                  className={`h-full bg-gradient-to-r ${currentStep.accent} transition-all duration-700`}
                  style={{ width: `${((activeStep + 1) / walkthroughSteps.length) * 100}%` }}
                />
              </div>

              <div className="flex flex-wrap items-center justify-between gap-4 pt-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.28em] text-cyan-300">Live product tour</p>
                  <h3 className="mt-2 text-2xl font-semibold text-white">{currentStep.title}</h3>
                </div>
                <div className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-slate-300">
                  Auto playing
                </div>
              </div>

              <div className="mt-8 grid gap-6 2xl:grid-cols-[minmax(0,1.05fr)_minmax(360px,0.95fr)]">
                <div className="rounded-[1.75rem] border border-white/10 bg-slate-950/55 p-5 transition-all duration-500">
                  <div className="flex items-center justify-between border-b border-white/10 pb-4">
                    <div className="flex items-center gap-3">
                      <div className={`rounded-2xl bg-gradient-to-r ${currentStep.accent} p-3 text-slate-950`}>
                        <CurrentStepIcon className="h-5 w-5" />
                      </div>
                      <div>
                        <p className="text-xs uppercase tracking-[0.28em] text-slate-400">Current scene</p>
                        <p className="mt-1 text-lg font-semibold text-white">{currentStep.eyebrow}</p>
                      </div>
                    </div>
                    <div className="rounded-2xl border border-white/10 px-4 py-3 text-right">
                      <p className="text-xs uppercase tracking-[0.24em] text-slate-400">{currentStep.statLabel}</p>
                      <p className="mt-1 text-base font-semibold text-white">{currentStep.statValue}</p>
                    </div>
                  </div>

                  <div className="mt-5 space-y-4">
                    {currentStep.bullets.map((bullet, index) => (
                      <div
                        key={bullet}
                        className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 transition-all duration-500"
                        style={{ transform: `translateX(${index === 0 ? 0 : 0}px)` }}
                      >
                        <div className="flex items-start gap-3">
                          <div className="mt-1 h-2.5 w-2.5 rounded-full bg-cyan-300" />
                          <p className="text-sm leading-7 text-slate-200">{bullet}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="rounded-[1.75rem] border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.08)_0%,rgba(255,255,255,0.02)_100%)] p-5">
                  <div className="flex items-center justify-between">
                    <p className="text-xs uppercase tracking-[0.28em] text-slate-400">Screen preview</p>
                    <div className="flex items-center gap-2 text-xs text-slate-400">
                      <Waves className="h-4 w-4 text-cyan-300" />
                      animated state
                    </div>
                  </div>

                  <div className="mt-5 rounded-[1.5rem] border border-white/10 bg-[#0a1220] p-4 shadow-inner">
                    <div className="flex items-center justify-between border-b border-white/10 pb-4">
                      <div>
                        <p className="text-sm font-semibold text-white">ZeroQwait Workspace</p>
                        <p className="text-xs uppercase tracking-[0.24em] text-slate-400">{currentStep.title}</p>
                      </div>
                      <div className="flex gap-2">
                        <div className="h-2.5 w-2.5 rounded-full bg-rose-400" />
                        <div className="h-2.5 w-2.5 rounded-full bg-amber-300" />
                        <div className="h-2.5 w-2.5 rounded-full bg-emerald-300" />
                      </div>
                    </div>

                    <div className="mt-4 grid gap-4 2xl:grid-cols-[minmax(240px,0.34fr)_minmax(0,0.66fr)] 2xl:items-start">
                      <div className="rounded-[1.4rem] border border-white/10 bg-slate-950/65 p-4">
                        <div className="flex items-center gap-3 border-b border-white/10 pb-3">
                          <Building2 className="h-5 w-5 text-cyan-300" />
                          <div>
                            <p className="text-sm font-semibold text-white">ZeroQ Demo Cuts</p>
                            <p className="text-xs text-slate-400">Live demo shop profile</p>
                          </div>
                        </div>
                        <div className="mt-4 space-y-2">
                          {currentStep.sidebar.map((item, index) => (
                            <div
                              key={item}
                              className={`rounded-xl px-3 py-2 text-sm transition-all duration-500 ${
                                index === activeStep % currentStep.sidebar.length
                                  ? "bg-cyan-300/15 text-cyan-100 shadow-[0_0_0_1px_rgba(103,232,249,0.22)]"
                                  : "bg-white/[0.03] text-slate-300"
                              }`}
                            >
                              {item}
                            </div>
                          ))}
                        </div>
                      </div>

                      <div className="relative min-w-0 overflow-hidden rounded-[1.4rem] border border-white/10 bg-[linear-gradient(180deg,rgba(10,18,32,0.96)_0%,rgba(6,12,24,0.98)_100%)] p-4">
                        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,_rgba(56,189,248,0.12),_transparent_30%),radial-gradient(circle_at_bottom_left,_rgba(249,115,22,0.12),_transparent_25%)]" />
                        <div className="relative min-h-[28rem]">
                          <div className="grid gap-3 sm:grid-cols-2">
                            <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                              <p className="text-xs uppercase tracking-[0.24em] text-slate-400">Mock screen</p>
                              <p className="mt-2 text-base font-semibold text-white">{currentStep.screenTitle}</p>
                              <p className="mt-2 text-sm leading-6 text-slate-300">{currentStep.screenSubtitle}</p>
                            </div>
                            <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                              <p className="text-xs uppercase tracking-[0.24em] text-slate-400">Narrative</p>
                              <p className="mt-2 text-base font-semibold text-white">What to say live</p>
                              <p className="mt-2 text-sm leading-6 text-slate-300">Explain how the product moves from interface to controlled execution.</p>
                            </div>
                          </div>

                          <div className="mt-4 grid gap-3 sm:grid-cols-2">
                            <div className="rounded-2xl border border-cyan-300/15 bg-cyan-300/10 p-4 transition-all duration-700 docs-float-soft">
                              <p className="text-xs uppercase tracking-[0.24em] text-cyan-100/80">Primary metric</p>
                              <p className="mt-2 text-lg font-semibold text-white">{currentStep.primaryMetric}</p>
                            </div>
                            <div className="rounded-2xl border border-orange-300/15 bg-orange-300/10 p-4 transition-all duration-700 docs-float-soft docs-float-soft-delayed">
                              <p className="text-xs uppercase tracking-[0.24em] text-orange-100/80">Secondary metric</p>
                              <p className="mt-2 text-lg font-semibold text-white">{currentStep.secondaryMetric}</p>
                            </div>
                          </div>

                          <div className="mt-4 rounded-2xl border border-white/10 bg-slate-950/60 p-4">
                            <div className="flex items-center justify-between">
                              <p className="text-xs uppercase tracking-[0.24em] text-slate-400">Animated activity rail</p>
                              <p className="text-xs text-slate-500">Step {activeStep + 1} / {walkthroughSteps.length}</p>
                            </div>
                            <div className="mt-4 space-y-3">
                              {currentStep.timeline.map((item, index) => (
                                <div key={item} className="flex items-center gap-3">
                                  <div className="relative flex h-6 w-6 items-center justify-center">
                                    <div className={`absolute h-6 w-6 rounded-full ${index === 1 ? "bg-cyan-300/18 docs-ping-ring" : "bg-white/5"}`} />
                                    <div className={`relative h-2.5 w-2.5 rounded-full ${index <= activeStep % 3 ? "bg-cyan-300" : "bg-slate-500"}`} />
                                  </div>
                                  <div className={`rounded-xl px-3 py-2 text-sm transition-all duration-500 ${index === 1 ? "bg-white/[0.06] text-white" : "bg-white/[0.03] text-slate-300"}`}>
                                    {item}
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>

                          <div className="mt-4 rounded-2xl border border-white/10 bg-gradient-to-r from-white/[0.06] to-white/[0.02] p-4 transition-all duration-500">
                            <p className="text-xs uppercase tracking-[0.24em] text-slate-400">Talk track</p>
                            <p className="mt-3 text-sm leading-7 text-slate-200">{currentStep.description}</p>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
        <div className="grid gap-8 lg:grid-cols-[0.75fr_1.25fr]">
          <div className="rounded-[2rem] border border-white/10 bg-white/[0.03] p-6">
            <p className="text-sm uppercase tracking-[0.28em] text-cyan-300">How to use the demo</p>
            <h2 className="mt-3 text-3xl font-semibold tracking-[-0.03em] text-white">Your five-minute showcase plan</h2>
            <div className="mt-6 space-y-4">
              {quickStart.map((step, index) => (
                <div key={step} className="flex items-start gap-4 rounded-2xl border border-white/10 bg-slate-900/60 p-4">
                  <div className="flex h-9 w-9 items-center justify-center rounded-full bg-white text-sm font-semibold text-slate-900">
                    {index + 1}
                  </div>
                  <p className="text-sm leading-7 text-slate-200">{step}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="grid gap-6 md:grid-cols-2">
            {technicalPillars.map((pillar) => {
              const Icon = pillar.icon;

              return (
                <div key={pillar.title} className="rounded-[2rem] border border-white/10 bg-slate-900/60 p-6">
                  <div className="flex items-center gap-3">
                    <div className="rounded-2xl bg-cyan-300/10 p-3 text-cyan-200">
                      <Icon className="h-5 w-5" />
                    </div>
                    <h3 className="text-xl font-semibold text-white">{pillar.title}</h3>
                  </div>
                  <p className="mt-4 text-sm leading-7 text-slate-300">{pillar.summary}</p>
                  <div className="mt-5 space-y-3">
                    {pillar.items.map((item) => (
                      <div key={item} className="flex items-start gap-3 text-sm leading-6 text-slate-200">
                        <div className="mt-1 h-2.5 w-2.5 rounded-full bg-cyan-300" />
                        <p>{item}</p>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      <section className="border-t border-white/10 bg-[#060d18] py-16">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-sm uppercase tracking-[0.28em] text-cyan-300">Infrastructure and technical detail</p>
              <h2 className="mt-3 text-3xl font-semibold tracking-[-0.03em] text-white">How the product is engineered</h2>
            </div>
            <p className="max-w-2xl text-sm leading-7 text-slate-300">
              Use this section when you want to switch from the product walkthrough into the system design story: architecture, data boundaries, AI orchestration, and deployment model.
            </p>
          </div>

          <div className="mt-8 grid gap-6 lg:grid-cols-3">
            {infrastructureHighlights.map((highlight) => (
              <div key={highlight.title} className="rounded-[2rem] border border-white/10 bg-white/[0.03] p-6">
                <h3 className="text-xl font-semibold text-white">{highlight.title}</h3>
                <p className="mt-4 text-sm leading-7 text-slate-300">{highlight.body}</p>
              </div>
            ))}
          </div>

          <div className="mt-8 rounded-[2rem] border border-cyan-300/10 bg-[linear-gradient(135deg,rgba(10,18,32,0.92)_0%,rgba(8,23,39,0.96)_100%)] p-6 shadow-[0_20px_80px_rgba(0,0,0,0.3)]">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div>
                <p className="text-sm uppercase tracking-[0.28em] text-cyan-300">Deep technical view</p>
                <h3 className="mt-2 text-2xl font-semibold text-white">Open the dedicated architecture route</h3>
                <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-300">
                  The main docs page is optimized for product storytelling. The separate architecture route is optimized for infrastructure layers, runtime boundaries, service topology, and deployment paths.
                </p>
              </div>
              <RouterLink
                to="/docs/architecture"
                className="inline-flex items-center gap-2 rounded-full bg-white px-5 py-3 text-sm font-semibold text-slate-900 transition-transform hover:-translate-y-0.5"
              >
                Open /docs/architecture
                <ArrowRight className="h-4 w-4" />
              </RouterLink>
            </div>
          </div>

          <div className="mt-8 grid gap-6 lg:grid-cols-[1.05fr_0.95fr]">
            <div className="rounded-[2rem] border border-white/10 bg-slate-900/60 p-6">
              <p className="text-sm uppercase tracking-[0.28em] text-slate-400">Architecture layers</p>
              <div className="mt-6 space-y-4">
                {[
                  {
                    title: "Experience layer",
                    body: "Landing-page receptionist, public booking surfaces, owner dashboard, agent inbox, and agent brain.",
                  },
                  {
                    title: "Application layer",
                    body: "FastAPI APIs for public flows, owner-agent execution, voice, auth, shops, queues, analytics, and uploads.",
                  },
                  {
                    title: "Agent runtime",
                    body: "LangGraph supervisor, specialist agents, approval checkpoints, and checkpointed conversation state.",
                  },
                  {
                    title: "Service layer",
                    body: "Booking, Finance, HR, Odoo, Postgres, and Voice MCP services plus Temporal-driven workflow execution.",
                  },
                  {
                    title: "State and integration layer",
                    body: "PostgreSQL, Redis, Odoo, NVIDIA NIM, Whisper ASR, Qwen3-TTS, Telegram, and AWS SNS.",
                  },
                ].map((layer, index) => (
                  <div key={layer.title} className="relative overflow-hidden rounded-[1.5rem] border border-white/10 bg-[#0a1220] p-5">
                    <div className="absolute inset-y-0 left-0 w-1 bg-gradient-to-b from-cyan-300 via-sky-400 to-orange-300" />
                    <div className="pl-4">
                      <p className="text-xs uppercase tracking-[0.24em] text-slate-400">Layer {index + 1}</p>
                      <h3 className="mt-2 text-lg font-semibold text-white">{layer.title}</h3>
                      <p className="mt-2 text-sm leading-7 text-slate-300">{layer.body}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-[2rem] border border-white/10 bg-slate-900/60 p-6">
              <p className="text-sm uppercase tracking-[0.28em] text-slate-400">Why this architecture matters</p>
              <div className="mt-6 space-y-4">
                {[
                  {
                    title: "It presents AI as operations, not novelty.",
                    icon: Bot,
                    body: "The owner experience is designed around control, workflow, and visibility rather than a generic chat prompt.",
                  },
                  {
                    title: "It keeps business actions bounded.",
                    icon: ShieldCheck,
                    body: "MCP service boundaries and approval checkpoints make operational execution easier to reason about and safer to scale.",
                  },
                  {
                    title: "It supports continuity.",
                    icon: Database,
                    body: "Checkpoints, commitments, and scheduled workflows allow the system to persist state and follow through over time.",
                  },
                  {
                    title: "It is built for growth.",
                    icon: Building2,
                    body: "The platform supports shared free-tier runtime today and a stronger premium isolation model without rewriting the product.",
                  },
                ].map((item) => {
                  const Icon = item.icon;

                  return (
                    <div key={item.title} className="rounded-[1.5rem] border border-white/10 bg-[#0a1220] p-5">
                      <div className="flex items-center gap-3">
                        <div className="rounded-2xl bg-cyan-300/10 p-3 text-cyan-200">
                          <Icon className="h-5 w-5" />
                        </div>
                        <h3 className="text-lg font-semibold text-white">{item.title}</h3>
                      </div>
                      <p className="mt-4 text-sm leading-7 text-slate-300">{item.body}</p>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}