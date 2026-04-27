import type {
  AgentFeedEvent,
  BriefingAction,
  InsightItem,
  OwnerBriefing,
  PendingApproval,
} from "./types";

type QuickAction = {
  label: string;
  payload: string;
};

const normalizeId = (value: string) => value.replace(/[^a-zA-Z0-9_-]+/g, "_");

export const createWorkspaceFeedSeed = (
  briefing: OwnerBriefing | null,
  pendingApprovals: PendingApproval[]
): AgentFeedEvent[] => {
  if (!briefing) return [];

  const seedPrefix = normalizeId(`${briefing.shop_id}_${briefing.generated_at}`);
  const events: AgentFeedEvent[] = [
    {
      id: `${seedPrefix}_briefing`,
      type: "system",
      title: "Daily briefing ready",
      description: briefing.summary,
      timestamp: briefing.generated_at,
      payload: briefing,
    },
  ];

  briefing.alerts.slice(0, 2).forEach((alert, index) => {
    events.push({
      id: `${seedPrefix}_alert_${index}`,
      type: alert.title.toLowerCase().includes("queue") ? "queue_update" : "system",
      title: alert.title,
      description: alert.body,
      timestamp: alert.created_at || briefing.generated_at,
      payload: alert,
    });
  });

  if (pendingApprovals.length > 0) {
    events.push({
      id: `${seedPrefix}_pending`,
      type: "approval_required",
      title: "Owner decisions are waiting",
      description: `${pendingApprovals.length} approval request${pendingApprovals.length === 1 ? "" : "s"} can unblock queued agent work.`,
      timestamp: briefing.generated_at,
      payload: pendingApprovals,
    });
  }

  const suggestedAction = briefing.actions[0];
  if (suggestedAction) {
    events.push({
      id: `${seedPrefix}_action`,
      type: "system",
      title: `Suggested next step: ${suggestedAction.label}`,
      description: suggestedAction.description || suggestedAction.payload,
      timestamp: briefing.generated_at,
      payload: suggestedAction,
    });
  }

  return events;
};

export const createWorkspaceInsightSeed = (
  briefing: OwnerBriefing | null,
  pendingApprovals: PendingApproval[]
): InsightItem[] => {
  if (!briefing) return [];

  const seedPrefix = normalizeId(`${briefing.shop_id}_${briefing.generated_at}`);
  const insights: InsightItem[] = [
    {
      id: `${seedPrefix}_focus`,
      type: "summary",
      summary: {
        id: `${seedPrefix}_focus_summary`,
        title: "Today's focus",
        body: briefing.summary,
        severity: briefing.alerts[0]?.severity || "info",
        chips: [
          `${briefing.metrics.queue_length} waiting`,
          `${briefing.metrics.estimated_wait_minutes} min wait`,
          `${briefing.metrics.active_employees} staff`,
        ],
        timestamp: briefing.generated_at,
      },
      timestamp: briefing.generated_at,
    },
    {
      id: `${seedPrefix}_operations_chart`,
      type: "chart",
      chart: {
        id: `${seedPrefix}_operations_chart_data`,
        title: "Operational Load",
        chartType: "bar",
        xKey: "label",
        series: [{ key: "value", label: "Volume" }],
        showLegend: false,
        showGrid: true,
        data: [
          { label: "Waiting", value: briefing.metrics.queue_length },
          { label: "Serving", value: briefing.metrics.people_being_served },
          { label: "Staff", value: briefing.metrics.active_employees },
          { label: "Pending", value: Math.max(briefing.metrics.pending_approvals, pendingApprovals.length) },
          { label: "Services", value: briefing.metrics.active_services },
        ],
        timestamp: briefing.generated_at,
      },
      timestamp: briefing.generated_at,
    },
    {
      id: `${seedPrefix}_commercial`,
      type: "summary",
      summary: {
        id: `${seedPrefix}_commercial_summary`,
        title: "Commercial snapshot",
        body: `Today is tracking at ${briefing.metrics.today_revenue.toFixed(0)} revenue across ${briefing.metrics.today_transactions} transactions, with ${briefing.metrics.weekly_revenue.toFixed(0)} booked so far this week.`,
        severity: briefing.metrics.today_transactions > 0 || briefing.metrics.weekly_revenue > 0 ? "success" : "info",
        chips: [
          `Today ${briefing.metrics.today_revenue.toFixed(0)}`,
          `Week ${briefing.metrics.weekly_revenue.toFixed(0)}`,
          `${briefing.metrics.today_transactions} transactions`,
        ],
        timestamp: briefing.generated_at,
      },
      timestamp: briefing.generated_at,
    },
  ];

  const urgentAlert = briefing.alerts.find((alert) => alert.severity === "warning" || alert.severity === "error");
  if (urgentAlert) {
    insights.unshift({
      id: `${seedPrefix}_alert_summary`,
      type: "summary",
      summary: {
        id: `${seedPrefix}_alert_summary_data`,
        title: urgentAlert.title,
        body: urgentAlert.body,
        severity: urgentAlert.severity,
        chips: [urgentAlert.severity.toUpperCase()],
        timestamp: urgentAlert.created_at || briefing.generated_at,
      },
      timestamp: urgentAlert.created_at || briefing.generated_at,
    });
  }

  return insights;
};

export const createWorkspaceQuickActions = (
  briefing: OwnerBriefing | null,
  pendingApprovals: PendingApproval[],
  shopName?: string | null
): QuickAction[] => {
  const quickActions: QuickAction[] = [];

  if (pendingApprovals.length > 0) {
    quickActions.push({
      label: "Review approvals",
      payload: "Show me the pending approvals and tell me what needs my decision first.",
    });
  }

  if (briefing?.actions?.length) {
    briefing.actions.forEach((action: BriefingAction) => {
      if (!quickActions.some((item) => item.label === action.label)) {
        quickActions.push({ label: action.label, payload: action.payload });
      }
    });
  }

  if (quickActions.length === 0) {
    quickActions.push(
      { label: "Give me today's queue summary", payload: `Give me today's queue summary for ${shopName || "my shop"}` },
      { label: "Show this week's revenue trend", payload: "Show this week's revenue trend" },
      { label: "Who is on shift now?", payload: "Who is on shift now?" }
    );
  }

  return quickActions.slice(0, 3);
};