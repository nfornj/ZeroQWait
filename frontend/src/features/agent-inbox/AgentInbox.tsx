import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import axios from "axios";
import {
  Alert,
  alpha,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Divider,
  FormControl,
  Grid,
  InputLabel,
  MenuItem,
  Select,
  SelectChangeEvent,
  Stack,
  Tooltip,
  Typography,
  useTheme,
} from "@mui/material";
import AutorenewRoundedIcon from "@mui/icons-material/AutorenewRounded";
import { useShop } from "../../contexts/ShopContext";
import AgentFeed from "./AgentFeed";
import ApprovalCard from "./ApprovalCard";
import AgentInsights from "./AgentInsights";
import ThinkingSteps, { ThinkingStep } from "./ThinkingSteps";
import MasterAIAgent from "../../landing-page/components/MasterAIAgent";
import type { AgentFeedEvent, ChatMessage, PendingApproval } from "./types";

type ShopSummary = {
  id: number;
  name: string;
  slug?: string;
  primary_color?: string;
  secondary_color?: string;
};

const nowIso = () => new Date().toISOString();

const toId = (prefix: string) => `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;

const buildIntroMessage = (shopName?: string): ChatMessage => ({
  id: toId("msg_intro"),
  role: "assistant",
  content: shopName
    ? `Welcome back to ${shopName}. I can help with queue status, team scheduling, approvals, and daily performance summaries. What would you like to handle first?`
    : "Welcome to your Supervisor workspace. I can help with queue status, team scheduling, approvals, and daily performance summaries.",
  timestamp: nowIso(),
});

const apiBaseUrl = process.env.REACT_APP_API_URL || "/api";

const buildWebSocketUrl = (shopId: number): string => {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  return `${protocol}://${window.location.host}/api/ws/${shopId}`;
};

