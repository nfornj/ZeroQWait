import type {
  AgentFeedEvent,
  ApprovalExecutionResult,
  InsightItem,
  PendingApproval,
} from "./types";

interface ApprovalDecisionResponse {
  message: string;
  status: string;
  agent?: string;
  tool_results?: ApprovalExecutionResult;
}

const labelForAction = (action: string): string => {
  switch (action) {
    case "close_queue":
      return "Queue closed";
    case "assign_shift":
      return "Shift assigned";
    case "add_employee":
      return "Employee added";
    case "remove_employee":
      return "Employee removed";
    default:
      return action.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
  }
};

const buildDescription = (
  approval: PendingApproval,
  response: ApprovalDecisionResponse,
): string => {
  const toolResults = response.tool_results;
  if (typeof toolResults?.message === "string" && toolResults.message.trim()) {
    return toolResults.message;
  }

  if (typeof response.message === "string" && response.message.trim()) {
    return response.message;
  }

  if (approval.action === "assign_shift") {
    const date = approval.details.date;
    const startTime = approval.details.start_time;
    const endTime = approval.details.end_time;
    const employeeId = approval.details.user_id;
    return `Employee ${employeeId} is scheduled on ${date} from ${startTime} to ${endTime}.`;
  }

  return `${labelForAction(approval.action)} completed.`;
};

const buildChips = (approval: PendingApproval, result?: ApprovalExecutionResult): string[] => {
  const chips: string[] = [];

  if (typeof result?.status === "string" && result.status.trim()) {
    chips.push(result.status);
  }

  if (approval.action === "assign_shift") {
    const employeeId = approval.details.user_id;
    const date = approval.details.date;
    const startTime = approval.details.start_time;
    const endTime = approval.details.end_time;
    if (employeeId) {
      chips.push(`Employee ${employeeId}`);
    }
    if (date && startTime && endTime) {
      chips.push(`${date} ${startTime}-${endTime}`);
    }
  }

  if (approval.action === "close_queue") {
    chips.push("Intake paused");
  }

  return chips.slice(0, 3);
};

export const buildApprovalOutcomeFeedEvent = (
  approval: PendingApproval,
  approved: boolean,
  response: ApprovalDecisionResponse,
  timestamp: string,
): AgentFeedEvent | null => {
  if (!approved || !response.tool_results) {
    return null;
  }

  return {
    id: `approval_outcome_${approval.action}_${timestamp}`,
    type: approval.action === "close_queue" ? "queue_update" : "tool_result",
    title: labelForAction(approval.action),
    description: buildDescription(approval, response),
    timestamp,
    payload: {
      approval,
      tool_results: response.tool_results,
    },
  };
};

export const buildApprovalOutcomeInsight = (
  approval: PendingApproval,
  approved: boolean,
  response: ApprovalDecisionResponse,
  timestamp: string,
): InsightItem | null => {
  if (!approved || !response.tool_results) {
    return null;
  }

  return {
    id: `approval_outcome_summary_${approval.action}_${timestamp}`,
    type: "summary",
    summary: {
      id: `approval_outcome_summary_data_${approval.action}_${timestamp}`,
      title: labelForAction(approval.action),
      body: buildDescription(approval, response),
      severity: "success",
      chips: buildChips(approval, response.tool_results),
      timestamp,
    },
    timestamp,
  };
};