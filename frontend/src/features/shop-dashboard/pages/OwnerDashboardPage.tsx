import React, { useCallback, useMemo, useState } from "react";
import {
  Alert,
  alpha,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Divider,
  Grid,
  Stack,
  Tab,
  Tabs,
  Typography,
  useTheme,
} from "@mui/material";
import AutoGraphRoundedIcon from "@mui/icons-material/AutoGraphRounded";
import CalendarMonthRoundedIcon from "@mui/icons-material/CalendarMonthRounded";
import ContentCutRoundedIcon from "@mui/icons-material/ContentCutRounded";
import GroupsRoundedIcon from "@mui/icons-material/GroupsRounded";
import InsightsRoundedIcon from "@mui/icons-material/InsightsRounded";
import QueueRoundedIcon from "@mui/icons-material/QueueRounded";
import SmartToyRoundedIcon from "@mui/icons-material/SmartToyRounded";
import TuneRoundedIcon from "@mui/icons-material/TuneRounded";
import WarningAmberRoundedIcon from "@mui/icons-material/WarningAmberRounded";
import { useQueryClient } from "@tanstack/react-query";
import { Link as RouterLink } from "react-router-dom";

import { useAuth } from "../../../contexts/AuthContext";
import { useShop } from "../../../contexts/ShopContext";
import api from "../../../services/api";
import AgentChat from "../../agent-inbox/AgentChat";
import OwnerDocumentsPanel from "../../agent-inbox/OwnerDocumentsPanel";
import AgentFeed from "../../agent-inbox/AgentFeed";
import ApprovalCard from "../../agent-inbox/ApprovalCard";
import OwnerBriefing from "../../agent-inbox/OwnerBriefing";
import {
  ownerDashboardKeys,
  useOwnerBriefingQuery,
  useOwnerDocumentsQuery,
  useOwnerFeedQuery,
  useOwnerOperationsSnapshot,
  useOwnerPoliciesQuery,
  usePendingApprovalsQuery,
} from "../../agent-inbox/ownerDashboardQueries";
import type {
  AgentChart,
  AgentFeedEvent,
  AgentFile,
  ApprovalExecutionResult,
  BriefingAction,
  ChatMessage,
  OwnerDocumentRecord,
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

const buildIntroMessage = (shopName?: string): ChatMessage => ({
  id: toId("msg_intro"),
  role: "assistant",
  content: shopName
    ? `Welcome back to ${shopName}. Use the Today view for operational priorities, Operations for live business summaries, or ask the supervisor agent to handle an action.`
    : "Welcome back. Use the Today view for operational priorities, Operations for live business summaries, or ask the supervisor agent to handle an action.",
  status: "done",
  timestamp: nowIso(),
});

const parseStreamChart = (payload: Record<string, any>): AgentChart | null => {
  if (!Array.isArray(payload.data) || payload.data.length === 0) {
    return null;
  }

  return {
    id: `chart_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
    title: String(payload.title || "Chart"),
    chartType: payload.chartType || "bar",
    data: payload.data,
    xKey: payload.xKey,
    yKey: payload.yKey,
    timestamp: nowIso(),
  };
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

interface TabPanelProps {
  activeValue: string;
  value: string;
  children: React.ReactNode;
}

const TabPanel: React.FC<TabPanelProps> = ({ activeValue, value, children }) => {
  if (activeValue !== value) return null;
  return <Box sx={{ pt: 2.5 }}>{children}</Box>;
};

interface OperationsCardProps {
  title: string;
  value: string;
  description: string;
  caption: string;
  icon: React.ReactNode;
  to: string;
  cta: string;
}

const OperationsCard: React.FC<OperationsCardProps> = ({ title, value, description, caption, icon, to, cta }) => (
  <Card variant="outlined" sx={{ borderRadius: 3, height: "100%" }}>
    <CardContent sx={{ display: "flex", flexDirection: "column", gap: 1.5, height: "100%" }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <Typography variant="overline" color="text.secondary">
          {title}
        </Typography>
        {icon}
      </Stack>
      <Typography variant="h4" sx={{ fontWeight: 800, letterSpacing: "-0.04em" }}>
        {value}
      </Typography>
      <Typography variant="body2" color="text.secondary">
        {description}
      </Typography>
      <Typography variant="caption" color="text.secondary" sx={{ mt: "auto" }}>
        {caption}
      </Typography>
      <Button component={RouterLink} to={to} variant="outlined" sx={{ alignSelf: "flex-start", borderRadius: 999, textTransform: "none", fontWeight: 700 }}>
        {cta}
      </Button>
    </CardContent>
  </Card>
);

const OwnerDashboardPage: React.FC = () => {
  const muiTheme = useTheme();
  const queryClient = useQueryClient();
  const { shop } = useShop();
  const { token } = useAuth();
  const [activeSection, setActiveSection] = useState<"today" | "operations" | "agent">("today");
  const [messages, setMessages] = useState<ChatMessage[]>(() => [buildIntroMessage()]);
  const [localFeedEvents, setLocalFeedEvents] = useState<AgentFeedEvent[]>([]);
  const [streamedPendingApprovals, setStreamedPendingApprovals] = useState<PendingApproval[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isUploadingDocuments, setIsUploadingDocuments] = useState(false);
  const [isApproving, setIsApproving] = useState(false);
  const [isMarkingAllRead, setIsMarkingAllRead] = useState(false);
  const [markingNotificationId, setMarkingNotificationId] = useState<number | null>(null);
  const [actingDocumentId, setActingDocumentId] = useState<number | null>(null);
  const [actingDocumentType, setActingDocumentType] = useState<"reindex" | "delete" | null>(null);
  const [dashboardError, setDashboardError] = useState<string | null>(null);

  const briefingQuery = useOwnerBriefingQuery(shop?.id);
  const pendingQuery = usePendingApprovalsQuery(shop?.id);
  const feedQuery = useOwnerFeedQuery(shop?.id);
  const documentsQuery = useOwnerDocumentsQuery(shop?.id);
  const policiesQuery = useOwnerPoliciesQuery(shop?.id);
  const operationsSnapshot = useOwnerOperationsSnapshot(shop?.id);

  const brandPrimary = shop?.primary_color || muiTheme.palette.primary.main;
  const brandSecondary = shop?.secondary_color || brandPrimary;
  const panelCardBg =
    muiTheme.palette.mode === "dark"
      ? "rgba(255, 255, 255, 0.05)"
      : alpha("#ffffff", 0.72);
  const panelCardBorder =
    muiTheme.palette.mode === "dark"
      ? alpha(brandPrimary, 0.24)
      : alpha(brandPrimary, 0.16);

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

  const unreadFeedCount = useMemo(
    () => (feedQuery.data || []).filter((event) => event.notification_id && event.status === "unread").length,
    [feedQuery.data]
  );

  const policySummary = useMemo(() => {
    return (policiesQuery.data || []).reduce<Record<string, number>>((summary, policy) => {
      summary[policy.mode] = (summary[policy.mode] || 0) + 1;
      return summary;
    }, {});
  }, [policiesQuery.data]);

  const handleApproveDecision = useCallback(
    async (approval: PendingApproval, approved: boolean) => {
      if (!shop?.id) return;
      setDashboardError(null);
      setIsApproving(true);

      try {
        const response = await api.post<{
          message?: string;
          status?: string;
          agent?: string;
          tool_results?: ApprovalExecutionResult;
        }>("/v2/agent/approve", {
          shop_id: shop.id,
          action_id: approval.action_id,
          approved,
        });

        const eventTimestamp = nowIso();
        setStreamedPendingApprovals((prev) =>
          prev.filter((item) => item.action_id !== approval.action_id)
        );
        setMessages((prev) => [
          ...prev,
          {
            id: toId("msg_system"),
            role: "system",
            content: response.data.message || `Action ${approved ? "approved" : "rejected"}.`,
            status: "done",
            timestamp: eventTimestamp,
            agent: response.data.agent,
          },
        ]);
        addFeedEvent({
          type: "approval_decision",
          title: approved ? "Action approved" : "Action rejected",
          description: `You ${approved ? "approved" : "rejected"} '${approval.action}'.`,
          payload: response.data.tool_results || response.data,
        });

        await Promise.all([
          queryClient.invalidateQueries({ queryKey: ownerDashboardKeys.pending(shop.id) }),
          queryClient.invalidateQueries({ queryKey: ownerDashboardKeys.briefing(shop.id) }),
          queryClient.invalidateQueries({ queryKey: ownerDashboardKeys.feed(shop.id) }),
        ]);
      } catch (error) {
        const detail = getErrorDetail(error, "Failed to submit approval decision");
        setDashboardError(detail);
        addFeedEvent({
          type: "error",
          title: "Approval failed",
          description: detail,
        });
      } finally {
        setIsApproving(false);
      }
    },
    [addFeedEvent, queryClient, shop?.id]
  );

  const handleMarkNotificationRead = useCallback(
    async (notificationId: number) => {
      if (!shop?.id) return;
      setDashboardError(null);
      setMarkingNotificationId(notificationId);

      try {
        await api.post(`/v2/agent/notifications/${notificationId}/read`, {
          shop_id: shop.id,
        });
        await queryClient.invalidateQueries({ queryKey: ownerDashboardKeys.feed(shop.id) });
      } catch (error) {
        setDashboardError(getErrorDetail(error, "Failed to mark notification as read"));
      } finally {
        setMarkingNotificationId(null);
      }
    },
    [queryClient, shop?.id]
  );

  const handleMarkAllNotificationsRead = useCallback(async () => {
    if (!shop?.id) return;
    setDashboardError(null);
    setIsMarkingAllRead(true);

    try {
      await api.post("/v2/agent/notifications/read-all", { shop_id: shop.id });
      await queryClient.invalidateQueries({ queryKey: ownerDashboardKeys.feed(shop.id) });
    } catch (error) {
      setDashboardError(getErrorDetail(error, "Failed to clear unread notifications"));
    } finally {
      setIsMarkingAllRead(false);
    }
  }, [queryClient, shop?.id]);

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

  const handleReindexDocument = useCallback(
    async (document: OwnerDocumentRecord) => {
      if (!shop?.id) return;

      setDashboardError(null);
      setActingDocumentId(document.id);
      setActingDocumentType("reindex");

      try {
        const response = await api.post<{ message: string; indexed_chunks: number }>(
          `/v2/agent/documents/${document.id}/reindex`,
          { shop_id: shop.id },
        );

        setMessages((prev) => [
          ...prev,
          {
            id: toId("msg_system"),
            role: "system",
            content: response.data.message,
            status: "done",
            timestamp: nowIso(),
            agent: "system",
          },
        ]);
        addFeedEvent({
          type: "system",
          title: "Document re-indexed",
          description: response.data.message,
          payload: { document_id: document.id, indexed_chunks: response.data.indexed_chunks },
        });

        await queryClient.invalidateQueries({ queryKey: ownerDashboardKeys.documents(shop.id) });
      } catch (error) {
        const detail = getErrorDetail(error, "Failed to re-index document");
        setDashboardError(detail);
        addFeedEvent({
          type: "error",
          title: "Document re-index failed",
          description: detail,
        });
      } finally {
        setActingDocumentId(null);
        setActingDocumentType(null);
      }
    },
    [addFeedEvent, queryClient, shop?.id],
  );

  const handleDeleteDocument = useCallback(
    async (document: OwnerDocumentRecord) => {
      if (!shop?.id) return;

      const label = document.relative_path || document.filename;
      if (!window.confirm(`Delete ${label} from secure storage and remove its indexed knowledge?`)) {
        return;
      }

      setDashboardError(null);
      setActingDocumentId(document.id);
      setActingDocumentType("delete");

      try {
        const response = await api.delete<{ message: string }>(`/v2/agent/documents/${document.id}`, {
          params: { shop_id: shop.id },
        });

        setMessages((prev) => [
          ...prev,
          {
            id: toId("msg_system"),
            role: "system",
            content: response.data.message,
            status: "done",
            timestamp: nowIso(),
            agent: "system",
          },
        ]);
        addFeedEvent({
          type: "system",
          title: "Document removed",
          description: response.data.message,
          payload: { document_id: document.id },
        });

        await queryClient.invalidateQueries({ queryKey: ownerDashboardKeys.documents(shop.id) });
      } catch (error) {
        const detail = getErrorDetail(error, "Failed to delete document");
        setDashboardError(detail);
        addFeedEvent({
          type: "error",
          title: "Document delete failed",
          description: detail,
        });
      } finally {
        setActingDocumentId(null);
        setActingDocumentType(null);
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
                  thinkingComplete: true,
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
              applyAssistantDelta(content);
            }
            return;
          }

          if (eventType === "thinking_step") {
            const stepId = `${String(eventJson.step || eventJson.label || "step")}_${String(eventJson.tool || "")}`;
            updateAssistantMessage((msg) => {
              if (msg.id !== assistantMessageId) return msg;

              const existingSteps = msg.thinkingSteps || [];
              const existing = existingSteps.find((step) => step.id === stepId);
              const nextStatus: ThinkingStep["status"] =
                eventJson.status === "active"
                  ? "active"
                  : eventJson.status === "done"
                    ? "completed"
                    : "pending";
              const nextSteps = existing
                ? existingSteps.map((step) =>
                    step.id === stepId
                      ? {
                          ...step,
                          label: String(eventJson.label || step.label),
                          status:
                            eventJson.status === "active"
                              ? "active"
                              : eventJson.status === "done"
                                ? "completed"
                                : step.status,
                          agent: eventJson.agent || step.agent,
                        }
                      : step
                  )
                : [
                    ...existingSteps,
                    {
                      id: stepId,
                      label: String(eventJson.label || "Thinking"),
                      status: nextStatus,
                      agent: eventJson.agent,
                    },
                  ];

              return {
                ...msg,
                thinkingSteps: nextSteps,
                thinkingComplete: false,
              };
            });
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
            addFeedEvent({
              type: "agent_switch",
              title: "Agent switched",
              description: `Supervisor delegated to ${String(eventJson.agent || "sub-agent")}.`,
              payload: eventJson,
            });
            return;
          }

          if (eventType === "tool_call") {
            addFeedEvent({
              type: "tool_call",
              title: `Tool call: ${String(eventJson.tool || "unknown")}`,
              description: "Tool execution started.",
              payload: eventJson,
            });
            return;
          }

          if (eventType === "tool_result") {
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

          if (eventType === "file") {
            const file = parseStreamFile(eventJson);
            if (file) {
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
        const detail = getErrorDetail(error, "Failed to stream agent response");
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
        setMessages((prev) => {
          const target = prev.find((msg) => msg.id === assistantMessageId);
          if (!target) return prev;

          const contentEmpty = !String(target.content || "").trim();
          const hasRichPayload = Boolean((target.charts && target.charts.length > 0) || (target.files && target.files.length > 0));
          if (contentEmpty || !streamEndedWithDone) {
            return prev.map((msg) =>
              msg.id === assistantMessageId
                ? {
                    ...msg,
                    content: contentEmpty && !hasRichPayload ? "Something went wrong — please try again." : msg.content,
                    status: "error",
                    thinkingComplete: true,
                  }
                : msg
            );
          }

          return prev.map((msg) =>
            msg.id === assistantMessageId
              ? { ...msg, status: msg.status === "error" ? "error" : "done", thinkingComplete: true }
              : msg
          );
        });
        setIsStreaming(false);
      }
    },
    [addFeedEvent, queryClient, shop?.id, token]
  );

  const derivedOperationsCards = useMemo(() => {
    const nextAvailability = operationsSnapshot.employeeAvailability.find((entry) => entry.next_available_slot);
    return [
      {
        title: "Queues",
        value: `${operationsSnapshot.stats.waiting}`,
        description: `${operationsSnapshot.stats.activeQueues} queue${operationsSnapshot.stats.activeQueues === 1 ? "" : "s"} active with an estimated wait of ${operationsSnapshot.stats.etaMinutes} minutes.`,
        caption: `${operationsSnapshot.queueMetrics?.people_being_served || 0} currently being served`,
        icon: <QueueRoundedIcon sx={{ color: brandPrimary }} />,
        to: "/queues",
        cta: "Open queues",
      },
      {
        title: "Appointments",
        value: `${operationsSnapshot.stats.confirmedAppointments}`,
        description: `${operationsSnapshot.stats.activeAppointments} active appointment${operationsSnapshot.stats.activeAppointments === 1 ? "" : "s"} today across the live schedule.`,
        caption: operationsSnapshot.appointments[0]
          ? `Next at ${formatDateTime(operationsSnapshot.appointments[0].scheduled_start)}`
          : "No appointments scheduled today",
        icon: <CalendarMonthRoundedIcon sx={{ color: brandSecondary }} />,
        to: "/appointments",
        cta: "Open appointments",
      },
      {
        title: "Team",
        value: `${operationsSnapshot.stats.clockedInEmployees}/${operationsSnapshot.stats.totalEmployees}`,
        description: `${operationsSnapshot.stats.unavailableEmployees} team member${operationsSnapshot.stats.unavailableEmployees === 1 ? "" : "s"} currently unavailable.`,
        caption: nextAvailability ? `${nextAvailability.username} next free at ${formatDateTime(nextAvailability.next_available_slot)}` : "No upcoming availability published",
        icon: <GroupsRoundedIcon sx={{ color: brandPrimary }} />,
        to: "/employees",
        cta: "Open team",
      },
      {
        title: "Services",
        value: `${operationsSnapshot.stats.totalServices}`,
        description: `Average service length is ${operationsSnapshot.stats.averageServiceDuration || 0} minutes with an average price of ${formatCurrency(operationsSnapshot.stats.averageServiceCost)}.`,
        caption: operationsSnapshot.services[0] ? `${operationsSnapshot.services[0].name} is currently published` : "No services configured yet",
        icon: <ContentCutRoundedIcon sx={{ color: brandSecondary }} />,
        to: "/services",
        cta: "Open services",
      },
    ];
  }, [
    brandPrimary,
    brandSecondary,
    operationsSnapshot.appointments,
    operationsSnapshot.employeeAvailability,
    operationsSnapshot.queueMetrics,
    operationsSnapshot.services,
    operationsSnapshot.stats,
  ]);

  const handleSectionChange = (_event: React.SyntheticEvent, value: string) => {
    setActiveSection(value as "today" | "operations" | "agent");
  };

  const handleOpenAgentFromToday = useCallback(async (action?: BriefingAction) => {
    setActiveSection("agent");
    if (action?.payload) {
      await handleSend(action.payload);
    }
  }, [handleSend]);

  return (
    <Box sx={{ width: "100%", maxWidth: { sm: "100%", md: "1700px" } }}>
      <Header />

      <Stack spacing={2.5}>
        <Card
          variant="outlined"
          sx={{
            borderRadius: 3,
            borderColor: panelCardBorder,
            bgcolor: panelCardBg,
            backdropFilter: "blur(20px)",
          }}
        >
          <CardContent>
            <Stack spacing={1.5}>
              <Stack
                direction={{ xs: "column", lg: "row" }}
                spacing={1.5}
                justifyContent="space-between"
                alignItems={{ xs: "flex-start", lg: "center" }}
              >
                <Box>
                  <Typography variant="overline" sx={{ color: brandPrimary, fontWeight: 800, letterSpacing: "0.16em" }}>
                    OWNER WORKSPACE
                  </Typography>
                  <Typography variant="h4" sx={{ fontWeight: 800, letterSpacing: "-0.05em", mt: 0.5 }}>
                    Today, operations, and agent control in one owner shell.
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 1, maxWidth: 760 }}>
                    Today surfaces briefings, approvals, and feed. Operations summarizes queues, appointments, team, and services with deep links into the existing workspaces. Agent keeps the live assistant available without dominating the page.
                  </Typography>
                </Box>
                <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap">
                  <Chip icon={<WarningAmberRoundedIcon />} label={`${pendingApprovals.length} pending approval${pendingApprovals.length === 1 ? "" : "s"}`} />
                  <Chip icon={<AutoGraphRoundedIcon />} label={`${operationsSnapshot.stats.confirmedAppointments} appointments today`} />
                  <Chip icon={<SmartToyRoundedIcon />} label={isStreaming ? "Agent active" : "Agent ready"} />
                </Stack>
              </Stack>

              <Tabs
                value={activeSection}
                onChange={handleSectionChange}
                variant="scrollable"
                allowScrollButtonsMobile
                sx={{
                  borderTop: `1px solid ${alpha(brandPrimary, 0.12)}`,
                  pt: 1,
                  "& .MuiTabs-indicator": {
                    backgroundColor: brandPrimary,
                    height: 3,
                    borderRadius: 999,
                  },
                }}
              >
                <Tab value="today" icon={<InsightsRoundedIcon />} iconPosition="start" label="Today" sx={{ textTransform: "none", fontWeight: 700 }} />
                <Tab value="operations" icon={<QueueRoundedIcon />} iconPosition="start" label="Operations" sx={{ textTransform: "none", fontWeight: 700 }} />
                <Tab value="agent" icon={<SmartToyRoundedIcon />} iconPosition="start" label="Agent" sx={{ textTransform: "none", fontWeight: 700 }} />
              </Tabs>
            </Stack>
          </CardContent>
        </Card>

        {dashboardError && <Alert severity="error">{dashboardError}</Alert>}

        {!shop?.id && (
          <Alert severity="warning">
            No active shop selected. Choose a shop from the owner navigation bar before using the dashboard.
          </Alert>
        )}

        <TabPanel activeValue={activeSection} value="today">
          <Stack spacing={2}>
            {briefingQuery.isLoading ? (
              <Card variant="outlined" sx={{ borderRadius: 3 }}>
                <CardContent>
                  <Stack direction="row" spacing={1} alignItems="center">
                    <CircularProgress size={18} />
                    <Typography variant="body2" color="text.secondary">
                      Loading your live briefing...
                    </Typography>
                  </Stack>
                </CardContent>
              </Card>
            ) : (
              <OwnerBriefing briefing={briefingQuery.data || null} onAction={handleOpenAgentFromToday} />
            )}

            <Grid container spacing={2}>
              <Grid size={{ xs: 12, lg: 5 }}>
                <Stack spacing={2}>
                  <Card
                    variant="outlined"
                    sx={{
                      borderRadius: 3,
                      borderColor: panelCardBorder,
                      bgcolor: panelCardBg,
                      backdropFilter: "blur(20px)",
                    }}
                  >
                    <CardContent sx={{ py: 1.5 }}>
                      <Stack spacing={1.25}>
                        <Stack direction="row" justifyContent="space-between" alignItems="center">
                          <Typography variant="h6">Pending Approvals</Typography>
                          <Chip size="small" label={pendingApprovals.length} sx={{ bgcolor: alpha(brandPrimary, 0.14), color: brandPrimary, fontWeight: 700 }} />
                        </Stack>
                        <Divider sx={{ borderColor: alpha(brandPrimary, 0.12) }} />
                        {pendingQuery.isLoading ? (
                          <Stack direction="row" spacing={1} alignItems="center" py={1}>
                            <CircularProgress size={16} />
                            <Typography variant="body2" color="text.secondary">
                              Refreshing approvals...
                            </Typography>
                          </Stack>
                        ) : pendingApprovals.length > 0 ? (
                          pendingApprovals.slice(0, 4).map((approval) => (
                            <ApprovalCard
                              key={approval.action_id || `${approval.action}_${approval.shop_id}`}
                              approval={approval}
                              isSubmitting={isApproving}
                              onDecision={handleApproveDecision}
                            />
                          ))
                        ) : (
                          <Typography variant="body2" color="text.secondary">
                            No actions are waiting for approval right now.
                          </Typography>
                        )}
                      </Stack>
                    </CardContent>
                  </Card>

                  <Card variant="outlined" sx={{ borderRadius: 3 }}>
                    <CardContent>
                      <Stack spacing={1.25}>
                        <Typography variant="h6">Quick actions</Typography>
                        <Typography variant="body2" color="text.secondary">
                          Jump straight into the detailed workspaces when you need full control.
                        </Typography>
                        <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap">
                          <Button component={RouterLink} to="/overview" variant="outlined" sx={{ borderRadius: 999, textTransform: "none", fontWeight: 700 }}>
                            View analytics
                          </Button>
                          <Button component={RouterLink} to="/appointments" variant="outlined" sx={{ borderRadius: 999, textTransform: "none", fontWeight: 700 }}>
                            Open schedule
                          </Button>
                        </Stack>
                      </Stack>
                    </CardContent>
                  </Card>
                </Stack>
              </Grid>

              <Grid size={{ xs: 12, lg: 7 }}>
                <AgentFeed
                  events={displayedFeedEvents}
                  unreadCount={unreadFeedCount}
                  isMarkingAllRead={isMarkingAllRead}
                  markingNotificationId={markingNotificationId}
                  onMarkAsRead={handleMarkNotificationRead}
                  onMarkAllAsRead={handleMarkAllNotificationsRead}
                  maxHeight={{ xs: 420, lg: 720 }}
                />
              </Grid>
            </Grid>
          </Stack>
        </TabPanel>

        <TabPanel activeValue={activeSection} value="operations">
          <Stack spacing={2}>
            <Card variant="outlined" sx={{ borderRadius: 3 }}>
              <CardContent>
                <Stack direction={{ xs: "column", md: "row" }} spacing={1.5} justifyContent="space-between">
                  <Box>
                    <Typography variant="h6">Operations summary</Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 0.75 }}>
                      These summaries are powered by the existing queue, appointment, employee, and service endpoints. The detailed workspaces stay live and unchanged behind each card.
                    </Typography>
                  </Box>
                  <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap">
                    <Button component={RouterLink} to="/overview" variant="contained" sx={{ borderRadius: 999, textTransform: "none", fontWeight: 700 }}>
                      Open overview
                    </Button>
                    <Button component={RouterLink} to="/settings" variant="outlined" sx={{ borderRadius: 999, textTransform: "none", fontWeight: 700 }}>
                      Shop setup
                    </Button>
                  </Stack>
                </Stack>
              </CardContent>
            </Card>

            {operationsSnapshot.isLoading ? (
              <Card variant="outlined" sx={{ borderRadius: 3 }}>
                <CardContent>
                  <Stack direction="row" spacing={1} alignItems="center">
                    <CircularProgress size={18} />
                    <Typography variant="body2" color="text.secondary">
                      Loading operations snapshots...
                    </Typography>
                  </Stack>
                </CardContent>
              </Card>
            ) : (
              <Grid container spacing={2}>
                {derivedOperationsCards.map((card) => (
                  <Grid key={card.title} size={{ xs: 12, md: 6 }}>
                    <OperationsCard {...card} />
                  </Grid>
                ))}
              </Grid>
            )}
          </Stack>
        </TabPanel>

        <TabPanel activeValue={activeSection} value="agent">
          <Grid container spacing={2}>
            <Grid size={{ xs: 12, lg: 7.5 }}>
              <Box sx={{ minHeight: { lg: 640 } }}>
                <AgentChat
                  messages={messages}
                  isStreaming={isStreaming}
                  isUploading={isUploadingDocuments}
                  onSend={handleSend}
                  onUpload={handleUploadDocuments}
                />
              </Box>
            </Grid>
            <Grid size={{ xs: 12, lg: 4.5 }}>
              <Stack spacing={2}>
                <Card variant="outlined" sx={{ borderRadius: 3 }}>
                  <CardContent>
                    <Stack spacing={1.25}>
                      <Stack direction="row" spacing={1} alignItems="center">
                        <TuneRoundedIcon sx={{ color: brandPrimary }} />
                        <Typography variant="h6">Agent controls</Typography>
                      </Stack>
                      <Typography variant="body2" color="text.secondary">
                        Policy management remains on the same backend contract. This view surfaces the current automation posture without widening scope.
                      </Typography>
                      <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap">
                        {Object.keys(policySummary).length > 0 ? (
                          Object.entries(policySummary).map(([mode, count]) => (
                            <Chip key={mode} label={`${labelForPolicyMode(mode)}: ${count}`} variant="outlined" />
                          ))
                        ) : (
                          <Chip label={policiesQuery.isLoading ? "Loading policies" : "No policies loaded"} variant="outlined" />
                        )}
                      </Stack>
                    </Stack>
                  </CardContent>
                </Card>

                <OwnerDocumentsPanel
                  documents={documentsQuery.data || []}
                  isLoading={documentsQuery.isLoading}
                  actingDocumentId={actingDocumentId}
                  actingType={actingDocumentType}
                  onReindex={handleReindexDocument}
                  onDelete={handleDeleteDocument}
                />

                <AgentFeed
                  events={displayedFeedEvents.slice(0, 8)}
                  unreadCount={unreadFeedCount}
                  isMarkingAllRead={isMarkingAllRead}
                  markingNotificationId={markingNotificationId}
                  onMarkAsRead={handleMarkNotificationRead}
                  onMarkAllAsRead={handleMarkAllNotificationsRead}
                  maxHeight={{ xs: 320, lg: 420 }}
                />
              </Stack>
            </Grid>
          </Grid>
        </TabPanel>
      </Stack>
    </Box>
  );
};

export default OwnerDashboardPage;