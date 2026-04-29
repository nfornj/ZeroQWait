import { useCallback, useState } from "react";

import api from "../../../services/api";
import {
  buildApprovalOutcomeFeedEvent,
  buildApprovalOutcomeInsight,
} from "../approvalOutcome";
import { nowIso } from "../agentInboxShared";
import type {
  AgentFeedEvent,
  ApprovalExecutionResult,
  InsightItem,
  PendingApproval,
} from "../types";

type FeedEventInput = Omit<AgentFeedEvent, "id" | "timestamp">;

interface UseApprovalDecisionsOptions {
  shopId?: number;
  addFeedEvent: (event: FeedEventInput) => void;
  appendSystemMessage: (content: string, agent?: string) => void;
  prependInsightItem: (item: InsightItem) => void;
  refreshPendingApprovals: () => Promise<void>;
  refreshBriefing: () => Promise<void>;
  refreshFeed: () => Promise<void>;
  setError: (value: string | null) => void;
}

export const useApprovalDecisions = ({
  shopId,
  addFeedEvent,
  appendSystemMessage,
  prependInsightItem,
  refreshPendingApprovals,
  refreshBriefing,
  refreshFeed,
  setError,
}: UseApprovalDecisionsOptions) => {
  const [isApproving, setIsApproving] = useState(false);

  const handleApprovalDecision = useCallback(
    async (approval: PendingApproval, approved: boolean) => {
      if (!shopId) return;

      setError(null);
      setIsApproving(true);

      try {
        const payload = {
          shop_id: shopId,
          action_id: approval.action_id,
          approved,
        };
        const eventTimestamp = nowIso();

        const response = await api.post<{
          message: string;
          status: string;
          agent?: string;
          tool_results?: ApprovalExecutionResult;
        }>("/v2/agent/approve", payload);

        appendSystemMessage(
          response.data.message || `Action ${approved ? "approved" : "rejected"}.`,
          response.data.agent,
        );

        addFeedEvent({
          type: "approval_decision",
          title: approved ? "Action approved" : "Action rejected",
          description: `You ${approved ? "approved" : "rejected"} '${approval.action}'.`,
          payload,
        });

        const outcomeEvent = buildApprovalOutcomeFeedEvent(approval, approved, response.data, eventTimestamp);
        if (outcomeEvent) {
          addFeedEvent({
            type: outcomeEvent.type,
            title: outcomeEvent.title,
            description: outcomeEvent.description,
            payload: outcomeEvent.payload,
          });
        }

        const outcomeInsight = buildApprovalOutcomeInsight(approval, approved, response.data, eventTimestamp);
        if (outcomeInsight) {
          prependInsightItem(outcomeInsight);
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
    [
      addFeedEvent,
      appendSystemMessage,
      prependInsightItem,
      refreshBriefing,
      refreshFeed,
      refreshPendingApprovals,
      setError,
      shopId,
    ],
  );

  return { handleApprovalDecision, isApproving };
};

export default useApprovalDecisions;