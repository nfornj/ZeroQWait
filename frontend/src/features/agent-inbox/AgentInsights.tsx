import React, { useMemo } from "react";
import {
  alpha,
  Card,
  CardContent,
  Chip,
  Grid,
  Stack,
  Typography,
  useTheme,
} from "@mui/material";
import PsychologyRoundedIcon from "@mui/icons-material/PsychologyRounded";
import BoltRoundedIcon from "@mui/icons-material/BoltRounded";
import GppMaybeRoundedIcon from "@mui/icons-material/GppMaybeRounded";
import { BarChart } from "@mui/x-charts/BarChart";
import { SparkLineChart } from "@mui/x-charts/SparkLineChart";
import type { AgentFeedEvent, ChatMessage, PendingApproval } from "./types";
import { useShop } from "../../contexts/ShopContext";

interface AgentInsightsProps {
  messages: ChatMessage[];
  events: AgentFeedEvent[];
  pendingApprovals: PendingApproval[];
}

const AgentInsights: React.FC<AgentInsightsProps> = ({ messages, events, pendingApprovals }) => {
  const muiTheme = useTheme();
  const { shop } = useShop();
  const brandPrimary = shop?.primary_color || muiTheme.palette.primary.main;
  const brandSecondary = shop?.secondary_color || brandPrimary;
  const cardBg =
    muiTheme.palette.mode === "dark"
      ? "rgba(255, 255, 255, 0.05)"
      : alpha("#ffffff", 0.68);
  const cardBorder =
    muiTheme.palette.mode === "dark"
      ? alpha(brandPrimary, 0.24)
      : alpha(brandPrimary, 0.16);

  const assistantMessages = useMemo(
    () => messages.filter((m) => m.role === "assistant" && m.content.trim().length > 0),
    [messages]
  );

  const responseLengths = useMemo(
    () => assistantMessages.slice(-12).map((m) => m.content.length),
    [assistantMessages]
  );

  const eventBuckets = useMemo(() => {
    const tracked: AgentFeedEvent["type"][] = [
      "agent_switch",
      "tool_call",
      "tool_result",
      "approval_required",
      "approval_decision",
      "queue_update",
      "error",
    ];

    const counts = new Map<AgentFeedEvent["type"], number>();
    tracked.forEach((t) => counts.set(t, 0));

    events.slice(0, 40).forEach((event) => {
      if (counts.has(event.type)) {
        counts.set(event.type, (counts.get(event.type) || 0) + 1);
      }
    });

    return {
      labels: tracked.map((t) => t.replace(/_/g, " ")),
      values: tracked.map((t) => counts.get(t) || 0),
    };
  }, [events]);

  return (
    <Card
      variant="outlined"
      sx={{
        borderRadius: 3,
        borderColor: cardBorder,
        bgcolor: cardBg,
        backdropFilter: "blur(20px)",
        boxShadow: `0 18px 50px ${alpha(brandPrimary, 0.08)}`,
      }}
    >
      <CardContent>
        <Stack direction="row" justifyContent="space-between" alignItems="center" mb={1}>
          <Typography variant="h6">Context Snapshot</Typography>
          <Chip
            size="small"
            label="Live"
            sx={{
              bgcolor: brandPrimary,
              color: muiTheme.palette.getContrastText(brandPrimary),
              fontWeight: 700,
            }}
          />
        </Stack>

        <Typography variant="body2" color="text.secondary" mb={2}>
          A lightweight view of activity, approvals, and response patterns around the current chat context.
        </Typography>

        <Grid container spacing={1.25} mb={2}>
          <Grid size={{ xs: 12, sm: 4 }}>
            <Card
              variant="outlined"
              sx={{
                borderRadius: 2,
                borderColor: alpha(brandPrimary, 0.16),
                bgcolor: alpha(brandPrimary, 0.05),
              }}
            >
              <CardContent sx={{ py: 1.5 }}>
                <Stack direction="row" spacing={1} alignItems="center" mb={0.5}>
                  <PsychologyRoundedIcon fontSize="small" sx={{ color: brandPrimary }} />
                  <Typography variant="caption" color="text.secondary">
                    Assistant Replies
                  </Typography>
                </Stack>
                <Typography variant="h6">{assistantMessages.length}</Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid size={{ xs: 12, sm: 4 }}>
            <Card
              variant="outlined"
              sx={{
                borderRadius: 2,
                borderColor: alpha(brandPrimary, 0.16),
                bgcolor: alpha(brandPrimary, 0.05),
              }}
            >
              <CardContent sx={{ py: 1.5 }}>
                <Stack direction="row" spacing={1} alignItems="center" mb={0.5}>
                  <BoltRoundedIcon fontSize="small" sx={{ color: brandSecondary }} />
                  <Typography variant="caption" color="text.secondary">
                    Tool Events
                  </Typography>
                </Stack>
                <Typography variant="h6">
                  {events.filter((e) => e.type === "tool_call" || e.type === "tool_result").length}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid size={{ xs: 12, sm: 4 }}>
            <Card
              variant="outlined"
              sx={{
                borderRadius: 2,
                borderColor: alpha(brandPrimary, 0.16),
                bgcolor: alpha(brandPrimary, 0.05),
              }}
            >
              <CardContent sx={{ py: 1.5 }}>
                <Stack direction="row" spacing={1} alignItems="center" mb={0.5}>
                  <GppMaybeRoundedIcon fontSize="small" sx={{ color: brandSecondary }} />
                  <Typography variant="caption" color="text.secondary">
                    Pending Approvals
                  </Typography>
                </Stack>
                <Typography variant="h6">{pendingApprovals.length}</Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>

        <Typography variant="subtitle2" sx={{ mb: 1 }}>
          Event Mix (latest 40)
        </Typography>
        <BarChart
          height={170}
          xAxis={[{ scaleType: "band", data: eventBuckets.labels }]}
          series={[{ data: eventBuckets.values, color: brandPrimary, label: "events" }]}
          margin={{ left: 30, right: 10, top: 10, bottom: 50 }}
        />

        <Typography variant="subtitle2" sx={{ mt: 1.5, mb: 0.75 }}>
          Response Length Trend
        </Typography>
        <SparkLineChart
          data={responseLengths.length > 1 ? responseLengths : [0, ...(responseLengths || [])]}
          height={70}
          area
          color={brandSecondary}
          showHighlight
          showTooltip
        />
      </CardContent>
    </Card>
  );
};

export default AgentInsights;
