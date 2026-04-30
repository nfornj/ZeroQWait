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
import { keyframes } from "@mui/material/styles";
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

const pulse = keyframes`
  0% { transform: scale(1); box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.28); }
  70% { transform: scale(1.02); box-shadow: 0 0 0 12px rgba(34, 197, 94, 0); }
  100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); }
`;

const flowDash = keyframes`
  from { stroke-dashoffset: 28; }
  to { stroke-dashoffset: 0; }
`;

const glow = keyframes`
  0%, 100% { opacity: 0.62; }
  50% { opacity: 1; }
`;

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

interface BrainNodeConfig {
  id: BrainNodeId;
  label: string;
  subtitle: string;
  x: number;
  y: number;
  color: string;
  icon: React.ReactNode;
}

interface BrainEdgeConfig {
  id: string;
  from: BrainNodeId;
  to: BrainNodeId;
  label: string;
}

interface PositionedNode extends BrainNodeConfig {
  active: boolean;
  statusText: string;
}

const nodeW = 170;
const nodeH = 78;

const nodeCenter = (node: BrainNodeConfig) => ({
  x: node.x + nodeW / 2,
  y: node.y + nodeH / 2,
});

const pathForEdge = (from: BrainNodeConfig, to: BrainNodeConfig) => {
  const start = nodeCenter(from);
  const end = nodeCenter(to);
  const midX = (start.x + end.x) / 2;
  const curve = Math.max(40, Math.abs(start.x - end.x) / 3);
  return `M ${start.x} ${start.y} C ${midX - curve / 2} ${start.y}, ${midX + curve / 2} ${end.y}, ${end.x} ${end.y}`;
};

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

