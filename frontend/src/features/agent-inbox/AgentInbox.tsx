import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { cn } from "../../lib/utils";

import { useShop } from "../../contexts/ShopContext";
import api from "../../services/api";
import AgentChat from "./AgentChat";
import AgentFeed from "./AgentFeed";
import AgentInsights from "./AgentInsights";
import InsightsPanel from "./InsightsPanel";
import OwnerBriefing from "./OwnerBriefing";
import PendingApprovalsPanel from "./PendingApprovalsPanel";
import PoliciesPanel from "./PoliciesPanel";
import { buildIntroMessage } from "./agentInboxShared";
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
  const { shop, loading: shopLoading } = useShop();

  const [persistedFeedEvents, setPersistedFeedEvents] = useState<AgentFeedEvent[]>([]);;
  const [pendingApprovals, setPendingApprovals] = useState<PendingApproval[]>([]);
  const [policies, setPolicies] = useState<ShopPolicy[]>([]);
  const [briefing, setBriefing] = useState<OwnerBriefingData | null>(null);
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
    error,
    setError,
    appendSystemMessage,
    handleSend,
    isVoiceEnabled,
    isSpeaking,
    toggleVoice,
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

  const handleBriefingAction = useCallback(
    (action: BriefingAction) => {
      addFeedEvent({
        type: "chat",
        title: `Action: ${action.label}`,
        description: action.description || action.payload,
        payload: action,
      });
      void handleSend({ text: action.payload });
    },
    [addFeedEvent, handleSend],
  );

  const promptSections = useMemo(() => {
    const quickActions = createWorkspaceQuickActions(briefing, pendingApprovals, shop?.name);
    return [
      {
        id: "quick-actions",
        title: "Suggested actions",
        prompts: quickActions.map((action) => ({
          id: action.label.replace(/[^a-zA-Z0-9_-]+/g, "_"),
          label: action.label,
          prompt: action.payload,
        })),
      },
    ];
  }, [briefing, pendingApprovals, shop?.name]);

  return (
    <div
      className="w-full mx-auto flex flex-col"
      style={{ maxWidth: "1800px", height: "calc(100dvh - var(--navbar-h, 57px))" }}
    >
      <div className="flex flex-col flex-1 min-h-0">
        {/* Error banner */}
        {error && (
          <div className="mx-3 mt-2 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-2 text-sm text-red-400">
            {error}
          </div>
        )}

        {/* No-shop warning */}
        {!shop?.id && !shopLoading && (
          <div className="mx-3 mt-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-2 text-sm text-amber-400">
            No active shop selected. Refresh the shop workspace or choose an active shop from the top bar if you manage more than one location.
          </div>
        )}

        {/* Main layout */}
        <div className="flex flex-col md:flex-row flex-1 min-h-0 gap-1 md:overflow-hidden">
          {/* Left: chat (7/12) */}
          <div className="flex flex-col min-h-0 flex-[7] md:h-full">
            {shop?.id && (
              <AgentChat
                messages={messages}
                isStreaming={isStreaming}
                onSend={handleSend}
                promptSections={promptSections}
                interactablesStorageKey={`agent-inbox-${shop.id}`}
                isVoiceEnabled={isVoiceEnabled}
                isSpeaking={isSpeaking}
                onToggleVoice={toggleVoice}
              />
            )}
            <div className="flex-shrink-0 px-3 pb-1">
              <button
                type="button"
                onClick={() => setInsightsOpen((open) => !open)}
                className="flex h-7 w-7 items-center justify-center rounded-lg text-blue-400 hover:bg-muted transition-colors"
              >
                <ChevronDown
                  className={cn("h-4 w-4 transition-transform duration-200", insightsOpen && "rotate-180")}
                />
              </button>
              {insightsOpen && (
                <div className="mt-2">
                  <AgentInsights
                    messages={messages}
                    events={displayedFeedEvents}
                    pendingApprovals={pendingApprovals}
                  />
                </div>
              )}
            </div>
          </div>

          {/* Right: context panel (5/12) */}
          <div className="flex min-h-0 flex-[5] md:h-full">
            <div className="flex flex-col flex-1 min-h-0 gap-3 md:h-full">
              <OwnerBriefing briefing={briefing} onAction={handleBriefingAction} isLoading={briefingQuery.isLoading} />
              <div className="flex-1 min-h-0 overflow-y-auto md:overflow-y-auto pr-0 md:pr-1 flex flex-col gap-3">
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
                  isLoading={feedQuery.isLoading}
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
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AgentInbox;