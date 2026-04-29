import {
  createWorkspaceFeedSeed,
  createWorkspaceInsightSeed,
  createWorkspaceQuickActions,
} from "./workspaceSeed";
import type { OwnerBriefing, PendingApproval } from "./types";

const briefing: OwnerBriefing = {
  shop_id: 7,
  shop_name: "North Barbers",
  generated_at: "2026-04-21T04:00:00Z",
  source: "scheduled",
  summary: "North Barbers currently has 5 people waiting, 2 being served, 2 active staff detected, and 1 pending approval.",
  metrics: {
    queue_length: 5,
    estimated_wait_minutes: 28,
    people_being_served: 2,
    active_employees: 2,
    active_services: 4,
    pending_approvals: 1,
    today_revenue: 340,
    today_transactions: 9,
    weekly_revenue: 1925,
  },
  alerts: [
    {
      severity: "warning",
      title: "Queue pressure is building",
      body: "There are 5 people waiting with an estimated wait of 28 minutes.",
      created_at: "2026-04-21T03:58:00Z",
    },
  ],
  recommendations: ["Review pending approvals first."],
  actions: [
    {
      label: "Check queue",
      payload: "Give me the live queue status and tell me if I need to intervene.",
      description: "Review demand and wait time pressure.",
    },
  ],
};

const pending: PendingApproval[] = [
  {
    action_id: "approval_1",
    action: "close_queue",
    details: { reason: "Queue is over capacity" },
    shop_id: 7,
  },
];

describe("workspaceSeed helpers", () => {
  it("builds seeded feed events from briefing and pending approvals", () => {
    const events = createWorkspaceFeedSeed(briefing, pending);

    expect(events.map((event) => event.title)).toEqual(
      expect.arrayContaining([
        "Daily briefing ready",
        "Queue pressure is building",
        "Owner decisions are waiting",
        "Suggested next step: Check queue",
      ])
    );
  });

  it("builds seeded insights with summaries and an operational chart", () => {
    const insights = createWorkspaceInsightSeed(briefing, pending);

    expect(insights.some((item) => item.type === "summary" && item.summary?.title === "Today's focus")).toBe(true);
    expect(insights.some((item) => item.type === "chart" && item.chart?.title === "Operational Load")).toBe(true);
    expect(insights.some((item) => item.type === "summary" && item.summary?.title === "Commercial snapshot")).toBe(true);
  });

  it("prioritizes approval quick actions before briefing actions", () => {
    const quickActions = createWorkspaceQuickActions(briefing, pending, briefing.shop_name);

    expect(quickActions[0]).toEqual(
      expect.objectContaining({ label: "Review approvals" })
    );
    expect(quickActions).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ label: "Check queue" }),
      ])
    );
  });
});