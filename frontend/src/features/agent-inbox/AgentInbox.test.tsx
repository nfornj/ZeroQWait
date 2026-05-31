import React from "react";
import "@testing-library/jest-dom";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { CompleteAttachment } from "@assistant-ui/react";

import AgentInbox from "./AgentInbox";
import AgentChat from "./AgentChat";
import api from "../../services/api";
import { ThemeProvider } from "../../contexts/ThemeContext";
import { TooltipProvider } from "../../components/ui/tooltip";
import { createAgentChartFromPayload } from "./types";

jest.mock("@assistant-ui/react", () => {
  const React = require("react");

  const RuntimeContext = React.createContext(null);
  const MessageContext = React.createContext(null);
  const AttachmentContext = React.createContext(null);
  const AuiContext = React.createContext({
    interactables: () => ({
      setPersistenceAdapter: jest.fn(),
      importState: jest.fn(),
      flush: jest.fn(async () => undefined),
    }),
    subscribe: () => () => undefined,
  });

  const renderAsChild = (children: React.ReactNode, props: Record<string, unknown>) => {
    if (React.isValidElement(children)) {
      return React.cloneElement(children, props);
    }

    return React.createElement(React.Fragment, null, children);
  };

  const passthrough = ({ children }: { children?: React.ReactNode }) => React.createElement(React.Fragment, null, children);

  return {
    __esModule: true,
    AuiIf: ({ condition, children }: { condition: ((state: any) => boolean) | boolean; children?: React.ReactNode }) => {
      const runtime = React.useContext(RuntimeContext);
      const visible = typeof condition === "function" ? condition({ composer: { dictation: runtime?.composer?.dictation ?? null } }) : Boolean(condition);
      return visible ? React.createElement(React.Fragment, null, children) : null;
    },
    CompositeAttachmentAdapter: class CompositeAttachmentAdapter {
      adapters: any[];

      constructor(adapters: any[]) {
        this.adapters = adapters;
      }
    },
    WebSpeechDictationAdapter: class WebSpeechDictationAdapter {
      static isSupported() {
        return true;
      }

      constructor(_options?: any) {}
    },
    AssistantRuntimeProvider: ({ runtime, aui, children }: { runtime: any; aui?: any; children?: React.ReactNode }) =>
      React.createElement(
        AuiContext.Provider,
        { value: aui || React.useContext(AuiContext) },
        React.createElement(RuntimeContext.Provider, { value: runtime }, children),
      ),
    useAui: () => React.useContext(AuiContext),
    Interactables: () => ({}),
    useAssistantInteractable: (_name: string, config: { id?: string }) => config.id || "mock-task-board",
    useInteractableState: (_id: string, fallback: any) => React.useState(fallback),
    useExternalStoreRuntime: ({ messages, convertMessage }: { messages: any[]; convertMessage: (message: any) => any }) => ({
      messages: messages.map((message) => ({ ...convertMessage(message), __externalMessage: message })),
      composer: { setText: jest.fn(), addAttachment: jest.fn(), dictation: null },
    }),
    useThreadRuntime: () => React.useContext(RuntimeContext),
    useThreadComposer: (selector: (state: { text: string }) => unknown) => selector({ text: "" }),
    useAttachment: () => React.useContext(AttachmentContext),
    getExternalStoreMessages: (message: any) => [message.__externalMessage || message],
    AttachmentPrimitive: {
      Root: passthrough,
      Name: () => {
        const attachment = React.useContext(AttachmentContext);
        return React.createElement(React.Fragment, null, attachment?.name || "");
      },
      unstable_Thumb: () => {
        const attachment = React.useContext(AttachmentContext);
        const ext = attachment?.name?.split(".").pop() || "file";
        return React.createElement(React.Fragment, null, `.${ext}`);
      },
      Remove: ({ asChild, children, ...props }: any) => (asChild ? renderAsChild(children, props) : passthrough({ children })),
    },
    ActionBarPrimitive: {
      Root: passthrough,
      Edit: ({ asChild, children, ...props }: any) => (asChild ? renderAsChild(children, props) : passthrough({ children })),
      Copy: ({ asChild, children, ...props }: any) => (asChild ? renderAsChild(children, props) : passthrough({ children })),
      Reload: ({ asChild, children, ...props }: any) => (asChild ? renderAsChild(children, props) : passthrough({ children })),
    },
    BranchPickerPrimitive: {
      Root: passthrough,
      Previous: ({ asChild, children, ...props }: any) => (asChild ? renderAsChild(children, props) : passthrough({ children })),
      Next: ({ asChild, children, ...props }: any) => (asChild ? renderAsChild(children, props) : passthrough({ children })),
      Number: () => React.createElement("span", null, "1"),
      Count: () => React.createElement("span", null, "1"),
    },
    ChainOfThoughtPrimitive: {
      Root: passthrough,
      AccordionTrigger: ({ children, ...props }: any) => React.createElement("button", props, children),
      Parts: ({ children }: any) => {
        const message = React.useContext(MessageContext);
        const parts = Array.isArray(message?.content)
          ? message.content.filter((part: any) => part.type === "reasoning" || part.type === "tool-call")
          : [];

        if (typeof children !== "function") {
          return null;
        }

        return React.createElement(
          React.Fragment,
          null,
          parts.map((part: any, index: number) =>
            React.createElement(React.Fragment, { key: `${part.type}_${index}` }, children({ part })),
          ),
        );
      },
    },
    ComposerPrimitive: {
      Root: passthrough,
      Input: ({ asChild, children, ...props }: any) => (asChild ? renderAsChild(children, props) : passthrough({ children })),
      AddAttachment: ({ asChild, children, ...props }: any) => (asChild ? renderAsChild(children, props) : passthrough({ children })),
      Attachments: () => null,
      Dictate: ({ asChild, children, ...props }: any) => (asChild ? renderAsChild(children, props) : passthrough({ children })),
      StopDictation: ({ asChild, children, ...props }: any) => (asChild ? renderAsChild(children, props) : passthrough({ children })),
      Cancel: ({ asChild, children, ...props }: any) => (asChild ? renderAsChild(children, props) : passthrough({ children })),
      Send: ({ asChild, children, ...props }: any) => (asChild ? renderAsChild(children, props) : passthrough({ children })),
    },
    MessagePrimitive: {
      Root: passthrough,
      Attachments: ({ children }: any) => {
        const message = React.useContext(MessageContext);
        const attachments = message?.__externalMessage?.attachments || message?.attachments || [];

        if (typeof children !== "function") {
          return null;
        }

        return React.createElement(
          React.Fragment,
          null,
          attachments.map((attachment: any, index: number) =>
            React.createElement(
              AttachmentContext.Provider,
              { key: attachment.id || index, value: attachment },
              children({ attachment }),
            ),
          ),
        );
      },
      Parts: ({ components }: any) => {
        const message = React.useContext(MessageContext);
        const parts = Array.isArray(message?.content) ? message.content : [];
        const renderedChainParents = new Set<string>();

        return React.createElement(
          React.Fragment,
          null,
          parts.map((part: any, index: number) => {
            if (part.type === "text" && components?.Text) {
              return React.createElement(React.Fragment, { key: `${part.type}_${index}` }, components.Text({ text: part.text }));
            }

            if ((part.type === "reasoning" || part.type === "tool-call") && components?.ChainOfThought) {
              const parentKey = typeof part.parentId === "string" && part.parentId ? part.parentId : `${part.type}_${index}`;
              if (renderedChainParents.has(parentKey)) {
                return null;
              }
              renderedChainParents.add(parentKey);
              return React.createElement(React.Fragment, { key: `${part.type}_${index}` }, components.ChainOfThought({}));
            }

            return null;
          }),
        );
      },
    },
    ThreadPrimitive: {
      Root: passthrough,
      Viewport: passthrough,
      ViewportFooter: passthrough,
      Messages: ({ children }: { children: (payload: { message: any }) => React.ReactNode }) => {
        const runtime = React.useContext(RuntimeContext) as { messages?: any[] } | null;
        const messages = runtime?.messages || [];

        return React.createElement(
          React.Fragment,
          null,
          messages.map((message) =>
            React.createElement(
              MessageContext.Provider,
              { key: message.id, value: message },
              children({ message }),
            )
          ),
        );
      },
    },
  };
});

