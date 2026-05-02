import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  alpha,
  Avatar,
  Box,
  Button,
  IconButton,
  Stack,
  Typography,
  useTheme,
} from "@mui/material";
import ChevronRightRoundedIcon from "@mui/icons-material/ChevronRightRounded";
import ContentCopyRoundedIcon from "@mui/icons-material/ContentCopyRounded";
import EditOutlinedIcon from "@mui/icons-material/EditOutlined";
import ExpandMoreRoundedIcon from "@mui/icons-material/ExpandMoreRounded";
import MicNoneRoundedIcon from "@mui/icons-material/MicNoneRounded";
import NavigateBeforeRoundedIcon from "@mui/icons-material/NavigateBeforeRounded";
import NavigateNextRoundedIcon from "@mui/icons-material/NavigateNextRounded";
import PsychologyAltOutlinedIcon from "@mui/icons-material/PsychologyAltOutlined";
import RefreshRoundedIcon from "@mui/icons-material/RefreshRounded";
import StopRoundedIcon from "@mui/icons-material/StopRounded";
import BuildCircleOutlinedIcon from "@mui/icons-material/BuildCircleOutlined";
import UploadFileRoundedIcon from "@mui/icons-material/UploadFileRounded";
import VolumeUpRoundedIcon from "@mui/icons-material/VolumeUpRounded";
import VolumeOffRoundedIcon from "@mui/icons-material/VolumeOffRounded";
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
import { BarChart } from "@mui/x-charts/BarChart";
import { LineChart } from "@mui/x-charts/LineChart";
import { PieChart } from "@mui/x-charts/PieChart";
import { SparkLineChart } from "@mui/x-charts/SparkLineChart";
import ReactMarkdown from "react-markdown";
import DataTable from "../../components/DataTable";
import {
  ComposerAddAttachment,
  ComposerAttachments,
  UserMessageAttachments,
} from "../../components/AssistantUIAttachment";
import { Composer } from "../../components/assistant-ui/thread";
import { resolveAgentChart } from "./types";
import type { AgentChart, AgentFile, AgentTable, ChatMessage, ResolvedAgentChart } from "./types";
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
    adapter:
      | {
          save: (state: PersistedInteractablesState) => void | Promise<void>;
        }
      | undefined,
  ) => void;
  importState: (saved: PersistedInteractablesState) => void;
  flush: () => Promise<void>;
};

type InteractablesAuiClient = AssistantClient & {
  interactables: () => InteractablesMethods;
};

const CHAIN_OF_THOUGHT_PARENT_SUFFIX = "reasoning";

const GENERIC_REASONING_PREFIXES = [
  "thinking",
  "analyzing",
  "reviewing",
  "checking",
  "gathering",
  "working",
  "planning",
];

const DOCUMENT_ATTACHMENT_ACCEPT = [
  ".txt",
  ".md",
  ".markdown",
  ".csv",
  ".json",
  ".html",
  ".htm",
  ".xml",
  ".yml",
  ".yaml",
  ".tsv",
  "text/plain",
  "text/markdown",
  "text/csv",
  "application/json",
  "text/html",
  "text/xml",
  "application/xml",
].join(",");

const ComposerDictationButton: React.FC<{ disabled?: boolean; supported: boolean }> = ({ disabled = false, supported }) => {
  const muiTheme = useTheme();
  const getDictationState = (state: unknown) =>
    ((state as { composer?: { dictation?: unknown } } | null)?.composer?.dictation ?? null);

  const baseSx = {
    width: 34,
    height: 34,
    borderRadius: 2.5,
    color: muiTheme.palette.mode === "dark" ? alpha("#f5f3ef", 0.82) : "#6f6a63",
    "&:hover": {
      backgroundColor:
        muiTheme.palette.mode === "dark"
          ? alpha("#f5f3ef", 0.08)
          : alpha("#1f1d1a", 0.06),
    },
    "&.Mui-disabled": {
      color: alpha(muiTheme.palette.text.secondary, 0.4),
    },
  } as const;

  if (!supported) {
    return (
      <IconButton size="small" disabled sx={baseSx} aria-label="Dictation unavailable">
        <MicNoneRoundedIcon fontSize="small" />
      </IconButton>
    );
  }

  return (
    <>
      <AuiIf condition={(s) => getDictationState(s) == null}>
        <ComposerPrimitive.Dictate asChild>
          <IconButton size="small" disabled={disabled} sx={baseSx} aria-label="Start dictation">
            <MicNoneRoundedIcon fontSize="small" />
          </IconButton>
        </ComposerPrimitive.Dictate>
      </AuiIf>

      <AuiIf condition={(s) => getDictationState(s) != null}>
        <ComposerPrimitive.StopDictation asChild>
          <IconButton
            size="small"
            disabled={disabled}
            aria-label="Stop dictation"
            sx={{
              ...baseSx,
              color: muiTheme.palette.mode === "dark" ? "#f5f3ef" : muiTheme.palette.error.main,
            }}
          >
            <StopRoundedIcon sx={{ fontSize: 18 }} />
          </IconButton>
        </ComposerPrimitive.StopDictation>
      </AuiIf>
    </>
  );
};

const formatAgentName = (value: string) => {
  return value
    .replace(/[_-]+/g, " ")
    .trim()
    .replace(/\b\w/g, (char) => char.toUpperCase());
};

const formatAssistantLabel = (agent?: string | null) => {
  if (!agent?.trim()) {
    return "Assistant";
  }

  const formatted = formatAgentName(agent);

  if (/assistant$/i.test(formatted)) {
    return formatted;
  }

  return `${formatted} Assistant`;
};

const getAgentInitials = (label: string) => {
  const initials = label
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");

  return initials || "AI";
};

const formatTimestamp = (timestamp?: string) => {
  if (!timestamp) return "";

  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return "";

  return date.toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
  });
};

const getRenderableMessageText = (message?: ChatMessage) => {
  if (!message?.content) {
    return "";
  }

  return message.content.replace(/▊/g, "").trim();
};

const hasRenderableMessagePayload = (message?: ChatMessage) => {
  return Boolean(
    getRenderableMessageText(message) ||
      (message?.charts && message.charts.length > 0) ||
      (message?.tables && message.tables.length > 0) ||
      (message?.files && message.files.length > 0),
  );
};

