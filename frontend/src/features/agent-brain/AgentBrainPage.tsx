import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  Alert,
  alpha,
  Box,
  Button,
  Chip,
  CircularProgress,
  Divider,
  Paper,
  Stack,
  TextField,
  Typography,
  useTheme,
} from "@mui/material";
import AccountTreeRoundedIcon from "@mui/icons-material/AccountTreeRounded";
import AccessTimeRoundedIcon from "@mui/icons-material/AccessTimeRounded";
import AutoAwesomeRoundedIcon from "@mui/icons-material/AutoAwesomeRounded";
import CachedRoundedIcon from "@mui/icons-material/CachedRounded";
import CheckCircleRoundedIcon from "@mui/icons-material/CheckCircleRounded";
import ContentCutRoundedIcon from "@mui/icons-material/ContentCutRounded";
import StorageRoundedIcon from "@mui/icons-material/StorageRounded";
import EventRepeatRoundedIcon from "@mui/icons-material/EventRepeatRounded";
import GroupsRoundedIcon from "@mui/icons-material/GroupsRounded";
import HubRoundedIcon from "@mui/icons-material/HubRounded";
import MemoryRoundedIcon from "@mui/icons-material/MemoryRounded";
import PendingActionsRoundedIcon from "@mui/icons-material/PendingActionsRounded";
import PointOfSaleRoundedIcon from "@mui/icons-material/PointOfSaleRounded";
import PsychologyRoundedIcon from "@mui/icons-material/PsychologyRounded";
import SendRoundedIcon from "@mui/icons-material/SendRounded";
import StorefrontRoundedIcon from "@mui/icons-material/StorefrontRounded";
import ToolRoundedIcon from "@mui/icons-material/BuildRounded";
import { useQueryClient } from "@tanstack/react-query";

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
  { id: "temporal", label: "Temporal", subtitle: "Heartbeats & cron", color: "#0ea5e9", icon: <AccessTimeRoundedIcon />, position: { x: 0, y: 40 }, hasTarget: false },
  { id: "owner", label: "Owner", subtitle: "Commands & approvals", color: "#9333ea", icon: <StorefrontRoundedIcon />, position: { x: 0, y: 280 } },
  { id: "soul", label: "SOUL", subtitle: "Shop identity memory", color: "#a855f7", icon: <PsychologyRoundedIcon />, position: { x: 0, y: 500 } },
  { id: "supervisor", label: "Supervisor", subtitle: "Routes the agent team", color: "#22c55e", icon: <HubRoundedIcon />, position: { x: 320, y: 280 } },
  { id: "receptionist", label: "Receptionist", subtitle: "Queue & bookings", color: "#14b8a6", icon: <ContentCutRoundedIcon />, position: { x: 640, y: 40 } },
  { id: "finance", label: "Finance", subtitle: "Revenue & reports", color: "#f59e0b", icon: <PointOfSaleRoundedIcon />, position: { x: 640, y: 200 } },
  { id: "hr", label: "HR", subtitle: "Staff & shifts", color: "#ef4444", icon: <GroupsRoundedIcon />, position: { x: 640, y: 360 } },
  { id: "crm", label: "CRM", subtitle: "Contacts & pipeline", color: "#6366f1", icon: <AccountTreeRoundedIcon />, position: { x: 640, y: 520 } },
  { id: "tools", label: "MCP Tools", subtitle: "Booking · Finance · HR", color: "#64748b", icon: <ToolRoundedIcon />, position: { x: 960, y: 120 } },
  { id: "commitments", label: "Commitments", subtitle: "Follow-ups & promises", color: "#ec4899", icon: <PendingActionsRoundedIcon />, position: { x: 960, y: 280 } },
  { id: "schedules", label: "Schedules", subtitle: "Natural language cron", color: "#06b6d4", icon: <EventRepeatRoundedIcon />, position: { x: 960, y: 440 } },
  { id: "data", label: "Postgres + Redis", subtitle: "Durable & short memory", color: "#475569", icon: <StorageRoundedIcon />, position: { x: 320, y: 540 }, hasSource: false },
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
  const theme = useTheme();
  const queryClient = useQueryClient();
  const { shop, loading: shopLoading } = useShop();
  const brandPrimary = shop?.primary_color || theme.palette.primary.main;
  const brandSecondary = shop?.secondary_color || theme.palette.secondary.main;
  const isDark = theme.palette.mode === "dark";
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
    <Box sx={{ width: "100%", p: { xs: 1.5, md: 2.5 }, maxWidth: 1500, mx: "auto" }}>
      <Stack spacing={2}>
        <Stack direction={{ xs: "column", md: "row" }} spacing={1.5} alignItems={{ xs: "stretch", md: "center" }} justifyContent="space-between">
          <Box>
            <Stack direction="row" spacing={1} alignItems="center">
              <MemoryRoundedIcon sx={{ color: brandPrimary }} />
              <Typography variant="h5" fontWeight={800}>Agent Brain</Typography>
              <Chip
                size="small"
                icon={connectionStatus === "connected" ? <CheckCircleRoundedIcon /> : <CachedRoundedIcon />}
                label={connectionStatus === "connected" ? "Live" : connectionStatus}
                color={connectionStatus === "connected" ? "success" : "default"}
              />
            </Stack>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              {shop?.name || "Selected shop"} brain runtime: Supervisor, specialists, Temporal, memory, tools, and approvals.
            </Typography>
          </Box>
          <Stack direction="row" spacing={1} flexWrap="wrap" justifyContent={{ xs: "flex-start", md: "flex-end" }}>
            <Chip label={`Feed ${allEvents.length}`} size="small" />
            <Chip label={`Approvals ${(pendingQuery.data || []).length + localApprovals.length}`} size="small" color="warning" variant="outlined" />
            <Chip
              label={briefingQuery.data?.source === "scheduled" ? "Temporal active" : "Temporal armed"}
              size="small"
              sx={{ borderColor: alpha("#0ea5e9", 0.35), color: "#0284c7" }}
              variant="outlined"
            />
          </Stack>
        </Stack>

        {error && <Alert severity="warning" sx={{ borderRadius: 2 }}>{error}</Alert>}
        {shopLoading && <Alert severity="info" sx={{ borderRadius: 2 }}>Loading active shop context...</Alert>}

        <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", xl: "minmax(0, 1fr) 360px" }, gap: 2 }}>
          <Paper
            variant="outlined"
            sx={{
              position: "relative",
              height: { xs: 620, md: 720 },
              overflow: "hidden",
              borderRadius: 3,
              borderColor: alpha(brandPrimary, 0.16),
              bgcolor: isDark ? alpha("#020617", 0.78) : alpha("#f8fafc", 0.9),
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
          </Paper>

          <Stack spacing={2}>
            <Paper variant="outlined" sx={{ borderRadius: 3, p: 2, borderColor: alpha(brandPrimary, 0.16) }}>
              <Stack spacing={1.25}>
                <Stack direction="row" spacing={1} alignItems="center">
                  <AutoAwesomeRoundedIcon sx={{ color: brandSecondary }} />
                  <Typography variant="subtitle1" fontWeight={800}>Run through brain</Typography>
                </Stack>
                <TextField
                  value={prompt}
                  onChange={(event) => setPrompt(event.target.value)}
                  minRows={3}
                  multiline
                  fullWidth
                  size="small"
                  disabled={!shop?.id || isStreaming}
                />
                <Button
                  variant="contained"
                  startIcon={isStreaming ? <CircularProgress color="inherit" size={16} /> : <SendRoundedIcon />}
                  onClick={handleSubmit}
                  disabled={!shop?.id || !prompt.trim() || isStreaming}
                  sx={{ alignSelf: "flex-start", borderRadius: 2 }}
                >
                  {isStreaming ? "Running" : "Send"}
                </Button>
                {assistantText && (
                  <Box sx={{ p: 1.25, borderRadius: 2, bgcolor: alpha(brandPrimary, 0.06), border: `1px solid ${alpha(brandPrimary, 0.12)}` }}>
                    <Typography variant="caption" color="text.secondary">Latest response</Typography>
                    <Typography variant="body2" sx={{ mt: 0.5 }}>{assistantText}</Typography>
                  </Box>
                )}
              </Stack>
            </Paper>

            <Paper variant="outlined" sx={{ borderRadius: 3, p: 2, borderColor: alpha(brandPrimary, 0.16) }}>
              <Stack spacing={1.25}>
                <Typography variant="subtitle1" fontWeight={800}>Live signals</Typography>
                <Divider />
                <Stack spacing={1.1} sx={{ maxHeight: 430, overflowY: "auto", pr: 0.5 }}>
                  {allEvents.length === 0 && (
                    <Typography variant="body2" color="text.secondary">Waiting for real-time agent activity.</Typography>
                  )}
                  {allEvents.slice(0, 14).map((event) => (
                    <Box
                      key={event.id || `${event.type}_${event.timestamp}_${event.title}`}
                      sx={{ borderLeft: `3px solid ${eventMatchesBriefing(event) ? "#0ea5e9" : alpha(brandPrimary, 0.5)}`, pl: 1.25 }}
                    >
                      <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
                        <Chip size="small" label={event.type.replace(/_/g, " ")} />
                        <Typography variant="caption" color="text.secondary">{formatTime(event.timestamp)}</Typography>
                      </Stack>
                      <Typography variant="subtitle2" sx={{ mt: 0.5 }}>{event.title}</Typography>
                      <Typography variant="body2" color="text.secondary">{event.description}</Typography>
                    </Box>
                  ))}
                </Stack>
              </Stack>
            </Paper>

            <Paper variant="outlined" sx={{ borderRadius: 3, p: 2, borderColor: alpha(brandPrimary, 0.16) }}>
              <Typography variant="subtitle1" fontWeight={800} mb={1}>Brain state</Typography>
              <Stack spacing={0.75}>
                <Typography variant="body2" color="text.secondary">Morning heartbeat: 08:00 UTC</Typography>
                <Typography variant="body2" color="text.secondary">Evening wrap-up: 20:00 UTC</Typography>
                <Typography variant="body2" color="text.secondary">SOUL storage: Postgres foundation ready</Typography>
                <Typography variant="body2" color="text.secondary">Commitment auto-action: approval gated</Typography>
                {localInsights.length > 0 && (
                  <Typography variant="body2" color="text.secondary">New insights this session: {localInsights.length}</Typography>
                )}
              </Stack>
            </Paper>
          </Stack>
        </Box>
      </Stack>
    </Box>
  );
};

export default AgentBrainPage;
