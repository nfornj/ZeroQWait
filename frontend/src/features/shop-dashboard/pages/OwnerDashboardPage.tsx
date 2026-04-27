// RESTYLED: Perplexity-style
import React, { useCallback, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Stack,
} from "@mui/material";
import { useQueryClient } from "@tanstack/react-query";

import { useAuth } from "../../../contexts/AuthContext";
import { useShop } from "../../../contexts/ShopContext";
import api from "../../../services/api";
import AgentChat, {
  AgentChatPromptSection,
} from "../../agent-inbox/AgentChat";
import {
  ownerDashboardKeys,
  useOwnerBriefingQuery,
  useOwnerFeedQuery,
  useOwnerOperationsSnapshot,
  useOwnerPoliciesQuery,
  usePendingApprovalsQuery,
} from "../../agent-inbox/ownerDashboardQueries";
import { createAgentChartFromPayload } from "../../agent-inbox/types";
import type {
  AgentChart,
  AgentFeedEvent,
  AgentFile,
  AgentTable,
  ChatMessage,
  ThinkingStep,
  PendingApproval,
} from "../../agent-inbox/types";
import Header from "../components/Header";

const apiBaseUrl = process.env.REACT_APP_API_URL || "/api";

const nowIso = () => new Date().toISOString();
const toId = (prefix: string) => `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;

const POLICY_MODE_LABELS: Record<string, string> = {
  require_approval: "Require approval",
  allow: "Allow automatically",
  notify_only: "Auto-run and notify",
  silent: "Auto-run silently",
  forbid: "Block action",
};

const labelForPolicyMode = (mode?: string): string => {
  if (!mode) return "Policy controlled";
  return POLICY_MODE_LABELS[mode] || mode.replace(/_/g, " ");
};

const formatAssistantProgressLabel = (value?: string | null): string => {
  if (!value) return "Thinking";

  return value
    .split(/[_-]/g)
    .filter(Boolean)
    .map((token) => token.charAt(0).toUpperCase() + token.slice(1))
    .join(" ");
};

const buildAssistantProgressStep = (
  label: string,
  agent?: string | null,
  toolName?: string | null,
  status: ThinkingStep["status"] = "active",
  id?: string,
): ThinkingStep => ({
  id: id || `progress_${label.toLowerCase().replace(/[^a-z0-9]+/g, "_")}`,
  label,
  status,
  agent: agent || undefined,
  toolName: toolName || undefined,
});

const upsertThinkingStep = (existingSteps: ThinkingStep[] | undefined, nextStep: ThinkingStep): ThinkingStep[] => {
  const currentSteps = existingSteps || [];
  const index = currentSteps.findIndex((step) => step.id === nextStep.id);

  if (index === -1) {
    return [...currentSteps, nextStep];
  }

  const updated = [...currentSteps];
  updated[index] = {
    ...updated[index],
    ...nextStep,
  };
  return updated;
};

const parseStreamChart = (payload: Record<string, any>): AgentChart | null => {
  return createAgentChartFromPayload(payload, nowIso());
};

const parseStreamFile = (payload: Record<string, any>): AgentFile | null => {
  const content = String(payload.content || "");
  if (!content) {
    return null;
  }

  return {
    id: `file_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
    filename: String(payload.filename || "download"),
    content,
    mimeType: String(payload.mimeType || "application/octet-stream"),
    timestamp: nowIso(),
  };
};