const getTransientStatusLabel = (message?: ChatMessage, isRunning?: boolean) => {
  if (!message || message.role !== "assistant") {
    return null;
  }

  if (!isRunning && (message.status === "done" || message.status === "error")) {
    return null;
  }

  const hasProgressSignal = Boolean(
    isRunning || (message.thinkingSteps && message.thinkingSteps.length > 0) || message.status === "streaming",
  );
  if (!hasProgressSignal) {
    return null;
  }

  const hasRenderablePayload = hasRenderableMessagePayload(message);
  if (hasRenderablePayload) {
    return null;
  }

  const activeStep = [...(message.thinkingSteps || [])]
    .reverse()
    .find((step) => step.status === "active" || step.status === "pending");

  if (activeStep?.label?.trim()) {
    return activeStep.label.trim();
  }

  return "Thinking";
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
  if (message.role !== "assistant" || !message.thinkingSteps?.length) {
    return [];
  }

  const parentId = `${message.id}_${CHAIN_OF_THOUGHT_PARENT_SUFFIX}`;

  return message.thinkingSteps.flatMap((step) => {
    const label = step.label.trim();
    const toolName = step.toolName?.trim();

    if (step.id.startsWith("step_")) {
      return [];
    }

    if (toolName) {
      return [
        {
        type: "tool-call",
        toolCallId: `${message.id}_${step.id}`,
        toolName,
        args: {},
        argsText: "{}",
        parentId,
        } as MutableThreadPart,
      ];
    }

    if (!label) {
      return [];
    }

    const lowerLabel = label.toLowerCase();
    const isGenericStatusLabel = GENERIC_REASONING_PREFIXES.some((prefix) => lowerLabel.startsWith(prefix));
    if (isGenericStatusLabel && label.length < 60) {
      return [];
    }

    return [
      {
        type: "reasoning",
        text: label,
        parentId,
      } as MutableThreadPart,
    ];
  });
};

const hasChainOfThoughtParts = (message?: ThreadMessage) => {
  if (!message || message.role !== "assistant") {
    return false;
  }

  return message.content.some((part) => part.type === "reasoning" || part.type === "tool-call");
};

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
      content: [
        {
          type: "data" as const,
          name: "attachment",
          data: {
            filename: attachment.name,
            contentType: attachment.contentType || null,
            sizeBytes: attachment.file.size,
            textContent,
          },
        },
      ],
    };
  }

  async remove() {
    return;
  }
}

const attachmentAdapter = new CompositeAttachmentAdapter([new KnowledgeBaseAttachmentAdapter()]);

const buildThreadMessage = (message: ChatMessage): ThreadMessageLike => {
  const content: MutableThreadPart[] = [...buildChainOfThoughtParts(message)];
  const renderableText = message.role === "assistant" ? getRenderableMessageText(message) : message.content;

  if (renderableText || message.role !== "assistant") {
    content.push({
      type: "text",
      text: renderableText,
    });
  }

  for (const chart of message.charts || []) {
    content.push({
      type: "data",
      name: "chart",
      data: chart,
    });
  }

  for (const table of message.tables || []) {
    content.push({
      type: "data",
      name: "table",
      data: table,
    });
  }

  for (const file of message.files || []) {
    content.push({
      type: "data",
      name: "file",
      data: file,
    });
  }

  if (content.length === 0) {
    content.push({ type: "text", text: "" });
  }

  return {
    id: message.id,
    role: message.role,
    content,
    attachments: message.role === "user" ? message.attachments || [] : undefined,
    createdAt: new Date(message.timestamp),
    status: message.role === "assistant" ? mapMessageStatus(message.status) : undefined,
    metadata:
      message.role === "assistant"
        ? {
            custom: {
              agent: message.agent,
            },
          }
        : undefined,
  };
};

const getAppendMessageText = (message: AppendMessage) => {
  const textPart = message.content.find(
    (part): part is { type: "text"; text: string } => part.type === "text",
  );

  return textPart?.text.trim() || "";
};

const getAppendMessageAttachments = (message: AppendMessage) => {
  return message.role === "user" ? message.attachments || [] : [];
};

const buildChartPalette = (chart: ResolvedAgentChart, accent: string, fallbackColors: string[]) => {
  const explicit = Array.isArray(chart.colors) ? chart.colors.filter((value) => typeof value === "string" && value.trim()) : [];
  return explicit.length > 0 ? explicit : [accent, ...fallbackColors];
};

const toChartSeries = (chart: ResolvedAgentChart, palette: string[]) =>
  chart.series.map((series, index) => ({
    data: chart.data.map((point) => {
      const rawValue = point[series.key];
      return typeof rawValue === "number" ? rawValue : Number(rawValue ?? 0);
    }),
    label: series.label,
    color: series.color || palette[index % palette.length],
  }));

