import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  Circle,
  ClipboardCheck,
  Clock3,
  MessageCircle,
  PlayCircle,
  UserRound,
  XCircle,
} from "lucide-react";
import {
  useAssistantInteractable,
  useInteractableState,
} from "@assistant-ui/react";
import type { JSONSchema7 } from "json-schema";
import { cn } from "../../lib/utils";
import { useOwnerBrand } from "../../hooks/useOwnerBrand";
import type { PendingApproval } from "./types";

export type AgentActionStatus = "needs_decision" | "recommended" | "running" | "done";
export type AgentActionTab = "open" | "running" | "done";

export type AgentTaskBoardTask = {
  id: string;
  title: string;
  description: string;
  done: boolean;
  source: "manual" | "approval" | "agent";
  assignee?: string;
  createdAt: string;
  actionId?: string;
  status?: AgentActionStatus;
  agent?: string;
};

export type AgentTaskBoardState = {
  tasks: AgentTaskBoardTask[];
};

export type AgentTaskBoardExternalTask = Omit<AgentTaskBoardTask, "done"> & {
  done?: boolean;
  approval?: PendingApproval;
};

type RenderableActionTask = AgentTaskBoardTask & {
  approval?: PendingApproval;
};

interface AgentTaskBoardProps {
  interactableId: string;
  externalTasks?: AgentTaskBoardExternalTask[];
  isSubmittingDecision?: boolean;
  onDecision?: (approval: PendingApproval, approved: boolean) => Promise<boolean | void> | boolean | void;
  onDiscuss?: (task: AgentTaskBoardExternalTask) => void;
}

const TASK_BOARD_STATE_SCHEMA: JSONSchema7 = {
  type: "object",
  additionalProperties: false,
  required: ["tasks"],
  properties: {
    tasks: {
      type: "array",
      items: {
        type: "object",
        additionalProperties: false,
        required: ["id", "title", "description", "done", "source", "createdAt"],
        properties: {
          id: { type: "string" },
          title: { type: "string" },
          description: { type: "string" },
          done: { type: "boolean" },
          source: { type: "string", enum: ["manual", "approval", "agent"] },
          assignee: { type: "string" },
          createdAt: { type: "string" },
          actionId: { type: "string" },
          status: { type: "string", enum: ["needs_decision", "recommended", "running", "done"] },
          agent: { type: "string" },
        },
      },
    },
  },
};

const TASK_BOARD_INITIAL_STATE: AgentTaskBoardState = { tasks: [] };

const ACTION_STATUS_ORDER: Record<AgentActionStatus, number> = {
  needs_decision: 0,
  running: 1,
  recommended: 2,
  done: 3,
};

const TAB_LABELS: Array<{ id: AgentActionTab; label: string }> = [
  { id: "open", label: "Open" },
  { id: "running", label: "Running" },
  { id: "done", label: "Done" },
];

const defaultStatusForTask = (task: Pick<AgentTaskBoardTask, "source" | "done" | "status">): AgentActionStatus => {
  if (task.done || task.status === "done") return "done";
  if (task.status) return task.status;
  return task.source === "approval" ? "needs_decision" : "recommended";
};

const isDoneTask = (task: Pick<AgentTaskBoardTask, "done" | "status">) =>
  task.done || task.status === "done";

const sortTasks = (tasks: AgentTaskBoardTask[]) =>
  [...tasks].sort((left, right) => {
    const leftStatus = defaultStatusForTask(left);
    const rightStatus = defaultStatusForTask(right);
    if (leftStatus !== rightStatus) {
      return ACTION_STATUS_ORDER[leftStatus] - ACTION_STATUS_ORDER[rightStatus];
    }
    return new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime();
  });

const areTasksEqual = (left: AgentTaskBoardTask, right: AgentTaskBoardTask) =>
  left.id === right.id &&
  left.title === right.title &&
  left.description === right.description &&
  left.done === right.done &&
  left.source === right.source &&
  left.assignee === right.assignee &&
  left.createdAt === right.createdAt &&
  left.actionId === right.actionId &&
  left.status === right.status &&
  left.agent === right.agent;