const parseStreamTable = (payload: Record<string, any>): AgentTable | null => {
  if (!Array.isArray(payload.columns) || !Array.isArray(payload.data) || payload.columns.length === 0) {
    return null;
  }

  return {
    id: `table_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
    title: String(payload.title || "Table"),
    columns: payload.columns,
    data: payload.data,
    rowIdKey: String(payload.rowIdKey || payload.columns[0]?.key || "id"),
    timestamp: nowIso(),
  };
};

const normalizePendingApproval = (raw: Record<string, any>, fallbackShopId: number): PendingApproval => {
  const nested = raw && typeof raw === "object" ? raw : {};
  const detailPayload = nested.details && typeof nested.details === "object" ? nested.details : nested;

  return {
    action_id: nested.action_id,
    action: String(nested.action || detailPayload.action || "pending_action"),
    details: (detailPayload.details && typeof detailPayload.details === "object"
      ? detailPayload.details
      : detailPayload) as Record<string, unknown>,
    shop_id: Number(nested.shop_id || detailPayload.shop_id || fallbackShopId),
    policy_key: nested.policy_key || detailPayload.policy_key,
    policy_mode: nested.policy_mode || detailPayload.policy_mode,
    category: nested.category || detailPayload.category,
    title: nested.title || detailPayload.title,
    summary: nested.summary || detailPayload.summary,
    reason: nested.reason || detailPayload.reason || detailPayload.rationale,
    expected_impact: nested.expected_impact || detailPayload.expected_impact,
    risk_level: nested.risk_level || detailPayload.risk_level,
    urgency: nested.urgency || detailPayload.urgency,
    recommended_decision: nested.recommended_decision || detailPayload.recommended_decision,
  };
};

const formatCurrency = (value: number) =>
  new Intl.NumberFormat("en-CA", {
    style: "currency",
    currency: "CAD",
    maximumFractionDigits: value >= 100 ? 0 : 2,
  }).format(value || 0);

const formatDateTime = (value?: string | null) => {
  if (!value) return "No upcoming slot";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "No upcoming slot";
  return parsed.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
};

const getErrorDetail = (error: unknown, fallback: string) => {
  if (typeof error === "string") return error;
  if (error instanceof Error) return error.message;
  return fallback;
};

const STREAM_INTERRUPTED_MESSAGE = "The response stream was interrupted before completion. Partial output may be shown below.";
const STREAM_RETRY_MESSAGE = "The response was interrupted before it finished. Please try again.";

const normalizeStreamErrorDetail = (error: unknown, fallback: string) => {
  const detail = getErrorDetail(error, fallback).trim();
  const lowered = detail.toLowerCase();

  if (
    lowered.includes("error in input stream") ||
    lowered.includes("failed to fetch") ||
    lowered.includes("networkerror") ||
    lowered.includes("body stream")
  ) {
    return STREAM_INTERRUPTED_MESSAGE;
  }

  return detail || fallback;
};

const OwnerDashboardPage: React.FC = () => {
  const queryClient = useQueryClient();
  const { shop } = useShop();
  const { token } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [localFeedEvents, setLocalFeedEvents] = useState<AgentFeedEvent[]>([]);
  const [streamedPendingApprovals, setStreamedPendingApprovals] = useState<PendingApproval[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isUploadingDocuments, setIsUploadingDocuments] = useState(false);
  const [dashboardError, setDashboardError] = useState<string | null>(null);

  const briefingQuery = useOwnerBriefingQuery(shop?.id);
  const pendingQuery = usePendingApprovalsQuery(shop?.id);
  const feedQuery = useOwnerFeedQuery(shop?.id);
  const policiesQuery = useOwnerPoliciesQuery(shop?.id);
  const operationsSnapshot = useOwnerOperationsSnapshot(shop?.id);

  const addFeedEvent = useCallback((event: Omit<AgentFeedEvent, "id" | "timestamp">) => {
    setLocalFeedEvents((prev) => [
      {
        id: toId("feed"),
        timestamp: nowIso(),
        ...event,
      },
      ...prev,
    ]);
  }, []);

  const pendingApprovals = useMemo(() => {
    const merged = [...streamedPendingApprovals, ...(pendingQuery.data || [])];
    const deduped = new Map<string, PendingApproval>();
    merged.forEach((approval) => {
      const key = approval.action_id || `${approval.action}_${approval.shop_id}`;
      if (!deduped.has(key)) {
        deduped.set(key, approval);
      }
    });
    return Array.from(deduped.values());
  }, [pendingQuery.data, streamedPendingApprovals]);

  const displayedFeedEvents = useMemo(() => {
    const merged = [...localFeedEvents, ...(feedQuery.data || [])];
    const deduped = new Map<string, AgentFeedEvent>();
    merged.forEach((event) => {
      const key = event.id || `${event.type}_${event.timestamp}_${event.title}`;
      if (!deduped.has(key)) {
        deduped.set(key, event);
      }
    });
    return Array.from(deduped.values()).sort(
      (left, right) => new Date(right.timestamp).getTime() - new Date(left.timestamp).getTime()
    );
  }, [feedQuery.data, localFeedEvents]);

  const policySummary = useMemo(() => {
    return (policiesQuery.data || []).reduce<Record<string, number>>((summary, policy) => {
      summary[policy.mode] = (summary[policy.mode] || 0) + 1;
      return summary;
    }, {});
  }, [policiesQuery.data]);

  const handleUploadDocuments = useCallback(
    async (selectedFiles: File[]) => {
      if (!shop?.id) {
        setDashboardError("No active shop selected for document upload.");
        return;
      }
      if (selectedFiles.length === 0) {
        return;
      }

      setDashboardError(null);
      setIsUploadingDocuments(true);

      try {
        const formData = new FormData();
        formData.append("shop_id", String(shop.id));

        selectedFiles.forEach((file) => {
          formData.append("files", file);
          formData.append(
            "relative_paths",
            ((file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name),
          );
        });

        const response = await api.post<{
          message: string;
          ingested_chunks: number;
          documents: Array<{
            id: number;
            filename: string;
            relative_path?: string | null;
            chunk_count: number;
            duplicate: boolean;
          }>;
        }>("/v2/agent/documents/upload", formData, {
          headers: {
            "Content-Type": "multipart/form-data",
          },
        });

        const uploadedCount = response.data.documents.length;
        const duplicateCount = response.data.documents.filter((document) => document.duplicate).length;
        const newDocumentCount = uploadedCount - duplicateCount;
        const uploadedNames = response.data.documents
          .slice(0, 3)
          .map((document) => document.relative_path || document.filename)
          .join(", ");

        setMessages((prev) => [
          ...prev,
          {
            id: toId("msg_system"),
            role: "system",
            content:
              duplicateCount > 0
                ? `Added ${newDocumentCount} new document${newDocumentCount === 1 ? "" : "s"} to the knowledge base and skipped ${duplicateCount} duplicate${duplicateCount === 1 ? "" : "s"}. ${uploadedNames ? `Latest files: ${uploadedNames}.` : ""}`
                : `Added ${uploadedCount} document${uploadedCount === 1 ? "" : "s"} to the knowledge base. ${uploadedNames ? `Latest files: ${uploadedNames}.` : ""}`,
            status: "done",
            timestamp: nowIso(),
            agent: "system",
          },
        ]);

        addFeedEvent({
          type: "system",
          title: "Knowledge base updated",
          description: response.data.message,
          payload: response.data.documents,
        });

        await queryClient.invalidateQueries({ queryKey: ownerDashboardKeys.documents(shop.id) });
      } catch (error) {
        const detail = getErrorDetail(error, "Failed to upload documents");
        setDashboardError(detail);
        addFeedEvent({
          type: "error",
          title: "Document upload failed",
          description: detail,
        });
      } finally {
        setIsUploadingDocuments(false);
      }
    },
    [addFeedEvent, queryClient, shop?.id],
  );


  const handleSend = useCallback(
    async (messageText: string) => {
      if (!shop?.id) {
        setDashboardError("No active shop selected for the owner dashboard.");
        return;
      }

      setDashboardError(null);
      setIsStreaming(true);

      const assistantMessageId = toId("msg_assistant");

      setMessages((prev) => [
        ...prev,
        {
          id: toId("msg_user"),
          role: "user",
          content: messageText,
          status: "done",
          timestamp: nowIso(),
        },
        {
          id: assistantMessageId,
          role: "assistant",
          content: "",
          status: "streaming",
          timestamp: nowIso(),
          retryMessage: messageText,
          thinkingSteps: [],
          thinkingComplete: false,
        },
      ]);

      addFeedEvent({
        type: "chat",
        title: "Owner message sent",
        description: messageText,
      });

      let streamEndedWithDone = false;
      let streamTerminalStatus: "completed" | "error" | null = null;
      let streamErrorDetail: string | null = null;
      let sawRenderableAssistantContent = false;

      try {
        const response = await fetch(`${apiBaseUrl}/v2/agent/chat/stream`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({
            message: messageText,
            shop_id: shop.id,
            is_voice: false,
          }),
        });

        if (!response.ok || !response.body) {
          throw new Error(`Streaming request failed with status ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        const updateAssistantMessage = (updater: (message: ChatMessage) => ChatMessage) => {
          setMessages((prev) =>
            prev.map((msg) => (msg.id === assistantMessageId ? updater(msg) : msg))
          );
        };

        const applyAssistantDelta = (delta: string) => {
          updateAssistantMessage((msg) =>
            msg.id === assistantMessageId
              ? {
                  ...msg,
                  content: `${msg.content}${delta}`,
                  status: "streaming",
                  thinkingComplete: false,
                }
              : msg
          );
        };

        const setAssistantProgress = (
          stepId: string,
          label: string,
          status: ThinkingStep["status"],
          agent?: string | null,
          toolName?: string | null,
        ) => {
          updateAssistantMessage((msg) =>
            msg.id === assistantMessageId
              ? {
                  ...msg,
                  agent: agent || msg.agent,
                  thinkingSteps: upsertThinkingStep(
                    msg.thinkingSteps,
                    buildAssistantProgressStep(label, agent, toolName, status, stepId),
                  ),
                  thinkingComplete: false,
                }
              : msg
          );
        };

        const handleEventData = (raw: string) => {
          if (raw === "[DONE]") {
            streamEndedWithDone = true;
            updateAssistantMessage((msg) =>
              msg.id === assistantMessageId
                ? { ...msg, status: "done", thinkingComplete: true }
                : msg
            );
            return;
          }

          let eventJson: Record<string, any>;
          try {
            eventJson = JSON.parse(raw);
          } catch {
            return;
          }

          const eventType = String(eventJson.type || "");
          if (eventType === "text") {
            const content = String(eventJson.content || "");
            if (content) {
              sawRenderableAssistantContent = true;
              applyAssistantDelta(content);
            }
            return;
          }

          if (eventType === "stream_status") {
            const status = String(eventJson.status || "");

            if (eventJson.agent) {
              updateAssistantMessage((msg) =>
                msg.id === assistantMessageId
                  ? {
                      ...msg,
                      agent: String(eventJson.agent),
                    }
                  : msg
              );
            }

            if (status === "completed") {
              streamTerminalStatus = "completed";
              addFeedEvent({
                type: "system",
                title: "Stream completed",
                description: `Supervisor response completed via ${String(eventJson.agent || "supervisor")}.`,
                payload: eventJson,
              });
              return;
            }

            if (status === "error") {
              streamTerminalStatus = "error";
              streamErrorDetail = normalizeStreamErrorDetail(eventJson.message, STREAM_RETRY_MESSAGE);
              setDashboardError(streamErrorDetail);
              addFeedEvent({
                type: "error",
                title: "Stream error",
                description: streamErrorDetail,
                payload: eventJson,
              });
            }
            return;
          }

          if (eventType === "error") {
            streamTerminalStatus = "error";
            streamErrorDetail = normalizeStreamErrorDetail(eventJson.message, STREAM_RETRY_MESSAGE);
            setDashboardError(streamErrorDetail);
            addFeedEvent({
              type: "error",
              title: "Stream error",
              description: streamErrorDetail,
              payload: eventJson,
            });
            return;
          }

          if (eventType === "thinking_step") {
            setAssistantProgress(
              `step_${String(eventJson.step || "thinking")}`,
              String(eventJson.label || "Thinking"),
              String(eventJson.status || "active") === "done" ? "completed" : "active",
              eventJson.agent ? String(eventJson.agent) : undefined,
              eventJson.tool ? String(eventJson.tool) : undefined,
            );
            return;
          }

          if (eventType === "reasoning") {
            const reasoningText = String(eventJson.text || "").trim();
            if (!reasoningText) {
              return;
            }

            setAssistantProgress(
              String(eventJson.id || `reasoning_${String(eventJson.step || Date.now())}`),
              reasoningText,
              "completed",
              eventJson.agent ? String(eventJson.agent) : undefined,
              eventJson.tool ? String(eventJson.tool) : undefined,
            );
            return;
          }

          if (eventType === "approval_required") {
            const approval = normalizePendingApproval((eventJson.details || eventJson) as Record<string, any>, shop.id);
            setStreamedPendingApprovals((prev) => {
              const exists = prev.some((item) => item.action_id && item.action_id === approval.action_id);
              if (exists) return prev;
              return [approval, ...prev];
            });
            addFeedEvent({
              type: "approval_required",
              title: "Approval required",
              description: `Action '${approval.action}' is waiting for your decision.`,
              payload: approval,
            });
            void queryClient.invalidateQueries({ queryKey: ownerDashboardKeys.pending(shop.id) });
            return;
          }

          if (eventType === "agent_switch") {
            updateAssistantMessage((msg) =>
              msg.id === assistantMessageId
                ? {
                    ...msg,
                    agent: eventJson.agent ? String(eventJson.agent) : msg.agent,
                  }
                : msg
            );
            addFeedEvent({
              type: "agent_switch",
              title: "Agent switched",
              description: `Supervisor delegated to ${String(eventJson.agent || "sub-agent")}.`,
              payload: eventJson,
            });
            return;
          }

          if (eventType === "tool_call") {
            setAssistantProgress(
              `tool_${String(eventJson.tool || "tool")}`,
              String(eventJson.label || `Running ${formatAssistantProgressLabel(String(eventJson.tool || "tool"))}`),
              "active",
              eventJson.agent ? String(eventJson.agent) : undefined,
              eventJson.tool ? String(eventJson.tool) : undefined,
            );
            addFeedEvent({
              type: "tool_call",
              title: `Tool call: ${String(eventJson.tool || "unknown")}`,
              description: "Tool execution started.",
              payload: eventJson,
            });
            return;
          }

          if (eventType === "tool_result") {
            setAssistantProgress(
              `tool_${String(eventJson.tool || "tool")}`,
              `Completed ${formatAssistantProgressLabel(String(eventJson.tool || "tool"))}`,
              "completed",
              eventJson.agent ? String(eventJson.agent) : undefined,
              eventJson.tool ? String(eventJson.tool) : undefined,
            );
            addFeedEvent({
              type: "tool_result",
              title: `Tool result: ${String(eventJson.tool || "unknown")}`,
              description: "Tool execution completed.",
              payload: eventJson,
            });
            return;
          }

          if (eventType === "chart") {
            const chart = parseStreamChart(eventJson);
            if (chart) {
              sawRenderableAssistantContent = true;
              updateAssistantMessage((msg) =>
                msg.id === assistantMessageId
                  ? {
                      ...msg,
                      charts: [...(msg.charts || []), chart],
                      thinkingComplete: true,
                    }
                  : msg
              );
            }
            return;
          }

          if (eventType === "table") {
            const table = parseStreamTable(eventJson);
            if (table) {
              sawRenderableAssistantContent = true;
              updateAssistantMessage((msg) =>
                msg.id === assistantMessageId
                  ? {
                      ...msg,
                      tables: [...(msg.tables || []), table],
                      thinkingComplete: true,
                    }
                  : msg
              );
            }
            return;
          }

          if (eventType === "file") {
            const file = parseStreamFile(eventJson);
            if (file) {
              sawRenderableAssistantContent = true;
              updateAssistantMessage((msg) =>
                msg.id === assistantMessageId
                  ? {
                      ...msg,
                      files: [...(msg.files || []), file],
                      thinkingComplete: true,
                    }
                  : msg
              );
            }
            return;
          }
        };

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed.startsWith("data:")) continue;
            handleEventData(trimmed.slice(5).trim());
          }
        }

        await Promise.all([
          queryClient.invalidateQueries({ queryKey: ownerDashboardKeys.pending(shop.id) }),
          queryClient.invalidateQueries({ queryKey: ownerDashboardKeys.briefing(shop.id) }),
          queryClient.invalidateQueries({ queryKey: ownerDashboardKeys.feed(shop.id) }),
        ]);
      } catch (error) {
        const detail = normalizeStreamErrorDetail(error, STREAM_RETRY_MESSAGE);
        streamTerminalStatus = "error";
        streamErrorDetail = streamErrorDetail || detail;
        setDashboardError(detail);
        addFeedEvent({
          type: "error",
          title: "Chat stream failed",
          description: detail,
        });
        setMessages((prev) =>
          prev.map((msg) => (msg.id === assistantMessageId ? { ...msg, status: "error" } : msg))
        );
      } finally {
        if (!streamEndedWithDone && streamTerminalStatus === null) {
          streamTerminalStatus = "error";
          streamErrorDetail = sawRenderableAssistantContent ? STREAM_INTERRUPTED_MESSAGE : STREAM_RETRY_MESSAGE;
          setDashboardError(streamErrorDetail);
          addFeedEvent({
            type: "error",
            title: "Stream interrupted",
            description: streamErrorDetail,
            payload: { endedWithDone: false },
          });
        }

        setMessages((prev) => {
          const target = prev.find((msg) => msg.id === assistantMessageId);
          if (!target) return prev;

          const contentEmpty = !String(target.content || "").trim();
          const hasRichPayload = Boolean(
            (target.charts && target.charts.length > 0) ||
              (target.tables && target.tables.length > 0) ||
              (target.files && target.files.length > 0)
          );

          if (streamTerminalStatus === "error") {
            return prev.map((msg) =>
              msg.id === assistantMessageId
                ? {
                    ...msg,
                    content: contentEmpty && !hasRichPayload ? (streamErrorDetail || STREAM_RETRY_MESSAGE) : msg.content,
                    status: "error",
                    thinkingComplete: true,
                  }
                : msg
            );
          }

          return prev.map((msg) =>
            msg.id === assistantMessageId
              ? { ...msg, status: streamEndedWithDone || streamTerminalStatus === "completed" ? "done" : msg.status, thinkingComplete: true }
              : msg
          );
        });
        setIsStreaming(false);
      }
    },
    [addFeedEvent, queryClient, shop?.id, token]
  );

  const contextPromptSections = useMemo<AgentChatPromptSection[]>(() => {
    const nextAvailability = operationsSnapshot.employeeAvailability.find((entry) => entry.next_available_slot);
    const sections: AgentChatPromptSection[] = [
      {
        id: "start",
        title: "Start with",
        prompts: [
          {
            id: "queue-summary",
            label: "Queue summary",
            prompt: "Give me today's queue summary and the next operational action.",
          },
          {
            id: "revenue-trend",
            label: "Revenue trend",
            prompt: "Show this week's revenue trend and explain any change worth acting on.",
          },
          {
            id: "shift-now",
            label: "Who's on shift",
            prompt: "Who is on shift now and where are the staffing gaps?",
          },
          {
            id: "crm-pipeline",
            label: "CRM pipeline",
            prompt: "Show my CRM pipeline summary and tell me what needs attention first.",
          },
        ],
      },
      {
        id: "workspace",
        title: "Workspace context",
        prompts: [
          {
            id: "queues",
            label: `Queues: ${operationsSnapshot.stats.waiting} waiting`,
            prompt: `Show the live queue status. There are ${operationsSnapshot.stats.waiting} people waiting, ${operationsSnapshot.stats.activeQueues} active queues, and ${operationsSnapshot.queueMetrics?.people_being_served || 0} currently being served.`,
          },
          {
            id: "appointments",
            label: `Appointments: ${operationsSnapshot.stats.confirmedAppointments} today`,
            prompt: `Review today's appointments. There are ${operationsSnapshot.stats.confirmedAppointments} confirmed appointments and ${operationsSnapshot.stats.activeAppointments} active appointments. ${operationsSnapshot.appointments[0] ? `The next appointment is at ${formatDateTime(operationsSnapshot.appointments[0].scheduled_start)}.` : "There are no appointments scheduled right now."}`,
          },
          {
            id: "team",
            label: `Team: ${operationsSnapshot.stats.clockedInEmployees}/${operationsSnapshot.stats.totalEmployees}`,
            prompt: `Review team availability. ${operationsSnapshot.stats.clockedInEmployees} of ${operationsSnapshot.stats.totalEmployees} employees are clocked in, and ${operationsSnapshot.stats.unavailableEmployees} are unavailable. ${nextAvailability ? `${nextAvailability.username} is next free at ${formatDateTime(nextAvailability.next_available_slot)}.` : "No upcoming availability is published."}`,
          },
          {
            id: "services",
            label: `Services: ${operationsSnapshot.stats.totalServices} active`,
            prompt: `Summarize current services. There are ${operationsSnapshot.stats.totalServices} active services with an average duration of ${operationsSnapshot.stats.averageServiceDuration || 0} minutes and an average price of ${formatCurrency(operationsSnapshot.stats.averageServiceCost)}.`,
          },
        ],
      },
    ];

    if (briefingQuery.data) {
      sections.push({
        id: "today",
        title: "Today",
        prompts: [
          {
            id: "briefing-summary",
            label: "Today summary",
            prompt: briefingQuery.data.summary,
          },
          ...(briefingQuery.data.actions || []).slice(0, 3).map((action, index) => ({
            id: `briefing-action-${index}`,
            label: action.label,
            prompt: action.payload,
          })),
          ...(briefingQuery.data.recommendations || []).slice(0, 2).map((recommendation, index) => ({
            id: `recommendation-${index}`,
            label: `Recommendation ${index + 1}`,
            prompt: recommendation,
          })),
        ],
      });
    }

    if (pendingApprovals.length > 0) {
      sections.push({
        id: "approvals",
        title: "Pending approvals",
        prompts: pendingApprovals.slice(0, 3).map((approval, index) => ({
          id: approval.action_id || `approval-${index}`,
          label: approval.title || approval.action.replace(/_/g, " "),
          prompt: `Review the pending approval '${approval.title || approval.action}'. Reason: ${approval.reason || "not provided"}. Expected impact: ${approval.expected_impact || "not provided"}. Tell me whether I should approve it.`,
        })),
      });
    }

    if (displayedFeedEvents.length > 0) {
      sections.push({
        id: "recent",
        title: "Recent activity",
        prompts: displayedFeedEvents.slice(0, 4).map((event) => ({
          id: `feed-${event.id}`,
          label: event.title,
          prompt: `Explain this recent activity and tell me if I should act on it: ${event.title}. ${event.description}`,
        })),
      });
    }

    if (Object.keys(policySummary).length > 0) {
      sections.push({
        id: "automation",
        title: "Automation",
        prompts: [
          {
            id: "policy-summary",
            label: "Automation posture",
            prompt: `Summarize my current automation policy posture. ${Object.entries(policySummary)
              .map(([mode, count]) => `${count} set to ${labelForPolicyMode(mode)}`)
              .join(", ")}.`,
          },
        ],
      });
    }

    return sections;
  }, [
    briefingQuery.data,
    displayedFeedEvents,
    operationsSnapshot.appointments,
    operationsSnapshot.employeeAvailability,
    operationsSnapshot.queueMetrics,
    operationsSnapshot.stats,
    pendingApprovals,
    policySummary,
  ]);

  return (
    <Box sx={{ width: "100%", maxWidth: { sm: "100%", md: "1680px" }, mx: "auto" }}>
      <Header />

      <Stack spacing={2}>
        {dashboardError && <Alert severity="error">{dashboardError}</Alert>}

        {!shop?.id && (
          <Alert severity="warning">
            No active shop selected. Choose a shop from the owner navigation bar before using the dashboard.
          </Alert>
        )}

        <Box
          sx={{
            height: { xs: 620, lg: "calc(100vh - 210px)" },
            minHeight: { xs: 620, lg: "calc(100vh - 210px)" },
            display: "flex",
          }}
        >
          <AgentChat
            messages={messages}
            isStreaming={isStreaming}
            isUploading={isUploadingDocuments}
            onSend={handleSend}
            onUpload={handleUploadDocuments}
            title="Hello there!"
            subtitle="How can I help you today?"
            promptSections={contextPromptSections}
          />
        </Box>
      </Stack>
    </Box>
  );
};

export default OwnerDashboardPage;