const InlineChart: React.FC<{ chart: AgentChart; accent: string }> = ({ chart, accent }) => {
  const muiTheme = useTheme();
  const resolvedChart = resolveAgentChart(chart);

  if (!resolvedChart) {
    return null;
  }

  const labels = resolvedChart.data.map((point) => String(point[resolvedChart.xKey] ?? ""));
  const palette = buildChartPalette(resolvedChart, accent, [
    muiTheme.palette.info.main,
    muiTheme.palette.success.main,
    muiTheme.palette.warning.main,
  ]);
  const chartSeries = toChartSeries(resolvedChart, palette);
  const primarySeries = chartSeries[0];

  return (
    <Box
      sx={{
        mt: 1,
        width: "100%",
        maxWidth: "100%",
      }}
    >
      <Box sx={{ mb: 1 }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
          {resolvedChart.title}
        </Typography>
        {resolvedChart.description ? (
          <Typography variant="caption" sx={{ color: "text.secondary" }}>
            {resolvedChart.description}
          </Typography>
        ) : null}
      </Box>
      {resolvedChart.chartType === "sparkline" && primarySeries ? (
        <SparkLineChart data={primarySeries.data} height={56} curve="natural" area color={primarySeries.color} />
      ) : resolvedChart.chartType === "pie" && primarySeries ? (
        <PieChart
          series={[
            {
              data: resolvedChart.data.map((point, index) => ({
                id: index,
                value: primarySeries.data[index] ?? 0,
                label: String(point[resolvedChart.xKey] ?? ""),
              })),
            },
          ]}
          height={180}
          margin={{ top: 8, right: 8, bottom: 8, left: 8 }}
          hideLegend={!resolvedChart.showLegend}
        />
      ) : resolvedChart.chartType === "line" ? (
        <LineChart
          xAxis={[{ data: labels, scaleType: "band" }]}
          series={chartSeries}
          height={180}
          margin={{ top: 8, right: 12, bottom: 28, left: 36 }}
          hideLegend={!resolvedChart.showLegend}
          grid={{ horizontal: resolvedChart.showGrid, vertical: false }}
        />
      ) : (
        <BarChart
          xAxis={[{ data: labels, scaleType: "band" }]}
          series={chartSeries}
          height={180}
          margin={{ top: 8, right: 12, bottom: 28, left: 36 }}
          hideLegend={!resolvedChart.showLegend}
          grid={{ horizontal: resolvedChart.showGrid, vertical: false }}
        />
      )}
    </Box>
  );
};

const InlineFile: React.FC<{ file: AgentFile; accent: string }> = ({ file, accent }) => {
  const href =
    file.content.startsWith("http://") || file.content.startsWith("https://")
      ? file.content
      : `data:${file.mimeType};base64,${file.content}`;

  return (
    <Box
      component="a"
      href={href}
      target="_blank"
      rel="noreferrer"
      download={file.filename}
      sx={{
        mt: 1,
        p: 0,
        display: "flex",
        flexDirection: "column",
        gap: 0.35,
        color: "inherit",
        textDecoration: "none",
      }}
    >
      <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
        {file.filename}
      </Typography>
      <Typography variant="caption" color="text.secondary">
        Open attachment
      </Typography>
    </Box>
  );
};

const InlineTable: React.FC<{ table: AgentTable; accent: string }> = ({ table, accent }) => {
  return (
    <Box
      sx={{
        mt: 1,
        width: "100%",
        maxWidth: "100%",
      }}
    >
      <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
        {table.title}
      </Typography>
      <DataTable columns={table.columns} data={table.data} rowIdKey={table.rowIdKey} />
    </Box>
  );
};

const StatusIndicator: React.FC<{ label: string; brandPrimary: string }> = ({ label, brandPrimary }) => {
  const muiTheme = useTheme();

  return (
    <Box
      sx={{
        display: "inline-flex",
        alignItems: "center",
        gap: 1.1,
        px: 1.1,
        py: 0.85,
        borderRadius: 999,
        color: alpha(muiTheme.palette.text.primary, 0.9),
        bgcolor: alpha(brandPrimary, muiTheme.palette.mode === "dark" ? 0.14 : 0.08),
        border: "1px solid",
        borderColor: alpha(brandPrimary, 0.14),
      }}
    >
      <Box sx={{ display: "inline-flex", alignItems: "center", gap: 0.55 }}>
        {[0, 1, 2].map((dotIndex) => (
          <Box
            key={dotIndex}
            component="span"
            sx={{
              width: 9,
              height: 9,
              borderRadius: "50%",
              bgcolor: alpha(brandPrimary, 0.9),
              animation: `agent-status-pulse 1.1s ${dotIndex * 0.14}s ease-in-out infinite`,
            }}
          />
        ))}
      </Box>
      <Typography variant="body2" sx={{ fontWeight: 600, letterSpacing: "0.01em" }}>
        {label}
      </Typography>
    </Box>
  );
};

/** Live elapsed-time counter while a response is streaming. */
const LiveTimer: React.FC<{ startedAt?: string; durationMs?: number; isDone: boolean }> = ({
  startedAt,
  durationMs,
  isDone,
}) => {
  const [elapsed, setElapsed] = React.useState<number>(() =>
    startedAt ? Math.max(0, Date.now() - Date.parse(startedAt)) : 0,
  );

  useEffect(() => {
    if (isDone || !startedAt) return;
    const id = setInterval(() => {
      setElapsed(Math.max(0, Date.now() - Date.parse(startedAt)));
    }, 100);
    return () => clearInterval(id);
  }, [isDone, startedAt]);

  const ms = isDone ? (durationMs ?? elapsed) : elapsed;
  const s = (ms / 1000).toFixed(1);
  return <span>{isDone ? `Processed in ${s}s` : `${s}s`}</span>;
};

/**
 * ProcessingBanner — shown ABOVE message content while streaming, and
 * replaced by a "Processed in X.Xs" caption once done.
 */
const ProcessingBanner: React.FC<{
  externalMessage?: ChatMessage;
  brandPrimary: string;
  isStreaming: boolean;
}> = ({ externalMessage, brandPrimary, isStreaming }) => {
  const muiTheme = useTheme();

  // Active step label from thinking steps
  const activeStep = externalMessage?.thinkingSteps?.length
    ? [...externalMessage.thinkingSteps].reverse().find((s) => s.status === "active" || s.status === "pending")
    : undefined;
  const stepLabel = activeStep?.label?.trim() || (isStreaming ? "Thinking" : "");

  if (!isStreaming && !externalMessage?.processingDuration && !externalMessage?.processingStartedAt) {
    return null;
  }

  if (isStreaming) {
    return (
      <Box
        sx={{
          display: "inline-flex",
          alignItems: "center",
          gap: 1.1,
          px: 1.2,
          py: 0.8,
          borderRadius: 999,
          bgcolor: alpha(brandPrimary, muiTheme.palette.mode === "dark" ? 0.13 : 0.07),
          border: "1px solid",
          borderColor: alpha(brandPrimary, 0.15),
          mb: 0.5,
        }}
      >
        {/* animated dots */}
        <Box sx={{ display: "inline-flex", alignItems: "center", gap: 0.45 }}>
          {[0, 1, 2].map((i) => (
            <Box
              key={i}
              component="span"
              sx={{
                width: 7,
                height: 7,
                borderRadius: "50%",
                bgcolor: alpha(brandPrimary, 0.85),
                animation: `agent-status-pulse 1.1s ${i * 0.14}s ease-in-out infinite`,
              }}
            />
          ))}
        </Box>
        {/* step label */}
        <Typography variant="body2" sx={{ fontWeight: 600, color: "text.primary", letterSpacing: "0.01em" }}>
          {stepLabel}
        </Typography>
        {/* live timer */}
        <Typography
          variant="caption"
          sx={{
            ml: 0.5,
            fontVariantNumeric: "tabular-nums",
            color: alpha(muiTheme.palette.text.secondary, 0.85),
            minWidth: 36,
            textAlign: "right",
          }}
        >
          <LiveTimer
            startedAt={externalMessage?.processingStartedAt}
            durationMs={externalMessage?.processingDuration}
            isDone={false}
          />
        </Typography>
      </Box>
    );
  }

  // Done — show "Processed in X.Xs"
  return (
    <Typography
      variant="caption"
      sx={{ color: alpha(muiTheme.palette.text.secondary, 0.75), fontVariantNumeric: "tabular-nums" }}
    >
      <LiveTimer
        startedAt={externalMessage?.processingStartedAt}
        durationMs={externalMessage?.processingDuration}
        isDone
      />
    </Typography>
  );
};

const MessageChainOfThought: React.FC<{ brandPrimary: string }> = ({ brandPrimary }) => {
  const muiTheme = useTheme();
  const [isExpanded, setIsExpanded] = useState(true);

  return (
    <ChainOfThoughtPrimitive.Root
      style={{
        width: "100%",
        marginTop: 8,
      }}
    >
      <ChainOfThoughtPrimitive.AccordionTrigger
        onClick={() => setIsExpanded((current) => !current)}
        style={{
          width: "100%",
          border: "none",
          background: "transparent",
          padding: 0,
          textAlign: "left",
          cursor: "pointer",
        }}
      >
        <Box
          sx={{
            px: 1.25,
            py: 1,
            borderRadius: 3,
            background:
              muiTheme.palette.mode === "dark"
                ? alpha(muiTheme.palette.background.paper, 0.62)
                : alpha(brandPrimary, 0.035),
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 1,
          }}
        >
          <Box sx={{ display: "inline-flex", alignItems: "center", gap: 0.8 }}>
            <PsychologyAltOutlinedIcon sx={{ fontSize: 16, color: alpha(brandPrimary, 0.9) }} />
            <Typography variant="body2" sx={{ fontWeight: 600, color: "text.primary" }}>
              Chain of thought
            </Typography>
          </Box>
          <ExpandMoreRoundedIcon sx={{ fontSize: 18, color: alpha(muiTheme.palette.text.secondary, 0.9) }} />
        </Box>
      </ChainOfThoughtPrimitive.AccordionTrigger>
      {isExpanded ? (
        <ChainOfThoughtPrimitive.Parts>
          {({ part }: { part: ThreadMessage["content"][number] }) => {
            if (part.type === "reasoning") {
              const text = typeof part.text === "string" ? part.text.trim() : "";
              if (!text) {
                return null;
              }

              return (
                <Box
                  sx={{
                    mt: 0.85,
                    pl: 1.4,
                    pr: 1.25,
                    py: 0.85,
                    borderLeft: `2px solid ${alpha(brandPrimary, 0.16)}`,
                  }}
                >
                  <Typography variant="body2" sx={{ color: "text.secondary", lineHeight: 1.55 }}>
                    {text}
                  </Typography>
                </Box>
              );
            }

            if (part.type === "tool-call") {
              const toolName = typeof part.toolName === "string" ? part.toolName : "tool";

              return (
                <Box
                  sx={{
                    mt: 0.85,
                    display: "flex",
                    alignItems: "center",
                    gap: 0.85,
                    pl: 1.15,
                    pr: 1.25,
                    py: 0.8,
                    borderRadius: 2,
                    bgcolor: alpha(brandPrimary, muiTheme.palette.mode === "dark" ? 0.12 : 0.05),
                  }}
                >
                  <BuildCircleOutlinedIcon sx={{ fontSize: 16, color: alpha(brandPrimary, 0.92) }} />
                  <Typography variant="body2" sx={{ color: "text.secondary", fontWeight: 600 }}>
                    {formatAgentName(toolName)}
                  </Typography>
                </Box>
              );
            }

            return null;
          }}
        </ChainOfThoughtPrimitive.Parts>
      ) : null}
    </ChainOfThoughtPrimitive.Root>
  );
};

const MarkdownMessageText: React.FC<{ text: string; role: ChatMessage["role"] }> = ({ text, role }) => {
  const muiTheme = useTheme();
  const linkColor = role === "user" ? alpha("#ffffff", 0.92) : muiTheme.palette.text.primary;

  if (!text.trim()) {
    return null;
  }

  return (
    <Box
      sx={{
        color: "inherit",
        fontSize: "0.97rem",
        lineHeight: 1.65,
        "& p": { m: 0 },
        "& p + p": { mt: 1.2 },
        "& ul, & ol": { my: 0.4, pl: 2.6 },
        "& li + li": { mt: 0.35 },
        "& strong": { fontWeight: 700 },
        "& code": {
          fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
          fontSize: "0.88em",
          px: 0.45,
          py: 0.15,
          borderRadius: 1,
          bgcolor: role === "user" ? alpha("#ffffff", 0.16) : alpha(muiTheme.palette.text.primary, 0.08),
        },
        "& pre": {
          m: 0,
          mt: 1.2,
          p: 1.25,
          borderRadius: 2,
          overflowX: "auto",
          bgcolor: role === "user" ? alpha("#ffffff", 0.12) : alpha(muiTheme.palette.text.primary, 0.06),
        },
        "& pre code": {
          p: 0,
          bgcolor: "transparent",
        },
      }}
    >
      <ReactMarkdown
        components={{
          a: ({ href, children }) => (
            <Box
              component="a"
              href={href}
              target="_blank"
              rel="noreferrer"
              sx={{
                color: linkColor,
                fontWeight: 600,
                textDecorationColor: alpha(linkColor, 0.45),
              }}
            >
              {children}
            </Box>
          ),
        }}
      >
        {text}
      </ReactMarkdown>
    </Box>
  );
};

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
    <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
      <MessagePrimitive.Parts
        components={{
          Text: ({ text }: TextMessagePartProps) => <MarkdownMessageText text={text} role={role} />,
          ChainOfThought: enableChainOfThought ? () => <MessageChainOfThought brandPrimary={accent} /> : undefined,
        }}
      />
      {charts.map((chart) => (
        <InlineChart key={chart.id} chart={chart} accent={accent} />
      ))}
      {tables.map((table) => (
        <InlineTable key={table.id} table={table} accent={accent} />
      ))}
      {files.map((file) => (
        <InlineFile key={file.id} file={file} accent={accent} />
      ))}
    </Box>
  );
};

