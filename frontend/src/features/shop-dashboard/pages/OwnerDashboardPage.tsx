// RESTYLED: Perplexity-style
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  IconButton,
  Stack,
  Tooltip,
} from "@mui/material";
import AddCommentOutlinedIcon from "@mui/icons-material/AddCommentOutlined";
import { useQueryClient } from "@tanstack/react-query";

import { useAuth } from "../../../contexts/AuthContext";
import { useShop } from "../../../contexts/ShopContext";
import api from "../../../services/api";
import AgentChat, {
  AgentChatSendPayload,
  AgentChatPromptSection,
} from "../../agent-inbox/AgentChat";
import AgentTaskBoard, {
  AgentTaskBoardExternalTask,
} from "../../agent-inbox/AgentTaskBoard";
import {
  ownerDashboardKeys,
  useOwnerBriefingQuery,
  useOwnerFeedQuery,
  useOwnerOperationsSnapshot,
  useOwnerPoliciesQuery,
  usePendingApprovalsQuery,
} from "../../agent-inbox/ownerDashboardQueries";
import { useApprovalDecisions } from "../../agent-inbox/hooks/useApprovalDecisions";
import { createAgentChartFromPayload } from "../../agent-inbox/types";
import type {
  AgentChart,
  AgentFeedEvent,
  AgentFile,
  AgentTable,
  ChatMessage,
  InsightItem,
  PendingApproval,
  ThinkingStep,
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
    approval_request_id: nested.approval_request_id || detailPayload.approval_request_id,
    created_at: nested.created_at || detailPayload.created_at,
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

const FALLBACK_TASK_TIMESTAMP = "1970-01-01T00:00:00.000Z";

const formatTaskActionLabel = (value?: string | null): string => {
  if (!value) {
    return "Agent task";
  }

  return value
    .split(/[_-]/g)
    .filter(Boolean)
    .map((token) => token.charAt(0).toUpperCase() + token.slice(1))
    .join(" ");
};

const summarizeApprovalValue = (value: unknown): string | null => {
  if (value === null || value === undefined || value === "") {
    return null;
  }

  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }

  if (Array.isArray(value)) {
    return `${value.length} item${value.length === 1 ? "" : "s"}`;
  }

  if (typeof value === "object") {
    const record = value as Record<string, unknown>;
    const label = record.name || record.title || record.email || record.phone || record.id;
    return label ? String(label) : null;
  }

  return null;
};

const buildApprovalTaskDetails = (approval: PendingApproval): string[] => {
  const details = approval.details || {};
  const lines = [
    approval.risk_level ? `Risk: ${String(approval.risk_level)}` : null,
    approval.urgency ? `Urgency: ${String(approval.urgency)}` : null,
    approval.recommended_decision ? `Suggested: ${String(approval.recommended_decision)}` : null,
    ...Object.entries(details)
      .filter(([key]) => !["shop_id", "user_id", "policy_key", "policy_mode", "details"].includes(key))
      .map(([key, value]) => {
        const summary = summarizeApprovalValue(value);
        if (!summary) return null;
        return `${formatTaskActionLabel(key)}: ${summary}`;
      }),
  ].filter((line): line is string => Boolean(line && line.trim()));

  return Array.from(new Set(lines)).slice(0, 5);
};

const getAttachmentFiles = (attachments: AgentChatSendPayload["attachments"]): File[] => {
  return (attachments || []).flatMap((attachment) => (attachment.file instanceof File ? [attachment.file] : []));
};

const STREAM_INTERRUPTED_MESSAGE = "The response stream was interrupted before completion. Partial output may be shown below.";
const STREAM_RETRY_MESSAGE = "The response was interrupted before it finished. Please try again.";

const ownerChatMessagesKey = (shopId: number) => `owner-chat-messages:${shopId}`;
const ownerChatActiveKey = (shopId: number) => `owner-chat-active:${shopId}`;