const AgentBrainPage: React.FC = () => {
  const theme = useTheme();
  const queryClient = useQueryClient();
  const { shop, loading: shopLoading } = useShop();
  const brandPrimary = shop?.primary_color || theme.palette.primary.main;
  const brandSecondary = shop?.secondary_color || theme.palette.secondary.main;
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

  useEffect(() => {
    const next: Record<string, number> = {};
    activeEdgeIds.forEach((edgeId) => {
      edgeId.split("-").forEach((part) => {
        next[part] = Date.now();
      });
    });
    if (Object.keys(next).length > 0) {
      setNodePulse((prev) => ({ ...prev, ...next }));
    }
  }, [activeEdgeIds]);

  const nodes = useMemo<BrainNodeConfig[]>(() => [
    { id: "owner", label: "Owner", subtitle: "Commands and approvals", x: 32, y: 228, color: brandPrimary, icon: <StorefrontRoundedIcon /> },
    { id: "temporal", label: "Temporal", subtitle: "Morning and evening heartbeats", x: 32, y: 48, color: "#0ea5e9", icon: <AccessTimeRoundedIcon /> },
    { id: "supervisor", label: "Supervisor", subtitle: "Routes the agent team", x: 330, y: 162, color: "#22c55e", icon: <HubRoundedIcon /> },
    { id: "soul", label: "SOUL", subtitle: "Shop identity memory", x: 330, y: 328, color: "#a855f7", icon: <PsychologyRoundedIcon /> },
    { id: "receptionist", label: "Receptionist", subtitle: "Queue and bookings", x: 640, y: 36, color: "#14b8a6", icon: <ContentCutRoundedIcon /> },
    { id: "finance", label: "Finance", subtitle: "Revenue and reports", x: 640, y: 142, color: "#f59e0b", icon: <PointOfSaleRoundedIcon /> },
    { id: "hr", label: "HR", subtitle: "Staff and shifts", x: 640, y: 248, color: "#ef4444", icon: <GroupsRoundedIcon /> },
    { id: "crm", label: "CRM", subtitle: "Contacts and pipeline", x: 640, y: 354, color: "#6366f1", icon: <AccountTreeRoundedIcon /> },
    { id: "tools", label: "MCP Tools", subtitle: "Booking, Finance, HR, CRM", x: 944, y: 116, color: "#64748b", icon: <ToolRoundedIcon /> },
    { id: "commitments", label: "Commitments", subtitle: "Follow-ups and promises", x: 944, y: 222, color: "#ec4899", icon: <PendingActionsRoundedIcon /> },
    { id: "schedules", label: "Schedules", subtitle: "Natural language cron", x: 944, y: 328, color: "#06b6d4", icon: <EventRepeatRoundedIcon /> },
    { id: "data", label: "Postgres + Redis", subtitle: "Durable and short memory", x: 330, y: 478, color: "#475569", icon: <StorageRoundedIcon /> },
  ], [brandPrimary]);

  const nodeById = useMemo(() => new Map(nodes.map((node) => [node.id, node])), [nodes]);

  const edges = useMemo<BrainEdgeConfig[]>(() => [
    { id: "owner-supervisor", from: "owner", to: "supervisor", label: "message" },
    { id: "supervisor-owner", from: "supervisor", to: "owner", label: "answer / approval" },
    { id: "temporal-supervisor", from: "temporal", to: "supervisor", label: "scheduled run" },
    { id: "supervisor-receptionist", from: "supervisor", to: "receptionist", label: "booking" },
    { id: "supervisor-finance", from: "supervisor", to: "finance", label: "finance" },
    { id: "supervisor-hr", from: "supervisor", to: "hr", label: "staff" },
    { id: "supervisor-crm", from: "supervisor", to: "crm", label: "crm" },
    { id: "supervisor-soul", from: "supervisor", to: "soul", label: "context" },
    { id: "supervisor-data", from: "supervisor", to: "data", label: "state" },
    { id: "receptionist-tools", from: "receptionist", to: "tools", label: "booking tools" },
    { id: "finance-tools", from: "finance", to: "tools", label: "finance tools" },
    { id: "hr-tools", from: "hr", to: "tools", label: "hr tools" },
    { id: "crm-tools", from: "crm", to: "tools", label: "crm tools" },
    { id: "supervisor-tools", from: "supervisor", to: "tools", label: "direct tool" },
    { id: "temporal-schedules", from: "temporal", to: "schedules", label: "cron" },
    { id: "temporal-commitments", from: "temporal", to: "commitments", label: "due date" },
    { id: "commitments-supervisor", from: "commitments", to: "supervisor", label: "follow-up" },
    { id: "soul-data", from: "soul", to: "data", label: "persist" },
  ], []);

  const positionedNodes = useMemo<PositionedNode[]>(() => {
    const pendingCount = (pendingQuery.data || []).length + localApprovals.length;
    const latestEvent = allEvents[0];
    return nodes.map((node) => {
      const active = Boolean(nodePulse[node.id] && Date.now() - nodePulse[node.id] < 6000);
      const statusText = (() => {
        if (node.id === "temporal") return briefingQuery.data?.source === "scheduled" ? "briefing generated" : "schedules armed";
        if (node.id === "supervisor") return isStreaming ? "thinking" : latestEvent ? "listening" : "idle";
        if (node.id === "owner") return pendingCount > 0 ? `${pendingCount} approval${pendingCount === 1 ? "" : "s"}` : "in control";
        if (node.id === "soul") return "foundation ready";
        if (node.id === "commitments") return "scanner next";
        if (node.id === "schedules") return "2 heartbeats";
        if (node.id === "data") return `${allEvents.length} recent events`;
        return active ? "working" : "ready";
      })();
      return { ...node, active, statusText };
    });
  }, [allEvents, briefingQuery.data?.source, isStreaming, localApprovals.length, nodePulse, nodes, pendingQuery.data]);

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
            <Chip label={briefingQuery.data?.source === "scheduled" ? "Temporal active" : "Temporal armed"} size="small" sx={{ borderColor: alpha("#0ea5e9", 0.35), color: "#0284c7" }} variant="outlined" />
          </Stack>
        </Stack>

        {error && <Alert severity="warning" sx={{ borderRadius: 2 }}>{error}</Alert>}
        {shopLoading && <Alert severity="info" sx={{ borderRadius: 2 }}>Loading active shop context...</Alert>}

        <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", xl: "minmax(0, 1fr) 360px" }, gap: 2 }}>
          <Paper
            variant="outlined"
            sx={{
              position: "relative",
              minHeight: { xs: 620, md: 690 },
              overflow: "hidden",
              borderRadius: 3,
              borderColor: alpha(brandPrimary, 0.16),
              bgcolor: theme.palette.mode === "dark" ? alpha("#020617", 0.76) : alpha("#ffffff", 0.8),
            }}
          >
            <Box sx={{ position: "absolute", inset: 0, overflow: "auto" }}>
              <Box sx={{ position: "relative", width: 1160, height: 690 }}>
                <svg width="1160" height="690" style={{ position: "absolute", inset: 0, pointerEvents: "none" }}>
                  <defs>
                    <marker id="brain-arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">
                      <path d="M0,0 L0,6 L9,3 z" fill={alpha(theme.palette.text.secondary, 0.6)} />
                    </marker>
                    <marker id="brain-arrow-active" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">
                      <path d="M0,0 L0,6 L9,3 z" fill="#22c55e" />
                    </marker>
                  </defs>
                  {edges.map((edge) => {
                    const from = nodeById.get(edge.from);
                    const to = nodeById.get(edge.to);
                    if (!from || !to) return null;
                    const active = activeEdgeIds.has(edge.id);
                    const path = pathForEdge(from, to);
                    const mid = nodeCenter({ ...from, x: (from.x + to.x) / 2, y: (from.y + to.y) / 2 });
                    return (
                      <g key={edge.id}>
                        <path
                          d={path}
                          fill="none"
                          stroke={active ? "#22c55e" : alpha(theme.palette.text.secondary, 0.22)}
                          strokeWidth={active ? 3 : 1.5}
                          strokeDasharray={active ? "10 8" : "0"}
                          markerEnd={`url(#${active ? "brain-arrow-active" : "brain-arrow"})`}
                          style={active ? { animation: `${flowDash} 900ms linear infinite` } : undefined}
                        />
                        {active && <circle r="4" fill="#22c55e" style={{ offsetPath: `path('${path}')`, animation: `${flowDash} 900ms linear infinite` } as React.CSSProperties} />}
                        <text x={mid.x} y={mid.y - 6} fill={alpha(theme.palette.text.secondary, 0.7)} fontSize="11" textAnchor="middle">
                          {edge.label}
                        </text>
                      </g>
                    );
                  })}
                </svg>

                {positionedNodes.map((node) => (
                  <Paper
                    key={node.id}
                    elevation={0}
                    sx={{
                      position: "absolute",
                      left: node.x,
                      top: node.y,
                      width: nodeW,
                      minHeight: nodeH,
                      borderRadius: 2.5,
                      p: 1.25,
                      border: "1px solid",
                      borderColor: node.active ? alpha(node.color, 0.72) : alpha(node.color, 0.22),
                      bgcolor: theme.palette.mode === "dark" ? alpha(node.color, node.active ? 0.18 : 0.1) : alpha("#ffffff", 0.9),
                      animation: node.active ? `${pulse} 1.8s ease-out infinite` : undefined,
                    }}
                  >
                    <Stack direction="row" spacing={1} alignItems="center" mb={0.75}>
                      <Box sx={{ width: 32, height: 32, borderRadius: 2, display: "grid", placeItems: "center", color: node.color, bgcolor: alpha(node.color, 0.14) }}>
                        {node.icon}
                      </Box>
                      <Box sx={{ minWidth: 0 }}>
                        <Typography variant="subtitle2" fontWeight={800} noWrap>{node.label}</Typography>
                        <Typography variant="caption" color="text.secondary" noWrap>{node.subtitle}</Typography>
                      </Box>
                    </Stack>
                    <Chip
                      size="small"
                      label={node.statusText}
                      sx={{
                        height: 22,
                        maxWidth: "100%",
                        color: node.active ? node.color : theme.palette.text.secondary,
                        bgcolor: alpha(node.color, node.active ? 0.16 : 0.08),
                        animation: node.active ? `${glow} 1.4s ease-in-out infinite` : undefined,
                      }}
                    />
                  </Paper>
                ))}
              </Box>
            </Box>
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
                    <Box key={event.id || `${event.type}_${event.timestamp}_${event.title}`} sx={{ borderLeft: `3px solid ${eventMatchesBriefing(event) ? "#0ea5e9" : alpha(brandPrimary, 0.5)}`, pl: 1.25 }}>
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
                {localInsights.length > 0 && <Typography variant="body2" color="text.secondary">New insights this session: {localInsights.length}</Typography>}
              </Stack>
            </Paper>
          </Stack>
        </Box>
      </Stack>
    </Box>
  );
};

export default AgentBrainPage;