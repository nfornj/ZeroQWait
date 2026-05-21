import type { CompleteAttachment } from "@assistant-ui/react";

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
  approval_request_id?: number | null;
  created_at?: string | null;
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

export interface OwnerDocumentRecord {
  id: number;
  filename: string;
  relative_path?: string | null;
  size_bytes: number;
  content_type?: string | null;
  knowledge_status: string;
  chunk_count: number;
  created_at?: string | null;
  updated_at?: string | null;
  duplicate?: boolean;
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
  /** ISO timestamp when the assistant response stream started (set on assistant messages) */
  processingStartedAt?: string;
  /** How long the full response took in milliseconds (set when status → done/error) */
  processingDuration?: number;
  agent?: string;
  retryMessage?: string;
  attachments?: readonly CompleteAttachment[];
  pendingAction?: PendingApproval;
  thinkingSteps?: ThinkingStep[];
  thinkingComplete?: boolean;
  charts?: AgentChart[];
  tables?: AgentTable[];
  files?: AgentFile[];
  /** Context-aware follow-up suggestions emitted by the backend after a completed response */
  suggestions?: string[];
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
  [key: string]: unknown;
}

export interface AgentChartSeries {
  key: string;
  label: string;
  color?: string;
}

export interface AgentChart {
  id: string;
  title: string;
  description?: string;
  chartType: ChartType;
  data: ChartDataPoint[];
  xKey?: string;
  yKey?: string;
  series?: AgentChartSeries[];
  colors?: string[];
  showLegend?: boolean;
  showGrid?: boolean;
  timestamp: string;
}

export interface ResolvedAgentChart extends AgentChart {
  xKey: string;
  series: AgentChartSeries[];
  showLegend: boolean;
  showGrid: boolean;
}

const isChartType = (value: unknown): value is ChartType =>
  value === "bar" || value === "line" || value === "pie" || value === "sparkline";

const isChartDataPoint = (value: unknown): value is ChartDataPoint =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const toChartId = () => `chart_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;

const formatSeriesLabel = (value: string) =>
  value
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/[_-]+/g, " ")
    .trim()
    .replace(/\b\w/g, (character) => character.toUpperCase());

const inferChartXKey = (data: ChartDataPoint[]): string => {
  const sample = data.find((row) => Object.keys(row).length > 0);
  if (!sample) {
    return "label";
  }

  if ("label" in sample) {
    return "label";
  }

  if ("period" in sample) {
    return "period";
  }

  const textKey = Object.keys(sample).find((key) => typeof sample[key] === "string");
  return textKey || Object.keys(sample)[0] || "label";
};

const inferChartSeriesKeys = (data: ChartDataPoint[], xKey: string): string[] => {
  const discoveredKeys = new Set<string>();

  data.forEach((row) => {
    Object.entries(row).forEach(([key, value]) => {
      if (key === xKey) {
        return;
      }

      const numericValue = typeof value === "number" ? value : Number(value);
      if (!Number.isNaN(numericValue)) {
        discoveredKeys.add(key);
      }
    });
  });

  return Array.from(discoveredKeys);
};

const normalizeChartSeries = (series: AgentChart["series"]): AgentChartSeries[] | undefined => {
  if (!Array.isArray(series)) {
    return undefined;
  }

  const normalized = series
    .filter((entry): entry is AgentChartSeries => Boolean(entry && typeof entry.key === "string" && entry.key.trim()))
    .map((entry) => ({
      key: entry.key.trim(),
      label: typeof entry.label === "string" && entry.label.trim() ? entry.label.trim() : formatSeriesLabel(entry.key),
      color: typeof entry.color === "string" && entry.color.trim() ? entry.color.trim() : undefined,
    }));

  return normalized.length > 0 ? normalized : undefined;
};

export const resolveAgentChart = (chart: AgentChart): ResolvedAgentChart | null => {
  const data = Array.isArray(chart.data) ? chart.data.filter(isChartDataPoint) : [];
  if (data.length === 0) {
    return null;
  }

  const xKey = typeof chart.xKey === "string" && chart.xKey.trim() ? chart.xKey.trim() : inferChartXKey(data);
  const explicitSeries = normalizeChartSeries(chart.series);
  const yKey = typeof chart.yKey === "string" && chart.yKey.trim() ? chart.yKey.trim() : undefined;
  const inferredSeriesKeys = yKey ? [yKey] : inferChartSeriesKeys(data, xKey);
  const series =
    explicitSeries ||
    inferredSeriesKeys.map((key) => ({
      key,
      label: formatSeriesLabel(key),
    }));

  if (series.length === 0) {
    return null;
  }

  return {
    ...chart,
    data,
    xKey,
    series,
    showLegend: typeof chart.showLegend === "boolean" ? chart.showLegend : series.length > 1,
    showGrid: typeof chart.showGrid === "boolean" ? chart.showGrid : true,
  };
};

export const createAgentChartFromPayload = (
  payload: Record<string, unknown>,
  timestamp: string = new Date().toISOString(),
): ResolvedAgentChart | null => {
  const data = Array.isArray(payload.data) ? payload.data.filter(isChartDataPoint) : [];
  if (data.length === 0) {
    return null;
  }

  const rawChartType = typeof payload.chartType === "string"
    ? payload.chartType
    : isChartType(payload.type)
      ? payload.type
      : undefined;
  const colors = Array.isArray(payload.colors)
    ? payload.colors.filter((value): value is string => typeof value === "string" && value.trim().length > 0)
    : undefined;

  return resolveAgentChart({
    id: toChartId(),
    title: typeof payload.title === "string" && payload.title.trim() ? payload.title.trim() : "Chart",
    description: typeof payload.description === "string" && payload.description.trim() ? payload.description.trim() : undefined,
    chartType: isChartType(rawChartType) ? rawChartType : "bar",
    data,
    xKey: typeof payload.xKey === "string" && payload.xKey.trim() ? payload.xKey.trim() : undefined,
    yKey: typeof payload.yKey === "string" && payload.yKey.trim() ? payload.yKey.trim() : undefined,
    series: normalizeChartSeries(Array.isArray(payload.series) ? (payload.series as AgentChartSeries[]) : undefined),
    colors: colors && colors.length > 0 ? colors : undefined,
    showLegend: typeof payload.showLegend === "boolean" ? payload.showLegend : undefined,
    showGrid: typeof payload.showGrid === "boolean" ? payload.showGrid : undefined,
    timestamp,
  });
};

export type TableFormatKind = "currency" | "delta" | "percent" | "number";

export interface AgentTableColumnFormat {
  kind: TableFormatKind;
  currency?: string;
  decimals?: number;
  showSign?: boolean;
  compact?: boolean;
  basis?: "fraction" | "unit";
  upIsPositive?: boolean;
}

export interface AgentTableColumn {
  key: string;
  label: string;
  align?: "left" | "center" | "right";
  priority?: "primary" | "secondary";
  format?: AgentTableColumnFormat;
}

export interface AgentTable {
  id: string;
  title: string;
  columns: AgentTableColumn[];
  data: Record<string, unknown>[];
  rowIdKey: string;
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
  type: "chart" | "file" | "summary" | "table";
  chart?: AgentChart;
  table?: AgentTable;
  file?: AgentFile;
  summary?: InsightSummary;
  timestamp: string;
}
