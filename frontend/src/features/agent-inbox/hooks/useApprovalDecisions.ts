import { useCallback, useState } from "react";

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

const API_BASE = process.env.REACT_APP_API_URL || "/api";

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

      const payload = {
        shop_id: shopId,
        action_id: approval.action_id,
        approved,
      };
      const eventTimestamp = nowIso();

      try {
        const token = localStorage.getItem("token");
        const response = await fetch(`${API_BASE}/v2/agent/approve/stream`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify(payload),
        });

        if (!response.ok || !response.body) {
          throw new Error(`Approval request failed with status ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let accumulatedText = "";
        let finalAgent = "supervisor";
        let finalToolResults: ApprovalExecutionResult | undefined;
        let finalStatus = approved ? "approved" : "rejected";
        let streamError: string | null = null;

        outer: while (true) {
          const { value, done } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed.startsWith("data:")) continue;

            const rawPayload = trimmed.slice(5).trim();
            if (rawPayload === "[DONE]") break outer;

            try {
              const event = JSON.parse(rawPayload);
              const eventType = String(event.type || "");

              if (eventType === "text") {
                accumulatedText += String(event.content || "");
              } else if (eventType === "stream_status") {
                finalStatus = String(event.status || finalStatus);
                if (event.agent) finalAgent = String(event.agent);
                if (event.tool_results) finalToolResults = event.tool_results as ApprovalExecutionResult;
              } else if (eventType === "error") {
                streamError = String(event.message || "Approval stream error");
              }
            } catch {
              // non-JSON SSE line — skip
            }
          }
        }

        if (streamError) throw new Error(streamError);

        const message = accumulatedText || `Action ${approved ? "approved" : "rejected"}.`;
        const syntheticResponse = {
          message,
          status: finalStatus,
          agent: finalAgent,
          tool_results: finalToolResults,
        };

        appendSystemMessage(message, finalAgent);

        addFeedEvent({
          type: "approval_decision",
          title: approved ? "Action approved" : "Action rejected",
          description: `You ${approved ? "approved" : "rejected"} '${approval.action}'.`,
          payload,
        });

        const outcomeEvent = buildApprovalOutcomeFeedEvent(approval, approved, syntheticResponse, eventTimestamp);
        if (outcomeEvent) {
          addFeedEvent({
            type: outcomeEvent.type,
            title: outcomeEvent.title,
            description: outcomeEvent.description,
            payload: outcomeEvent.payload,
          });
        }

        const outcomeInsight = buildApprovalOutcomeInsight(approval, approved, syntheticResponse, eventTimestamp);
        if (outcomeInsight) {
          prependInsightItem(outcomeInsight);
        }

        await refreshPendingApprovals();
        await refreshBriefing();
        await refreshFeed();
      } catch (err: any) {
        const detail = err?.message || "Failed to submit approval decision";
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