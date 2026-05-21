import React, { useMemo, useState } from "react";
import { Link as RouterLink } from "react-router-dom";
import type { LucideIcon } from "lucide-react";
import {
  ArrowRight,
  Bot,
  BrainCircuit,
  Building2,
  CheckCircle2,
  Cloud,
  Cpu,
  Database,
  GitBranch,
  Layers3,
  MessagesSquare,
  Mic,
  ServerCog,
  ShieldCheck,
  TimerReset,
  Workflow,
} from "lucide-react";

type LayerCard = {
  title: string;
  icon: LucideIcon;
  summary: string;
  chips: string[];
};

type FlowStep = {
  title: string;
  eyebrow: string;
  body: string;
  icon: LucideIcon;
  accent: string;
};

const layers: LayerCard[] = [
  {
    title: "Experience layer",
    icon: MessagesSquare,
    summary: "Customer AI receptionist, public booking surfaces, owner dashboard, agent inbox, and agent brain.",
    chips: ["Landing page", "Public booking", "Owner dashboard", "Agent inbox", "Agent brain"],
  },
  {
    title: "Application layer",
    icon: Layers3,
    summary: "FastAPI routes for auth, shops, queues, analytics, legacy customer chat, owner-agent execution, and voice.",
    chips: ["/api/agent/master", "/api/v2/agent", "/api/voice", "Auth", "Analytics"],
  },
  {
    title: "Agent runtime",
    icon: Bot,
    summary: "LangGraph supervisor orchestration, specialist execution, approval checkpoints, and persistent agent state.",
    chips: ["Supervisor", "Receptionist", "Finance", "HR", "CRM"],
  },
  {
    title: "Workflow and memory",
    icon: TimerReset,
    summary: "SOUL, commitments, schedules, and Temporal-backed operational follow-through.",
    chips: ["SOUL", "Commitments", "Schedules", "Temporal", "Checkpoint resume"],
  },
  {
    title: "Service boundaries",
    icon: ServerCog,
    summary: "MCP services isolate business actions and integrations from the agent runtime.",
    chips: ["Booking MCP", "Finance MCP", "HR MCP", "Odoo MCP", "Voice MCP"],
  },
  {
    title: "State and integrations",
    icon: Database,
    summary: "PostgreSQL, Redis, Odoo, NVIDIA NIM, ASR, TTS, Telegram, and AWS SNS complete the platform system.",
    chips: ["PostgreSQL", "Redis", "NVIDIA NIM", "Odoo", "SNS"],
  },
];

const flowSteps: FlowStep[] = [
  {
    eyebrow: "1. Entry",
    title: "Owner request enters the system",
    body: "The owner sends a message from the protected workspace. The backend authenticates the user, verifies shop ownership, and constructs tenant-scoped agent state.",
    icon: ShieldCheck,
    accent: "from-cyan-300 to-sky-400",
  },
  {
    eyebrow: "2. Orchestration",
    title: "Supervisor classifies and routes work",
    body: "The LangGraph supervisor decides whether the request belongs to receptionist, finance, HR, CRM, or a direct supervisory response.",
    icon: BrainCircuit,
    accent: "from-sky-400 to-indigo-400",
  },
  {
    eyebrow: "3. Execution",
    title: "Specialists execute through service boundaries",
    body: "Business actions are performed through MCP services and integration layers instead of unconstrained direct writes scattered across the agent code.",
    icon: Workflow,
    accent: "from-indigo-400 to-violet-400",
  },
  {
    eyebrow: "4. Safety",
    title: "High-impact work pauses for approval",
    body: "The runtime can interrupt before execution, persist the checkpoint, surface an approval event, and later resume cleanly from saved state.",
    icon: CheckCircle2,
    accent: "from-emerald-300 to-cyan-300",
  },
  {
    eyebrow: "5. Continuity",
    title: "Brain and workflow systems continue operating",
    body: "SOUL, commitments, schedules, and Temporal workflows extend the platform beyond one-turn chat into persistent operational assistance.",
    icon: TimerReset,
    accent: "from-orange-300 to-amber-300",
  },
];

const deploymentSteps = [
  "Merge or apply the frontend route changes into the branch you want to release.",
  "Validate locally with frontend typecheck and a local test deploy if needed.",
  "Push the tested change to the prod branch to trigger the production workflow.",
  "GitHub Actions builds the frontend image, updates manifests, and runs deployment/scripts/deploy-prod.sh on the self-hosted runner.",
  "The K3s cluster rolls out the updated frontend deployment behind Traefik.",
  "Cloudflare cache is purged at the end of the production workflow.",
  "Verify https://zeroqwait.com/docs and https://zeroqwait.com/docs/architecture after rollout.",
];

