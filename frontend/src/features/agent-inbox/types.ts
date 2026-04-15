export interface ThinkingStep {
  id: string;
  label: string;
  status: "pending" | "active" | "completed" | "error";
  agent?: string | null;
  toolName?: string | null;
}

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
  status: "sending" | "streaming" | "done" | "error";
  timestamp: string;
  agent?: string;
  retryMessage?: string;
  pendingAction?: PendingApproval;
  thinkingSteps?: ThinkingStep[];
  thinkingComplete?: boolean;
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
