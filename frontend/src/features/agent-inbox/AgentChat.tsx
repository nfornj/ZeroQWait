import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ChevronRight,
  Copy,
  Edit2,
  ChevronDown,
  Mic,
  ChevronLeft,
  Brain,
  RefreshCw,
  Square,
  Wrench,
  Volume2,
  VolumeX,
  AlertTriangle,
  CheckCircle2,
  MessageCircle,
  XCircle,
} from "lucide-react";
import {
  AuiIf,
  ActionBarPrimitive,
  AssistantRuntimeProvider,
  BranchPickerPrimitive,
  ChainOfThoughtPrimitive,
  ComposerPrimitive,
  Interactables,
  MessagePrimitive,
  ThreadPrimitive,
  CompositeAttachmentAdapter,
  WebSpeechDictationAdapter,
  getExternalStoreMessages,
  type AppendMessage,
  type AttachmentAdapter,
  type AssistantClient,
  type CompleteAttachment,
  type MessageStatus,
  type TextMessagePartProps,
  type ThreadMessage,
  type ThreadMessageLike,
  useExternalStoreRuntime,
  useAui,
  useThreadComposer,
  useThreadRuntime,
} from "@assistant-ui/react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  Tooltip,
} from "recharts";
import ReactMarkdown from "react-markdown";
import DataTable from "../../components/DataTable";
import {
  UserMessageAttachments,
} from "../../components/AssistantUIAttachment";
import { Composer } from "../../components/assistant-ui/thread";
import { cn } from "../../lib/utils";
import { useOwnerBrand } from "../../hooks/useOwnerBrand";
import { resolveAgentChart } from "./types";
import type { AgentChart, AgentFile, AgentTable, ChatMessage, PendingApproval, ResolvedAgentChart } from "./types";
import { useShop } from "../../contexts/ShopContext";

export interface AgentChatPromptItem {
  id: string;
  label: string;
  prompt: string;
}

export interface AgentChatPromptSection {
  id: string;
  title: string;
  prompts: AgentChatPromptItem[];
}

export interface AgentChatSummaryChip {
  id: string;
  label: string;
}

export interface AgentChatSendPayload {
  text: string;
  attachments?: readonly CompleteAttachment[];
}

interface AgentChatProps {
  messages: ChatMessage[];
  isStreaming: boolean;
  isUploading?: boolean;
  onSend: (payload: AgentChatSendPayload) => Promise<void>;
  title?: string;
  subtitle?: string;
  summaryChips?: AgentChatSummaryChip[];
  promptSections?: AgentChatPromptSection[];
  header?: React.ReactNode;
  sidebar?: React.ReactNode;
  interactablesStorageKey?: string;
  isVoiceEnabled?: boolean;
  isSpeaking?: boolean;
  onToggleVoice?: () => void;
  isSubmittingApproval?: boolean;
  onApprovalDecision?: (approval: PendingApproval, approved: boolean) => Promise<boolean | void> | boolean | void;
  onDiscussApproval?: (approval: PendingApproval) => void;
}

type AgentChatInnerProps = Omit<AgentChatProps, "messages" | "onSend"> & {
  brandPrimary: string;
  brandSecondary: string;
  hasDictation: boolean;
  messageCount: number;
  sidebar?: React.ReactNode;
};

type MutableThreadPart = Exclude<ThreadMessageLike["content"], string>[number];

type PersistedInteractablesState = Record<string, { name: string; state: unknown }>;

type InteractablesMethods = {
  setPersistenceAdapter: (
    adapter: { save: (state: PersistedInteractablesState) => void | Promise<void> } | undefined,
  ) => void;
  importState: (saved: PersistedInteractablesState) => void;
  flush: () => Promise<void>;
};

type InteractablesAuiClient = AssistantClient & {
  interactables: () => InteractablesMethods;
};

type ApprovalActionContextValue = {
  isSubmittingApproval?: boolean;
  onApprovalDecision?: AgentChatProps["onApprovalDecision"];
  onDiscussApproval?: AgentChatProps["onDiscussApproval"];
};

const ApprovalActionContext = React.createContext<ApprovalActionContextValue>({});

const CHAIN_OF_THOUGHT_PARENT_SUFFIX = "reasoning";

const GENERIC_REASONING_PREFIXES = [
  "thinking", "analyzing", "reviewing", "checking", "gathering", "working", "planning",
];

const DOCUMENT_ATTACHMENT_ACCEPT = [
  ".txt", ".md", ".markdown", ".csv", ".json", ".html", ".htm", ".xml", ".yml", ".yaml", ".tsv",
  "text/plain", "text/markdown", "text/csv", "application/json", "text/html", "text/xml", "application/xml",
].join(",");

// ── Helpers ──────────────────────────────────────────────────────────────────

const formatAgentName = (value: string) =>
  value.replace(/[_-]+/g, " ").trim().replace(/\b\w/g, (c) => c.toUpperCase());

const formatAssistantLabel = (agent?: string | null) => {
  if (!agent?.trim()) return "Assistant";
  const formatted = formatAgentName(agent);
  return /assistant$/i.test(formatted) ? formatted : `${formatted} Assistant`;
};

const getAgentInitials = (label: string) =>
  label.split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0]?.toUpperCase() ?? "").join("") || "AI";

const formatTimestamp = (timestamp?: string) => {
  if (!timestamp) return "";
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
};

const getRenderableMessageText = (message?: ChatMessage) =>
  message?.content ? message.content.replace(/▊/g, "").trim() : "";

const hasRenderableMessagePayload = (message?: ChatMessage) =>
  Boolean(
    getRenderableMessageText(message) ||
      (message?.charts && message.charts.length > 0) ||
      (message?.tables && message.tables.length > 0) ||
      (message?.files && message.files.length > 0),
  );

