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

interface StreamToolResultEvent {
  tool?: string;
  result?: ApprovalExecutionResult;
  agent?: string;
}

const labelForOperation = (operation: string): string => {
  switch (operation) {
    case "close_queue":
      return "Queue closed";
    case "assign_shift":
      return "Shift assigned";
    case "add_employee":
      return "Employee added";
    case "remove_employee":
      return "Employee removed";
    case "list_employees":
      return "Employee list ready";
    case "get_shifts":
      return "Shift schedule ready";
    case "list_queue":
      return "Queue status ready";
    case "daily_revenue":
      return "Daily revenue ready";
    case "weekly_summary":
      return "Weekly summary ready";
    default:
      return operation.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
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

  return `${labelForOperation(approval.action)} completed.`;
};

const buildChips = (operation: string, details: Record<string, unknown>, result?: ApprovalExecutionResult): string[] => {
  const chips: string[] = [];

  if (typeof result?.status === "string" && result.status.trim()) {
    chips.push(result.status);
  }

  if (operation === "assign_shift") {
    const employeeId = details.user_id;
    const date = details.date;
    const startTime = details.start_time;
    const endTime = details.end_time;
    if (employeeId) {
      chips.push(`Employee ${employeeId}`);
    }
    if (date && startTime && endTime) {
      chips.push(`${date} ${startTime}-${endTime}`);
    }
  }

  if (operation === "close_queue") {
    chips.push("Intake paused");
  }

  if (operation === "add_employee") {
    const username = result?.username;
    if (typeof username === "string" && username.trim()) {
      chips.push(username);
    }
  }

  if (operation === "list_employees" && Array.isArray((result as { employees?: unknown[] } | undefined)?.employees)) {
    chips.push(`${((result as { employees?: unknown[] }).employees || []).length} employees`);
  }

  if (operation === "get_shifts" && Array.isArray((result as { shifts?: unknown[] } | undefined)?.shifts)) {
    chips.push(`${((result as { shifts?: unknown[] }).shifts || []).length} shifts`);
  }

  return chips.slice(0, 3);
};

const buildStreamDescription = (operation: string, result?: ApprovalExecutionResult): string => {
  if (typeof result?.message === "string" && result.message.trim()) {
    return result.message;
  }

  if (operation === "list_employees" && Array.isArray((result as { employees?: unknown[] } | undefined)?.employees)) {
    const employees = ((result as { employees?: Array<{ name?: string; email?: string }> }).employees || []);
    if (employees.length === 0) {
      return "No employees matched the current request.";
    }
    return `Returned ${employees.length} employee${employees.length === 1 ? "" : "s"}.`;
  }

  if (operation === "get_shifts" && Array.isArray((result as { shifts?: unknown[] } | undefined)?.shifts)) {
    const shifts = ((result as { shifts?: unknown[] }).shifts || []);
    return `Returned ${shifts.length} scheduled shift${shifts.length === 1 ? "" : "s"}.`;
  }

  if (operation === "daily_revenue" || operation === "weekly_summary") {
    return `${labelForOperation(operation)}.`;
  }

  return `${labelForOperation(operation)} completed.`;
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
    title: labelForOperation(approval.action),
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
        title: labelForOperation(approval.action),
      body: buildDescription(approval, response),
      severity: "success",
      chips: buildChips(approval.action, approval.details, response.tool_results),
      timestamp,
    },
    timestamp,
  };
};

export const buildStreamToolResultFeedEvent = (
  streamEvent: StreamToolResultEvent,
  timestamp: string,
): AgentFeedEvent | null => {
  const operation = String(streamEvent.tool || streamEvent.result?.tool || "").trim();
  const result = streamEvent.result;
  if (!operation || !result) {
    return null;
  }

  return {
    id: `stream_tool_result_${operation}_${timestamp}`,
    type: operation === "close_queue" ? "queue_update" : "tool_result",
    title: labelForOperation(operation),
    description: buildStreamDescription(operation, result),
    timestamp,
    payload: {
      tool: operation,
      result,
      agent: streamEvent.agent,
    },
  };
};

export const buildStreamToolResultInsight = (
  streamEvent: StreamToolResultEvent,
  timestamp: string,
): InsightItem | null => {
  const operation = String(streamEvent.tool || streamEvent.result?.tool || "").trim();
  const result = streamEvent.result;
  if (!operation || !result) {
    return null;
  }

  return {
    id: `stream_tool_result_summary_${operation}_${timestamp}`,
    type: "summary",
    summary: {
      id: `stream_tool_result_summary_data_${operation}_${timestamp}`,
      title: labelForOperation(operation),
      body: buildStreamDescription(operation, result),
      severity: result.error ? "error" : "success",
      chips: buildChips(operation, result, result),
      timestamp,
    },
    timestamp,
  };
};