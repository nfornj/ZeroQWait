import type { ChatMessage, PendingApproval } from "./types";

export const nowIso = () => new Date().toISOString();

export const toId = (prefix: string) => `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;

export const buildIntroMessage = (): ChatMessage => ({
  id: toId("msg_intro"),
  role: "assistant",
  content:
    "Welcome to your Supervisor workspace. I can help with queue status, team scheduling, approvals, and daily performance summaries. What would you like to handle first?",
  status: "done",
  timestamp: nowIso(),
});

const POLICY_MODE_LABELS: Record<string, string> = {
  require_approval: "Require approval",
  allow: "Allow automatically",
  notify_only: "Auto-run and notify",
  silent: "Auto-run silently",
  forbid: "Block action",
};

export const labelForPolicyMode = (mode?: string): string => {
  if (!mode) return "Policy controlled";
  return POLICY_MODE_LABELS[mode] || mode.replace(/_/g, " ");
};

export const normalizePendingApproval = (
  raw: Record<string, any>,
  fallbackShopId: number,
): PendingApproval => {
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