const getTransientStatusLabel = (message?: ChatMessage, isRunning?: boolean) => {
  if (!message || message.role !== "assistant") return null;
  if (!isRunning && (message.status === "done" || message.status === "error")) return null;
  const hasProgressSignal = Boolean(
    isRunning || (message.thinkingSteps && message.thinkingSteps.length > 0) || message.status === "streaming",
  );
  if (!hasProgressSignal) return null;
  if (hasRenderableMessagePayload(message)) return null;
  const activeStep = [...(message.thinkingSteps || [])].reverse().find(
    (step) => step.status === "active" || step.status === "pending",
  );
  return activeStep?.label?.trim() || "Thinking";
};

const mapMessageStatus = (status: ChatMessage["status"]): MessageStatus | undefined => {
  switch (status) {
    case "streaming":
    case "sending":
      return { type: "running" };
    case "error":
      return { type: "incomplete", reason: "error" };
    case "done":
      return { type: "complete", reason: "unknown" };
    default:
      return undefined;
  }
};

const buildChainOfThoughtParts = (message: ChatMessage): MutableThreadPart[] => {
  if (message.role !== "assistant" || !message.thinkingSteps?.length) return [];
  const parentId = `${message.id}_${CHAIN_OF_THOUGHT_PARENT_SUFFIX}`;

  return message.thinkingSteps.flatMap((step) => {
    const label = step.label.trim();
    const toolName = step.toolName?.trim();
    if (step.id.startsWith("step_")) return [];
    if (toolName) {
      return [{ type: "tool-call", toolCallId: `${message.id}_${step.id}`, toolName, args: {}, argsText: "{}", parentId } as MutableThreadPart];
    }
    if (!label) return [];
    const lowerLabel = label.toLowerCase();
    if (GENERIC_REASONING_PREFIXES.some((p) => lowerLabel.startsWith(p)) && label.length < 60) return [];
    return [{ type: "reasoning", text: label, parentId } as MutableThreadPart];
  });
};

const hasChainOfThoughtParts = (message?: ThreadMessage) =>
  message?.role === "assistant" && message.content.some((p) => p.type === "reasoning" || p.type === "tool-call");

// ── Attachment adapter ────────────────────────────────────────────────────────

class KnowledgeBaseAttachmentAdapter implements AttachmentAdapter {
  accept = DOCUMENT_ATTACHMENT_ACCEPT;

  async add({ file }: { file: File }) {
    return {
      id: `${file.name}_${file.lastModified}_${file.size}`,
      type: "document" as const,
      name: file.name,
      contentType: file.type,
      file,
      status: { type: "requires-action", reason: "composer-send" } as const,
    };
  }

  async send(attachment: Awaited<ReturnType<KnowledgeBaseAttachmentAdapter["add"]>>) {
    const textContent = await new Promise<string>((resolve) => {
      const reader = new FileReader();
      reader.onload = (e) => resolve((e.target?.result as string) ?? "");
      reader.onerror = () => resolve("");
      reader.readAsText(attachment.file);
    });
    return {
      ...attachment,
      status: { type: "complete" } as const,
      content: [{
        type: "data" as const,
        name: "attachment",
        data: {
          filename: attachment.name,
          contentType: attachment.contentType || null,
          sizeBytes: attachment.file.size,
          textContent,
        },
      }],
    };
  }

  async remove() { return; }
}

const attachmentAdapter = new CompositeAttachmentAdapter([new KnowledgeBaseAttachmentAdapter()]);

const buildThreadMessage = (message: ChatMessage): ThreadMessageLike => {
  const content: MutableThreadPart[] = [...buildChainOfThoughtParts(message)];
  const renderableText = message.role === "assistant" ? getRenderableMessageText(message) : message.content;
  if (renderableText || message.role !== "assistant") {
    content.push({ type: "text", text: renderableText });
  }
  for (const chart of message.charts || []) content.push({ type: "data", name: "chart", data: chart });
  for (const table of message.tables || []) content.push({ type: "data", name: "table", data: table });
  for (const file of message.files || []) content.push({ type: "data", name: "file", data: file });
  if (content.length === 0) content.push({ type: "text", text: "" });

  return {
    id: message.id,
    role: message.role,
    content,
    attachments: message.role === "user" ? message.attachments || [] : undefined,
    createdAt: new Date(message.timestamp),
    status: message.role === "assistant" ? mapMessageStatus(message.status) : undefined,
    metadata: message.role === "assistant" ? { custom: { agent: message.agent } } : undefined,
  };
};

const getAppendMessageText = (message: AppendMessage) =>
  message.content.find((p): p is { type: "text"; text: string } => p.type === "text")?.text.trim() || "";

const getAppendMessageAttachments = (message: AppendMessage) =>
  message.role === "user" ? message.attachments || [] : [];

// ── Chart components (recharts) ───────────────────────────────────────────────

const buildChartPalette = (chart: ResolvedAgentChart, accent: string): string[] => {
  const explicit = Array.isArray(chart.colors)
    ? chart.colors.filter((v) => typeof v === "string" && v.trim())
    : [];
  return explicit.length > 0 ? explicit : [accent, "#0284c7", "#0f766e", "#ca8a04"];
};

