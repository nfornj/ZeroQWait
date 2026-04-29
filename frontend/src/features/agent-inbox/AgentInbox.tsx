import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  Box,
  Collapse,
  Grid,
  IconButton,
  Stack,
} from "@mui/material";
import ExpandMoreRoundedIcon from "@mui/icons-material/ExpandMoreRounded";
import { useQueryClient } from "@tanstack/react-query";

import { useAuth } from "../../contexts/AuthContext";
import { useShop } from "../../contexts/ShopContext";
import MasterAIAgent from "../../landing-page/components/MasterAIAgent";
import api from "../../services/api";
import AgentFeed from "./AgentFeed";
import AgentInsights from "./AgentInsights";
import InsightsPanel from "./InsightsPanel";
import OwnerBriefing from "./OwnerBriefing";
import PendingApprovalsPanel from "./PendingApprovalsPanel";
import PoliciesPanel from "./PoliciesPanel";
import ThinkingSteps from "./ThinkingSteps";
import { buildIntroMessage, toId } from "./agentInboxShared";
import { useApprovalDecisions } from "./hooks/useApprovalDecisions";
import { useAgentStream } from "./hooks/useAgentStream";
import { useAgentWebSocket } from "./hooks/useAgentWebSocket";
import {
  ownerDashboardKeys,
  useOwnerBriefingQuery,
  useOwnerFeedQuery,
  useOwnerPoliciesQuery,
  usePendingApprovalsQuery,
} from "./ownerDashboardQueries";
import type {
  AgentFeedEvent,
  BriefingAction,
  InsightItem,
  OwnerBriefing as OwnerBriefingData,
  PendingApproval,
  ShopPolicy,
} from "./types";
import {
  createWorkspaceFeedSeed,
  createWorkspaceInsightSeed,
  createWorkspaceQuickActions,
} from "./workspaceSeed";

