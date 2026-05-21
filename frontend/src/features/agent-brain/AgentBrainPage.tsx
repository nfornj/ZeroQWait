import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  Brain,
  BriefcaseBusiness,
  CalendarClock,
  CheckCircle,
  Clock,
  Database,
  GitBranch,
  Hammer,
  Landmark,
  MemoryStick,
  Network,
  RefreshCw,
  Scissors,
  Send,
  Sparkles,
  Store,
  Users,
} from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import {
  Background,
  BackgroundVariant,
  Controls,
  type Edge,
  MarkerType,
  MiniMap,
  type Node,
  type NodeTypes,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { useShop } from "../../contexts/ShopContext";
import { useThemeContext } from "../../contexts/ThemeContext";
import { useAgentStream } from "../agent-inbox/hooks/useAgentStream";
import { useAgentWebSocket } from "../agent-inbox/hooks/useAgentWebSocket";
import {
  ownerDashboardKeys,
  useOwnerBriefingQuery,
  useOwnerFeedQuery,
  usePendingApprovalsQuery,
} from "../agent-inbox/ownerDashboardQueries";
import type { AgentFeedEvent, ChatMessage, PendingApproval, ThinkingStep } from "../agent-inbox/types";
import BrainNode, { type BrainNodeData } from "./nodes/BrainNode";

type BrainNodeId =
  | "owner"
  | "temporal"
  | "supervisor"
  | "soul"
  | "receptionist"
  | "finance"
  | "hr"
  | "crm"
  | "tools"
  | "commitments"
  | "schedules"
  | "data";

interface NodeSeed {
  id: BrainNodeId;
  label: string;
  subtitle: string;
  color: string;
  icon: React.ReactNode;
  position: { x: number; y: number };
  hasTarget?: boolean;
  hasSource?: boolean;
}

interface EdgeSeed {
  id: string;
  source: BrainNodeId;
  target: BrainNodeId;
  label?: string;
}

const formatTime = (value?: string) => {
  if (!value) return "now";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "now";
  return parsed.toLocaleTimeString([], { hour: "numeric", minute: "2-digit", second: "2-digit" });
};

const eventMatchesBriefing = (event: AgentFeedEvent) => {
  const haystack = `${event.notification_type || ""} ${event.type || ""} ${event.title || ""}`.toLowerCase();
  return haystack.includes("briefing") || haystack.includes("wrap-up") || haystack.includes("wrap up");
};

const agentNodeFromValue = (value?: string | null): BrainNodeId | null => {
  const normalized = String(value || "").toLowerCase();
  if (normalized.includes("reception") || normalized.includes("booking")) return "receptionist";
  if (normalized.includes("finance")) return "finance";
  if (normalized === "hr" || normalized.includes("human") || normalized.includes("staff")) return "hr";
  if (normalized.includes("crm") || normalized.includes("customer")) return "crm";
  return null;
};

const eventToEdgeIds = (event: AgentFeedEvent): string[] => {
  const ids = new Set<string>();
  const payload = event.payload && typeof event.payload === "object" ? (event.payload as Record<string, any>) : {};
  const agent = agentNodeFromValue(String(payload.agent || payload.current_agent || event.description || ""));

  if (event.type === "chat") ids.add("owner-supervisor");
  if (event.type === "agent_switch") ids.add(`supervisor-${agent || "receptionist"}`);
  if (event.type === "tool_call" || event.type === "tool_result") ids.add(`${agent || "supervisor"}-tools`);
  if (event.type === "approval_required" || event.type === "approval_decision") ids.add("supervisor-owner");
  if (event.type === "queue_update") ids.add("receptionist-tools");
  if (eventMatchesBriefing(event)) {
    ids.add("temporal-supervisor");
    ids.add("supervisor-owner");
  }
  if (String(event.title || "").toLowerCase().includes("policy")) ids.add("supervisor-data");
  return Array.from(ids);
};

const thinkingToEdgeIds = (steps: ThinkingStep[]): string[] => {
  const ids = new Set<string>();
  steps.forEach((step) => {
    if (step.status !== "active") return;
    const agent = agentNodeFromValue(step.agent || step.label);
    if (agent) ids.add(`supervisor-${agent}`);
    if (step.toolName || step.label.toLowerCase().includes("calling")) ids.add(`${agent || "supervisor"}-tools`);
  });
  return Array.from(ids);
};

const latestAssistant = (messages: ChatMessage[]) =>
  [...messages].reverse().find((message) => message.role === "assistant");

const NODE_SEEDS: NodeSeed[] = [
  { id: "temporal", label: "Temporal", subtitle: "Heartbeats & cron", color: "#0ea5e9", icon: <Clock />, position: { x: 0, y: 40 }, hasTarget: false },
  { id: "owner", label: "Owner", subtitle: "Commands & approvals", color: "#9333ea", icon: <Store />, position: { x: 0, y: 280 } },
  { id: "soul", label: "SOUL", subtitle: "Shop identity memory", color: "#a855f7", icon: <Brain />, position: { x: 0, y: 500 } },
  { id: "supervisor", label: "Supervisor", subtitle: "Routes the agent team", color: "#22c55e", icon: <Network />, position: { x: 320, y: 280 } },
  { id: "receptionist", label: "Receptionist", subtitle: "Queue & bookings", color: "#14b8a6", icon: <Scissors />, position: { x: 640, y: 40 } },
  { id: "finance", label: "Finance", subtitle: "Revenue & reports", color: "#f59e0b", icon: <Landmark />, position: { x: 640, y: 200 } },
  { id: "hr", label: "HR", subtitle: "Staff & shifts", color: "#ef4444", icon: <Users />, position: { x: 640, y: 360 } },
  { id: "crm", label: "CRM", subtitle: "Contacts & pipeline", color: "#6366f1", icon: <GitBranch />, position: { x: 640, y: 520 } },
  { id: "tools", label: "MCP Tools", subtitle: "Booking · Finance · HR", color: "#64748b", icon: <Hammer />, position: { x: 960, y: 120 } },
  { id: "commitments", label: "Commitments", subtitle: "Follow-ups & promises", color: "#ec4899", icon: <BriefcaseBusiness />, position: { x: 960, y: 280 } },
  { id: "schedules", label: "Schedules", subtitle: "Natural language cron", color: "#06b6d4", icon: <CalendarClock />, position: { x: 960, y: 440 } },
  { id: "data", label: "Postgres + Redis", subtitle: "Durable & short memory", color: "#475569", icon: <Database />, position: { x: 320, y: 540 }, hasSource: false },
];

const EDGE_SEEDS: EdgeSeed[] = [
  { id: "owner-supervisor", source: "owner", target: "supervisor", label: "message" },
  { id: "supervisor-owner", source: "supervisor", target: "owner", label: "answer" },
  { id: "temporal-supervisor", source: "temporal", target: "supervisor", label: "scheduled" },
  { id: "supervisor-receptionist", source: "supervisor", target: "receptionist" },
  { id: "supervisor-finance", source: "supervisor", target: "finance" },
  { id: "supervisor-hr", source: "supervisor", target: "hr" },
  { id: "supervisor-crm", source: "supervisor", target: "crm" },
  { id: "supervisor-soul", source: "supervisor", target: "soul", label: "context" },
  { id: "supervisor-data", source: "supervisor", target: "data", label: "state" },
  { id: "receptionist-tools", source: "receptionist", target: "tools" },
  { id: "finance-tools", source: "finance", target: "tools" },
  { id: "hr-tools", source: "hr", target: "tools" },
  { id: "crm-tools", source: "crm", target: "tools" },
  { id: "temporal-schedules", source: "temporal", target: "schedules" },
  { id: "temporal-commitments", source: "temporal", target: "commitments" },
  { id: "commitments-supervisor", source: "commitments", target: "supervisor", label: "follow-up" },
  { id: "soul-data", source: "soul", target: "data" },
];

const nodeTypes: NodeTypes = { brain: BrainNode };

interface BrainCanvasProps {
  activeEdgeIds: Set<string>;
  activeNodeIds: Set<string>;
  statusByNode: Record<BrainNodeId, string>;
  isDark: boolean;
}

const BrainCanvas: React.FC<BrainCanvasProps> = ({ activeEdgeIds, activeNodeIds, statusByNode, isDark }) => {
  const initialNodes: Node[] = useMemo(
    () =>
      NODE_SEEDS.map((seed) => ({
        id: seed.id,
        type: "brain",
        position: seed.position,
        draggable: true,
        data: {
          label: seed.label,
          subtitle: seed.subtitle,
          status: statusByNode[seed.id] || "ready",
          color: seed.color,
          icon: seed.icon,
          active: activeNodeIds.has(seed.id),
          hasTarget: seed.hasTarget,
          hasSource: seed.hasSource,
        } satisfies BrainNodeData,
      })),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  const initialEdges: Edge[] = useMemo(
    () =>
      EDGE_SEEDS.map((seed) => {
        const active = activeEdgeIds.has(seed.id);
        return {
          id: seed.id,
          source: seed.source,
          target: seed.target,
          label: seed.label,
          type: "smoothstep",
          animated: active,
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: active ? "#22c55e" : isDark ? "#475569" : "#94a3b8",
            width: 16,
            height: 16,
          },
          style: {
            stroke: active ? "#22c55e" : isDark ? "#475569" : "#cbd5e1",
            strokeWidth: active ? 2.5 : 1.4,
          },
          labelStyle: {
            fill: isDark ? "#cbd5e1" : "#475569",
            fontSize: 11,
            fontWeight: 600,
          },
          labelBgStyle: {
            fill: isDark ? "#0f172a" : "#ffffff",
            fillOpacity: 0.85,
          },
          labelBgPadding: [4, 2] as [number, number],
          labelBgBorderRadius: 4,
        };
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Update node activity / status without resetting positions
  useEffect(() => {
    setNodes((current: Node[]) =>
      current.map((n: Node) => ({
        ...n,
        data: {
          ...n.data,
          active: activeNodeIds.has(n.id as BrainNodeId),
          status: statusByNode[n.id as BrainNodeId] || (n.data as BrainNodeData).status,
        },
      })),
    );
  }, [activeNodeIds, statusByNode, setNodes]);

  // Update edge animation/style live
  useEffect(() => {
    setEdges((current: Edge[]) =>
      current.map((e: Edge) => {
        const active = activeEdgeIds.has(e.id);
        return {
          ...e,
          animated: active,
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: active ? "#22c55e" : isDark ? "#475569" : "#94a3b8",
            width: 16,
            height: 16,
          },
          style: {
            stroke: active ? "#22c55e" : isDark ? "#475569" : "#cbd5e1",
            strokeWidth: active ? 2.5 : 1.4,
          },
        };
      }),
    );
  }, [activeEdgeIds, isDark, setEdges]);

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      nodeTypes={nodeTypes}
      fitView
      fitViewOptions={{ padding: 0.18 }}
      minZoom={0.4}
      maxZoom={1.6}
      proOptions={{ hideAttribution: true }}
      nodesConnectable={false}
      elementsSelectable
    >
      <Background
        variant={BackgroundVariant.Dots}
        gap={22}
        size={1.2}
        color={isDark ? "#1e293b" : "#cbd5e1"}
      />
      <Controls position="bottom-right" showInteractive={false} />
      <MiniMap
        pannable
        zoomable
        nodeStrokeWidth={2}
        nodeColor={(n: Node) => (n.data as BrainNodeData).color}
        maskColor={isDark ? "rgba(2,6,23,0.6)" : "rgba(241,245,249,0.7)"}
        style={{ width: 160, height: 110 }}
      />
    </ReactFlow>
  );
};

const AgentBrainPage: React.FC = () => {
  const queryClient = useQueryClient();
  const { shop, loading: shopLoading } = useShop();
  const { mode } = useThemeContext();
  const brandPrimary = shop?.primary_color || "hsl(var(--primary))";
  const brandSecondary = shop?.secondary_color || "hsl(var(--secondary))";
  const isDark = mode === "dark";
  const [prompt, setPrompt] = useState("Give me a live operations summary and route to the right specialist if needed.");
  const [localApprovals, setLocalApprovals] = useState<PendingApproval[]>([]);
  const [localInsights, setLocalInsights] = useState<any[]>([]);
  const [nodePulse, setNodePulse] = useState<Record<string, number>>({});

  const briefingQuery = useOwnerBriefingQuery(shop?.id);
  const feedQuery = useOwnerFeedQuery(shop?.id, 40);
  const pendingQuery = usePendingApprovalsQuery(shop?.id);

  const { feedEvents: websocketEvents, addFeedEvent, connectionStatus } = useAgentWebSocket(shop?.id);

  const refreshPendingApprovals = useCallback(async () => {
    if (!shop?.id) return;
    await queryClient.invalidateQueries({ queryKey: ownerDashboardKeys.pending(shop.id) });
  }, [queryClient, shop?.id]);

  const refreshBriefing = useCallback(async () => {
    if (!shop?.id) return;
    await queryClient.invalidateQueries({ queryKey: ownerDashboardKeys.briefing(shop.id) });
    await queryClient.invalidateQueries({ queryKey: ownerDashboardKeys.feed(shop.id) });
  }, [queryClient, shop?.id]);

  const addPendingApproval = useCallback((approval: PendingApproval) => {
    setLocalApprovals((prev) => [approval, ...prev]);
  }, []);

  const prependInsightItem = useCallback((item: any) => {
    setLocalInsights((prev) => [item, ...prev].slice(0, 10));
  }, []);

  const { messages, isStreaming, error, handleSend } = useAgentStream({
    shopId: shop?.id,
    addFeedEvent,
    addPendingApproval,
    prependInsightItem,
    refreshPendingApprovals,
    refreshBriefing,
  });

  const allEvents = useMemo(() => {
    const merged = [...websocketEvents, ...(feedQuery.data || [])];
    const seen = new Set<string>();
    return merged
      .filter((event) => {
        const key = event.id || `${event.type}_${event.timestamp}_${event.title}`;
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      })
      .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
      .slice(0, 50);
  }, [feedQuery.data, websocketEvents]);

  const assistant = latestAssistant(messages);
  const activeThinkingSteps = assistant?.thinkingSteps || [];

  const activeEdgeIds = useMemo(() => {
    const ids = new Set<string>();
    allEvents.slice(0, 8).forEach((event) => eventToEdgeIds(event).forEach((id) => ids.add(id)));
    thinkingToEdgeIds(activeThinkingSteps).forEach((id) => ids.add(id));
    if (isStreaming) ids.add("owner-supervisor");
    if (briefingQuery.data?.source === "scheduled") ids.add("temporal-supervisor");
    return ids;
  }, [activeThinkingSteps, allEvents, briefingQuery.data?.source, isStreaming]);

  // Track recently-pulsed nodes (edge endpoints) so a node glows for ~6s after activity
  useEffect(() => {
    if (activeEdgeIds.size === 0) return;
    const now = Date.now();
    setNodePulse((prev) => {
      const next = { ...prev };
      activeEdgeIds.forEach((edgeId) => {
        const seed = EDGE_SEEDS.find((e) => e.id === edgeId);
        if (!seed) return;
        next[seed.source] = now;
        next[seed.target] = now;
      });
      return next;
    });
  }, [activeEdgeIds]);

  // Sweep stale pulses every 2s
  useEffect(() => {
    const handle = window.setInterval(() => {
      setNodePulse((prev) => {
        const now = Date.now();
        const next: Record<string, number> = {};
        let changed = false;
        Object.entries(prev).forEach(([k, ts]) => {
          if (now - ts < 6000) next[k] = ts;
          else changed = true;
        });
        return changed ? next : prev;
      });
    }, 2000);
    return () => window.clearInterval(handle);
  }, []);

  const activeNodeIds = useMemo(() => {
    const now = Date.now();
    const set = new Set<string>();
    Object.entries(nodePulse).forEach(([k, ts]) => {
      if (now - ts < 6000) set.add(k);
    });
    return set;
  }, [nodePulse]);

  const statusByNode = useMemo<Record<BrainNodeId, string>>(() => {
    const pendingCount = (pendingQuery.data || []).length + localApprovals.length;
    const latestEvent = allEvents[0];
    return {
      temporal: briefingQuery.data?.source === "scheduled" ? "briefing live" : "schedules armed",
      owner: pendingCount > 0 ? `${pendingCount} approval${pendingCount === 1 ? "" : "s"}` : "in control",
      soul: "foundation ready",
      supervisor: isStreaming ? "thinking" : latestEvent ? "listening" : "idle",
      receptionist: activeNodeIds.has("receptionist") ? "working" : "ready",
      finance: activeNodeIds.has("finance") ? "working" : "ready",
      hr: activeNodeIds.has("hr") ? "working" : "ready",
      crm: activeNodeIds.has("crm") ? "working" : "ready",
      tools: activeNodeIds.has("tools") ? "executing" : "ready",
      commitments: "scanner next",
      schedules: "2 heartbeats",
      data: `${allEvents.length} recent events`,
    };
  }, [activeNodeIds, allEvents, briefingQuery.data?.source, isStreaming, localApprovals.length, pendingQuery.data]);

  const handleSubmit = useCallback(async () => {
    const clean = prompt.trim();
    if (!clean || isStreaming) return;
    await handleSend({ text: clean });
  }, [handleSend, isStreaming, prompt]);

  const assistantText = String(assistant?.content || "").trim();

  return (
    <div className="mx-auto w-full max-w-[1500px] p-4 md:p-6">
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <MemoryStick className="size-5" style={{ color: brandPrimary }} />
              <h1 className="text-2xl font-bold tracking-tight">Agent Brain</h1>
              <Badge variant={connectionStatus === "connected" ? "default" : "secondary"} className="gap-1.5">
                {connectionStatus === "connected" ? <CheckCircle className="size-3.5" /> : <RefreshCw className="size-3.5" />}
                {connectionStatus === "connected" ? "Live" : connectionStatus}
              </Badge>
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              {shop?.name || "Selected shop"} brain runtime: Supervisor, specialists, Temporal, memory, tools, and approvals.
            </p>
          </div>
          <div className="flex flex-wrap gap-2 md:justify-end">
            <Badge variant="secondary">Feed {allEvents.length}</Badge>
            <Badge variant="outline">Approvals {(pendingQuery.data || []).length + localApprovals.length}</Badge>
            <Badge variant="outline" className="border-cyan-500/40 text-cyan-600">
              {briefingQuery.data?.source === "scheduled" ? "Temporal active" : "Temporal armed"}
            </Badge>
          </div>
        </div>

        {error && (
          <Alert>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        {shopLoading && (
          <Alert>
            <AlertDescription>Loading active shop context...</AlertDescription>
          </Alert>
        )}

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
          <Card
            className="relative h-[620px] overflow-hidden md:h-[720px]"
            style={{
              borderColor: `color-mix(in srgb, ${brandPrimary} 16%, transparent)`,
              background: isDark ? "rgb(2 6 23 / 0.78)" : "rgb(248 250 252 / 0.9)",
            }}
          >
            <ReactFlowProvider>
              <BrainCanvas
                activeEdgeIds={activeEdgeIds}
                activeNodeIds={activeNodeIds as Set<string>}
                statusByNode={statusByNode}
                isDark={isDark}
              />
            </ReactFlowProvider>
          </Card>

          <div className="flex flex-col gap-4">
            <Card style={{ borderColor: `color-mix(in srgb, ${brandPrimary} 16%, transparent)` }}>
              <CardContent className="flex flex-col gap-3 p-4">
                <div className="flex items-center gap-2">
                  <Sparkles className="size-5" style={{ color: brandSecondary }} />
                  <h2 className="font-bold">Run through brain</h2>
                </div>
                <Textarea
                  value={prompt}
                  onChange={(event) => setPrompt(event.target.value)}
                  rows={4}
                  disabled={!shop?.id || isStreaming}
                />
                <Button
                  onClick={handleSubmit}
                  disabled={!shop?.id || !prompt.trim() || isStreaming}
                  className="self-start"
                >
                  {isStreaming ? <RefreshCw data-icon="inline-start" className="animate-spin" /> : <Send data-icon="inline-start" />}
                  {isStreaming ? "Running" : "Send"}
                </Button>
                {assistantText && (
                  <div
                    className="rounded-lg border p-3 text-sm"
                    style={{
                      borderColor: `color-mix(in srgb, ${brandPrimary} 12%, transparent)`,
                      background: `color-mix(in srgb, ${brandPrimary} 6%, transparent)`,
                    }}
                  >
                    <p className="text-xs text-muted-foreground">Latest response</p>
                    <p className="mt-1">{assistantText}</p>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card style={{ borderColor: `color-mix(in srgb, ${brandPrimary} 16%, transparent)` }}>
              <CardContent className="flex flex-col gap-3 p-4">
                <h2 className="font-bold">Live signals</h2>
                <Separator />
                <div className="flex max-h-[430px] flex-col gap-3 overflow-y-auto pr-1">
                  {allEvents.length === 0 && (
                    <p className="text-sm text-muted-foreground">Waiting for real-time agent activity.</p>
                  )}
                  {allEvents.slice(0, 14).map((event) => (
                    <div
                      key={event.id || `${event.type}_${event.timestamp}_${event.title}`}
                      className="border-l-2 pl-3"
                      style={{ borderColor: eventMatchesBriefing(event) ? "#0ea5e9" : brandPrimary }}
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant="secondary">{event.type.replace(/_/g, " ")}</Badge>
                        <span className="text-xs text-muted-foreground">{formatTime(event.timestamp)}</span>
                      </div>
                      <p className="mt-1 text-sm font-semibold">{event.title}</p>
                      <p className="text-sm text-muted-foreground">{event.description}</p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card style={{ borderColor: `color-mix(in srgb, ${brandPrimary} 16%, transparent)` }}>
              <CardContent className="p-4">
                <h2 className="mb-2 font-bold">Brain state</h2>
                <div className="flex flex-col gap-2 text-sm text-muted-foreground">
                  <p>Morning heartbeat: 08:00 UTC</p>
                  <p>Evening wrap-up: 20:00 UTC</p>
                  <p>SOUL storage: Postgres foundation ready</p>
                  <p>Commitment auto-action: approval gated</p>
                  {localInsights.length > 0 && <p>New insights this session: {localInsights.length}</p>}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AgentBrainPage;