const AgentInbox: React.FC = () => {
  const muiTheme = useTheme();
  const { shop, setShop } = useShop();
  const [ownedShops, setOwnedShops] = useState<ShopSummary[]>([]);
  const [shopsLoading, setShopsLoading] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [feedEvents, setFeedEvents] = useState<AgentFeedEvent[]>([]);
  const [thinkingSteps, setThinkingSteps] = useState<ThinkingStep[]>([]);
  const [pendingApprovals, setPendingApprovals] = useState<PendingApproval[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isApproving, setIsApproving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

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

  const refreshOwnedShops = useCallback(async () => {
    setShopsLoading(true);
    try {
      const response = await axios.get<ShopSummary[]>("/shops/my-shops");
      const shops = response.data || [];
      setOwnedShops(shops);

      if (!shop?.id && shops.length > 0) {
        const firstShop = shops[0];
        setShop({
          id: firstShop.id,
          name: firstShop.name,
          slug: firstShop.slug || "",
          primary_color: firstShop.primary_color,
          secondary_color: firstShop.secondary_color,
        });
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to load your shops");
    } finally {
      setShopsLoading(false);
    }
  }, [setShop, shop?.id]);

  const refreshPendingApprovals = useCallback(async () => {
    if (!shop?.id) return;
    try {
      const response = await axios.get<{ pending: PendingApproval[] }>(`/v2/agent/pending`, {
        params: { shop_id: shop.id },
      });
      setPendingApprovals(response.data.pending || []);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to load pending approvals");
    }
  }, [shop?.id]);

  useEffect(() => {
    refreshOwnedShops();
  }, [refreshOwnedShops]);

  useEffect(() => {
    if (!shop?.id) return;
    refreshPendingApprovals();
  }, [shop?.id, refreshPendingApprovals]);

  const handleShopSelection = useCallback(
    (event: SelectChangeEvent<string>) => {
      const nextShopId = Number(event.target.value);
      const selected = ownedShops.find((s) => s.id === nextShopId);
      if (!selected) return;

      setShop({
        id: selected.id,
        name: selected.name,
        slug: selected.slug || "",
        primary_color: selected.primary_color,
        secondary_color: selected.secondary_color,
      });
      setMessages([buildIntroMessage(selected.name)]);
      setFeedEvents([]);
      setPendingApprovals([]);
      setError(null);
    },
    [ownedShops, setShop]
  );

  useEffect(() => {
    if (!shop?.id) return;
    setMessages((prev) => {
      if (prev.length > 0) return prev;
      return [buildIntroMessage(shop.name)];
    });
  }, [shop?.id, shop?.name]);

  useEffect(() => {
    if (!shop?.id) return;

    const socket = new WebSocket(buildWebSocketUrl(shop.id));
    wsRef.current = socket;

    socket.onopen = () => {
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

    socket.onerror = () => {
      addFeedEvent({
        type: "error",
        title: "Feed connection issue",
        description: "Unable to maintain WebSocket connection for live feed updates.",
      });
    };

    socket.onclose = () => {
      addFeedEvent({
        type: "system",
        title: "Feed disconnected",
        description: "WebSocket connection closed.",
      });
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
        timestamp: nowIso(),
      };

      const assistantMessageId = toId("msg_assistant");
      const assistantPlaceholder: ChatMessage = {
        id: assistantMessageId,
        role: "assistant",
        content: "",
        timestamp: nowIso(),
      };

      setMessages((prev) => [...prev, userMessage, assistantPlaceholder]);
      addFeedEvent({
        type: "chat",
        title: "Owner message sent",
        description: messageText,
      });

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
                  }
                : msg
            )
          );
        };

        const handleEventData = (raw: string) => {
          if (raw === "[DONE]") return;

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
            const approval: PendingApproval = {
              action_id: eventJson.details?.action_id,
              action: String(eventJson.action || eventJson.details?.action || "pending_action"),
              details: (eventJson.details?.details || eventJson.details || {}) as Record<string, unknown>,
              shop_id: Number(eventJson.details?.shop_id || shop.id),
            };

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
      } catch (err: any) {
        const detail = err?.message || "Failed to stream agent response";
        setError(detail);
        addFeedEvent({
          type: "error",
          title: "Chat stream failed",
          description: detail,
        });
      } finally {
        setIsStreaming(false);
      }
    },
    [addFeedEvent, refreshPendingApprovals, shop?.id]
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

        const response = await axios.post<{
          message: string;
          status: string;
          agent?: string;
        }>(`/v2/agent/approve`, payload);

        setMessages((prev) => [
          ...prev,
          {
            id: toId("msg_system"),
            role: "system",
            content: response.data.message || `Action ${approved ? "approved" : "rejected"}.`,
            timestamp: nowIso(),
            agent: response.data.agent,
          },
        ]);

        addFeedEvent({
          type: "approval_decision",
          title: approved ? "Action approved" : "Action rejected",
          description: `You ${approved ? "approved" : "rejected"} '${approval.action}'.`,
          payload: payload,
        });

        await refreshPendingApprovals();
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
    [addFeedEvent, refreshPendingApprovals, shop?.id]
  );

  const latestPending = useMemo(() => pendingApprovals.slice(0, 3), [pendingApprovals]);
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
              text: `Welcome back to ${shop.name}. I can help with queue status, team scheduling, approvals, and daily performance summaries. What would you like to handle first?`,
              quickActions: [
                { label: "Give me today's queue summary", payload: "Give me today's queue summary" },
                { label: "Show this week's revenue trend", payload: "Show this week's revenue trend" },
                { label: "Who is on shift now?", payload: "Who is on shift now?" },
              ],
            },
          ]
        : [],
    [shop?.name]
  );

  const handleAgentStreamEvent = useCallback(
    (event: Record<string, any>) => {
      const eventType = String(event.type || "");

      if (eventType === "approval_required") {
        addFeedEvent({
          type: "approval_required",
          title: "Approval required",
          description: `Action '${String(event.action || event.details?.action || "pending_action")}' is waiting for your decision.`,
          payload: event,
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
        addFeedEvent({
          type: "tool_result",
          title: `Tool result: ${String(event.tool || "unknown")}`,
          description: "Tool execution completed.",
          payload: event,
        });
        setThinkingSteps((prev) =>
          prev.map((s) =>
            s.label === `Calling ${String(event.tool || "unknown")}...`
              ? { ...s, status: event.error ? ("error" as const) : ("completed" as const) }
              : s
          )
        );
      }
    },
    [addFeedEvent, refreshPendingApprovals]
  );

  const handleChatHistoryChange = useCallback((history: any[]) => {
    setMessages(
      history.map((item, index) => ({
        id: item.id || `mirrored_${index}`,
        role: item.role === "user" ? "user" : "assistant",
        content: item.text || "",
        timestamp: item.timestamp || nowIso(),
      }))
    );
  }, []);

  return (
    <Box sx={{ width: "100%", maxWidth: { sm: "100%", md: "1700px" } }}>
      <Stack spacing={1}>

        {error && <Alert severity="error">{error}</Alert>}

        <Card variant="outlined" sx={{ borderRadius: 3, borderColor: panelCardBorder, bgcolor: panelCardBg, backdropFilter: 'blur(18px)' }}>
          <CardContent sx={{ py: 1.5 }}>
            <Stack direction={{ xs: "column", md: "row" }} spacing={1} alignItems={{ xs: "stretch", md: "center" }} justifyContent="space-between">
              <Stack>
                <Typography variant="subtitle2">Active Shop Context</Typography>
                <Typography variant="body2" color="text.secondary">
                  Pick which business the supervisor should operate on.
                </Typography>
              </Stack>

              <Stack direction="row" spacing={1} alignItems="center" sx={{ minWidth: { xs: "100%", md: 420 } }}>
                <FormControl size="small" fullWidth>
                  <InputLabel id="agent-shop-select-label">Shop</InputLabel>
                  <Select
                    labelId="agent-shop-select-label"
                    label="Shop"
                    value={shop?.id ? String(shop.id) : ""}
                    onChange={handleShopSelection}
                    displayEmpty
                  >
                    {ownedShops.length === 0 && <MenuItem value="" disabled>No shops found</MenuItem>}
                    {ownedShops.map((ownedShop) => (
                      <MenuItem key={ownedShop.id} value={String(ownedShop.id)}>
                        {ownedShop.name}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>

                <Tooltip title="Reload shops">
                  <span>
                    <Button
                      variant="outlined"
                      onClick={refreshOwnedShops}
                      disabled={shopsLoading}
                      startIcon={<AutorenewRoundedIcon />}
                    >
                      Refresh
                    </Button>
                  </span>
                </Tooltip>
              </Stack>
            </Stack>
          </CardContent>
        </Card>

        {!shop?.id && (
          <Alert severity="warning">
            No active shop selected. Select a shop from the context card above to start the agent session.
          </Alert>
        )}

        <Grid container spacing={1.5}>
          <Grid size={{ xs: 12, xl: 7.5 }}>
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
                initialChatHistory={ownerInitialChatHistory}
                onStreamEvent={handleAgentStreamEvent}
                onChatHistoryChange={handleChatHistoryChange}
              />
            )}
          </Grid>
          <Grid size={{ xs: 12, xl: 4.5 }}>
            <Stack spacing={1.5}>
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
              <AgentInsights messages={messages} events={feedEvents} pendingApprovals={pendingApprovals} />
              <AgentFeed events={feedEvents} />
            </Stack>
          </Grid>
        </Grid>
      </Stack>
    </Box>
  );
};

export default AgentInbox;