jest.mock("react-markdown", () => ({
  __esModule: true,
  default: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
}));

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

jest.mock("../../contexts/AuthContext", () => ({
  useAuth: () => ({
    token: "test-owner-token",
    user: {
      id: 42,
      username: "bulk-owner",
      email: "bulk-owner@example.com",
      role: "shop_owner",
    },
    isAuthenticated: true,
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

jest.mock("recharts", () => {
  const React = require("react") as typeof import("react");

  return {
    __esModule: true,
    ResponsiveContainer: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
    BarChart: ({ children }: { children?: React.ReactNode }) => <svg data-testid="bar-chart">{children}</svg>,
    Bar: ({ name, dataKey }: { name?: string; dataKey?: string }) => <text>{name || dataKey}</text>,
    LineChart: ({ children, data }: { children?: React.ReactNode; data?: Record<string, unknown>[] }) => {
      const childArray = React.Children.toArray(children);
      const isLineSeries = (child: React.ReactNode) => {
        if (!React.isValidElement(child)) return false;
        const props = (child as React.ReactElement<{ stroke?: unknown }>).props;
        return Boolean(props.stroke);
      };
      const seriesCount = childArray.filter(isLineSeries).length;

      return (
        <svg data-testid="line-chart" data-series-count={seriesCount}>
          {children}
          {data?.map((point, index) => <text key={index}>{Object.values(point).join(" ")}</text>)}
        </svg>
      );
    },
    Line: ({ name, dataKey }: { name?: string; dataKey?: string }) => <text>{name || dataKey}</text>,
    PieChart: ({ children }: { children?: React.ReactNode }) => <svg data-testid="pie-chart">{children}</svg>,
    Pie: () => null,
    Cell: () => null,
    XAxis: () => null,
    YAxis: () => null,
    Tooltip: () => null,
    ReferenceLine: () => null,
  };
});

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
  {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });

    return render(
      <ThemeProvider>
        <TooltipProvider>
          <QueryClientProvider client={queryClient}>
            <AgentInbox />
          </QueryClientProvider>
        </TooltipProvider>
      </ThemeProvider>
    );
  };

const renderChat = (messages: React.ComponentProps<typeof AgentChat>["messages"]) =>
  render(
    <ThemeProvider>
      <TooltipProvider>
        <AgentChat
          messages={messages}
          isStreaming={false}
          onSend={jest.fn(async () => undefined)}
        />
      </TooltipProvider>
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
      if (url === "/v2/agent/notifications/read-all") {
        return Promise.resolve({ data: {} });
      }
      throw new Error(`Unexpected POST ${url}`);
    });

    global.fetch = jest.fn(async () => {
      pendingApprovals = [];
      const encoder = new TextEncoder();
      const chunks = [
        encoder.encode(
          [
            "data: {\"type\":\"text\",\"content\":\"Approval received. Employee Maria added successfully. Username: maria. Staff email: maria@example.com. Temporary password: secret123\"}",
            "data: {\"type\":\"stream_status\",\"status\":\"approved\",\"agent\":\"hr\",\"tool_results\":{\"message\":\"Employee Maria added successfully. Username: maria. Staff email: maria@example.com. Temporary password: secret123\",\"status\":\"added\",\"username\":\"maria\"}}",
            "data: [DONE]",
            "",
          ].join("\n"),
        ),
      ];

      return {
        ok: true,
        body: {
          getReader: () => ({
            read: jest
              .fn()
              .mockResolvedValueOnce({ value: chunks[0], done: false })
              .mockResolvedValueOnce({ value: undefined, done: true }),
          }),
        },
      } as unknown as Response;
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
    expect(screen.getByRole("button", { name: "Deny" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add" })).toBeInTheDocument();

    await waitFor(() => expect(mockedApi.get).toHaveBeenCalledWith("/v2/agent/pending", { params: { shop_id: 141 } }));
  });

  it("approves a pending card and refreshes the inbox state", async () => {
    renderInbox();

    expect(await screen.findByText("Pending Approvals")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Add" }));

    await waitFor(() => expect(global.fetch).toHaveBeenCalled());

    expect(global.fetch).toHaveBeenCalledWith(
      "/api/v2/agent/approve/stream",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          shop_id: 141,
          action_id: "approval_add_employee_1",
          approved: true,
        }),
      }),
    );

    expect(global.fetch).toHaveBeenCalled();
  });

  it("renders inline multi-series finance charts in the chat thread", async () => {
    const chart = createAgentChartFromPayload(
      {
        title: "Revenue Trend (this week)",
        description: "Revenue and customers by period.",
        chartType: "line",
        data: [
          { label: "2026-04-22", revenue: 50, customers: 4 },
          { label: "2026-04-26", revenue: 0, customers: 0 },
        ],
        xKey: "label",
        series: [
          { key: "revenue", label: "Revenue" },
          { key: "customers", label: "Customers" },
        ],
        showLegend: true,
        showGrid: true,
      },
      "2026-04-26T12:48:00.000Z",
    );

    expect(chart).not.toBeNull();

    renderChat([
      {
        id: "assistant_1",
        role: "assistant",
        content: "For this week, revenue and customer volume are shown below.",
        status: "done",
        timestamp: "2026-04-26T12:48:00.000Z",
        agent: "finance",
        charts: chart ? [chart] : [],
      },
    ]);

    expect(await screen.findByText("Finance Assistant")).toBeInTheDocument();
    expect(screen.getByText("Revenue Trend (this week)")).toBeInTheDocument();

    const lineChart = screen.getByTestId("line-chart");
    expect(lineChart).toHaveAttribute("data-series-count", "2");
    expect(lineChart).toHaveTextContent("Revenue");
    expect(lineChart).toHaveTextContent("Customers");
    expect(lineChart).toHaveTextContent("2026-04-22");
  });

  it("does not keep the thinking block once assistant text is available", async () => {
    renderChat([
      {
        id: "assistant_2",
        role: "assistant",
        content: "Queue is stable and ready for the next customer.",
        status: "done",
        timestamp: "2026-04-26T12:49:00.000Z",
        agent: "receptionist",
        thinkingSteps: [
          {
            id: "step_1",
            label: "Checking queue status",
            status: "completed",
            agent: "receptionist",
          },
        ],
      },
    ]);

    expect(await screen.findByText("Receptionist Assistant")).toBeInTheDocument();
    expect(screen.getByText("Queue is stable and ready for the next customer.")).toBeInTheDocument();
    expect(screen.queryByText(/^Thinking$/)).not.toBeInTheDocument();
  });

  it("hides the chain of thought once the final assistant response is available", async () => {
    renderChat([
      {
        id: "assistant_3",
        role: "assistant",
        content: "Finance summary ready.",
        status: "done",
        timestamp: "2026-04-26T12:50:00.000Z",
        agent: "finance",
        thinkingSteps: [
          {
            id: "reasoning_1",
            label: "I matched this to finance because the owner asked about revenue trends.",
            status: "completed",
            agent: "finance",
          },
          {
            id: "tool_finance",
            label: "Completed finance",
            status: "completed",
            agent: "finance",
            toolName: "finance",
          },
        ],
      },
    ]);

    expect(await screen.findByText("Finance Assistant")).toBeInTheDocument();
    expect(screen.getByText("Finance summary ready.")).toBeInTheDocument();
    expect(screen.queryByText("Chain of thought")).not.toBeInTheDocument();
    expect(
      screen.queryByText("I matched this to finance because the owner asked about revenue trends."),
    ).not.toBeInTheDocument();
  });

  it("shows only rich reasoning while the assistant is still thinking", async () => {
    renderChat([
      {
        id: "assistant_4",
        role: "assistant",
        content: "",
        status: "streaming",
        timestamp: "2026-04-26T12:51:00.000Z",
        agent: "hr",
        thinkingSteps: [
          {
            id: "step_classify_intent",
            label: "Classified HR Assistant",
            status: "completed",
            agent: "hr",
          },
          {
            id: "hr_reasoning",
            label: "The user is asking about staffing gaps, so I need today's shifts before I can assess coverage.",
            status: "completed",
            agent: "hr",
          },
          {
            id: "tool_get_shifts",
            label: "Completed Get Shifts",
            status: "completed",
            agent: "hr",
            toolName: "get_shifts",
          },
        ],
      },
    ]);

    expect(await screen.findByText("Hr Assistant")).toBeInTheDocument();
    expect(screen.getByText("Chain of thought")).toBeInTheDocument();
    expect(
      screen.getByText("The user is asking about staffing gaps, so I need today's shifts before I can assess coverage."),
    ).toBeInTheDocument();
    expect(screen.queryByText("Classified HR Assistant")).not.toBeInTheDocument();
    expect(screen.queryByText("Completed Get Shifts")).not.toBeInTheDocument();
  });

  it("lets the active chain of thought collapse and expand", async () => {
    renderChat([
      {
        id: "assistant_5",
        role: "assistant",
        content: "",
        status: "streaming",
        timestamp: "2026-04-26T12:52:00.000Z",
        agent: "hr",
        thinkingSteps: [
          {
            id: "hr_reasoning_toggle",
            label: "The user is asking about staffing gaps, so I need today's shifts before I can assess coverage.",
            status: "completed",
            agent: "hr",
          },
        ],
      },
    ]);

    const toggle = await screen.findByText("Chain of thought");
    const reasoning = screen.getByText(
      "The user is asking about staffing gaps, so I need today's shifts before I can assess coverage.",
    );

    expect(reasoning).toBeInTheDocument();

    fireEvent.click(toggle);
    expect(screen.queryByText(
      "The user is asking about staffing gaps, so I need today's shifts before I can assess coverage.",
    )).not.toBeInTheDocument();

    fireEvent.click(toggle);
    expect(screen.getByText(
      "The user is asking about staffing gaps, so I need today's shifts before I can assess coverage.",
    )).toBeInTheDocument();
  });

  it("renders sent user attachments in the chat thread", () => {
    const attachment: CompleteAttachment = {
      id: "attachment_finance_csv",
      type: "document",
      name: "finance_trend.csv",
      contentType: "text/csv",
      status: { type: "complete" },
      content: [
        {
          type: "data",
          name: "attachment",
          data: { filename: "finance_trend.csv" },
        },
      ],
    };

    renderChat([
      {
        id: "msg_user_attachment",
        role: "user",
        content: "Please summarize this file.",
        status: "done",
        timestamp: new Date().toISOString(),
        attachments: [attachment],
      },
    ]);

    expect(screen.getByText("finance_trend.csv")).toBeInTheDocument();
    expect(screen.getByText("Please summarize this file.")).toBeInTheDocument();
  });
});