const InlineChart: React.FC<{ chart: AgentChart; accent: string }> = ({ chart, accent }) => {
  const resolvedChart = resolveAgentChart(chart);
  if (!resolvedChart) return null;

  const palette = buildChartPalette(resolvedChart, accent);
  const primaryColor = palette[0] ?? accent;

  if (resolvedChart.chartType === "sparkline") {
    const sparkData = resolvedChart.data.map((point, i) => {
      const key = resolvedChart.series[0]?.key;
      const val = key ? point[key] : 0;
      return { i, value: typeof val === "number" ? val : Number(val ?? 0) };
    });
    return (
      <div className="mt-2 w-full">
        <div className="mb-1">
          <p className="text-sm font-bold">{resolvedChart.title}</p>
          {resolvedChart.description && <p className="text-xs text-muted-foreground">{resolvedChart.description}</p>}
        </div>
        <ResponsiveContainer width="100%" height={56}>
          <LineChart data={sparkData}>
            <Line type="monotone" dataKey="value" stroke={primaryColor} dot={false} strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    );
  }

  if (resolvedChart.chartType === "pie") {
    const key = resolvedChart.series[0]?.key;
    const pieData = resolvedChart.data.map((point, i) => ({
      name: String(point[resolvedChart.xKey] ?? i),
      value: key ? (typeof point[key] === "number" ? point[key] as number : Number(point[key] ?? 0)) : 0,
    }));
    return (
      <div className="mt-2 w-full">
        <div className="mb-1">
          <p className="text-sm font-bold">{resolvedChart.title}</p>
          {resolvedChart.description && <p className="text-xs text-muted-foreground">{resolvedChart.description}</p>}
        </div>
        <ResponsiveContainer width="100%" height={180}>
          <PieChart>
            <Pie data={pieData} dataKey="value" nameKey="name" innerRadius={32} outerRadius={72}>
              {pieData.map((_, i) => <Cell key={i} fill={palette[i % palette.length]} />)}
            </Pie>
            {resolvedChart.showLegend && <Tooltip />}
          </PieChart>
        </ResponsiveContainer>
      </div>
    );
  }

  if (resolvedChart.chartType === "line") {
    return (
      <div className="mt-2 w-full">
        <div className="mb-1">
          <p className="text-sm font-bold">{resolvedChart.title}</p>
          {resolvedChart.description && <p className="text-xs text-muted-foreground">{resolvedChart.description}</p>}
        </div>
        <ResponsiveContainer width="100%" height={180}>
          <LineChart data={resolvedChart.data} margin={{ top: 8, right: 12, bottom: 28, left: 36 }}>
            <XAxis dataKey={resolvedChart.xKey} tick={{ fontSize: 10 }} />
            {resolvedChart.showGrid && <YAxis tick={{ fontSize: 10 }} />}
            {resolvedChart.series.map((s, i) => (
              <Line key={s.key} type="monotone" dataKey={s.key}
                stroke={s.color || palette[i % palette.length]} dot={false} strokeWidth={2} name={s.label} />
            ))}
            {resolvedChart.showLegend && <Tooltip />}
          </LineChart>
        </ResponsiveContainer>
      </div>
    );
  }

  return (
    <div className="mt-2 w-full">
      <div className="mb-1">
        <p className="text-sm font-bold">{resolvedChart.title}</p>
        {resolvedChart.description && <p className="text-xs text-muted-foreground">{resolvedChart.description}</p>}
      </div>
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={resolvedChart.data} margin={{ top: 8, right: 12, bottom: 28, left: 36 }}>
          <XAxis dataKey={resolvedChart.xKey} tick={{ fontSize: 10 }} />
          {resolvedChart.showGrid && <YAxis tick={{ fontSize: 10 }} />}
          {resolvedChart.series.map((s, i) => (
            <Bar key={s.key} dataKey={s.key} fill={s.color || palette[i % palette.length]}
              name={s.label} radius={[3, 3, 0, 0]} />
          ))}
          {resolvedChart.showLegend && <Tooltip />}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};

const InlineFile: React.FC<{ file: AgentFile; accent: string }> = ({ file }) => {
  const href =
    file.content.startsWith("http://") || file.content.startsWith("https://")
      ? file.content
      : `data:${file.mimeType};base64,${file.content}`;

  return (
    <a href={href} target="_blank" rel="noreferrer" download={file.filename}
      className="mt-2 flex flex-col gap-1 text-inherit no-underline">
      <p className="text-sm font-bold">{file.filename}</p>
      <p className="text-xs text-muted-foreground">Open attachment</p>
    </a>
  );
};

const InlineTable: React.FC<{ table: AgentTable }> = ({ table }) => (
  <div className="mt-2 w-full max-w-full">
    <p className="text-sm font-bold mb-2">{table.title}</p>
    <DataTable columns={table.columns} data={table.data} rowIdKey={table.rowIdKey} />
  </div>
);

// ── Status indicator ──────────────────────────────────────────────────────────

const StatusIndicator: React.FC<{ label: string; brandPrimary: string }> = ({ label, brandPrimary }) => (
  <>
    <style>{`
      @keyframes agent-status-pulse {
        0%, 100% { opacity: 0.26; transform: scale(0.84); }
        50% { opacity: 1; transform: scale(1); }
      }
    `}</style>
    <div
      className="inline-flex items-center gap-2.5 rounded-full border px-2.5 py-2"
      style={{
        color: "hsl(var(--foreground) / 0.9)",
        backgroundColor: `${brandPrimary}14`,
        borderColor: `${brandPrimary}24`,
      }}
    >
      <div className="inline-flex items-center gap-1.5">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="inline-block rounded-full w-2 h-2"
            style={{
              backgroundColor: `${brandPrimary}e6`,
              animation: `agent-status-pulse 1.1s ${i * 0.14}s ease-in-out infinite`,
            }}
          />
        ))}
      </div>
      <span className="text-sm font-semibold tracking-[0.01em]">{label}</span>
    </div>
  </>
);

// ── Chain of thought ──────────────────────────────────────────────────────────

const MessageChainOfThought: React.FC<{ brandPrimary: string }> = ({ brandPrimary }) => {
  const [isExpanded, setIsExpanded] = useState(true);

  return (
    <ChainOfThoughtPrimitive.Root className="w-full mt-2">
      <ChainOfThoughtPrimitive.AccordionTrigger
        onClick={() => setIsExpanded((c) => !c)}
        className="w-full border-none bg-transparent p-0 text-left cursor-pointer"
      >
        <div
          className="flex items-center justify-between gap-2 px-3 py-2 rounded-xl"
          style={{ backgroundColor: `${brandPrimary}09` }}
        >
          <div className="flex items-center gap-2">
            <Brain className="h-4 w-4" style={{ color: `${brandPrimary}e6` }} />
            <span className="text-sm font-semibold text-foreground">Chain of thought</span>
          </div>
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        </div>
      </ChainOfThoughtPrimitive.AccordionTrigger>
      {isExpanded && (
        <ChainOfThoughtPrimitive.Parts>
          {({ part }: { part: ThreadMessage["content"][number] }) => {
            if (part.type === "reasoning") {
              const text = typeof part.text === "string" ? part.text.trim() : "";
              if (!text) return null;
              return (
                <div
                  className="mt-2 pl-4 pr-3 py-2 border-l-2"
                  style={{ borderColor: `${brandPrimary}29` }}
                >
                  <p className="text-sm text-muted-foreground leading-[1.55]">{text}</p>
                </div>
              );
            }
            if (part.type === "tool-call") {
              const toolName = typeof part.toolName === "string" ? part.toolName : "tool";
              return (
                <div
                  className="mt-2 flex items-center gap-2 pl-3 pr-4 py-2 rounded-lg"
                  style={{ backgroundColor: `${brandPrimary}1f` }}
                >
                  <Wrench className="h-4 w-4 flex-shrink-0" style={{ color: `${brandPrimary}eb` }} />
                  <span className="text-sm text-muted-foreground font-semibold">
                    {formatAgentName(toolName)}
                  </span>
                </div>
              );
            }
            return null;
          }}
        </ChainOfThoughtPrimitive.Parts>
      )}
    </ChainOfThoughtPrimitive.Root>
  );
};

