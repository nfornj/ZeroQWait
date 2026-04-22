import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  alpha,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Collapse,
  CircularProgress,
  Divider,
  Grid,
  IconButton,
  MenuItem,
  Stack,
  TextField,
  Typography,
  useTheme,
} from "@mui/material";
import ExpandMoreRoundedIcon from "@mui/icons-material/ExpandMoreRounded";
import { useShop } from "../../contexts/ShopContext";
import AgentFeed from "./AgentFeed";
import ApprovalCard from "./ApprovalCard";
import AgentInsights from "./AgentInsights";
import InsightsPanel from "./InsightsPanel";
import OwnerBriefing from "./OwnerBriefing";
import ThinkingSteps, { ThinkingStep } from "./ThinkingSteps";
import MasterAIAgent from "../../landing-page/components/MasterAIAgent";
import {
  buildApprovalOutcomeFeedEvent,
  buildApprovalOutcomeInsight,
  buildStreamToolResultFeedEvent,
  buildStreamToolResultInsight,
} from "./approvalOutcome";
import {
  createWorkspaceFeedSeed,
  createWorkspaceInsightSeed,
  createWorkspaceQuickActions,
} from "./workspaceSeed";
import type {
  ApprovalExecutionResult,
  AgentFeedEvent,
  BriefingAction,
  ChatMessage,
  InsightItem,
  OwnerBriefing as OwnerBriefingData,
  PendingApproval,
  ShopPolicy,
} from "./types";
import api from "../../services/api";

const nowIso = () => new Date().toISOString();

const toId = (prefix: string) => `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;

const buildIntroMessage = (): ChatMessage => ({
  id: toId("msg_intro"),
  role: "assistant",
  content: "Welcome to your Supervisor workspace. I can help with queue status, team scheduling, approvals, and daily performance summaries. What would you like to handle first?",
  status: "done",
  timestamp: nowIso(),
});

const apiBaseUrl = process.env.REACT_APP_API_URL || "/api";

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

const buildWebSocketUrl = (shopId: number): string => {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  return `${protocol}://${window.location.host}/api/ws/${shopId}`;
};