const MessageBranchPicker: React.FC = () => {
  const muiTheme = useTheme();

  return (
    <BranchPickerPrimitive.Root
      hideWhenSingleBranch
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 2,
        color: alpha(muiTheme.palette.text.secondary, 0.78),
        fontSize: "0.75rem",
        lineHeight: 1,
      }}
    >
      <BranchPickerPrimitive.Previous asChild>
        <IconButton
          size="small"
          sx={{
            width: 24,
            height: 24,
            color: "inherit",
          }}
        >
          <NavigateBeforeRoundedIcon sx={{ fontSize: 16 }} />
        </IconButton>
      </BranchPickerPrimitive.Previous>
      <Typography component="span" variant="caption" sx={{ color: "inherit", fontWeight: 600 }}>
        <BranchPickerPrimitive.Number /> / <BranchPickerPrimitive.Count />
      </Typography>
      <BranchPickerPrimitive.Next asChild>
        <IconButton
          size="small"
          sx={{
            width: 24,
            height: 24,
            color: "inherit",
          }}
        >
          <NavigateNextRoundedIcon sx={{ fontSize: 16 }} />
        </IconButton>
      </BranchPickerPrimitive.Next>
    </BranchPickerPrimitive.Root>
  );
};

const UserActionBar: React.FC = () => {
  const muiTheme = useTheme();

  return (
    <ActionBarPrimitive.Root
      hideWhenRunning
      autohide="not-last"
      style={{ display: "flex", alignItems: "center", gap: 4 }}
    >
      <ActionBarPrimitive.Edit asChild>
        <IconButton
          size="small"
          aria-label="Edit message"
          sx={{
            width: 28,
            height: 28,
            color: alpha(muiTheme.palette.text.secondary, 0.88),
          }}
        >
          <EditOutlinedIcon sx={{ fontSize: 16 }} />
        </IconButton>
      </ActionBarPrimitive.Edit>
    </ActionBarPrimitive.Root>
  );
};