const AgentInbox: React.FC = () => {
  const queryClient = useQueryClient();
  const { shop } = useShop();
  const { token } = useAuth();
  const [persistedFeedEvents, setPersistedFeedEvents] = useState<AgentFeedEvent[]>([]);
  const [pendingApprovals, setPendingApprovals] = useState<PendingApproval[]>([]);
  const [policies, setPolicies] = useState<ShopPolicy[]>([]);
  const [briefing, setBriefing] = useState<OwnerBriefingData | null>(null);
  const [externalActionRequest, setExternalActionRequest] = useState<(BriefingAction & { id: string }) | null>(null);
  const [insightsOpen, setInsightsOpen] = useState(false);
  const [streamedInsightItems, setStreamedInsightItems] = useState<InsightItem[]>([]);
  const [savingPolicyKey, setSavingPolicyKey] = useState<string | null>(null);
  const [markingNotificationId, setMarkingNotificationId] = useState<number | null>(null);
  const [isMarkingAllRead, setIsMarkingAllRead] = useState(false);
  const previousShopIdRef = useRef<number | null>(null);

  const pendingApprovalsQuery = usePendingApprovalsQuery(shop?.id);
  const briefingQuery = useOwnerBriefingQuery(shop?.id);
  const feedQuery = useOwnerFeedQuery(shop?.id);
  const policiesQuery = useOwnerPoliciesQuery(shop?.id);

  const addPendingApproval = useCallback((approval: PendingApproval) => {
    setPendingApprovals((prev) => {
      const exists = prev.some((item) => item.action_id && item.action_id === approval.action_id);
      if (exists) return prev;
      return [approval, ...prev];
    });
  }, []);

  const prependInsightItem = useCallback((item: InsightItem) => {
    setStreamedInsightItems((prev) => [item, ...prev]);
  }, []);

  const { feedEvents, addFeedEvent } = useAgentWebSocket(shop?.id);

  const refreshPendingApprovals = useCallback(async () => {
    if (!shop?.id) return;
    await queryClient.invalidateQueries({ queryKey: ownerDashboardKeys.pending(shop.id) });
  }, [queryClient, shop?.id]);

  const refreshBriefing = useCallback(async () => {
    if (!shop?.id) return;
    await queryClient.invalidateQueries({ queryKey: ownerDashboardKeys.briefing(shop.id) });
  }, [queryClient, shop?.id]);

  const refreshFeed = useCallback(async () => {
    if (!shop?.id) return;
    await queryClient.invalidateQueries({ queryKey: ownerDashboardKeys.feed(shop.id) });
  }, [queryClient, shop?.id]);

  const refreshPolicies = useCallback(async () => {
    if (!shop?.id) return;
    await queryClient.invalidateQueries({ queryKey: ownerDashboardKeys.policies(shop.id) });
  }, [queryClient, shop?.id]);

  const {
    messages,
    setMessages,
    isStreaming,
    thinkingSteps,
    error,
    setError,
    appendSystemMessage,
    handleStreamEvent,
    handleChatHistoryChange,
  } = useAgentStream({
    shopId: shop?.id,
    addFeedEvent,
    addPendingApproval,
    prependInsightItem,
    refreshPendingApprovals,
    refreshBriefing,
  });

  const { handleApprovalDecision, isApproving } = useApprovalDecisions({
    shopId: shop?.id,
    addFeedEvent,
    appendSystemMessage,
    prependInsightItem,
    refreshPendingApprovals,
    refreshBriefing,
    refreshFeed,
    setError,
  });

  useEffect(() => {
    setPendingApprovals(pendingApprovalsQuery.data || []);
  }, [pendingApprovalsQuery.data]);

  useEffect(() => {
    setBriefing(briefingQuery.data || null);
  }, [briefingQuery.data]);

  useEffect(() => {
    setPersistedFeedEvents(feedQuery.data || []);
  }, [feedQuery.data]);

  useEffect(() => {
    setPolicies(policiesQuery.data || []);
  }, [policiesQuery.data]);

  useEffect(() => {
    const queryError = pendingApprovalsQuery.error || briefingQuery.error || feedQuery.error || policiesQuery.error;
    if (!queryError) return;

    const detail =
      (queryError as any)?.response?.data?.detail ||
      (queryError as Error)?.message ||
      "Failed to load owner workspace data";
    setError(detail);
  }, [briefingQuery.error, feedQuery.error, pendingApprovalsQuery.error, policiesQuery.error, setError]);

  useEffect(() => {
    if (!shop?.id) return;

    const shopChanged = previousShopIdRef.current !== null && previousShopIdRef.current !== shop.id;
    previousShopIdRef.current = shop.id;

    if (shopChanged) {
      setMessages([buildIntroMessage()]);
      setPersistedFeedEvents([]);
      setPendingApprovals([]);
      setPolicies([]);
      setBriefing(null);
      setStreamedInsightItems([]);
      setError(null);
      return;
    }

    setMessages((prev) => (prev.length > 0 ? prev : [buildIntroMessage()]));
  }, [setError, setMessages, shop?.id]);

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
          prev.map((item) => (item.policy_key === updatedPolicy.policy_key ? updatedPolicy : item)),
        );
        addFeedEvent({
          type: "system",
          title: "Policy updated",
          description: `${policy.title} is now set to ${updatedPolicy.mode.replace(/_/g, " ")}.`,
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
    [addFeedEvent, setError, shop?.id],
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
            event.notification_id === notificationId ? { ...event, ...response.data.notification } : event,
          ),
        );
      } catch (err: any) {
        setError(err?.response?.data?.detail || "Failed to mark notification as read");
      } finally {
        setMarkingNotificationId(null);
      }
    },
    [setError, shop?.id],
  );

  const handleMarkAllNotificationsRead = useCallback(async () => {
    if (!shop?.id) return;
    setError(null);
    setIsMarkingAllRead(true);
    try {
      await api.post(`/v2/agent/notifications/read-all`, { shop_id: shop.id });
      setPersistedFeedEvents((prev) =>
        prev.map((event) => (event.notification_id ? { ...event, status: "read" } : event)),
      );
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to clear unread notifications");
    } finally {
      setIsMarkingAllRead(false);
    }
  }, [setError, shop?.id]);

  const latestPending = useMemo(() => pendingApprovals.slice(0, 3), [pendingApprovals]);
  const seededFeedEvents = useMemo(
    () => createWorkspaceFeedSeed(briefing, pendingApprovals),
    [briefing, pendingApprovals],
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
      (left, right) => new Date(right.timestamp).getTime() - new Date(left.timestamp).getTime(),
    );
  }, [feedEvents, persistedFeedEvents, seededFeedEvents]);

  const unreadFeedCount = useMemo(
    () => persistedFeedEvents.filter((event) => event.notification_id && event.status === "unread").length,
    [persistedFeedEvents],
  );

  const seededInsightItems = useMemo(
    () => createWorkspaceInsightSeed(briefing, pendingApprovals),
    [briefing, pendingApprovals],
  );

  const insightItems = useMemo(() => {
    const seen = new Set(streamedInsightItems.map((item) => item.id));
    return [...streamedInsightItems, ...seededInsightItems.filter((item) => !seen.has(item.id))];
  }, [streamedInsightItems, seededInsightItems]);

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
    [briefing, pendingApprovals, shop?.name],
  );

  const handleBriefingAction = useCallback(
    (action: BriefingAction) => {
      setExternalActionRequest({ ...action, id: toId("briefing_action") });
      addFeedEvent({
        type: "chat",
        title: `Action: ${action.label}`,
        description: action.description || action.payload,
        payload: action,
      });
    },
    [addFeedEvent],
  );

  const handleExternalActionHandled = useCallback(() => {
    setExternalActionRequest(null);
  }, []);

  const ownerAgentRequestHeaders = useMemo(
    () => (token ? { Authorization: `Bearer ${token}` } : undefined),
    [token],
  );

  return (
    <Box
      sx={{
        width: "100%",
        maxWidth: { xs: "100%", md: "1800px" },
        mx: "auto",
        height: "calc(100dvh - var(--navbar-h, 57px))",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <Box sx={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0, gap: 0 }}>
        {error && <Alert severity="error">{error}</Alert>}

        {!shop?.id && (
          <Alert severity="warning">
            No active shop selected. Refresh the shop workspace or choose an active shop from the top bar if you manage more than one location.
          </Alert>
        )}

        <Grid
          container
          spacing={1.5}
          sx={{
            flex: 1,
            minHeight: 0,
            height: "100%",
            alignItems: { md: "stretch" },
            overflow: { md: "hidden" },
          }}
        >
          <Grid
            size={{ xs: 12, md: 7.25 }}
            sx={{
              display: "flex",
              flexDirection: "column",
              minHeight: 0,
              height: { md: "100%" },
            }}
          >
            {thinkingSteps.length > 0 && <ThinkingSteps steps={thinkingSteps} isComplete={!isStreaming} />}
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
                brandPrimaryColor={shop.primary_color || undefined}
                brandSecondaryColor={shop.secondary_color || shop.primary_color || undefined}
                streamEndpoint="/api/v2/agent/chat/stream"
                requestHeaders={ownerAgentRequestHeaders}
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
                      onClick={() => setInsightsOpen((open) => !open)}
                      sx={{ color: "#0078d4", p: 0.25 }}
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
                onStreamEvent={handleStreamEvent}
                onChatHistoryChange={handleChatHistoryChange}
              />
            )}
          </Grid>

          <Grid
            size={{ xs: 12, md: 4.75 }}
            sx={{
              display: "flex",
              minHeight: 0,
              height: { md: "100%" },
            }}
          >
            <Stack spacing={1.25} sx={{ flex: 1, minHeight: 0, height: { md: "100%" } }}>
              <OwnerBriefing briefing={briefing} onAction={handleBriefingAction} />
              <Box
                sx={{
                  flex: 1,
                  minHeight: 0,
                  overflowY: { xs: "visible", md: "auto" },
                  pr: { md: 0.5 },
                  display: "flex",
                  flexDirection: "column",
                  gap: 1.25,
                }}
              >
                {latestPending.length > 0 && (
                  <PendingApprovalsPanel
                    approvals={pendingApprovals}
                    isApproving={isApproving}
                    onDecision={handleApprovalDecision}
                  />
                )}

                <AgentFeed
                  events={displayedFeedEvents}
                  unreadCount={unreadFeedCount}
                  isMarkingAllRead={isMarkingAllRead}
                  markingNotificationId={markingNotificationId}
                  onMarkAsRead={handleMarkNotificationRead}
                  onMarkAllAsRead={handleMarkAllNotificationsRead}
                  maxHeight={{ xs: 260, md: 360 }}
                />

                <InsightsPanel items={insightItems} />

                {shop?.id && (
                  <PoliciesPanel
                    policies={policies}
                    savingPolicyKey={savingPolicyKey}
                    onModeChange={handlePolicyModeChange}
                    onRetry={() => void refreshPolicies()}
                  />
                )}
              </Box>
            </Stack>
          </Grid>
        </Grid>
      </Box>
    </Box>
  );
};

export default AgentInbox;