const normalizeExternalTask = (
  task: AgentTaskBoardExternalTask,
  existing?: AgentTaskBoardTask,
): AgentTaskBoardTask => {
  const status = defaultStatusForTask({
    source: task.source,
    done: task.done ?? existing?.done ?? false,
    status: task.status ?? existing?.status,
  });

  return {
    id: task.id,
    title: task.title,
    description: task.description,
    done: status === "done" || existing?.done || task.done || false,
    source: task.source,
    assignee: task.assignee,
    createdAt: task.createdAt,
    actionId: task.actionId,
    status,
    agent: task.agent,
  };
};

const formatActionSource = (task: RenderableActionTask) => {
  if (task.approval?.category) return String(task.approval.category).replace(/_/g, " ");
  if (task.agent) return task.agent.replace(/_/g, " ");
  if (task.source === "approval") return "Approval";
  return "Agent";
};

const formatStatusLabel = (task: RenderableActionTask) => {
  const status = defaultStatusForTask(task);
  if (status === "needs_decision") return "Needs owner decision";
  if (status === "running") return "Running";
  if (status === "done") return "Completed";
  return "Recommended";
};

const getStatusIcon = (task: RenderableActionTask) => {
  const status = defaultStatusForTask(task);
  if (status === "needs_decision") return AlertTriangle;
  if (status === "running") return PlayCircle;
  if (status === "done") return CheckCircle2;
  return Circle;
};

const formatTime = (value?: string) => {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
};

const formatDetailValue = (value: unknown) => {
  if (typeof value === "string") return value.replace(/_/g, " ");
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (value == null) return "";
  return "";
};

const buildDetailRows = (task: RenderableActionTask) => {
  const details = task.approval?.details || {};
  const preferredKeys = [
    ["employee_username", "Employee"],
    ["employee_name", "Employee"],
    ["user_id", "Employee ID"],
    ["date", "Date"],
    ["start_time", "Start"],
    ["end_time", "End"],
    ["reason", "Reason"],
  ] as const;

  return preferredKeys
    .map(([key, label]) => ({ label, value: formatDetailValue(details[key]) }))
    .filter((row) => row.value);
};

const getImpactText = (task: RenderableActionTask) =>
  task.approval?.expected_impact ||
  task.approval?.summary ||
  task.approval?.reason ||
  task.description;

const getPrimaryDecisionLabel = (task: RenderableActionTask) => {
  const action = task.approval?.action || task.actionId || "";
  if (action.includes("assign_shift")) return "Approve shift";
  if (action.includes("close_queue")) return "Approve closure";
  if (action.includes("add_employee")) return "Approve hire";
  if (action.includes("record_payment")) return "Approve payment";
  if (action.includes("create_invoice")) return "Approve invoice";
  return "Approve";
};

const getTabForTask = (task: RenderableActionTask): AgentActionTab => {
  const status = defaultStatusForTask(task);
  if (status === "done") return "done";
  if (status === "running") return "running";
  return "open";
};