const AssistantActionBar: React.FC = () => {
  const muiTheme = useTheme();

  return (
    <ActionBarPrimitive.Root
      hideWhenRunning
      autohide="not-last"
      style={{ display: "flex", alignItems: "center", gap: 4 }}
    >
      <ActionBarPrimitive.Copy asChild>
        <IconButton
          size="small"
          aria-label="Copy response"
          sx={{
            width: 28,
            height: 28,
            color: alpha(muiTheme.palette.text.secondary, 0.88),
          }}
        >
          <ContentCopyRoundedIcon sx={{ fontSize: 16 }} />
        </IconButton>
      </ActionBarPrimitive.Copy>

      <ActionBarPrimitive.Reload asChild>
        <IconButton
          size="small"
          aria-label="Regenerate response"
          sx={{
            width: 28,
            height: 28,
            color: alpha(muiTheme.palette.text.secondary, 0.88),
          }}
        >
          <RefreshRoundedIcon sx={{ fontSize: 16 }} />
        </IconButton>
      </ActionBarPrimitive.Reload>
    </ActionBarPrimitive.Root>
  );
};

const EditComposerMessage: React.FC<{ brandPrimary: string }> = ({ brandPrimary }) => {
  const muiTheme = useTheme();

  return (
    <MessagePrimitive.Root>
      <Box
        sx={{
          display: "flex",
          justifyContent: "flex-end",
          width: "100%",
          px: { xs: 1.25, md: 1.5 },
          py: 0.45,
        }}
      >
        <ComposerPrimitive.Root
          style={{
            width: "100%",
            maxWidth: "82%",
            display: "flex",
            flexDirection: "column",
            borderRadius: 20,
            border: `1px solid ${alpha(brandPrimary, 0.18)}`,
            background: muiTheme.palette.mode === "dark" ? alpha("#1f1f21", 0.96) : "#fcfbf9",
          }}
        >
          <ComposerPrimitive.Input asChild>
            <textarea
              rows={1}
              style={{
                minHeight: 72,
                maxHeight: 240,
                border: "none",
                outline: "none",
                resize: "none",
                background: "transparent",
                color: muiTheme.palette.text.primary,
                fontFamily: "inherit",
                fontSize: "0.98rem",
                lineHeight: 1.55,
                padding: "14px 16px 8px",
              }}
            />
          </ComposerPrimitive.Input>

          <Box sx={{ display: "flex", justifyContent: "flex-end", gap: 1, px: 1.5, pb: 1.5 }}>
            <ComposerPrimitive.Cancel asChild>
              <Button
                size="small"
                variant="text"
                sx={{ borderRadius: 999, textTransform: "none", fontWeight: 700 }}
              >
                Cancel
              </Button>
            </ComposerPrimitive.Cancel>
            <ComposerPrimitive.Send asChild>
              <Button
                size="small"
                variant="contained"
                sx={{
                  borderRadius: 999,
                  textTransform: "none",
                  fontWeight: 700,
                  boxShadow: "none",
                }}
              >
                Update
              </Button>
            </ComposerPrimitive.Send>
          </Box>
        </ComposerPrimitive.Root>
      </Box>
    </MessagePrimitive.Root>
  );
};

const UserThreadMessage = React.memo<{
  brandPrimary: string;
  externalMessage?: ChatMessage;
}>(({ brandPrimary, externalMessage }) => {
  const muiTheme = useTheme();
  const hasText = Boolean(externalMessage?.content.trim());
  const hasAttachments = Boolean(externalMessage?.attachments?.length);

  return (
    <MessagePrimitive.Root>
      <Box
        sx={{
          display: "flex",
          justifyContent: "flex-end",
          width: "100%",
          px: { xs: 1.25, md: 1.5 },
          py: 0.45,
        }}
      >
        <Box
          sx={{
            maxWidth: { xs: "90%", sm: "82%" },
            display: "flex",
            flexDirection: "column",
            alignItems: "flex-end",
            gap: 0.35,
          }}
        >
          <Box
            sx={{
              px: 1.6,
              py: 1.2,
              borderRadius: "22px 22px 8px 22px",
              bgcolor: brandPrimary,
              color: muiTheme.palette.getContrastText(brandPrimary),
              display: "flex",
              flexDirection: "column",
              gap: hasAttachments && hasText ? 1 : 0.25,
            }}
          >
            {hasAttachments ? (
              <UserMessageAttachments />
            ) : null}
            {hasText ? <MessageRichContent accent={brandPrimary} role="user" externalMessage={externalMessage} /> : null}
          </Box>
          {externalMessage?.timestamp && (
            <Typography variant="caption" sx={{ color: alpha(muiTheme.palette.text.secondary, 0.84) }}>
              {formatTimestamp(externalMessage.timestamp)}
            </Typography>
          )}
          <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
            <MessageBranchPicker />
            <UserActionBar />
          </Box>
        </Box>
      </Box>
    </MessagePrimitive.Root>
  );
});

