import React from "react";
import "@testing-library/jest-dom";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ThemeProvider, createTheme } from "@mui/material/styles";

import AgentInbox from "./AgentInbox";
import api from "../../services/api";

jest.mock("../../contexts/ShopContext", () => ({
  useShop: () => ({
    shop: {
      id: 141,
      name: "Bulk Owner Test Shop",
      slug: "bulk-owner-test-shop",
      primary_color: "#1976d2",
      secondary_color: "#00a3a3",
    },
  }),
}));

jest.mock("../../landing-page/components/MasterAIAgent", () => ({
  __esModule: true,
  default: () => <div data-testid="master-ai-agent">agent shell</div>,
}));

jest.mock("./AgentFeed", () => ({
  __esModule: true,
  default: ({ events }: { events: Array<{ id: string; title: string; description: string }> }) => (
    <div data-testid="agent-feed">
      {events.map((event) => (
        <div key={event.id}>{`${event.title}: ${event.description}`}</div>
      ))}
    </div>
  ),
}));

jest.mock("./AgentInsights", () => ({
  __esModule: true,
  default: () => <div data-testid="agent-insights" />,
}));

jest.mock("./InsightsPanel", () => ({
  __esModule: true,
  default: () => <div data-testid="insights-panel" />,
}));

jest.mock("./ThinkingSteps", () => ({
  __esModule: true,
  default: () => <div data-testid="thinking-steps" />,
}));

jest.mock("../../services/api", () => ({
  __esModule: true,
  default: {
    get: jest.fn(),
    post: jest.fn(),
    put: jest.fn(),
  },
}));

const mockedApi = api as unknown as {
  get: jest.Mock;
  post: jest.Mock;
  put: jest.Mock;
};

const approvalPayload = {
  action_id: "approval_add_employee_1",
  action: "add_employee",
  details: {
    name: "Maria",
    email: "maria@example.com",
    phone: "123-456-7890",
    role: "stylist",
  },
  shop_id: 141,
  policy_key: "approval.add_employee",
  policy_mode: "require_approval",
  category: "staffing",
  title: "Add Team Member",
  summary: "Add Maria to the shop team.",
  reason: "Create a new employee record for Maria.",
  expected_impact: "The person will appear in team management and become eligible for shift assignment.",
  risk_level: "medium",
  urgency: "normal",
  recommended_decision: "Approve if the hiring or onboarding decision is final.",
};

const briefingPayload = {
  shop_id: 141,
  shop_name: "Bulk Owner Test Shop",
  generated_at: "2026-04-21T15:00:00Z",
  source: "scheduled",
  summary: "Bulk Owner Test Shop currently has 1 people waiting, 1 being served, 2 active staff detected, and 1 pending approval.",
  metrics: {
    queue_length: 1,
    estimated_wait_minutes: 16,
    people_being_served: 1,
    active_employees: 2,
    active_services: 1,
    pending_approvals: 1,
    today_revenue: 120,
    today_transactions: 3,
    weekly_revenue: 735,
  },
  alerts: [
    {
      severity: "warning",
      title: "Queue pressure building",
      body: "One walk-in is waiting while another appointment is being served.",
    },
  ],
  recommendations: [
    "Approve Maria if onboarding is final.",
    "Watch the afternoon wait time.",
  ],
  actions: [
    {
      label: "Show this week's revenue trend",
      payload: "Show this week's revenue trend",
      description: "Review this week's commercial performance.",
    },
  ],
  alert_history: [],
};

const policiesPayload = [
  {
    action: "add_employee",
    policy_key: "approval.add_employee",
    category: "staffing",
    title: "Add Team Member",
    risk_level: "medium",
    urgency: "normal",
    default_mode: "require_approval",
    mode: "require_approval",
    explicit: false,
    supported_modes: ["require_approval", "allow", "notify_only", "forbid"],
  },
];

class MockWebSocket {
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: (() => void) | null = null;

  constructor(_url: string) {}

  close() {}
}

const renderInbox = () =>
  render(
    <ThemeProvider theme={createTheme()}>
      <AgentInbox />
    </ThemeProvider>
  );

describe("AgentInbox", () => {
  beforeEach(() => {
    let pendingApprovals = [approvalPayload];

    Object.defineProperty(window, "WebSocket", {
      writable: true,
      value: MockWebSocket,
    });

    mockedApi.get.mockImplementation((url: string) => {
      if (url === "/v2/agent/pending") {
        return Promise.resolve({ data: { pending: pendingApprovals } });
      }
      if (url === "/v2/agent/briefing") {
        return Promise.resolve({ data: briefingPayload });
      }
      if (url === "/v2/agent/feed") {
        return Promise.resolve({ data: { events: [] } });
      }
      if (url === "/v2/agent/policies") {
        return Promise.resolve({ data: { policies: policiesPayload } });
      }
      throw new Error(`Unexpected GET ${url}`);
    });

    mockedApi.post.mockImplementation((url: string) => {
      if (url === "/v2/agent/approve") {
        pendingApprovals = [];
        return Promise.resolve({
          data: {
            message: "Approval received. Employee Maria added successfully. Username: maria. Staff email: maria@example.com. Temporary password: secret123",
            status: "approved",
            agent: "hr",
            tool_results: {
              message: "Employee Maria added successfully. Username: maria. Staff email: maria@example.com. Temporary password: secret123",
              status: "added",
              username: "maria",
            },
          },
        });
      }
      if (url === "/v2/agent/notifications/read-all") {
        return Promise.resolve({ data: {} });
      }
      throw new Error(`Unexpected POST ${url}`);
    });

    mockedApi.put.mockReset();
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  it("renders the finance briefing and pending approval card from the inbox APIs", async () => {
    renderInbox();

    expect(await screen.findByText("Daily Briefing")).toBeInTheDocument();
    expect(screen.getAllByText(/Bulk Owner Test Shop currently has 1 people waiting/i).length).toBeGreaterThan(0);
    expect(screen.getByText("Today Revenue")).toBeInTheDocument();
    expect(screen.getByText(/120/)).toBeInTheDocument();
    expect(screen.getByText("Pending Approvals")).toBeInTheDocument();
    expect(screen.getAllByText("Add Team Member").length).toBeGreaterThan(0);
    expect(screen.getByText("Approval Required")).toBeInTheDocument();

    await waitFor(() => expect(mockedApi.get).toHaveBeenCalledWith("/v2/agent/pending", { params: { shop_id: 141 } }));
  });

  it("approves a pending card and refreshes the inbox state", async () => {
    renderInbox();

    expect(await screen.findByText("Pending Approvals")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Approve" }));

    await waitFor(() => {
      expect(mockedApi.post).toHaveBeenCalledWith("/v2/agent/approve", {
        shop_id: 141,
        action_id: "approval_add_employee_1",
        approved: true,
      });
    });

    await waitFor(() => {
      expect(screen.queryByText("Pending Approvals")).not.toBeInTheDocument();
    });
    expect(screen.getByText(/Action approved: You approved 'add_employee'\./i)).toBeInTheDocument();
    expect(screen.getByText(/Employee added: Employee Maria added successfully\./i)).toBeInTheDocument();
  });
});