const AgentInbox: React.FC = () => {
  const muiTheme = useTheme();
  const { shop } = useShop();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [feedEvents, setFeedEvents] = useState<AgentFeedEvent[]>([]);
  const [persistedFeedEvents, setPersistedFeedEvents] = useState<AgentFeedEvent[]>([]);
  const [thinkingSteps, setThinkingSteps] = useState<ThinkingStep[]>([]);
  const [pendingApprovals, setPendingApprovals] = useState<PendingApproval[]>([]);
  const [policies, setPolicies] = useState<ShopPolicy[]>([]);
  const [briefing, setBriefing] = useState<OwnerBriefingData | null>(null);
  const [externalActionRequest, setExternalActionRequest] = useState<(BriefingAction & { id: string }) | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isApproving, setIsApproving] = useState(false);
  const [insightsOpen, setInsightsOpen] = useState(false);
  const [streamedInsightItems, setStreamedInsightItems] = useState<InsightItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [savingPolicyKey, setSavingPolicyKey] = useState<string | null>(null);
  const [markingNotificationId, setMarkingNotificationId] = useState<number | null>(null);
  const [isMarkingAllRead, setIsMarkingAllRead] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const previousShopIdRef = useRef<number | null>(null);

  const addFeedEvent = useCallback((event: Omit<AgentFeedEvent, "id" | "timestamp">) => {
    setFeedEvents((prev) => [
      {
        id: toId("feed"),
        timestamp: nowIso(),
        ...event,
      },
      ...prev,
    ]);
  }, []);

  const refreshPendingApprovals = useCallback(async () => {
    if (!shop?.id) return;
    try {
      const response = await api.get<{ pending: PendingApproval[] }>(`/v2/agent/pending`, {
        params: { shop_id: shop.id },
      });
      setPendingApprovals(response.data.pending || []);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to load pending approvals");
    }
  }, [shop?.id]);

  const refreshBriefing = useCallback(async () => {
    if (!shop?.id) return;
    try {
      const response = await api.get<OwnerBriefingData>(`/v2/agent/briefing`, {
        params: { shop_id: shop.id },
      });
      setBriefing(response.data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to load owner briefing");
    }
  }, [shop?.id]);

  const refreshFeed = useCallback(async () => {
    if (!shop?.id) return;
    try {
      const response = await api.get<{ events: AgentFeedEvent[] }>(`/v2/agent/feed`, {
        params: { shop_id: shop.id },
      });
      setPersistedFeedEvents(response.data.events || []);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to load notification feed");
    }
  }, [shop?.id]);

  const refreshPolicies = useCallback(async () => {
    if (!shop?.id) return;
    try {
      const response = await api.get<{ policies: ShopPolicy[] }>(`/v2/agent/policies`, {
        params: { shop_id: shop.id },
      });
      setPolicies(response.data.policies || []);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to load approval policies");
    }
  }, [shop?.id]);

  useEffect(() => {
    if (!shop?.id) return;
    refreshPendingApprovals();
    refreshBriefing();
    refreshFeed();
    refreshPolicies();
  }, [shop?.id, refreshPendingApprovals, refreshBriefing, refreshFeed, refreshPolicies]);

  useEffect(() => {
    if (!shop?.id) return;

    const shopChanged = previousShopIdRef.current !== null && previousShopIdRef.current !== shop.id;
    previousShopIdRef.current = shop.id;

    if (shopChanged) {
      setMessages([buildIntroMessage()]);
      setFeedEvents([]);
      setPersistedFeedEvents([]);
      setPendingApprovals([]);
      setPolicies([]);
      setBriefing(null);
      setStreamedInsightItems([]);
      setThinkingSteps([]);
      setError(null);
      return;
    }

    setMessages((prev) => {
      if (prev.length > 0) return prev;
      return [buildIntroMessage()];
    });
  }, [shop?.id]);

  const handlePolicyModeChange = useCallback(
    async (policy: ShopPolicy, nextMode: string) => {
      if (!shop?.id || !policy.policy_key || nextMode === policy.mode) return;

      setError(null);
      setSavingPolicyKey(policy.policy_key);
      try {
        const response = await api.put<{ policy: ShopPolicy }>(
          `/v2/agent/policies/${encodeURIComponent(policy.policy_key)}`,
          {
            shop_id: shop.id,
            mode: nextMode,
          },
        );
        const updatedPolicy = response.data.policy;
        setPolicies((prev) =>
          prev.map((item) => (item.policy_key === updatedPolicy.policy_key ? updatedPolicy : item))
        );
        addFeedEvent({
          type: "system",
          title: "Policy updated",
          description: `${policy.title} is now set to ${labelForPolicyMode(updatedPolicy.mode)}.`,
          payload: updatedPolicy,
        });
      } catch (err: any) {
        const detail = err?.response?.data?.detail || err?.message || "Failed to update approval policy";
        setError(detail);
        addFeedEvent({
          type: "error",
          title: "Policy update failed",
          description: detail,
        });
      } finally {
        setSavingPolicyKey(null);
      }
    },
    [addFeedEvent, shop?.id]
  );

  useEffect(() => {
    if (!shop?.id) return;

    const socket = new WebSocket(buildWebSocketUrl(shop.id));
    wsRef.current = socket;

    socket.onopen = () => {
      connected = true;
      addFeedEvent({
        type: "system",
        title: "Feed connected",
        description: "Real-time shop updates are active.",
      });
    };

    socket.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data);
        const queueSize = Array.isArray(parsed.queue_items) ? parsed.queue_items.length : undefined;
        addFeedEvent({
          type: "queue_update",
          title: "Shop live snapshot",
          description:
            typeof queueSize === "number"
              ? `Current active queue size: ${queueSize}`
              : "Received a real-time queue update.",
          payload: parsed,
        });
      } catch {
        addFeedEvent({
          type: "system",
          title: "WebSocket update",
          description: String(event.data),
        });
      }
    };

    let connected = false;

    socket.onerror = () => {
      // Silently ignore — WS endpoint may not be deployed yet
    };

    socket.onclose = () => {
      if (connected) {
        addFeedEvent({
          type: "system",
          title: "Feed disconnected",
          description: "WebSocket connection closed.",
        });
      }
    };

    return () => {
      socket.close();
      wsRef.current = null;
    };
  }, [shop?.id, addFeedEvent]);

  const handleSend = useCallback(
    async (messageText: string) => {
      if (!shop?.id) {
        setError("No active shop selected for agent inbox");
        return;
      }

      setError(null);
      setIsStreaming(true);
      setThinkingSteps([]);

      const userMessage: ChatMessage = {
        id: toId("msg_user"),
        role: "user",
        content: messageText,
        status: "done",
        timestamp: nowIso(),
      };

      const assistantMessageId = toId("msg_assistant");
      const assistantPlaceholder: ChatMessage = {
        id: assistantMessageId,
        role: "assistant",
        content: "",
        status: "streaming",
        retryMessage: messageText,
        timestamp: nowIso(),
      };

      setMessages((prev) => [...prev, userMessage, assistantPlaceholder]);
      addFeedEvent({
        type: "chat",
        title: "Owner message sent",
        description: messageText,
      });

      let streamEndedWithDone = false;

      try {
        const token = localStorage.getItem("token");
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

        const applyAssistantDelta = (delta: string) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId
                ? {
                    ...msg,
                    content: `${msg.content}${delta}`,
                    status: "streaming",
                  }
                : msg
            )
          );
        };

        const handleEventData = (raw: string) => {
          if (raw === "[DONE]") {
            streamEndedWithDone = true;
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMessageId
                  ? {
                      ...msg,
                      status: "done",
                    }
                  : msg
              )
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
            if (content) applyAssistantDelta(content);
            return;
          }

          if (eventType === "approval_required") {
            const approval = normalizePendingApproval(
              (eventJson.details || eventJson) as Record<string, any>,
              shop.id,
            );

            setPendingApprovals((prev) => {
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
            setThinkingSteps((prev) => {
              const updated = prev.map((s) =>
                s.status === "active" ? { ...s, status: "completed" as const } : s
              );
              return [
                ...updated,
                {
                  id: `tool-${String(eventJson.tool || "unknown")}-${Date.now()}`,
                  label: `Calling ${String(eventJson.tool || "unknown")}...`,
                  status: "active" as const,
                },
              ];
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
            setThinkingSteps((prev) =>
              prev.map((s) =>
                s.label === `Calling ${String(eventJson.tool || "unknown")}...`
                  ? { ...s, status: eventJson.error ? ("error" as const) : ("completed" as const) }
                  : s
              )
            );
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

        await refreshPendingApprovals();
        await refreshBriefing();
      } catch (err: any) {
        const detail = err?.message || "Failed to stream agent response";
        setError(detail);
        addFeedEvent({
          type: "error",
          title: "Chat stream failed",
          description: detail,
        });
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMessageId
              ? {
                  ...msg,
                  status: "error",
                }
              : msg
          )
        );
      } finally {
        setMessages((prev) => {
          const target = prev.find((msg) => msg.id === assistantMessageId);
          if (!target) return prev;

          const contentEmpty = !String(target.content || "").trim();
          if (contentEmpty || !streamEndedWithDone) {
            return prev.map((msg) =>
              msg.id === assistantMessageId
                ? {
                    ...msg,
                    content: contentEmpty
                      ? "Something went wrong — please try again."
                      : msg.content,
                    status: "error",
                  }
                : msg
            );
          }

          return prev.map((msg) =>
            msg.id === assistantMessageId
              ? {
                  ...msg,
                  status: msg.status === "error" ? "error" : "done",
                }
              : msg
          );
        });
        setIsStreaming(false);
      }
    },
    [addFeedEvent, refreshBriefing, refreshPendingApprovals, shop?.id]
  );

  const handleApprovalDecision = useCallback(
    async (approval: PendingApproval, approved: boolean) => {
      if (!shop?.id) return;
      setError(null);
      setIsApproving(true);

      try {
        const payload = {
          shop_id: shop.id,
          action_id: approval.action_id,
          approved,
        };
        const eventTimestamp = nowIso();

        const response = await api.post<{
          message: string;
          status: string;
          agent?: string;
          tool_results?: ApprovalExecutionResult;
        }>(`/v2/agent/approve`, payload);

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
          payload: payload,
        });

        const outcomeEvent = buildApprovalOutcomeFeedEvent(
          approval,
          approved,
          response.data,
          eventTimestamp,
        );
        if (outcomeEvent) {
          addFeedEvent({
            type: outcomeEvent.type,
            title: outcomeEvent.title,
            description: outcomeEvent.description,
            payload: outcomeEvent.payload,
          });
        }

        const outcomeInsight = buildApprovalOutcomeInsight(
          approval,
          approved,
          response.data,
          eventTimestamp,
        );
        if (outcomeInsight) {
          setStreamedInsightItems((prev) => [outcomeInsight, ...prev]);
        }

        await refreshPendingApprovals();
        await refreshBriefing();
        await refreshFeed();
      } catch (err: any) {
        const detail = err?.response?.data?.detail || err?.message || "Failed to submit approval decision";
        setError(detail);
        addFeedEvent({
          type: "error",
          title: "Approval failed",
          description: detail,
        });
      } finally {
        setIsApproving(false);
      }
    },
    [addFeedEvent, refreshBriefing, refreshFeed, refreshPendingApprovals, shop?.id]
  );

  const handleMarkNotificationRead = useCallback(
    async (notificationId: number) => {
      if (!shop?.id) return;
      setError(null);
      setMarkingNotificationId(notificationId);
      try {
        const response = await api.post<{ notification: AgentFeedEvent }>(
          `/v2/agent/notifications/${notificationId}/read`,
          { shop_id: shop.id },
        );
        setPersistedFeedEvents((prev) =>
          prev.map((event) =>
            event.notification_id === notificationId
              ? { ...event, ...response.data.notification }
              : event
          )
        );
      } catch (err: any) {
        setError(err?.response?.data?.detail || "Failed to mark notification as read");
      } finally {
        setMarkingNotificationId(null);
      }
    },
    [shop?.id]
  );

  const handleMarkAllNotificationsRead = useCallback(
    async () => {
      if (!shop?.id) return;
      setError(null);
      setIsMarkingAllRead(true);
      try {
        await api.post(`/v2/agent/notifications/read-all`, { shop_id: shop.id });
        setPersistedFeedEvents((prev) =>
          prev.map((event) =>
            event.notification_id
              ? { ...event, status: "read" }
              : event
          )
        );
      } catch (err: any) {
        setError(err?.response?.data?.detail || "Failed to clear unread notifications");
      } finally {
        setIsMarkingAllRead(false);
      }
    },
    [shop?.id]
  );

  const latestPending = useMemo(() => pendingApprovals.slice(0, 3), [pendingApprovals]);
  const seededFeedEvents = useMemo(
    () => createWorkspaceFeedSeed(briefing, pendingApprovals),
    [briefing, pendingApprovals]
  );
  const displayedFeedEvents = useMemo(() => {
    const merged = [...feedEvents, ...persistedFeedEvents, ...seededFeedEvents];
    const deduped = new Map<string, AgentFeedEvent>();
    merged.forEach((event) => {
      if (!deduped.has(event.id)) {
        deduped.set(event.id, event);
      }
    });
    return Array.from(deduped.values()).sort(
      (left, right) => new Date(right.timestamp).getTime() - new Date(left.timestamp).getTime()
    );
  }, [feedEvents, persistedFeedEvents, seededFeedEvents]);
  const unreadFeedCount = useMemo(
    () => persistedFeedEvents.filter((event) => event.notification_id && event.status === "unread").length,
    [persistedFeedEvents]
  );
  const seededInsightItems = useMemo(
    () => createWorkspaceInsightSeed(briefing, pendingApprovals),
    [briefing, pendingApprovals]
  );
  const insightItems = useMemo(() => {
    const seen = new Set(streamedInsightItems.map((item) => item.id));
    return [...streamedInsightItems, ...seededInsightItems.filter((item) => !seen.has(item.id))];
  }, [streamedInsightItems, seededInsightItems]);
  const brandPrimary = shop?.primary_color || muiTheme.palette.primary.main;
  const brandSecondary = shop?.secondary_color || brandPrimary;
  const panelCardBg =
    muiTheme.palette.mode === "dark"
      ? "rgba(255, 255, 255, 0.05)"
      : alpha("#ffffff", 0.68);
  const panelCardBorder =
    muiTheme.palette.mode === "dark"
      ? alpha(brandPrimary, 0.24)
      : alpha(brandPrimary, 0.16);
  const ownerInitialChatHistory = useMemo(
    () =>
      shop?.name
        ? [
            {
              role: "ai" as const,
              text: briefing?.summary
                ? `Welcome back to ${shop.name}. ${briefing.summary} What would you like to handle first?`
                : `Welcome back to ${shop.name}. I can help with queue status, team scheduling, approvals, and daily performance summaries. What would you like to handle first?`,
              quickActions: createWorkspaceQuickActions(briefing, pendingApprovals, shop.name),
            },
          ]
        : [],
    [briefing, pendingApprovals, shop?.name]
  );

  const handleAgentStreamEvent = useCallback(
    (event: Record<string, any>) => {
      const eventType = String(event.type || "");

      if (eventType === "approval_required") {
        const approval = normalizePendingApproval((event.details || event) as Record<string, any>, shop?.id || 0);
        setPendingApprovals((prev) => {
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
        void refreshPendingApprovals();
        return;
      }

      if (eventType === "agent_switch") {
        addFeedEvent({
          type: "agent_switch",
          title: "Agent switched",
          description: `Supervisor delegated to ${String(event.agent || "sub-agent")}.`,
          payload: event,
        });
        return;
      }

      if (eventType === "tool_call") {
        addFeedEvent({
          type: "tool_call",
          title: `Tool call: ${String(event.tool || "unknown")}`,
          description: "Tool execution started.",
          payload: event,
        });
        setThinkingSteps((prev) => {
          const updated = prev.map((s) =>
            s.status === "active" ? { ...s, status: "completed" as const } : s
          );
          return [
            ...updated,
            {
              id: `tool-${String(event.tool || "unknown")}-${Date.now()}`,
              label: `Calling ${String(event.tool || "unknown")}...`,
              status: "active" as const,
            },
          ];
        });
        return;
      }

      if (eventType === "tool_result") {
        const eventTimestamp = String(event.timestamp || nowIso());
        const outcomeEvent = buildStreamToolResultFeedEvent(
          {
            tool: event.tool,
            result: event.result,
            agent: event.agent,
          },
          eventTimestamp,
        );
        if (outcomeEvent) {
          addFeedEvent({
            type: outcomeEvent.type,
            title: outcomeEvent.title,
            description: outcomeEvent.description,
            payload: outcomeEvent.payload,
          });
        } else {
          addFeedEvent({
            type: "tool_result",
            title: `Tool result: ${String(event.tool || "unknown")}`,
            description: "Tool execution completed.",
            payload: event,
          });
        }

        const outcomeInsight = buildStreamToolResultInsight(
          {
            tool: event.tool,
            result: event.result,
            agent: event.agent,
          },
          eventTimestamp,
        );
        if (outcomeInsight) {
          setStreamedInsightItems((prev) => [outcomeInsight, ...prev]);
        }
        setThinkingSteps((prev) =>
          prev.map((s) =>
            s.label === `Calling ${String(event.tool || "unknown")}...`
              ? { ...s, status: event.error ? ("error" as const) : ("completed" as const) }
              : s
          )
        );
        return;
      }

      // Accumulate charts and files into the right-panel InsightsPanel
      if (eventType === "chart" && event._parsed_chart) {
        const chart = event._parsed_chart;
        setStreamedInsightItems((prev) => [
          { id: chart.id, type: "chart", chart, timestamp: chart.timestamp },
          ...prev,
        ]);
        return;
      }

      if (eventType === "file" && event._parsed_file) {
        const file = event._parsed_file;
        setStreamedInsightItems((prev) => [
          { id: file.id, type: "file", file, timestamp: file.timestamp },
          ...prev,
        ]);
        return;
      }
    },
    [addFeedEvent, refreshPendingApprovals, shop?.id]
  );

  const handleChatHistoryChange = useCallback((history: any[]) => {
    setMessages(
      history.map((item, index) => ({
        id: item.id || `mirrored_${index}`,
        role: item.role === "user" ? "user" : "assistant",
        content: item.text || "",
        status: item.status || "done",
        timestamp: item.timestamp || nowIso(),
      }))
    );
  }, []);

  const handleBriefingAction = useCallback((action: BriefingAction) => {
    setExternalActionRequest({ ...action, id: toId("briefing_action") });
    addFeedEvent({
      type: "chat",
      title: `Action: ${action.label}`,
      description: action.description || action.payload,
      payload: action,
    });
  }, [addFeedEvent]);

  const handleExternalActionHandled = useCallback(() => {
    setExternalActionRequest(null);
  }, []);

  return (
    <Box sx={{ width: "100%", maxWidth: { sm: "100%", md: "1700px" }, height: "calc(100dvh - 64px)", display: "flex", flexDirection: "column" }}>
      <Stack spacing={1} sx={{ flex: 1, minHeight: 0 }}>

        {error && <Alert severity="error">{error}</Alert>}

        {!shop?.id && (
          <Alert severity="warning">
            No active shop selected. Refresh the shop workspace or choose an active shop from the top bar if you manage more than one location.
          </Alert>
        )}

        <Grid container spacing={1.5} sx={{ flex: 1, minHeight: 0 }}>
          <Grid size={{ xs: 12, xl: 7.5 }} sx={{ display: "flex", flexDirection: "column", minHeight: 0 }}>
            {thinkingSteps.length > 0 && (
              <ThinkingSteps
                steps={thinkingSteps}
                isComplete={!isStreaming}
              />
            )}
            {shop?.id && (
              <MasterAIAgent
                key={shop.id}
                forceOpen
                embedded
                hideCloseButton
                hideUtilityControls
                disableVoiceMode
                compactEmbedded
                initialInteractionMode="chat"
                shopContext={{
                  id: shop.id,
                  name: shop.name,
                  slug: shop.slug,
                }}
                brandPrimaryColor={brandPrimary}
                brandSecondaryColor={brandSecondary}
                streamEndpoint="/api/v2/agent/chat/stream"
                requestHeaders={{
                  Authorization: `Bearer ${localStorage.getItem("token") || ""}`,
                }}
                extraRequestBody={{
                  shop_id: shop.id,
                  is_voice: false,
                }}
                externalActionRequest={externalActionRequest}
                onExternalActionHandled={handleExternalActionHandled}
                initialChatHistory={ownerInitialChatHistory}
                embeddedFooter={
                  <Box sx={{ width: "100%" }}>
                    <IconButton
                      size="small"
                      onClick={() => setInsightsOpen((o) => !o)}
                      sx={{
                        color: "#0078d4",
                        p: 0.25,
                      }}
                    >
                      <ExpandMoreRoundedIcon
                        sx={{
                          fontSize: 18,
                          transition: "transform 0.18s",
                          transform: insightsOpen ? "rotate(180deg)" : "rotate(0deg)",
                        }}
                      />
                    </IconButton>
                    <Collapse in={insightsOpen} unmountOnExit>
                      <Box mt={0.75}>
                        <AgentInsights
                          messages={messages}
                          events={displayedFeedEvents}
                          pendingApprovals={pendingApprovals}
                        />
                      </Box>
                    </Collapse>
                  </Box>
                }
                onStreamEvent={handleAgentStreamEvent}
                onChatHistoryChange={handleChatHistoryChange}
              />
            )}
          </Grid>
          <Grid size={{ xs: 12, xl: 4.5 }}>
            <Stack spacing={1.5}>
              <OwnerBriefing briefing={briefing} onAction={handleBriefingAction} />
              {shop?.id && (
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
                      <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={1}>
                        <Box>
                          <Typography variant="h6">Approval Policies</Typography>
                          <Typography variant="body2" color="text.secondary">
                            Choose what the agent team can run automatically for this shop.
                          </Typography>
                        </Box>
                        {savingPolicyKey ? (
                          <CircularProgress size={18} />
                        ) : (
                          <Chip
                            size="small"
                            label={`${policies.length} actions`}
                            sx={{
                              bgcolor: alpha(brandPrimary, 0.14),
                              color: brandPrimary,
                              border: `1px solid ${alpha(brandPrimary, 0.22)}`,
                              fontWeight: 700,
                            }}
                          />
                        )}
                      </Stack>
                      <Divider sx={{ borderColor: alpha(brandPrimary, 0.12) }} />
                      {policies.length === 0 ? (
                        <Stack spacing={1}>
                          <Typography variant="body2" color="text.secondary">
                            No approval policies are available for this shop yet.
                          </Typography>
                          <Button size="small" onClick={() => void refreshPolicies()} sx={{ alignSelf: "flex-start" }}>
                            Retry
                          </Button>
                        </Stack>
                      ) : (
                        policies.map((policy) => {
                          const isSaving = savingPolicyKey === policy.policy_key;
                          return (
                            <Box
                              key={policy.policy_key}
                              sx={{
                                p: 1.25,
                                borderRadius: 2.5,
                                border: `1px solid ${alpha(brandPrimary, 0.12)}`,
                                bgcolor: alpha(brandPrimary, 0.04),
                              }}
                            >
                              <Stack spacing={1}>
                                <Stack
                                  direction={{ xs: "column", md: "row" }}
                                  justifyContent="space-between"
                                  spacing={1}
                                >
                                  <Box sx={{ minWidth: 0 }}>
                                    <Typography variant="subtitle2" sx={{ color: brandPrimary }}>
                                      {policy.title}
                                    </Typography>
                                    <Stack direction="row" spacing={0.75} useFlexGap flexWrap="wrap" mt={0.5}>
                                      <Chip size="small" variant="outlined" label={policy.category} />
                                      <Chip size="small" variant="outlined" label={`${policy.risk_level || "medium"} risk`} />
                                      <Chip
                                        size="small"
                                        variant="outlined"
                                        label={policy.explicit ? "Custom mode" : `Default: ${labelForPolicyMode(policy.default_mode)}`}
                                      />
                                    </Stack>
                                  </Box>
                                  <TextField
                                    select
                                    size="small"
                                    label="Mode"
                                    value={policy.mode}
                                    disabled={isSaving}
                                    onChange={(event) => void handlePolicyModeChange(policy, event.target.value)}
                                    sx={{ minWidth: { xs: "100%", md: 220 } }}
                                  >
                                    {(policy.supported_modes || []).map((mode) => (
                                      <MenuItem key={mode} value={mode}>
                                        {labelForPolicyMode(mode)}
                                      </MenuItem>
                                    ))}
                                  </TextField>
                                </Stack>
                                <Typography variant="caption" color="text.secondary">
                                  Current mode: {labelForPolicyMode(policy.mode)}
                                  {isSaving ? " · Saving..." : ""}
                                </Typography>
                              </Stack>
                            </Box>
                          );
                        })
                      )}
                    </Stack>
                  </CardContent>
                </Card>
              )}
              <InsightsPanel items={insightItems} />
              {latestPending.length > 0 && (
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
                    <Stack spacing={1}>
                      <Stack direction="row" justifyContent="space-between" alignItems="center">
                        <Typography variant="h6">Pending Approvals</Typography>
                        <Chip
                          size="small"
                          label={latestPending.length}
                          sx={{
                            bgcolor: alpha(brandPrimary, 0.14),
                            color: brandPrimary,
                            border: `1px solid ${alpha(brandPrimary, 0.22)}`,
                            fontWeight: 700,
                          }}
                        />
                      </Stack>
                      <Divider sx={{ borderColor: alpha(brandPrimary, 0.12) }} />
                      {latestPending.map((approval) => (
                        <ApprovalCard
                          key={approval.action_id || `${approval.action}_${approval.shop_id}`}
                          approval={approval}
                          isSubmitting={isApproving}
                          onDecision={handleApprovalDecision}
                        />
                      ))}
                    </Stack>
                  </CardContent>
                </Card>
              )}
              <AgentFeed
                events={displayedFeedEvents}
                unreadCount={unreadFeedCount}
                isMarkingAllRead={isMarkingAllRead}
                markingNotificationId={markingNotificationId}
                onMarkAsRead={handleMarkNotificationRead}
                onMarkAllAsRead={handleMarkAllNotificationsRead}
              />
            </Stack>
          </Grid>
        </Grid>
      </Stack>
    </Box>
  );
};

export default AgentInbox;