export default function DocsArchitecturePage() {
  const [activeFlow, setActiveFlow] = useState(0);

  const currentFlow = useMemo(() => flowSteps[activeFlow], [activeFlow]);
  const CurrentIcon = currentFlow.icon;

  return (
    <div className="min-h-screen bg-[#07111f] text-slate-100">
      <div className="relative overflow-hidden border-b border-white/10 bg-[radial-gradient(circle_at_top_left,_rgba(56,189,248,0.18),_transparent_30%),radial-gradient(circle_at_top_right,_rgba(99,102,241,0.16),_transparent_26%),linear-gradient(180deg,#08101d_0%,#0b1322_50%,#07111f_100%)]">
        <div className="absolute inset-0 opacity-35">
          <div className="absolute left-10 top-14 h-56 w-56 rounded-full bg-cyan-400/15 blur-3xl docs-float-soft" />
          <div className="absolute right-12 top-20 h-72 w-72 rounded-full bg-indigo-400/15 blur-3xl docs-float-soft docs-float-soft-delayed" />
        </div>
        <section className="relative mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8 lg:py-24">
          <div className="grid gap-10 lg:grid-cols-[1.15fr_0.85fr] lg:items-center">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-4 py-2 text-sm text-cyan-100 backdrop-blur">
                <Workflow className="h-4 w-4 text-cyan-300" />
                Deep technical and infrastructure route
              </div>
              <h1 className="mt-6 max-w-4xl text-4xl font-semibold leading-tight tracking-[-0.04em] text-white sm:text-5xl lg:text-6xl">
                ZeroQwait architecture, runtime boundaries, and deployment flow
              </h1>
              <p className="mt-6 max-w-3xl text-lg leading-8 text-slate-300 sm:text-xl">
                This route is built for technical walkthroughs. It focuses on orchestration, services, state, safety, workflow persistence, infrastructure layout, and the exact release path that makes the public docs UI live on zeroqwait.com.
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                <RouterLink
                  to="/docs"
                  className="inline-flex items-center gap-2 rounded-full bg-white px-5 py-3 text-sm font-semibold text-slate-900 transition-transform hover:-translate-y-0.5"
                >
                  Back to showcase docs
                  <ArrowRight className="h-4 w-4" />
                </RouterLink>
                <a
                  href="#release"
                  className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-5 py-3 text-sm font-semibold text-slate-100 transition-colors hover:bg-white/10"
                >
                  Jump to release steps
                  <GitBranch className="h-4 w-4" />
                </a>
              </div>
            </div>

            <div className="rounded-[2rem] border border-white/10 bg-white/5 p-6 backdrop-blur-xl">
              <p className="text-sm uppercase tracking-[0.28em] text-slate-400">System snapshot</p>
              <div className="mt-6 grid gap-4 sm:grid-cols-2">
                {[
                  { label: "Primary orchestration", value: "LangGraph supervisor", icon: Bot },
                  { label: "Workflow engine", value: "Temporal", icon: TimerReset },
                  { label: "Primary data plane", value: "PostgreSQL + Redis", icon: Database },
                  { label: "Production platform", value: "K3s + Traefik", icon: Cloud },
                ].map((item) => {
                  const Icon = item.icon;
                  return (
                    <div key={item.label} className="rounded-[1.5rem] border border-white/10 bg-slate-950/50 p-4">
                      <div className="flex items-center gap-3">
                        <div className="rounded-2xl bg-cyan-300/10 p-3 text-cyan-200">
                          <Icon className="h-5 w-5" />
                        </div>
                        <div>
                          <p className="text-xs uppercase tracking-[0.24em] text-slate-400">{item.label}</p>
                          <p className="mt-1 text-base font-semibold text-white">{item.value}</p>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </section>
      </div>

      <section className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.28em] text-cyan-300">Architecture stack</p>
            <h2 className="mt-3 text-3xl font-semibold tracking-[-0.03em] text-white">The platform in layers</h2>
          </div>
          <p className="max-w-2xl text-sm leading-7 text-slate-300">
            This layer map is optimized for technical reviewers who want to understand where product surfaces end, orchestration begins, and infrastructure responsibilities take over.
          </p>
        </div>

        <div className="mt-8 grid gap-6 lg:grid-cols-3">
          {layers.map((layer) => {
            const Icon = layer.icon;
            return (
              <div key={layer.title} className="rounded-[2rem] border border-white/10 bg-slate-900/60 p-6 shadow-[0_20px_80px_rgba(0,0,0,0.22)]">
                <div className="flex items-center gap-3">
                  <div className="rounded-2xl bg-cyan-300/10 p-3 text-cyan-200">
                    <Icon className="h-5 w-5" />
                  </div>
                  <h3 className="text-xl font-semibold text-white">{layer.title}</h3>
                </div>
                <p className="mt-4 text-sm leading-7 text-slate-300">{layer.summary}</p>
                <div className="mt-5 flex flex-wrap gap-2">
                  {layer.chips.map((chip) => (
                    <span key={chip} className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs font-medium text-slate-200">
                      {chip}
                    </span>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <section className="border-y border-white/10 bg-white/[0.03] py-16">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-sm uppercase tracking-[0.28em] text-cyan-300">Execution flow</p>
              <h2 className="mt-3 text-3xl font-semibold tracking-[-0.03em] text-white">How a request moves through the runtime</h2>
            </div>
            <p className="max-w-2xl text-sm leading-7 text-slate-300">
              This explains the control plane: routing, execution, service boundaries, checkpointing, and continuation.
            </p>
          </div>

          <div className="mt-10 grid gap-8 lg:grid-cols-[0.85fr_1.15fr] lg:items-start">
            <div className="space-y-4">
              {flowSteps.map((step, index) => {
                const Icon = step.icon;
                const isActive = index === activeFlow;

                return (
                  <button
                    key={step.title}
                    type="button"
                    onClick={() => setActiveFlow(index)}
                    className={`w-full rounded-[1.75rem] border p-5 text-left transition-all duration-500 ${
                      isActive
                        ? "border-cyan-300/35 bg-slate-900 shadow-[0_16px_60px_rgba(34,211,238,0.12)]"
                        : "border-white/10 bg-slate-900/50 hover:border-white/20 hover:bg-slate-900/70"
                    }`}
                  >
                    <div className="flex items-start gap-4">
                      <div className={`rounded-2xl bg-gradient-to-r ${step.accent} p-3 text-slate-950`}>
                        <Icon className="h-5 w-5" />
                      </div>
                      <div>
                        <p className="text-xs uppercase tracking-[0.24em] text-slate-400">{step.eyebrow}</p>
                        <h3 className="mt-2 text-lg font-semibold text-white">{step.title}</h3>
                        <p className="mt-2 text-sm leading-7 text-slate-300">{step.body}</p>
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>

            <div className="rounded-[2rem] border border-white/10 bg-[#081424] p-6 shadow-[0_30px_100px_rgba(0,0,0,0.35)]">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs uppercase tracking-[0.28em] text-cyan-300">Focused stage</p>
                  <h3 className="mt-2 text-2xl font-semibold text-white">{currentFlow.title}</h3>
                </div>
                <div className={`rounded-2xl bg-gradient-to-r ${currentFlow.accent} p-3 text-slate-950`}>
                  <CurrentIcon className="h-5 w-5" />
                </div>
              </div>

              <div className="mt-6 grid gap-4 xl:grid-cols-[0.42fr_0.58fr]">
                <div className="rounded-[1.5rem] border border-white/10 bg-slate-950/60 p-4">
                  <p className="text-xs uppercase tracking-[0.24em] text-slate-400">Runtime chain</p>
                  <div className="mt-4 space-y-3">
                    {flowSteps.map((step, index) => (
                      <div key={step.title} className="flex items-center gap-3">
                        <div className={`h-3 w-3 rounded-full ${index <= activeFlow ? "bg-cyan-300" : "bg-slate-600"}`} />
                        <div className={`rounded-xl px-3 py-2 text-sm ${index === activeFlow ? "bg-white/[0.07] text-white" : "bg-white/[0.03] text-slate-300"}`}>
                          {step.title}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="rounded-[1.5rem] border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.06)_0%,rgba(255,255,255,0.02)_100%)] p-4">
                  <div className="rounded-2xl border border-white/10 bg-slate-950/60 p-4">
                    <p className="text-xs uppercase tracking-[0.24em] text-slate-400">Stage explanation</p>
                    <p className="mt-3 text-sm leading-7 text-slate-200">{currentFlow.body}</p>
                  </div>

                  <div className="mt-4 grid gap-3 sm:grid-cols-2">
                    {[
                      { label: "Tenant scope", value: "shop-scoped runtime" },
                      { label: "Safety posture", value: activeFlow >= 3 ? "checkpoint and approval aware" : "pre-approval execution path" },
                    ].map((item) => (
                      <div key={item.label} className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                        <p className="text-xs uppercase tracking-[0.24em] text-slate-400">{item.label}</p>
                        <p className="mt-2 text-base font-semibold text-white">{item.value}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
        <div className="grid gap-6 lg:grid-cols-3">
          {[
            {
              title: "Voice and multimodal surface",
              icon: Mic,
              body: "Whisper ASR and Qwen3-TTS are externalized so conversational audio remains consistent and operationally isolated from the main API path.",
            },
            {
              title: "Business system integration",
              icon: Building2,
              body: "Odoo, AWS SNS, and MCP services extend the product into real operational systems rather than a standalone interface demo.",
            },
            {
              title: "Production deployment",
              icon: Cloud,
              body: "K3s, Traefik, GHCR-backed image delivery, and GitHub Actions provide a practical production path from code to public site.",
            },
          ].map((item) => {
            const Icon = item.icon;
            return (
              <div key={item.title} className="rounded-[2rem] border border-white/10 bg-slate-900/60 p-6">
                <div className="rounded-2xl bg-cyan-300/10 p-3 text-cyan-200 w-fit">
                  <Icon className="h-5 w-5" />
                </div>
                <h3 className="mt-5 text-xl font-semibold text-white">{item.title}</h3>
                <p className="mt-4 text-sm leading-7 text-slate-300">{item.body}</p>
              </div>
            );
          })}
        </div>
      </section>

      <section id="release" className="border-t border-white/10 bg-[#060d18] py-16">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-sm uppercase tracking-[0.28em] text-cyan-300">Exact go-live path</p>
              <h2 className="mt-3 text-3xl font-semibold tracking-[-0.03em] text-white">How `/docs` and `/docs/architecture` reach zeroqwait.com</h2>
            </div>
            <p className="max-w-2xl text-sm leading-7 text-slate-300">
              These steps match the current production flow in this repository: `prod` branch push, self-hosted GitHub Actions, GHCR image publishing, and K3s rollout behind Traefik.
            </p>
          </div>

          <div className="mt-8 grid gap-8 lg:grid-cols-[0.9fr_1.1fr]">
            <div className="rounded-[2rem] border border-white/10 bg-slate-900/60 p-6">
              <p className="text-sm uppercase tracking-[0.28em] text-slate-400">Release checklist</p>
              <div className="mt-6 space-y-4">
                {deploymentSteps.map((step, index) => (
                  <div key={step} className="flex items-start gap-4 rounded-2xl border border-white/10 bg-[#0a1220] p-4">
                    <div className="flex h-9 w-9 items-center justify-center rounded-full bg-white text-sm font-semibold text-slate-900">
                      {index + 1}
                    </div>
                    <p className="text-sm leading-7 text-slate-200">{step}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-[2rem] border border-white/10 bg-slate-900/60 p-6">
              <p className="text-sm uppercase tracking-[0.28em] text-slate-400">Concrete commands and checks</p>
              <div className="mt-6 space-y-4 rounded-[1.5rem] border border-white/10 bg-[#0a1220] p-5 font-mono text-sm text-slate-200">
                <p>cd /home/neekrishrichu/projects/FastCuts/frontend</p>
                <p>npm run typecheck</p>
                <p>cd /home/neekrishrichu/projects/FastCuts</p>
                <p>bash deployment/scripts/deploy-test.sh</p>
                <p>git push origin &lt;your-branch&gt;</p>
                <p>git push origin prod</p>
                <p>gh run list --workflow deploy-prod.yml</p>
                <p>curl -I https://zeroqwait.com/docs</p>
                <p>curl -I https://zeroqwait.com/docs/architecture</p>
              </div>

              <div className="mt-6 rounded-[1.5rem] border border-cyan-300/15 bg-cyan-300/10 p-5 text-sm leading-7 text-cyan-50">
                Frontend routes are client-side routes, so the critical requirement is that the production frontend image containing the updated React bundle is rolled out successfully. Once the frontend deployment is updated behind Traefik, both public routes become available at zeroqwait.com.
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}