const AssistantThreadMessage = React.memo<{
  externalMessage?: ChatMessage;
  threadMessage?: ThreadMessage;
  brandPrimary: string;
}>(({ externalMessage, threadMessage, brandPrimary }) => {
  const muiTheme = useTheme();
  const isRunning = threadMessage?.status?.type === "running";
  const isStreaming = externalMessage?.status === "streaming" || isRunning;
  const hasRenderablePayload = hasRenderableMessagePayload(externalMessage);
  const showChainOfThought = hasChainOfThoughtParts(threadMessage);
  const label = formatAssistantLabel(externalMessage?.agent);
  const initials = getAgentInitials(label);

  // Only return null when there is genuinely nothing to show at all
  if (!hasRenderablePayload && !isStreaming && !showChainOfThought) {
    return null;
  }

  return (
    <MessagePrimitive.Root>
      <Box
        sx={{
          display: "flex",
          justifyContent: "flex-start",
          alignItems: "flex-start",
          gap: 1.1,
          width: "100%",
          px: { xs: 1.25, md: 1.5 },
          py: 0.55,
        }}
      >
        <Avatar
          sx={{
            width: 32,
            height: 32,
            mt: 0.15,
            fontSize: "0.78rem",
            fontWeight: 700,
            bgcolor: alpha(brandPrimary, 0.12),
            color: brandPrimary,
            border: "1px solid",
            borderColor: alpha(brandPrimary, 0.14),
          }}
        >
          {initials}
        </Avatar>
        <Box
          sx={{
            maxWidth: { xs: "96%", sm: "88%" },
            width: "100%",
            display: "flex",
            flexDirection: "column",
            alignItems: "flex-start",
            gap: 0.5,
          }}
        >
          <Typography variant="caption" sx={{ color: alpha(muiTheme.palette.text.secondary, 0.9), fontWeight: 600 }}>
            {label}
          </Typography>

          {/* Processing banner — always shown while streaming, above content */}
          {isStreaming && (
            <ProcessingBanner
              externalMessage={externalMessage}
              brandPrimary={brandPrimary}
              isStreaming={isStreaming}
            />
          )}

          {/* Content area — shown whenever there is renderable payload or chain-of-thought */}
          {(hasRenderablePayload || showChainOfThought) && (
            <Box sx={{ width: "100%", color: "text.primary", pr: { xs: 0.5, sm: 1.5 } }}>
              <MessageRichContent
                accent={brandPrimary}
                role="assistant"
                enableChainOfThought={showChainOfThought}
                externalMessage={externalMessage}
              />
            </Box>
          )}

          {/* Processing time / timestamp — shown when not streaming */}
          {!isStreaming && (
            <ProcessingBanner
              externalMessage={externalMessage}
              brandPrimary={brandPrimary}
              isStreaming={false}
            />
          )}

          <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
            <MessageBranchPicker />
            <AssistantActionBar />
          </Box>
        </Box>
      </Box>
    </MessagePrimitive.Root>
  );
});