const persistOwnerChatSnapshot = (shopId: number, messages: ChatMessage[], active: boolean) => {
  try {
    sessionStorage.setItem(ownerChatMessagesKey(shopId), JSON.stringify(messages));
    sessionStorage.setItem(ownerChatActiveKey(shopId), active ? "1" : "0");
  } catch {
    // sessionStorage full or unavailable — skip silently
  }
};

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
  const { shop, loading: shopLoading } = useShop();
  const { token } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [localFeedEvents, setLocalFeedEvents] = useState<AgentFeedEvent[]>([]);
  const [streamedPendingApprovals, setStreamedPendingApprovals] = useState<PendingApproval[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isUploadingDocuments, setIsUploadingDocuments] = useState(false);
  const [dashboardError, setDashboardError] = useState<string | null>(null);
  const messagesRef = useRef<ChatMessage[]>([]);
  const mountedRef = useRef(true);

  // Abort controller for the active stream — aborted when component unmounts
  // or when a new message is sent while a previous stream is still running.
  const activeStreamAbortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  // Keep the stream alive across route/tab switches. The async stream handler
  // writes progress to sessionStorage so the Agent view can restore it later.
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  // Restore conversation history when the component mounts (covers tab
  // switches and page refreshes).  We check sessionStorage first so that
  // charts / tables generated during the current browser session survive
  // navigation.  When sessionStorage is empty we fall back to the API which
  // returns text-only checkpoint history.
  const historyLoadedForRef = useRef<number | null>(null);
  useEffect(() => {
    if (!shop?.id || historyLoadedForRef.current === shop.id) return;
    historyLoadedForRef.current = shop.id;

    // 1. Try sessionStorage (preserves charts across refreshes / tab switches)
    try {
      const raw = sessionStorage.getItem(ownerChatMessagesKey(shop.id));
      if (raw) {
        const parsed: ChatMessage[] = JSON.parse(raw);
        if (parsed.length > 0) {
          setMessages(parsed);
          setIsStreaming(sessionStorage.getItem(ownerChatActiveKey(shop.id)) === "1");
          return;
        }
      }
    } catch {
      // Ignore parse errors — fall through to API
    }

    // 2. Fallback: LangGraph checkpoint (text-only, cross-session)
    const authToken = token || localStorage.getItem("token");
    fetch(`${apiBaseUrl}/v2/agent/history?shop_id=${shop.id}`, {
      headers: authToken ? { Authorization: `Bearer ${authToken}` } : {},
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        const raw: { role: string; content: string; timestamp?: string | null }[] =
          data?.messages ?? [];
        if (raw.length === 0) return;
        const restored: ChatMessage[] = raw
          .filter((m) => m.content && m.content.trim())
          .map((m, i) => ({
            id: toId(`msg_history_${i}`),
            role: m.role === "user" ? ("user" as const) : ("assistant" as const),
            content: m.content,
            status: "done" as const,
            timestamp: m.timestamp ?? nowIso(),
          }));
        if (restored.length > 0) {
          setMessages(restored);
        }
      })
      .catch(() => {
        // Non-fatal — chat will start empty on history load failure
      });
  }, [shop?.id, token]);

  // Persist messages (including charts / tables) to sessionStorage on every
  // change — including during streaming so thinking steps survive tab switches.
  // We save a snapshot where any in-progress "streaming" message is marked
  // "done" so that when it is restored after unmount it renders cleanly.
  useEffect(() => {
    if (!shop?.id || messages.length === 0) return;
    persistOwnerChatSnapshot(shop.id, messages, isStreaming);
  }, [isStreaming, messages, shop?.id]);

  useEffect(() => {
    if (!shop?.id) return;

    const intervalId = window.setInterval(() => {
      const active = sessionStorage.getItem(ownerChatActiveKey(shop.id)) === "1";
      if (!active) return;

      try {
        const raw = sessionStorage.getItem(ownerChatMessagesKey(shop.id));
        if (!raw) return;
        const parsed: ChatMessage[] = JSON.parse(raw);
        if (parsed.length > 0) {
          setMessages(parsed);
          setIsStreaming(true);
        }
      } catch {
        // Ignore malformed session snapshots.
      }
    }, 1000);

    return () => window.clearInterval(intervalId);
  }, [shop?.id]);

  // ── New chat ────────────────────────────────────────────────────────────
  const [showNewChatDialog, setShowNewChatDialog] = useState(false);
  const [isResettingChat, setIsResettingChat] = useState(false);

  const handleNewChatConfirm = useCallback(async () => {
    if (!shop?.id) return;
    setIsResettingChat(true);
    try {
      const authToken = token || localStorage.getItem("token");
      await fetch(`${apiBaseUrl}/v2/agent/reset-conversation?shop_id=${shop.id}`, {
        method: "POST",
        headers: authToken ? { Authorization: `Bearer ${authToken}` } : {},
      });
    } catch {
      // Best-effort — clear locally even if API fails
    } finally {
      setIsResettingChat(false);
    }
    // Clear persisted messages and reset state
    try {
      sessionStorage.removeItem(ownerChatMessagesKey(shop.id));
      sessionStorage.removeItem(ownerChatActiveKey(shop.id));
    } catch {
      // ignore
    }
    historyLoadedForRef.current = null;
    setMessages([]);
    setShowNewChatDialog(false);
  }, [shop?.id, token]);


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

  const commitMessages = useCallback(
    (updater: (current: ChatMessage[]) => ChatMessage[], active = false) => {
      const next = updater(messagesRef.current);
      messagesRef.current = next;
      if (shop?.id) {
        persistOwnerChatSnapshot(shop.id, next, active);
      }
      if (mountedRef.current) {
        setMessages(next);
      }
      return next;
    },
    [shop?.id],
  );

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

  const uploadDocumentsToKnowledgeBase = useCallback(
    async (selectedFiles: File[]) => {
      if (!shop?.id) {
        throw new Error("No active shop selected for document upload.");
      }
      if (selectedFiles.length === 0) {
        return null;
      }

      setDashboardError(null);
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

      addFeedEvent({
        type: "system",
        title: "Knowledge base updated",
        description: response.data.message,
        payload: response.data.documents,
      });

      await queryClient.invalidateQueries({ queryKey: ownerDashboardKeys.documents(shop.id) });
      return response.data;
    },
    [addFeedEvent, queryClient, shop?.id],
  );

  const appendSystemMessage = useCallback(
    (content: string, _agent?: string) => {
      setMessages((prev) => [
        ...prev,
        {
          id: toId("msg_system"),
          role: "system" as const,
          content,
          status: "done" as const,
          timestamp: nowIso(),
        },
      ]);
    },
    [],
  );

  const { handleApprovalDecision, isApproving } = useApprovalDecisions({
    shopId: shop?.id,
    addFeedEvent,
    appendSystemMessage,
    prependInsightItem: (_item: InsightItem) => {},
    refreshPendingApprovals: async () => {
      if (shop?.id) {
        await queryClient.invalidateQueries({ queryKey: ownerDashboardKeys.pending(shop.id) });
      }
    },
    refreshBriefing: async () => {
      if (shop?.id) {
        await queryClient.invalidateQueries({ queryKey: ownerDashboardKeys.briefing(shop.id) });
      }
    },
    refreshFeed: async () => {
      if (shop?.id) {
        await queryClient.invalidateQueries({ queryKey: ownerDashboardKeys.feed(shop.id) });
      }
    },
    setError: setDashboardError,
  });

  const handleApprovalTaskClick = useCallback(
    (actionId: string) => {
      const approval =
        pendingApprovals.find((item) => item.action_id === actionId) ||
        displayedFeedEvents.reduce<PendingApproval | undefined>((match, event) => {
          if (match || event.type !== "approval_required") {
            return match;
          }
          const payload =
            event.payload && typeof event.payload === "object"
              ? (event.payload as Record<string, unknown>)
              : null;
          return payload?.action_id === actionId
            ? normalizePendingApproval(payload as Record<string, any>, shop?.id || 0)
            : undefined;
        }, undefined);
      if (!approval) {
        const el = document.querySelector(`[data-approval-id="${actionId}"]`);
        el?.scrollIntoView({ behavior: "smooth", block: "center" });
        return;
      }

      setMessages((prev) => {
        const alreadyExists = prev.some(
          (message) => message.pendingAction?.action_id && message.pendingAction.action_id === actionId,
        );
        if (alreadyExists) {
          return prev;
        }

        return [
          ...prev,
          {
            id: toId("msg_approval_task"),
            role: "assistant" as const,
            content: "Approval request opened from the Task Board.",
            status: "done" as const,
            timestamp: nowIso(),
            pendingAction: approval,
            thinkingComplete: true,
          },
        ];
      });

      window.setTimeout(() => {
        const el = document.querySelector(`[data-approval-id="${actionId}"]`);
        el?.scrollIntoView({ behavior: "smooth", block: "center" });
      }, 50);
    },
    [displayedFeedEvents, pendingApprovals, shop?.id],
  );

  const handleSend = useCallback(
    async ({ text, attachments = [] }: AgentChatSendPayload) => {
      if (!shop?.id) {
        // Only surface the error after the shop context has finished loading.
        // During the loading window the shop is legitimately absent — showing an
        // error here would be incorrect and would persist since nothing clears it.
        if (!shopLoading) {
          setDashboardError("No active shop selected for the owner dashboard.");
        }
        return;
      }

      const messageText = text.trim();
      const attachmentFiles = getAttachmentFiles(attachments);

      if (!messageText && attachmentFiles.length === 0) {
        return;
      }

      setDashboardError(null);
      const shouldRequestAssistantResponse = Boolean(messageText);
      const assistantMessageId = shouldRequestAssistantResponse ? toId("msg_assistant") : null;

      commitMessages(
        (prev) => [
          ...prev,
          {
            id: toId("msg_user"),
            role: "user",
            content: messageText,
            status: "done",
            timestamp: nowIso(),
            attachments,
          },
          ...(assistantMessageId
            ? [
                {
                  id: assistantMessageId,
                  role: "assistant" as const,
                  content: "",
                  status: "streaming" as const,
                  timestamp: nowIso(),
                  processingStartedAt: nowIso(),
                  retryMessage: messageText,
                  thinkingSteps: [],
                  thinkingComplete: false,
                },
              ]
            : []),
        ],
        Boolean(assistantMessageId),
      );

      addFeedEvent({
        type: "chat",
        title: attachmentFiles.length > 0 && !messageText ? "Documents attached" : "Owner message sent",
        description:
          messageText ||
          `Attached ${attachmentFiles.length} document${attachmentFiles.length === 1 ? "" : "s"} to the conversation.`,
      });

      if (attachmentFiles.length > 0) {
        setIsUploadingDocuments(true);

        try {
          await uploadDocumentsToKnowledgeBase(attachmentFiles);
        } catch (error) {
          const detail = getErrorDetail(error, "Failed to upload documents");
          setDashboardError(detail);
          addFeedEvent({
            type: "error",
            title: "Document upload failed",
            description: detail,
          });

          if (assistantMessageId) {
            setMessages((prev) =>
              prev.map((message) =>
                message.id === assistantMessageId
                  ? {
                      ...message,
                      content: detail,
                      status: "error",
                      thinkingComplete: true,
                    }
                  : message,
              ),
            );
          }

          return;
        } finally {
          setIsUploadingDocuments(false);
        }
      }

      if (!assistantMessageId) {
        return;
      }

      setIsStreaming(true);

      // Create a fresh AbortController for this stream.  Any previous stream
      // (e.g. rapid send) is cancelled first.
      if (activeStreamAbortRef.current) {
        activeStreamAbortRef.current.abort();
      }
      const abortController = new AbortController();
      activeStreamAbortRef.current = abortController;

      let streamEndedWithDone = false;
      let streamTerminalStatus: "completed" | "error" | null = null;
      let streamErrorDetail: string | null = null;
        let sawRenderableAssistantContent = false;

        try {
        const response = await fetch(`${apiBaseUrl}/v2/agent/chat/stream`, {
          method: "POST",
          signal: abortController.signal,
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
          commitMessages(
            (prev) => prev.map((msg) => (msg.id === assistantMessageId ? updater(msg) : msg)),
            true,
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
            // Inject a standalone approval card message into chat
            commitMessages(
              (prev) => {
                const alreadyExists = prev.some(
                  (m) => m.pendingAction?.action_id && m.pendingAction.action_id === approval.action_id,
                );
                if (alreadyExists) return prev;
                return [
                  ...prev,
                  {
                    id: toId("msg_approval"),
                    role: "assistant" as const,
                    content: "",
                    status: "done" as const,
                    timestamp: nowIso(),
                    pendingAction: approval,
                    thinkingComplete: true,
                  },
                ];
              },
              true,
            );
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
        // An AbortError means the component unmounted or the user navigated
        // away — not a real failure.  The partial state has already been
        // persisted to sessionStorage by the save effect; just mark done.
        if (error instanceof DOMException && error.name === "AbortError") {
          commitMessages(
            (prev) =>
              prev.map((msg) =>
                msg.id === assistantMessageId
                  ? {
                      ...msg,
                      status: "done",
                      thinkingComplete: true,
                      processingDuration: msg.processingStartedAt
                        ? Date.now() - Date.parse(msg.processingStartedAt)
                        : undefined,
                    }
                  : msg
              ),
            false,
          );
          setIsStreaming(false);
          return;
        }
        const detail = normalizeStreamErrorDetail(error, STREAM_RETRY_MESSAGE);
        streamTerminalStatus = "error";
        streamErrorDetail = streamErrorDetail || detail;
        setDashboardError(detail);
        addFeedEvent({
          type: "error",
          title: "Chat stream failed",
          description: detail,
        });
        commitMessages(
          (prev) => prev.map((msg) => (msg.id === assistantMessageId ? { ...msg, status: "error" } : msg)),
          false,
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

        commitMessages(
          (prev) => {
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
                      processingDuration: msg.processingStartedAt
                        ? Date.now() - Date.parse(msg.processingStartedAt)
                        : undefined,
                    }
                  : msg
              );
            }

            return prev.map((msg) =>
              msg.id === assistantMessageId
                ? {
                    ...msg,
                    status: streamEndedWithDone || streamTerminalStatus === "completed" ? "done" : msg.status,
                    thinkingComplete: true,
                    processingDuration: msg.processingStartedAt
                      ? Date.now() - Date.parse(msg.processingStartedAt)
                      : undefined,
                  }
                : msg
            );
          },
          false,
        );
        setIsStreaming(false);
      }
    },
    [addFeedEvent, commitMessages, queryClient, shop?.id, token, uploadDocumentsToKnowledgeBase]
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

  const taskBoardTasks = useMemo<AgentTaskBoardExternalTask[]>(() => {
    const tasks = new Map<string, AgentTaskBoardExternalTask>();
    const briefingActions = briefingQuery.data?.actions || [];

    pendingApprovals.forEach((approval, index) => {
      const matchingEvent = approval.action_id
        ? displayedFeedEvents.find((event) => {
            if (event.type !== "approval_required") {
              return false;
            }

            const payload =
              event.payload && typeof event.payload === "object"
                ? (event.payload as Record<string, unknown>)
                : null;

            return payload?.action_id === approval.action_id;
          })
        : undefined;

      const taskId =
        approval.action_id || `approval_task_${shop?.id || "owner"}_${approval.action}_${index}`;

      tasks.set(taskId, {
        id: taskId,
        title: approval.title || formatTaskActionLabel(approval.action),
        description:
          approval.summary ||
          approval.reason ||
          approval.expected_impact ||
          `Action '${formatTaskActionLabel(approval.action)}' is waiting for owner approval.`,
        source: "approval",
        assignee: "Owner",
        createdAt:
          approval.created_at ||
          matchingEvent?.timestamp ||
          briefingQuery.data?.generated_at ||
          FALLBACK_TASK_TIMESTAMP,
        actionId: approval.action_id,
        detailLines: buildApprovalTaskDetails(approval),
      });
    });

    displayedFeedEvents.forEach((event, index) => {
      if (event.type !== "approval_required") {
        return;
      }

      const payload =
        event.payload && typeof event.payload === "object"
          ? (event.payload as Record<string, unknown>)
          : {};
      const actionId = typeof payload.action_id === "string" ? payload.action_id : undefined;
      const taskId = actionId || `feed_task_${event.id || index}`;

      if (tasks.has(taskId)) {
        return;
      }

      tasks.set(taskId, {
        id: taskId,
        title:
          (typeof payload.title === "string" && payload.title.trim()) ||
          event.title ||
          "Approval task",
        description:
          (typeof payload.summary === "string" && payload.summary.trim()) ||
          (typeof payload.expected_impact === "string" && payload.expected_impact.trim()) ||
          (typeof payload.reason === "string" && payload.reason.trim()) ||
          event.description ||
          "Agent approval task",
        source: actionId ? "approval" : "agent",
        assignee: "Owner",
        createdAt:
          (typeof payload.created_at === "string" && payload.created_at.trim()) ||
          event.timestamp ||
          briefingQuery.data?.generated_at ||
          FALLBACK_TASK_TIMESTAMP,
        actionId,
        detailLines: buildApprovalTaskDetails(normalizePendingApproval(payload, shop?.id || 0)),
      });
    });

    briefingActions.forEach((action, index) => {
      const taskId = `briefing_task_${shop?.id || "owner"}_${index}_${action.label
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "_")
        .replace(/^_|_$/g, "")}`;

      if (tasks.has(taskId)) {
        return;
      }

      tasks.set(taskId, {
        id: taskId,
        title: action.label,
        description: action.description || action.payload,
        source: "agent",
        assignee: "Owner",
        createdAt: briefingQuery.data?.generated_at || FALLBACK_TASK_TIMESTAMP,
      });
    });

    return Array.from(tasks.values()).sort(
      (left, right) => new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime(),
    );
  }, [briefingQuery.data?.actions, briefingQuery.data?.generated_at, displayedFeedEvents, pendingApprovals, shop?.id]);

  return (
    <Box
      sx={{
        width: "100%",
        display: "flex",
        flexDirection: "column",
        height: "100%",
        minHeight: 0,
      }}
    >
      <Stack spacing={2} sx={{ flex: 1, minHeight: 0 }}>
        {dashboardError && <Alert severity="error">{dashboardError}</Alert>}

        {!shop?.id && !shopLoading && (
          <Alert severity="warning">
            No active shop selected. Choose a shop from the owner navigation bar before using the dashboard.
          </Alert>
        )}

        <Box
          sx={{
            display: "flex",
            flex: 1,
            minHeight: 0,
          }}
        >
          <AgentChat
            messages={messages}
            isStreaming={isStreaming}
            isUploading={isUploadingDocuments}
            onSend={handleSend}
            onApprovalDecision={handleApprovalDecision}
            isApproving={isApproving}
            title="Hello there!"
            subtitle="How can I help you today?"
            promptSections={contextPromptSections}
            header={
              <Box sx={{ display: "flex", alignItems: "center", width: "100%" }}>
                <Box sx={{ flex: 1, minWidth: 0 }}>
                  <Header />
                </Box>
                <Tooltip title="New chat">
                  <IconButton
                    size="small"
                    onClick={() => setShowNewChatDialog(true)}
                    disabled={isStreaming || messages.length === 0}
                    sx={{ flexShrink: 0, ml: 1 }}
                    aria-label="Start new chat"
                  >
                    <AddCommentOutlinedIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              </Box>
            }
            interactablesStorageKey={shop?.id ? `owner-dashboard-task-board:${shop.id}` : undefined}
            sidebar={
              <AgentTaskBoard
                interactableId={`owner-task-board-${shop?.id || "default"}`}
                externalTasks={taskBoardTasks}
                onApprovalTaskClick={handleApprovalTaskClick}
              />
            }
          />
        </Box>
      </Stack>

      {/* New chat confirmation dialog */}
      <Dialog
        open={showNewChatDialog}
        onClose={() => !isResettingChat && setShowNewChatDialog(false)}
        aria-labelledby="new-chat-dialog-title"
      >
        <DialogTitle id="new-chat-dialog-title">Start a new conversation?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            This will permanently delete your current conversation history. The AI will start
            fresh with no memory of previous messages.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => setShowNewChatDialog(false)}
            disabled={isResettingChat}
          >
            Cancel
          </Button>
          <Button
            onClick={handleNewChatConfirm}
            color="error"
            variant="contained"
            disabled={isResettingChat}
          >
            {isResettingChat ? "Clearing…" : "Clear and start fresh"}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default OwnerDashboardPage;
