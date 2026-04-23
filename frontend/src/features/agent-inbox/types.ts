export interface ThinkingStep {
  id: string;
  label: string;
  status: "pending" | "active" | "completed" | "error";
  agent?: string | null;
  toolName?: string | null;
}

export interface PendingApproval {
  action_id?: string;
  action: string;
  details: Record<string, unknown>;
  shop_id: number;
  policy_key?: string;
  policy_mode?: string;
  category?: string;
  title?: string;
  summary?: string;
  reason?: string;
  expected_impact?: string;
  risk_level?: "low" | "medium" | "high" | string;
  urgency?: string;
  recommended_decision?: string;
}

export interface ShopPolicy {
  action: string;
  policy_key: string;
  category: string;
  title: string;
  risk_level?: "low" | "medium" | "high" | string;
  urgency?: string;
  default_mode: string;
  mode: string;
  explicit: boolean;
  supported_modes: string[];
}

export interface ApprovalExecutionResult {
  message?: string;
  status?: string;
  shop_id?: number;
  user_id?: number;
  shift?: Record<string, unknown>;
  employee?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface BriefingAlert {
  severity: "success" | "info" | "warning" | "error";
  title: string;
  body: string;
  created_at?: string;
}

export interface BriefingAction {
  label: string;
  payload: string;
  description?: string;
}

export interface OwnerBriefing {
  shop_id: number;
  shop_name: string;
  generated_at: string;
  source?: string;
  summary: string;
  metrics: {
    queue_length: number;
    estimated_wait_minutes: number;
    people_being_served: number;
    active_employees: number;
    active_services: number;
    pending_approvals: number;
    today_revenue: number;
    today_transactions: number;
    weekly_revenue: number;
  };
  alerts: BriefingAlert[];
  alert_history?: BriefingAlert[];
  recent_notifications?: AgentFeedEvent[];
  recommendations: string[];
  actions: BriefingAction[];
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  status: "sending" | "streaming" | "done" | "error";
  timestamp: string;
  agent?: string;
  retryMessage?: string;
  pendingAction?: PendingApproval;
  thinkingSteps?: ThinkingStep[];
  thinkingComplete?: boolean;
  charts?: AgentChart[];
  files?: AgentFile[];
}

export interface AgentFeedEvent {
  id: string;
  type:
    | "chat"
    | "agent_switch"
    | "tool_call"
    | "tool_result"
    | "approval_required"
    | "approval_decision"
    | "queue_update"
    | "error"
    | "system";
  title: string;
  description: string;
  timestamp: string;
  severity?: "success" | "info" | "warning" | "error" | string;
  status?: "unread" | "read" | "archived" | string;
  notification_type?: string;
  notification_id?: number | null;
  payload?: unknown;
}

/* ── Rich content types for charts, files, and follow-up suggestions ── */

export type ChartType = "bar" | "line" | "pie" | "sparkline";

export interface ChartDataPoint {
  label: string;
  value: number;
  [key: string]: unknown;
}

export interface AgentChart {
  id: string;
  title: string;
  chartType: ChartType;
  data: ChartDataPoint[];
  xKey?: string;
  yKey?: string;
  timestamp: string;
}

export interface AgentFile {
  id: string;
  filename: string;
  /** base64-encoded blob OR a URL */
  content: string;
  mimeType: string;
  timestamp: string;
}

export interface InsightSummary {
  id: string;
  title: string;
  body: string;
  severity: "success" | "info" | "warning" | "error";
  chips?: string[];
  timestamp: string;
}

export interface InsightItem {
  id: string;
  type: "chart" | "file" | "summary";
  chart?: AgentChart;
  file?: AgentFile;
  summary?: InsightSummary;
  timestamp: string;
}