const SystemThreadMessage = React.memo<{
  externalMessage?: ChatMessage;
  brandPrimary: string;
  brandSecondary: string;
}>(({ externalMessage, brandPrimary, brandSecondary }) => {
  const muiTheme = useTheme();

  return (
    <MessagePrimitive.Root>
      <Box
        sx={{
          display: "flex",
          justifyContent: "flex-start",
          width: "100%",
          px: { xs: 1.25, md: 1.5 },
          py: 0.35,
        }}
      >
        <Box
          sx={{
            maxWidth: { xs: "94%", sm: "84%" },
            display: "flex",
            flexDirection: "column",
            gap: 0.5,
          }}
        >
          <Typography variant="caption" sx={{ color: alpha(muiTheme.palette.text.secondary, 0.9) }}>
            System
          </Typography>
          <Box
            sx={{
              p: 1.35,
              borderRadius: 3,
              border: "1px dashed",
              borderColor: alpha(brandPrimary, 0.18),
              bgcolor: muiTheme.palette.mode === "dark" ? alpha(brandSecondary, 0.12) : alpha(brandPrimary, 0.05),
              color: "text.secondary",
            }}
          >
            <MessageRichContent accent={brandPrimary} role="system" externalMessage={externalMessage} />
          </Box>
        </Box>
      </Box>
    </MessagePrimitive.Root>
  );
});

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
}) => {
  const muiTheme = useTheme();
  const folderInputRef = useRef<HTMLInputElement | null>(null);
  const threadRuntime = useThreadRuntime();
  const composerText = useThreadComposer((state) => state.text);
  const panelBorder = alpha(brandPrimary, muiTheme.palette.mode === "dark" ? 0.24 : 0.16);
  const showWelcomeState = messageCount === 0;
  const promptGroups = useMemo<AgentChatPromptSection[]>(() => {
    if (promptSections.length > 0) {
      return promptSections.filter((section) => section.prompts.length > 0);
    }

    return [
      {
        id: "default",
        title: "Start with",
        prompts: [
          {
            id: "queue-summary",
            label: "Give me today's queue summary",
            prompt: "Give me today's queue summary",
          },
          {
            id: "revenue-trend",
            label: "Show this week's revenue trend",
            prompt: "Show this week's revenue trend",
          },
          {
            id: "shift-now",
            label: "Who is on shift now?",
            prompt: "Who is on shift now?",
          },
          {
            id: "crm-pipeline",
            label: "Show my CRM pipeline summary",
            prompt: "Show my CRM pipeline summary",
          },
        ],
      },
    ];
  }, [promptSections]);
  const suggestionCards = useMemo(() => {
    return promptGroups
      .flatMap((section) => section.prompts)
      .filter((prompt, index, allPrompts) => allPrompts.findIndex((candidate) => candidate.id === prompt.id) === index)
      .slice(0, 3);
  }, [promptGroups]);

  const insertPrompt = useCallback(
    (prompt: string) => {
      const trimmed = composerText.trim();
      if (!trimmed) {
        threadRuntime.composer.setText(prompt);
        return;
      }
      if (trimmed.includes(prompt)) {
        return;
      }
      threadRuntime.composer.setText(`${trimmed}\n${prompt}`);
    },
    [composerText, threadRuntime],
  );

  const handleFolderSelection = useCallback(
    async (event: React.ChangeEvent<HTMLInputElement>) => {
      const selectedFiles = Array.from(event.target.files || []);
      event.target.value = "";
      if (selectedFiles.length === 0 || isUploading || isStreaming) {
        return;
      }

      for (const file of selectedFiles) {
        try {
          await threadRuntime.composer.addAttachment(file);
        } catch {
          continue;
        }
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
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        width: "100%",
        height: "100%",
        minHeight: 0,
        px: { xs: 1, md: 2 },
        pb: 0,
        "@keyframes agent-status-pulse": {
          "0%, 100%": {
            opacity: 0.26,
            transform: "scale(0.84)",
          },
          "50%": {
            opacity: 1,
            transform: "scale(1)",
          },
        },
      }}
    >
      <Box
        sx={{
          width: "100%",
          maxWidth: { xs: "100%", lg: 900 },
          mx: "auto",
          display: "flex",
          flexDirection: "column",
          flex: 1,
          minHeight: 0,
          position: "relative",
        }}
      >
          <input
            ref={folderInputRef}
            type="file"
            hidden
            multiple
            accept={DOCUMENT_ATTACHMENT_ACCEPT}
            onChange={handleFolderSelection}
          />

          <ThreadPrimitive.Root
            style={{
              flex: 1,
              minHeight: 0,
              display: "flex",
              flexDirection: "column",
              fontFamily: "inherit",
            }}
          >
            <ThreadPrimitive.Viewport
              autoScroll
              style={{
                flex: "1 1 0",
                minHeight: 0,
                borderRadius: 32,
                border: "none",
                background: "transparent",
                overflowX: "hidden",
                overflowY: "auto",
                paddingTop: showWelcomeState ? 0 : 10,
              }}
            >
              {showWelcomeState ? (
                <Box
                  sx={{
                    minHeight: "100%",
                    display: "flex",
                    alignItems: "stretch",
                    justifyContent: "flex-start",
                    px: { xs: 1, md: 1.5 },
                    pt: { xs: 1.5, md: 2 },
                    pb: { xs: 1, md: 1.5 },
                  }}
                >
                  <Stack spacing={2.5} sx={{ width: "100%", maxWidth: 720, mx: "auto" }}>
                    <Stack spacing={0.5}>
                      <Typography
                        variant="h2"
                        sx={{
                          fontWeight: 700,
                          letterSpacing: "-0.035em",
                          color: "text.primary",
                        }}
                      >
                        {title}
                      </Typography>
                      <Typography
                        variant="h5"
                        sx={{
                          fontWeight: 400,
                          color: "text.secondary",
                          letterSpacing: "-0.02em",
                        }}
                      >
                        {subtitle}
                      </Typography>
                    </Stack>

                    <Box
                      sx={{
                        display: "grid",
                        gridTemplateColumns: { xs: "1fr", md: "repeat(2, minmax(0, 1fr))" },
                        gap: 1,
                        width: "100%",
                      }}
                    >
                      {suggestionCards.map((prompt) => (
                        <Box
                          key={prompt.id}
                          component="button"
                          type="button"
                          onClick={() => insertPrompt(prompt.prompt)}
                          disabled={isStreaming || isUploading}
                          sx={{
                            p: 1.75,
                            borderRadius: 3,
                            border: "1px solid",
                            borderColor: alpha(brandPrimary, 0.14),
                            bgcolor:
                              muiTheme.palette.mode === "dark"
                                ? alpha(muiTheme.palette.background.paper, 0.72)
                                : alpha(muiTheme.palette.common.white, 0.74),
                            textAlign: "left",
                            cursor: isStreaming || isUploading ? "default" : "pointer",
                            transition: "background-color 140ms ease, border-color 140ms ease, transform 140ms ease",
                            "&:hover": isStreaming || isUploading ? undefined : {
                              borderColor: alpha(brandPrimary, 0.28),
                              backgroundColor: alpha(brandPrimary, 0.06),
                              transform: "translateY(-1px)",
                            },
                            "&:disabled": {
                              opacity: 0.72,
                            },
                          }}
                        >
                          <Typography variant="subtitle1" sx={{ fontWeight: 600, color: "text.primary" }}>
                            {prompt.label}
                          </Typography>
                          <Typography
                            variant="body1"
                            sx={{
                              mt: 0.4,
                              color: "text.secondary",
                              lineHeight: 1.45,
                            }}
                          >
                            {prompt.prompt}
                          </Typography>
                        </Box>
                      ))}
                    </Box>
                  </Stack>
                </Box>
              ) : (
                <ThreadPrimitive.Messages>
                  {({ message }: { message: ThreadMessage }) => {
                    const [externalMessage] = getExternalStoreMessages(message) as ChatMessage[];
                    const isEditing = Boolean((message as ThreadMessage & { composer?: { isEditing?: boolean } }).composer?.isEditing);

                    if (externalMessage?.role === "user") {
                      if (isEditing) {
                        return <EditComposerMessage brandPrimary={brandPrimary} />;
                      }

                      return <UserThreadMessage externalMessage={externalMessage} brandPrimary={brandPrimary} />;
                    }

                    if (externalMessage?.role === "system") {
                      return (
                        <SystemThreadMessage
                          externalMessage={externalMessage}
                          brandPrimary={brandPrimary}
                          brandSecondary={brandSecondary}
                        />
                      );
                    }

                    return (
                      <AssistantThreadMessage
                        externalMessage={externalMessage}
                        threadMessage={message}
                        brandPrimary={brandPrimary}
                      />
                    );
                  }}
                </ThreadPrimitive.Messages>
              )}
            </ThreadPrimitive.Viewport>

            <Box
              sx={{
                width: "100%",
                maxWidth: 760,
                mx: "auto",
                mt: "auto",
                pt: 1,
                pb: { xs: 0.75, md: 1 },
                borderTop: "1px solid",
                borderColor:
                  muiTheme.palette.mode === "dark"
                    ? alpha(muiTheme.palette.common.white, 0.08)
                    : alpha(muiTheme.palette.text.primary, 0.08),
                background:
                  muiTheme.palette.mode === "dark"
                    ? `linear-gradient(180deg, ${alpha("#111214", 0)} 0%, ${alpha("#111214", 0.92)} 22%)`
                    : `linear-gradient(180deg, ${alpha("#ffffff", 0)} 0%, ${alpha("#faf8f5", 0.98)} 22%)`,
              }}
            >
              <ThreadPrimitive.ViewportFooter
                style={{
                  width: "100%",
                  padding: 0,
                }}
              >
                <Composer
                  placeholder="Ask a follow-up"
                  disabled={isUploading || isStreaming}
                  isRunning={isStreaming}
                  onOpenFolderPicker={openFolderPicker}
                  dictationControl={
                    <>
                      {onToggleVoice && (
                        <IconButton
                          size="small"
                          onClick={onToggleVoice}
                          disabled={isUploading || isStreaming}
                          aria-label={isVoiceEnabled ? "Disable voice" : "Enable voice"}
                          sx={{
                            width: 34,
                            height: 34,
                            borderRadius: 2.5,
                            color: isVoiceEnabled
                              ? brandPrimary
                              : muiTheme.palette.mode === "dark"
                              ? alpha("#f5f3ef", 0.82)
                              : "#6f6a63",
                            bgcolor: isVoiceEnabled
                              ? alpha(brandPrimary, muiTheme.palette.mode === "dark" ? 0.18 : 0.1)
                              : "transparent",
                            "@keyframes voice-pulse": {
                              "0%, 100%": { opacity: 0.7 },
                              "50%": { opacity: 1 },
                            },
                            animation: isSpeaking ? "voice-pulse 1s ease-in-out infinite" : "none",
                            "&:hover": {
                              backgroundColor: isVoiceEnabled
                                ? alpha(brandPrimary, 0.22)
                                : muiTheme.palette.mode === "dark"
                                ? alpha("#f5f3ef", 0.08)
                                : alpha("#1f1d1a", 0.06),
                            },
                            "&.Mui-disabled": { color: alpha(muiTheme.palette.text.secondary, 0.4) },
                          }}
                        >
                          {isVoiceEnabled ? (
                            <VolumeUpRoundedIcon fontSize="small" />
                          ) : (
                            <VolumeOffRoundedIcon fontSize="small" />
                          )}
                        </IconButton>
                      )}
                      <ComposerDictationButton
                        disabled={isUploading || isStreaming}
                        supported={hasDictation}
                      />
                    </>
                  }
                />
              </ThreadPrimitive.ViewportFooter>
            </Box>
          </ThreadPrimitive.Root>
      </Box>
    </Box>
  );
};

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
}) => {
  const muiTheme = useTheme();
  const { shop } = useShop();
  const aui = useAui({ interactables: Interactables() } as any) as InteractablesAuiClient;
  const lastInteractablesStorageKeyRef = useRef<string | null>(null);
  const brandPrimary = shop?.primary_color || muiTheme.palette.primary.main;
  const brandSecondary = shop?.secondary_color || brandPrimary;
  const dictationAdapter = useMemo(
    () =>
      WebSpeechDictationAdapter.isSupported()
        ? new WebSpeechDictationAdapter({
            language: "en-US",
            continuous: true,
            interimResults: true,
          })
        : undefined,
    [],
  );

  const convertMessage = useCallback((message: ChatMessage) => buildThreadMessage(message), []);

  const handleNewMessage = useCallback(
    async (message: AppendMessage) => {
      const trimmed = getAppendMessageText(message);
      const attachments = getAppendMessageAttachments(message);

      if ((!trimmed && attachments.length === 0) || isStreaming || isUploading) {
        return;
      }

      await onSend({ text: trimmed, attachments });
    },
    [isStreaming, isUploading, onSend],
  );

  const handleEditMessage = useCallback(
    async (message: AppendMessage) => {
      const trimmed = getAppendMessageText(message);
      const attachments = getAppendMessageAttachments(message);

      if ((!trimmed && attachments.length === 0) || isStreaming || isUploading) {
        return;
      }

      // Edits send the revised text as a new conversation turn rather than patching history —
      // intentional until the backend supports message-id-based re-runs.
      await onSend({ text: trimmed, attachments });
    },
    [isStreaming, isUploading, onSend],
  );

  const handleReloadMessage = useCallback(
    async (parentId: string | null) => {
      if (!parentId || isStreaming || isUploading) {
        return;
      }

      const targetIndex = messages.findIndex((message) => message.id === parentId);
      if (targetIndex === -1) {
        return;
      }

      const targetMessage = messages[targetIndex];
      const retryText =
        targetMessage?.retryMessage ||
        [...messages.slice(0, targetIndex)].reverse().find((message) => message.role === "user")?.content ||
        "";

      if (!retryText.trim()) {
        return;
      }

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
    adapters: {
      attachments: attachmentAdapter,
      dictation: dictationAdapter,
    },
  });

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
        try {
          aui.interactables().importState(JSON.parse(savedState));
        } catch {
          window.localStorage.removeItem(interactablesStorageKey);
        }
      }

      lastInteractablesStorageKeyRef.current = interactablesStorageKey;
    }

    return () => {
      void aui.interactables().flush();
    };
  }, [aui, interactablesStorageKey]);

  return (
    <AssistantRuntimeProvider runtime={runtime} aui={aui}>
      <Box
        sx={{
          display: "flex",
          flexDirection: { xs: "column", md: "row" },
          gap: { xs: 1.5, md: 0 },
          flex: 1,
          minHeight: 0,
          width: "100%",
        }}
      >
        <Box sx={{ flex: 1, minWidth: 0, minHeight: 0, display: "flex", flexDirection: "column" }}>
          {header ? (
            <Box
              sx={{
                px: { xs: 1, md: 2 },
                pt: { xs: 1, md: 1.25 },
                pb: { xs: 0.5, md: 0.75 },
                flexShrink: 0,
              }}
            >
              {header}
            </Box>
          ) : null}

          <Box sx={{ flex: 1, minHeight: 0 }}>
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
          </Box>
        </Box>

        {sidebar ? (
          <Box
            sx={{
              width: { xs: "100%", md: 360 },
              minWidth: { md: 320 },
              maxWidth: { md: 400 },
              flexShrink: 0,
              minHeight: { xs: 320, md: 0 },
              display: "flex",
              alignSelf: "stretch",
              height: { xs: "auto", md: "100%" },
            }}
          >
            {sidebar}
          </Box>
        ) : null}
      </Box>
    </AssistantRuntimeProvider>
  );
};

export default AgentChat;
