import React, { useMemo } from "react";
import { Brain, Zap, ShieldAlert } from "lucide-react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  LineChart,
  Line,
  ReferenceLine,
} from "recharts";
import { useOwnerBrand } from "../../hooks/useOwnerBrand";
import type { AgentFeedEvent, ChatMessage, PendingApproval } from "./types";

interface AgentInsightsProps {
  messages: ChatMessage[];
  events: AgentFeedEvent[];
  pendingApprovals: PendingApproval[];
}

const AgentInsights: React.FC<AgentInsightsProps> = ({ messages, events, pendingApprovals }) => {
  const brand = useOwnerBrand();

  const assistantMessages = useMemo(
    () => messages.filter((m) => m.role === "assistant" && m.content.trim().length > 0),
    [messages],
  );

  const responseLengths = useMemo(
    () =>
      assistantMessages.slice(-12).map((m, i) => ({ index: i, value: m.content.length })),
    [assistantMessages],
  );

  const eventBuckets = useMemo(() => {
    const tracked: AgentFeedEvent["type"][] = [
      "agent_switch",
      "tool_call",
      "tool_result",
      "approval_required",
      "approval_decision",
      "queue_update",
      "error",
    ];

    const counts = new Map<AgentFeedEvent["type"], number>();
    tracked.forEach((t) => counts.set(t, 0));
    events.slice(0, 40).forEach((event) => {
      if (counts.has(event.type)) {
        counts.set(event.type, (counts.get(event.type) || 0) + 1);
      }
    });

    return tracked.map((t) => ({
      name: t.replace(/_/g, " "),
      events: counts.get(t) || 0,
    }));
  }, [events]);

  return (
    <div
      className="rounded-2xl border backdrop-blur-xl"
      style={{
        borderColor: brand.glass.border,
        backgroundColor: brand.glass.bg,
        boxShadow: `0 18px 50px ${brand.primary}14`,
      }}
    >
      <div className="px-4 py-4">
        {/* Header */}
        <div className="flex items-center justify-between mb-1">
          <p className="text-base font-semibold">Context Snapshot</p>
          <span
            className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-bold"
            style={{
              backgroundColor: brand.primary,
              color: "#fff",
            }}
          >
            Live
          </span>
        </div>

        <p className="text-sm text-muted-foreground mb-3 leading-relaxed">
          A lightweight view of activity, approvals, and response patterns around the current chat context.
        </p>

        {/* Stat cards */}
        <div className="grid grid-cols-3 gap-2 mb-3">
          {[
            {
              icon: <Brain className="h-3.5 w-3.5" style={{ color: brand.primary }} />,
              label: "Assistant Replies",
              value: assistantMessages.length,
            },
            {
              icon: <Zap className="h-3.5 w-3.5" style={{ color: brand.secondary }} />,
              label: "Tool Events",
              value: events.filter((e) => e.type === "tool_call" || e.type === "tool_result").length,
            },
            {
              icon: <ShieldAlert className="h-3.5 w-3.5" style={{ color: brand.secondary }} />,
              label: "Pending Approvals",
              value: pendingApprovals.length,
            },
          ].map(({ icon, label, value }) => (
            <div
              key={label}
              className="rounded-xl border p-2.5"
              style={{
                borderColor: `${brand.primary}29`,
                backgroundColor: `${brand.primary}0d`,
              }}
            >
              <div className="flex items-center gap-1.5 mb-1">
                {icon}
                <span className="text-xs text-muted-foreground">{label}</span>
              </div>
              <p className="text-base font-semibold">{value}</p>
            </div>
          ))}
        </div>

        {/* Event mix chart */}
        <p className="text-xs font-semibold mb-2 text-muted-foreground uppercase tracking-wide">
          Event Mix (latest 40)
        </p>
        <ResponsiveContainer width="100%" height={170}>
          <BarChart data={eventBuckets} margin={{ left: 16, right: 8, top: 8, bottom: 44 }}>
            <XAxis
              dataKey="name"
              tick={{ fontSize: 9, fill: "hsl(var(--muted-foreground))" }}
              angle={-30}
              textAnchor="end"
              interval={0}
            />
            <YAxis tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} />
            <Tooltip
              contentStyle={{
                background: "hsl(var(--background))",
                border: "1px solid hsl(var(--border))",
                borderRadius: 8,
                fontSize: 12,
              }}
            />
            <Bar dataKey="events" fill={brand.primary} radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>

        {/* Response length trend */}
        <p className="text-xs font-semibold mt-3 mb-1.5 text-muted-foreground uppercase tracking-wide">
          Response Length Trend
        </p>
        <ResponsiveContainer width="100%" height={70}>
          <LineChart
            data={responseLengths.length > 1 ? responseLengths : [{ index: 0, value: 0 }, ...responseLengths]}
          >
            <Line
              type="monotone"
              dataKey="value"
              stroke={brand.secondary}
              dot={false}
              strokeWidth={2}
            />
            <Tooltip
              contentStyle={{
                background: "hsl(var(--background))",
                border: "1px solid hsl(var(--border))",
                borderRadius: 8,
                fontSize: 12,
              }}
              formatter={(v) => [`${v} chars`, "Length"]}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default AgentInsights;