const AgentTaskBoard: React.FC<AgentTaskBoardProps> = ({
  interactableId,
  externalTasks = [],
  isSubmittingDecision = false,
  onDecision,
  onDiscuss,
}) => {
  const brand = useOwnerBrand();
  const [activeTab, setActiveTab] = useState<AgentActionTab>("open");
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);

  const registeredId = useAssistantInteractable("taskBoard", {
    id: interactableId,
    description:
      "A persistent owner action board for manual follow-ups, employee tasks, and approval work generated by the agent workspace.",
    stateSchema: TASK_BOARD_STATE_SCHEMA,
    initialState: TASK_BOARD_INITIAL_STATE,
  });

  const [state, { setState, setSelected, isPending, error }] =
    useInteractableState<AgentTaskBoardState>(registeredId, TASK_BOARD_INITIAL_STATE);

  useEffect(() => {
    setState((prev: AgentTaskBoardState) => {
      const existingTasks = prev.tasks || [];
      const externalTaskIds = new Set(externalTasks.map((task) => task.id));
      const retainedTasks = existingTasks.filter(
        (task) => task.source === "manual" || externalTaskIds.has(task.id),
      );
      const taskMap = new Map<string, AgentTaskBoardTask>(
        retainedTasks.map((task) => [task.id, task]),
      );
      let changed = retainedTasks.length !== existingTasks.length;

      externalTasks.forEach((task) => {
        const current = taskMap.get(task.id);
        const next = normalizeExternalTask(task, current);
        if (!current || !areTasksEqual(current, next)) {
          taskMap.set(next.id, next);
          changed = true;
        }
      });

      if (!changed) return prev;

      return { tasks: sortTasks(Array.from(taskMap.values())) };
    });
  }, [externalTasks, setState]);

  const externalTaskMap = useMemo(
    () => new Map(externalTasks.map((task) => [task.id, task])),
    [externalTasks],
  );

  const tasks = useMemo<RenderableActionTask[]>(
    () =>
      sortTasks(state.tasks || []).map((task) => ({
        ...task,
        approval: externalTaskMap.get(task.id)?.approval,
      })),
    [externalTaskMap, state.tasks],
  );

  const tabCounts = useMemo(
    () =>
      tasks.reduce<Record<AgentActionTab, number>>(
        (summary, task) => {
          summary[getTabForTask(task)] += 1;
          return summary;
        },
        { open: 0, running: 0, done: 0 },
      ),
    [tasks],
  );

  const tabTasks = useMemo(
    () => tasks.filter((task) => getTabForTask(task) === activeTab),
    [activeTab, tasks],
  );

  useEffect(() => {
    if (tabTasks.length === 0) {
      setSelectedTaskId(null);
      return;
    }
    if (!selectedTaskId || !tabTasks.some((task) => task.id === selectedTaskId)) {
      setSelectedTaskId(tabTasks[0].id);
    }
  }, [selectedTaskId, tabTasks]);

  const selectedTask = useMemo(
    () => tabTasks.find((task) => task.id === selectedTaskId) || tabTasks[0],
    [selectedTaskId, tabTasks],
  );

  const handleToggleManualTask = useCallback(
    (taskId: string) => {
      setSelected(true);
      setState((prev: AgentTaskBoardState) => ({
        tasks: sortTasks(
          (prev.tasks || []).map((task: AgentTaskBoardTask) => {
            if (task.id !== taskId || task.source === "approval") return task;
            const done = !task.done;
            return {
              ...task,
              done,
              status: done ? "done" : "recommended",
            };
          }),
        ),
      }));
    },
    [setSelected, setState],
  );

  const handleDecision = useCallback(
    async (task: RenderableActionTask, approved: boolean) => {
      if (!task.approval || !onDecision) return;
      setSelected(true);
      await onDecision(task.approval, approved);
    },
    [onDecision, setSelected],
  );

  const handleDiscuss = useCallback(
    (task: RenderableActionTask) => {
      setSelected(true);
      onDiscuss?.(task);
    },
    [onDiscuss, setSelected],
  );

  const doneCount = tasks.filter(isDoneTask).length;

  return (
    <div
      onClick={() => setSelected(true)}
      className="w-full h-full flex flex-col overflow-hidden border-l border-border bg-background min-h-[320px] md:min-h-0"
    >
      <div className="border-b border-border px-4 py-3">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <ClipboardCheck className="h-4 w-4 flex-shrink-0" style={{ color: brand.primary }} />
              <p className="text-sm font-bold text-foreground">Agent Actions</p>
              {isPending && (
                <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-border border-t-primary" />
              )}
            </div>
            <p className="mt-0.5 text-xs text-muted-foreground">
              Decisions and follow-ups connected to the agent.
            </p>
          </div>

          {tasks.length > 0 && (
            <span
              className="rounded-full px-2.5 py-1 text-xs font-bold"
              style={{ backgroundColor: `${brand.primary}14`, color: brand.primary }}
            >
              {doneCount}/{tasks.length}
            </span>
          )}
        </div>

        <div className="mt-3 grid grid-cols-3 rounded-2xl border border-border bg-muted/40 p-1">
          {TAB_LABELS.map((tab) => {
            const selected = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  "min-h-8 rounded-xl px-2 text-xs font-bold transition-colors",
                  selected ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
                )}
              >
                <span className="block truncate">{tab.label}</span>
                <span className="text-[11px] font-semibold opacity-75">{tabCounts[tab.id]}</span>
              </button>
            );
          })}
        </div>
      </div>

      {Boolean(error) && (
        <div className="mx-4 mt-3 rounded-2xl border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-500">
          Failed to sync agent actions.
        </div>
      )}

      {tasks.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 px-6 text-center">
          <Bot className="h-9 w-9 text-muted-foreground/35" />
          <p className="text-sm font-semibold text-muted-foreground">No agent actions yet.</p>
          <p className="text-xs leading-5 text-muted-foreground/80">
            Ask the Supervisor for a queue, revenue, or staffing recommendation.
          </p>
        </div>
      ) : (
        <div className="flex min-h-0 flex-1 flex-col">
          <div className="border-b border-border px-3 py-2">
            {tabTasks.length === 0 ? (
              <div className="flex min-h-[88px] items-center justify-center rounded-2xl border border-dashed border-border px-4 text-center">
                <p className="text-sm text-muted-foreground">No actions in this state.</p>
              </div>
            ) : (
              <div className="flex flex-col gap-1.5">
                {tabTasks.slice(0, 4).map((task) => {
                  const Icon = getStatusIcon(task);
                  const selected = selectedTask?.id === task.id;
                  const status = defaultStatusForTask(task);
                  return (
                    <button
                      key={task.id}
                      type="button"
                      onClick={() => setSelectedTaskId(task.id)}
                      className={cn(
                        "flex w-full items-start gap-3 rounded-2xl border px-3 py-2.5 text-left transition-colors",
                        selected
                          ? "border-primary/30 bg-primary/[0.06]"
                          : "border-transparent hover:border-border hover:bg-muted/40",
                      )}
                    >
                      <span
                        className={cn(
                          "mt-0.5 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full",
                          status === "needs_decision" && "bg-amber-500/10 text-amber-600",
                          status === "running" && "bg-blue-500/10 text-blue-600",
                          status === "done" && "bg-emerald-500/10 text-emerald-600",
                          status === "recommended" && "bg-muted text-muted-foreground",
                        )}
                      >
                        <Icon className="h-4 w-4" />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-bold text-foreground">{task.title}</span>
                        <span className="mt-0.5 line-clamp-2 block text-xs leading-5 text-muted-foreground">
                          {task.description}
                        </span>
                      </span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
            {selectedTask ? (
              <div className="flex flex-col gap-4">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-bold"
                      style={{ backgroundColor: `${brand.primary}14`, color: brand.primary }}
                    >
                      {formatStatusLabel(selectedTask)}
                    </span>
                    {selectedTask.approval?.risk_level && (
                      <span className="inline-flex items-center rounded-full bg-amber-500/10 px-2.5 py-1 text-xs font-bold text-amber-700">
                        {String(selectedTask.approval.risk_level)} risk
                      </span>
                    )}
                  </div>
                  <h3 className="mt-3 text-lg font-bold leading-tight text-foreground">
                    {selectedTask.title}
                  </h3>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">
                    {selectedTask.description}
                  </p>
                </div>

                <div className="grid gap-3 border-y border-border py-4">
                  <div>
                    <p className="text-xs font-bold uppercase tracking-[0.08em] text-muted-foreground">
                      Why this matters
                    </p>
                    <p className="mt-1 text-sm leading-6 text-foreground">{getImpactText(selectedTask)}</p>
                  </div>

                  <div>
                    <p className="text-xs font-bold uppercase tracking-[0.08em] text-muted-foreground">
                      Agent context
                    </p>
                    <div className="mt-2 grid gap-2 text-sm">
                      <div className="flex items-center justify-between gap-3">
                        <span className="inline-flex items-center gap-2 text-muted-foreground">
                          <Bot className="h-4 w-4" />
                          Source
                        </span>
                        <span className="truncate font-semibold capitalize text-foreground">
                          {formatActionSource(selectedTask)}
                        </span>
                      </div>
                      <div className="flex items-center justify-between gap-3">
                        <span className="inline-flex items-center gap-2 text-muted-foreground">
                          <UserRound className="h-4 w-4" />
                          Owner
                        </span>
                        <span className="truncate font-semibold text-foreground">
                          {selectedTask.assignee || "Owner"}
                        </span>
                      </div>
                      <div className="flex items-center justify-between gap-3">
                        <span className="inline-flex items-center gap-2 text-muted-foreground">
                          <Clock3 className="h-4 w-4" />
                          Created
                        </span>
                        <span className="truncate font-semibold text-foreground">
                          {formatTime(selectedTask.createdAt) || "Just now"}
                        </span>
                      </div>
                    </div>
                  </div>

                  {buildDetailRows(selectedTask).length > 0 && (
                    <div>
                      <p className="text-xs font-bold uppercase tracking-[0.08em] text-muted-foreground">
                        What will happen
                      </p>
                      <div className="mt-2 grid gap-2">
                        {buildDetailRows(selectedTask).map((row) => (
                          <div key={row.label} className="flex items-start justify-between gap-3 text-sm">
                            <span className="text-muted-foreground">{row.label}</span>
                            <span className="max-w-[58%] text-right font-semibold text-foreground">
                              {row.value}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

              </div>
            ) : null}
          </div>

          {selectedTask && (
            <div className="border-t border-border bg-background/95 px-4 py-3 shadow-[0_-10px_24px_rgba(15,23,42,0.04)]">
              {selectedTask.approval ? (
                <div className="flex flex-col gap-2">
                  <button
                    type="button"
                    disabled={isSubmittingDecision || !onDecision}
                    onClick={() => void handleDecision(selectedTask, true)}
                    className="min-h-11 rounded-2xl px-4 text-sm font-bold text-white transition-opacity disabled:opacity-50"
                    style={{ backgroundColor: brand.primary }}
                  >
                    {isSubmittingDecision ? "Submitting..." : getPrimaryDecisionLabel(selectedTask)}
                  </button>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      disabled={isSubmittingDecision || !onDecision}
                      onClick={() => void handleDecision(selectedTask, false)}
                      className="inline-flex min-h-10 items-center justify-center gap-2 rounded-2xl border border-border px-3 text-sm font-bold text-foreground transition-colors hover:bg-muted disabled:opacity-50"
                    >
                      <XCircle className="h-4 w-4" />
                      Reject
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDiscuss(selectedTask)}
                      className="inline-flex min-h-10 items-center justify-center gap-2 rounded-2xl border border-border px-3 text-sm font-bold text-foreground transition-colors hover:bg-muted"
                    >
                      <MessageCircle className="h-4 w-4" />
                      Discuss
                    </button>
                  </div>
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => handleToggleManualTask(selectedTask.id)}
                    className="inline-flex min-h-10 items-center justify-center gap-2 rounded-2xl border border-border px-3 text-sm font-bold text-foreground transition-colors hover:bg-muted"
                  >
                    {isDoneTask(selectedTask) ? (
                      <Circle className="h-4 w-4" />
                    ) : (
                      <CheckCircle2 className="h-4 w-4" />
                    )}
                    {isDoneTask(selectedTask) ? "Reopen" : "Mark done"}
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDiscuss(selectedTask)}
                    className="inline-flex min-h-10 items-center justify-center gap-2 rounded-2xl border border-border px-3 text-sm font-bold text-foreground transition-colors hover:bg-muted"
                  >
                    <MessageCircle className="h-4 w-4" />
                    Discuss
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default AgentTaskBoard;