// ── Markdown message ──────────────────────────────────────────────────────────

const MarkdownMessageText: React.FC<{ text: string; role: ChatMessage["role"] }> = ({ text, role }) => {
  if (!text.trim()) return null;

  return (
    <div className={cn(
      "text-[0.97rem] leading-[1.65]",
      "[&_p]:m-0 [&_p+p]:mt-4",
      "[&_ul,&_ol]:my-1 [&_ul,&_ol]:pl-8",
      "[&_li+li]:mt-1",
      "[&_strong]:font-bold",
      "[&_code]:font-mono [&_code]:text-[0.88em] [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:rounded",
      "[&_pre]:m-0 [&_pre]:mt-4 [&_pre]:p-3 [&_pre]:rounded-xl [&_pre]:overflow-x-auto",
      "[&_pre_code]:p-0",
      role === "user"
        ? "[&_code]:bg-white/20 [&_pre]:bg-white/10"
        : "[&_code]:bg-foreground/[0.08] [&_pre]:bg-foreground/[0.06]",
    )}>
      <ReactMarkdown
        components={{
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noreferrer"
              className={cn("font-semibold", role === "user" ? "text-white/90" : "text-foreground")}
            >
              {children}
            </a>
          ),
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
};

const formatApprovalActionLabel = (action?: string) => {
  if (!action) return "Approve";
  if (action.includes("assign_shift")) return "Approve shift";
  if (action.includes("close_queue")) return "Approve closure";
  if (action.includes("add_employee")) return "Approve hire";
  if (action.includes("record_payment")) return "Approve payment";
  if (action.includes("create_invoice")) return "Approve invoice";
  return "Approve";
};

const InlinePendingActionCard: React.FC<{
  approval: PendingApproval;
  accent: string;
}> = ({ approval, accent }) => {
  const { isSubmittingApproval, onApprovalDecision, onDiscussApproval } = React.useContext(ApprovalActionContext);
  const title = approval.title || approval.action.replace(/[_-]+/g, " ");
  const description =
    approval.summary ||
    approval.expected_impact ||
    approval.reason ||
    "This agent action is paused until the owner decides.";

  return (
    <div
      className="mt-2 rounded-2xl border bg-background/95 p-4"
      style={{ borderColor: `${accent}33` }}
    >
      <div className="flex items-start gap-3">
        <div
          className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full"
          style={{ backgroundColor: `${accent}14`, color: accent }}
        >
          <AlertTriangle className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-bold text-foreground">{title}</p>
            <span
              className="rounded-full px-2 py-0.5 text-[11px] font-bold"
              style={{ backgroundColor: `${accent}14`, color: accent }}
            >
              Needs decision
            </span>
            {approval.risk_level && (
              <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-[11px] font-bold text-amber-700">
                {String(approval.risk_level)} risk
              </span>
            )}
          </div>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">{description}</p>
          <p className="mt-2 text-xs font-semibold text-muted-foreground">
            Linked to Agent Actions. Approving or rejecting updates the agent workflow.
          </p>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-2 pl-12">
        <button
          type="button"
          disabled={isSubmittingApproval || !onApprovalDecision}
          onClick={() => void onApprovalDecision?.(approval, true)}
          className="inline-flex min-h-9 items-center gap-2 rounded-full px-3 text-sm font-bold text-white transition-opacity disabled:opacity-50"
          style={{ backgroundColor: accent }}
        >
          <CheckCircle2 className="h-4 w-4" />
          {isSubmittingApproval ? "Submitting..." : formatApprovalActionLabel(approval.action)}
        </button>
        <button
          type="button"
          disabled={isSubmittingApproval || !onApprovalDecision}
          onClick={() => void onApprovalDecision?.(approval, false)}
          className="inline-flex min-h-9 items-center gap-2 rounded-full border border-border px-3 text-sm font-bold text-foreground transition-colors hover:bg-muted disabled:opacity-50"
        >
          <XCircle className="h-4 w-4" />
          Reject
        </button>
        <button
          type="button"
          onClick={() => onDiscussApproval?.(approval)}
          className="inline-flex min-h-9 items-center gap-2 rounded-full border border-border px-3 text-sm font-bold text-foreground transition-colors hover:bg-muted"
        >
          <MessageCircle className="h-4 w-4" />
          Discuss
        </button>
      </div>
    </div>
  );
};

// ── Message rich content ──────────────────────────────────────────────────────

const MessageRichContent: React.FC<{
  accent: string;
  role: ChatMessage["role"];
  enableChainOfThought?: boolean;
  externalMessage?: ChatMessage;
}> = ({ accent, role, enableChainOfThought = false, externalMessage }) => {
  const charts = externalMessage?.charts || [];
  const tables = externalMessage?.tables || [];
  const files = externalMessage?.files || [];

  return (
    <div className="flex flex-col gap-2">
      <MessagePrimitive.Parts
        components={{
          Text: ({ text }: TextMessagePartProps) => <MarkdownMessageText text={text} role={role} />,
          ChainOfThought: enableChainOfThought ? () => <MessageChainOfThought brandPrimary={accent} /> : undefined,
        }}
      />
      {charts.map((chart) => <InlineChart key={chart.id} chart={chart} accent={accent} />)}
      {tables.map((table) => <InlineTable key={table.id} table={table} />)}
      {files.map((file) => <InlineFile key={file.id} file={file} accent={accent} />)}
      {externalMessage?.pendingAction && role === "assistant" && (
        <InlinePendingActionCard approval={externalMessage.pendingAction} accent={accent} />
      )}
    </div>
  );
};

// ── Branch picker ─────────────────────────────────────────────────────────────

const MessageBranchPicker: React.FC = () => (
  <BranchPickerPrimitive.Root hideWhenSingleBranch
    className="inline-flex items-center gap-0.5 text-muted-foreground/78 text-xs">
    <BranchPickerPrimitive.Previous asChild>
      <button type="button" aria-label="Previous branch"
        className="flex h-6 w-6 items-center justify-center rounded hover:bg-muted transition-colors">
        <ChevronLeft className="h-4 w-4" />
      </button>
    </BranchPickerPrimitive.Previous>
    <span className="font-semibold">
      <BranchPickerPrimitive.Number /> / <BranchPickerPrimitive.Count />
    </span>
    <BranchPickerPrimitive.Next asChild>
      <button type="button" aria-label="Next branch"
        className="flex h-6 w-6 items-center justify-center rounded hover:bg-muted transition-colors">
        <ChevronRight className="h-4 w-4" />
      </button>
    </BranchPickerPrimitive.Next>
  </BranchPickerPrimitive.Root>
);

// ── Action bars ───────────────────────────────────────────────────────────────

const iconBtnCls = "flex h-7 w-7 items-center justify-center rounded text-muted-foreground/88 hover:bg-muted transition-colors";

const UserActionBar: React.FC = () => (
  <ActionBarPrimitive.Root hideWhenRunning autohide="not-last"
    className="flex items-center gap-1">
    <ActionBarPrimitive.Edit asChild>
      <button type="button" aria-label="Edit message" className={iconBtnCls}>
        <Edit2 className="h-4 w-4" />
      </button>
    </ActionBarPrimitive.Edit>
  </ActionBarPrimitive.Root>
);

const AssistantActionBar: React.FC = () => (
  <ActionBarPrimitive.Root hideWhenRunning autohide="not-last"
    className="flex items-center gap-1">
    <ActionBarPrimitive.Copy asChild>
      <button type="button" aria-label="Copy response" className={iconBtnCls}>
        <Copy className="h-4 w-4" />
      </button>
    </ActionBarPrimitive.Copy>
    <ActionBarPrimitive.Reload asChild>
      <button type="button" aria-label="Regenerate response" className={iconBtnCls}>
        <RefreshCw className="h-4 w-4" />
      </button>
    </ActionBarPrimitive.Reload>
  </ActionBarPrimitive.Root>
);

// ── Edit composer ─────────────────────────────────────────────────────────────

const EditComposerMessage: React.FC<{ brandPrimary: string }> = ({ brandPrimary }) => (
  <MessagePrimitive.Root>
    <div className="flex justify-end w-full px-4 py-1.5">
      <ComposerPrimitive.Root
        className="w-full max-w-[82%] flex flex-col rounded-2xl border bg-background/95"
        style={{ borderColor: `${brandPrimary}2e` }}
      >
        <ComposerPrimitive.Input asChild>
          <textarea
            rows={1}
            className="min-h-[72px] max-h-60 border-none outline-none resize-none bg-transparent text-foreground font-inherit text-[0.98rem] leading-[1.55] p-4 pb-2"
          />
        </ComposerPrimitive.Input>
        <div className="flex justify-end gap-2 px-4 pb-4">
          <ComposerPrimitive.Cancel asChild>
            <button type="button" className="rounded-full px-4 py-1.5 text-sm font-bold text-muted-foreground hover:text-foreground transition-colors">
              Cancel
            </button>
          </ComposerPrimitive.Cancel>
          <ComposerPrimitive.Send asChild>
            <button type="button" className="rounded-full px-4 py-1.5 text-sm font-bold bg-primary text-primary-foreground hover:bg-primary/90 transition-colors">
              Update
            </button>
          </ComposerPrimitive.Send>
        </div>
      </ComposerPrimitive.Root>
    </div>
  </MessagePrimitive.Root>
);

// ── Thread messages ───────────────────────────────────────────────────────────

const UserThreadMessage = React.memo<{
  brandPrimary: string;
  externalMessage?: ChatMessage;
}>(({ brandPrimary, externalMessage }) => {
  const hasText = Boolean(externalMessage?.content.trim());
  const hasAttachments = Boolean(externalMessage?.attachments?.length);

  return (
    <MessagePrimitive.Root>
      <div className="flex justify-end w-full px-4 md:px-5 py-1.5">
        <div className="max-w-[90%] sm:max-w-[82%] flex flex-col items-end gap-1">
          <div
            className="flex flex-col rounded-[22px_22px_8px_22px] px-5 py-4"
            style={{
              backgroundColor: brandPrimary,
              color: "#fff",
              gap: hasAttachments && hasText ? 8 : 4,
            }}
          >
            {hasAttachments && <UserMessageAttachments />}
            {hasText && <MessageRichContent accent={brandPrimary} role="user" externalMessage={externalMessage} />}
          </div>
          {externalMessage?.timestamp && (
            <span className="text-xs text-muted-foreground/84">
              {formatTimestamp(externalMessage.timestamp)}
            </span>
          )}
          <div className="flex items-center gap-1.5">
            <MessageBranchPicker />
            <UserActionBar />
          </div>
        </div>
      </div>
    </MessagePrimitive.Root>
  );
});

const AssistantThreadMessage = React.memo<{
  externalMessage?: ChatMessage;
  threadMessage?: ThreadMessage;
  brandPrimary: string;
}>(({ externalMessage, threadMessage, brandPrimary }) => {
  const isRunning = threadMessage?.status?.type === "running";
  const statusLabel = getTransientStatusLabel(externalMessage, isRunning);
  const hasRenderablePayload = hasRenderableMessagePayload(externalMessage);
  const showChainOfThought = !hasRenderablePayload && hasChainOfThoughtParts(threadMessage);
  const label = formatAssistantLabel(externalMessage?.agent);
  const initials = getAgentInitials(label);

  if (!hasRenderablePayload && !statusLabel && !showChainOfThought) return null;

  return (
    <MessagePrimitive.Root>
      <div className="flex justify-start items-start gap-3 w-full px-4 md:px-5 py-2">
        {/* Avatar */}
        <div
          className="w-8 h-8 mt-0.5 rounded-full flex items-center justify-center flex-shrink-0 border text-xs font-bold"
          style={{
            backgroundColor: `${brandPrimary}1f`,
            color: brandPrimary,
            borderColor: `${brandPrimary}24`,
          }}
        >
          {initials}
        </div>

        {/* Content */}
        <div className="max-w-[96%] sm:max-w-[88%] w-full flex flex-col items-start gap-1.5">
          <span className="text-xs font-semibold text-muted-foreground/90">{label}</span>

          {statusLabel && !hasRenderablePayload && !showChainOfThought ? (
            <StatusIndicator label={statusLabel} brandPrimary={brandPrimary} />
          ) : (
            <>
              {(hasRenderablePayload || showChainOfThought) && (
                <div className="w-full text-foreground pr-2 sm:pr-6">
                  <MessageRichContent
                    accent={brandPrimary}
                    role="assistant"
                    enableChainOfThought={showChainOfThought}
                    externalMessage={externalMessage}
                  />
                </div>
              )}
              {externalMessage?.timestamp && (
                <span className="text-xs text-muted-foreground/88">
                  {formatTimestamp(externalMessage.timestamp)}
                </span>
              )}
              <div className="flex items-center gap-1.5">
                <MessageBranchPicker />
                <AssistantActionBar />
              </div>
            </>
          )}
        </div>
      </div>
    </MessagePrimitive.Root>
  );
});

const SystemThreadMessage = React.memo<{
  externalMessage?: ChatMessage;
  brandPrimary: string;
  brandSecondary: string;
}>(({ externalMessage, brandPrimary, brandSecondary }) => (
  <MessagePrimitive.Root>
    <div className="flex justify-start w-full px-4 md:px-5 py-1.5">
      <div className="max-w-[94%] sm:max-w-[84%] flex flex-col gap-1.5">
        <span className="text-xs text-muted-foreground/90">System</span>
        <div
          className="rounded-xl border border-dashed p-3"
          style={{
            borderColor: `${brandPrimary}2e`,
            backgroundColor: `${brandSecondary}1f`,
            color: "hsl(var(--muted-foreground))",
          }}
        >
          <MessageRichContent accent={brandPrimary} role="system" externalMessage={externalMessage} />
        </div>
      </div>
    </div>
  </MessagePrimitive.Root>
));

// ── Dictation button ──────────────────────────────────────────────────────────

const ComposerDictationButton: React.FC<{ disabled?: boolean; supported: boolean }> = ({
  disabled = false,
  supported,
}) => {
  const baseCls = "flex h-[34px] w-[34px] items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-40";

  if (!supported) {
    return (
      <button type="button" disabled className={baseCls} aria-label="Dictation unavailable">
        <Mic className="h-4 w-4" />
      </button>
    );
  }

  const getDictationState = (state: unknown) =>
    ((state as { composer?: { dictation?: unknown } } | null)?.composer?.dictation ?? null);

  return (
    <>
      <AuiIf condition={(s) => getDictationState(s) == null}>
        <ComposerPrimitive.Dictate asChild>
          <button type="button" disabled={disabled} aria-label="Start dictation" className={baseCls}>
            <Mic className="h-4 w-4" />
          </button>
        </ComposerPrimitive.Dictate>
      </AuiIf>
      <AuiIf condition={(s) => getDictationState(s) != null}>
        <ComposerPrimitive.StopDictation asChild>
          <button type="button" disabled={disabled} aria-label="Stop dictation"
            className={cn(baseCls, "text-red-400")}>
            <Square className="h-4 w-4" />
          </button>
        </ComposerPrimitive.StopDictation>
      </AuiIf>
    </>
  );
};

// ── Inner chat ────────────────────────────────────────────────────────────────

const AgentChatInner: React.FC<AgentChatInnerProps> = ({
  isStreaming,
  isUploading = false,
  title = "Hello there!",
  subtitle = "How can I help you today?",
  promptSections = [],
  brandPrimary,
  brandSecondary,
  hasDictation,
  messageCount,
  isVoiceEnabled = false,
  isSpeaking = false,
  onToggleVoice,
  isSubmittingApproval = false,
  onApprovalDecision,
  onDiscussApproval,
}) => {
  const folderInputRef = useRef<HTMLInputElement | null>(null);
  const threadRuntime = useThreadRuntime();
  const composerText = useThreadComposer((state) => state.text);
  const showWelcomeState = messageCount === 0;

  const promptGroups = useMemo<AgentChatPromptSection[]>(() => {
    if (promptSections.length > 0) return promptSections.filter((s) => s.prompts.length > 0);
    return [{
      id: "default",
      title: "Start with",
      prompts: [
        { id: "queue-summary", label: "Give me today's queue summary", prompt: "Give me today's queue summary" },
        { id: "revenue-trend", label: "Show this week's revenue trend", prompt: "Show this week's revenue trend" },
        { id: "shift-now", label: "Who is on shift now?", prompt: "Who is on shift now?" },
        { id: "crm-pipeline", label: "Show my CRM pipeline summary", prompt: "Show my CRM pipeline summary" },
      ],
    }];
  }, [promptSections]);

  const suggestionCards = useMemo(() =>
    promptGroups.flatMap((s) => s.prompts)
      .filter((p, i, arr) => arr.findIndex((c) => c.id === p.id) === i)
      .slice(0, 3),
  [promptGroups]);

  const insertPrompt = useCallback(
    (prompt: string) => {
      const trimmed = composerText.trim();
      if (!trimmed) { threadRuntime.composer.setText(prompt); return; }
      if (trimmed.includes(prompt)) return;
      threadRuntime.composer.setText(`${trimmed}\n${prompt}`);
    },
    [composerText, threadRuntime],
  );

  const handleFolderSelection = useCallback(
    async (event: React.ChangeEvent<HTMLInputElement>) => {
      const selectedFiles = Array.from(event.target.files || []);
      event.target.value = "";
      if (selectedFiles.length === 0 || isUploading || isStreaming) return;
      for (const file of selectedFiles) {
        try { await threadRuntime.composer.addAttachment(file); } catch { continue; }
      }
    },
    [isStreaming, isUploading, threadRuntime],
  );

  const openFolderPicker = useCallback(() => {
    if (folderInputRef.current) {
      folderInputRef.current.setAttribute("webkitdirectory", "");
      folderInputRef.current.setAttribute("directory", "");
      folderInputRef.current.click();
    }
  }, []);

  return (
    <div className="flex flex-col w-full h-full min-h-0 px-3 md:px-6 pb-0">
      <style>{`
        @keyframes agent-status-pulse {
          0%, 100% { opacity: 0.26; transform: scale(0.84); }
          50% { opacity: 1; transform: scale(1); }
        }
        @keyframes voice-pulse {
          0%, 100% { opacity: 0.7; }
          50% { opacity: 1; }
        }
      `}</style>

      <div className="w-full max-w-[900px] lg:max-w-none mx-auto flex flex-col flex-1 min-h-0 relative">
        <input
          ref={folderInputRef}
          type="file"
          hidden
          multiple
          accept={DOCUMENT_ATTACHMENT_ACCEPT}
          onChange={handleFolderSelection}
        />

        <ThreadPrimitive.Root
          className="flex-1 min-h-0 flex flex-col"
          style={{ fontFamily: "inherit" }}
        >
          <ThreadPrimitive.Viewport
            autoScroll
            className="flex-1 min-h-0 rounded-3xl bg-transparent overflow-x-hidden overflow-y-auto"
            style={{ paddingTop: showWelcomeState ? 0 : 10 }}
          >
            {showWelcomeState ? (
              <div className="min-h-full flex items-stretch justify-start px-3 md:px-4 pt-4 md:pt-6 pb-3 md:pb-4">
                <div className="w-full max-w-2xl mx-auto flex flex-col gap-6">
                  <div className="flex flex-col gap-1">
                    <h2 className="text-3xl font-bold tracking-[-0.035em] text-foreground">{title}</h2>
                    <p className="text-xl font-normal text-muted-foreground tracking-[-0.02em]">{subtitle}</p>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2 w-full">
                    {suggestionCards.map((prompt) => (
                      <button
                        key={prompt.id}
                        type="button"
                        onClick={() => insertPrompt(prompt.prompt)}
                        disabled={isStreaming || isUploading}
                        className={cn(
                          "p-4 rounded-xl border text-left transition-all duration-150",
                          "hover:-translate-y-px disabled:opacity-70 disabled:cursor-default",
                        )}
                        style={{
                          borderColor: `${brandPrimary}24`,
                          backgroundColor: "hsl(var(--background) / 0.74)",
                        }}
                        onMouseEnter={(e) => {
                          if (!isStreaming && !isUploading) {
                            (e.currentTarget as HTMLElement).style.borderColor = `${brandPrimary}47`;
                            (e.currentTarget as HTMLElement).style.backgroundColor = `${brandPrimary}0f`;
                          }
                        }}
                        onMouseLeave={(e) => {
                          (e.currentTarget as HTMLElement).style.borderColor = `${brandPrimary}24`;
                          (e.currentTarget as HTMLElement).style.backgroundColor = "hsl(var(--background) / 0.74)";
                        }}
                      >
                        <p className="text-base font-semibold text-foreground">{prompt.label}</p>
                        <p className="mt-1 text-sm text-muted-foreground leading-[1.45]">{prompt.prompt}</p>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <ThreadPrimitive.Messages>
                {({ message }: { message: ThreadMessage }) => {
                  const [externalMessage] = getExternalStoreMessages(message) as ChatMessage[];
                  const isEditing = Boolean((message as ThreadMessage & { composer?: { isEditing?: boolean } }).composer?.isEditing);

                  if (externalMessage?.role === "user") {
                    if (isEditing) return <EditComposerMessage brandPrimary={brandPrimary} />;
                    return <UserThreadMessage externalMessage={externalMessage} brandPrimary={brandPrimary} />;
                  }
                  if (externalMessage?.role === "system") {
                    return <SystemThreadMessage externalMessage={externalMessage} brandPrimary={brandPrimary} brandSecondary={brandSecondary} />;
                  }
                  return <AssistantThreadMessage externalMessage={externalMessage} threadMessage={message} brandPrimary={brandPrimary} />;
                }}
              </ThreadPrimitive.Messages>
            )}
          </ThreadPrimitive.Viewport>

          {/* Composer footer */}
          <div
            className="w-full max-w-[760px] mx-auto mt-auto pt-3 pb-4 md:pb-5"
            style={{
              background: "linear-gradient(180deg, transparent 0%, hsl(var(--background) / 0.94) 24%)",
            }}
          >
            <ThreadPrimitive.ViewportFooter className="w-full p-0">
              <Composer
                placeholder="Ask a follow-up..."
                disabled={isUploading || isStreaming}
                isRunning={isStreaming}
                accentColor={brandPrimary}
                onOpenFolderPicker={openFolderPicker}
                dictationControl={
                  <>
                    {onToggleVoice && (
                      <button
                        type="button"
                        onClick={onToggleVoice}
                        disabled={isUploading || isStreaming}
                        aria-label={isVoiceEnabled ? "Disable voice" : "Enable voice"}
                        className={cn(
                          "flex h-[34px] w-[34px] items-center justify-center rounded-full text-muted-foreground transition-colors disabled:opacity-40",
                          isVoiceEnabled ? "" : "hover:bg-muted hover:text-foreground",
                        )}
                        style={{
                          color: isVoiceEnabled ? brandPrimary : undefined,
                          backgroundColor: isVoiceEnabled ? `${brandPrimary}14` : undefined,
                          animation: isSpeaking ? "voice-pulse 1s ease-in-out infinite" : "none",
                        }}
                      >
                        {isVoiceEnabled ? <Volume2 className="h-4 w-4" /> : <VolumeX className="h-4 w-4" />}
                      </button>
                    )}
                    <ComposerDictationButton disabled={isUploading || isStreaming} supported={hasDictation} />
                  </>
                }
              />
            </ThreadPrimitive.ViewportFooter>
          </div>
        </ThreadPrimitive.Root>
      </div>
    </div>
  );
};

// ── AgentChat (outer) ─────────────────────────────────────────────────────────

const AgentChat: React.FC<AgentChatProps> = ({
  messages,
  isStreaming,
  isUploading = false,
  onSend,
  title = "Hello there!",
  subtitle = "How can I help you today?",
  summaryChips = [],
  promptSections = [],
  header,
  sidebar,
  interactablesStorageKey,
  isVoiceEnabled = false,
  isSpeaking = false,
  onToggleVoice,
  isSubmittingApproval = false,
  onApprovalDecision,
  onDiscussApproval,
}) => {
  const { shop } = useShop();
  const brand = useOwnerBrand();
  const aui = useAui({ interactables: Interactables() } as any) as InteractablesAuiClient;
  const lastInteractablesStorageKeyRef = useRef<string | null>(null);
  const brandPrimary = shop?.primary_color || brand.primary;
  const brandSecondary = shop?.secondary_color || brandPrimary;

  const dictationAdapter = useMemo(
    () =>
      WebSpeechDictationAdapter.isSupported()
        ? new WebSpeechDictationAdapter({ language: "en-US", continuous: true, interimResults: true })
        : undefined,
    [],
  );

  const convertMessage = useCallback((message: ChatMessage) => buildThreadMessage(message), []);

  const handleNewMessage = useCallback(
    async (message: AppendMessage) => {
      const trimmed = getAppendMessageText(message);
      const attachments = getAppendMessageAttachments(message);
      if ((!trimmed && attachments.length === 0) || isStreaming || isUploading) return;
      await onSend({ text: trimmed, attachments });
    },
    [isStreaming, isUploading, onSend],
  );

  const handleEditMessage = useCallback(
    async (message: AppendMessage) => {
      const trimmed = getAppendMessageText(message);
      const attachments = getAppendMessageAttachments(message);
      if ((!trimmed && attachments.length === 0) || isStreaming || isUploading) return;
      await onSend({ text: trimmed, attachments });
    },
    [isStreaming, isUploading, onSend],
  );

  const handleReloadMessage = useCallback(
    async (parentId: string | null) => {
      if (!parentId || isStreaming || isUploading) return;
      const targetIndex = messages.findIndex((m) => m.id === parentId);
      if (targetIndex === -1) return;
      const targetMessage = messages[targetIndex];
      const retryText =
        targetMessage?.retryMessage ||
        [...messages.slice(0, targetIndex)].reverse().find((m) => m.role === "user")?.content ||
        "";
      if (!retryText.trim()) return;
      await onSend({ text: retryText.trim() });
    },
    [isStreaming, isUploading, messages, onSend],
  );

  const runtime = useExternalStoreRuntime<ChatMessage>({
    messages,
    convertMessage,
    onNew: handleNewMessage,
    onEdit: handleEditMessage,
    onReload: handleReloadMessage,
    isDisabled: isStreaming || isUploading,
    adapters: { attachments: attachmentAdapter, dictation: dictationAdapter },
  });

  const approvalActionContext = useMemo<ApprovalActionContextValue>(
    () => ({
      isSubmittingApproval,
      onApprovalDecision,
      onDiscussApproval,
    }),
    [isSubmittingApproval, onApprovalDecision, onDiscussApproval],
  );

  useEffect(() => {
    if (!interactablesStorageKey || typeof window === "undefined") {
      aui.interactables().setPersistenceAdapter(undefined);
      return;
    }
    aui.interactables().setPersistenceAdapter({
      save: async (state: PersistedInteractablesState) => {
        window.localStorage.setItem(interactablesStorageKey, JSON.stringify(state));
      },
    });
    if (lastInteractablesStorageKeyRef.current !== interactablesStorageKey) {
      const savedState = window.localStorage.getItem(interactablesStorageKey);
      if (savedState) {
        try { aui.interactables().importState(JSON.parse(savedState)); }
        catch { window.localStorage.removeItem(interactablesStorageKey); }
      }
      lastInteractablesStorageKeyRef.current = interactablesStorageKey;
    }
    return () => { void aui.interactables().flush(); };
  }, [aui, interactablesStorageKey]);

  return (
    <AssistantRuntimeProvider runtime={runtime} aui={aui}>
      <ApprovalActionContext.Provider value={approvalActionContext}>
        <div className="flex flex-col md:flex-row gap-0 flex-1 min-h-0 w-full">
          <div className="flex-1 min-w-0 min-h-0 flex flex-col">
            {header && (
              <div className="px-3 md:px-6 pt-3 md:pt-4 pb-2 md:pb-2.5 flex-shrink-0">
                {header}
              </div>
            )}
            <div className="flex-1 min-h-0">
              <AgentChatInner
                isStreaming={isStreaming}
                isUploading={isUploading}
                title={title}
                subtitle={subtitle}
                summaryChips={summaryChips}
                promptSections={promptSections}
                brandPrimary={brandPrimary}
                brandSecondary={brandSecondary}
                hasDictation={Boolean(dictationAdapter)}
                messageCount={messages.length}
                isVoiceEnabled={isVoiceEnabled}
                isSpeaking={isSpeaking}
                onToggleVoice={onToggleVoice}
              />
            </div>
          </div>

          {sidebar && (
            <div className="w-full md:w-[380px] md:min-w-[340px] md:max-w-[420px] flex-shrink-0 min-h-[320px] md:min-h-0 flex self-stretch md:h-full">
              {sidebar}
            </div>
          )}
        </div>
      </ApprovalActionContext.Provider>
    </AssistantRuntimeProvider>
  );
};

export default AgentChat;
