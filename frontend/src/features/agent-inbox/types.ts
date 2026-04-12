export interface PendingApproval {
  action_id?: string;
  action: string;
  details: Record<string, unknown>;
  shop_id: number;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: string;
  agent?: string;
  pendingAction?: PendingApproval;
}

export interface AgentFeedEvent {
  id: string;
  type:
    | "chat"
    | "agent_switch"
    | "tool_call"
    | "tool_result"
    | "approval_required"
    | "approval_decision"
    | "queue_update"
    | "error"
    | "system";
  title: string;
  description: string;
  timestamp: string;
  payload?: unknown;
}
