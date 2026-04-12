import React from "react";
import {
  alpha,
  Box,
  Card,
  CardContent,
  Chip,
  Divider,
  Stack,
  Typography,
  useTheme,
} from "@mui/material";
import type { AgentFeedEvent } from "./types";
import { useShop } from "../../contexts/ShopContext";

interface AgentFeedProps {
  events: AgentFeedEvent[];
}

const typeColorMap: Record<AgentFeedEvent["type"], "default" | "primary" | "success" | "warning" | "error" | "info"> = {
  chat: "default",
  agent_switch: "info",
  tool_call: "primary",
  tool_result: "success",
  approval_required: "warning",
  approval_decision: "success",
  queue_update: "info",
  error: "error",
  system: "default",
};

const AgentFeed: React.FC<AgentFeedProps> = ({ events }) => {
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

  return (
    <Card
      variant="outlined"
      sx={{
        borderRadius: 3,
        minHeight: 320,
        borderColor: cardBorder,
        bgcolor: cardBg,
        backdropFilter: "blur(20px)",
        boxShadow: `0 18px 50px ${alpha(brandPrimary, 0.08)}`,
      }}
    >
      <CardContent>
        <Typography variant="h6" mb={1}>
          Activity Feed
        </Typography>
        <Typography variant="body2" color="text.secondary" mb={2}>
          Background timeline of orchestration events and live shop updates.
        </Typography>

        <Stack spacing={1.25} sx={{ maxHeight: 320, overflowY: "auto", pr: 0.5 }}>
          {events.length === 0 ? (
            <Box py={2}>
              <Typography variant="body2" color="text.secondary">
                No activity yet. Send a message to start the feed.
              </Typography>
            </Box>
          ) : (
            events.map((event, index) => (
              <React.Fragment key={event.id}>
                <Stack direction="row" spacing={1} alignItems="flex-start" justifyContent="space-between">
                  <Box sx={{ flex: 1, minWidth: 0 }}>
                    <Stack direction="row" spacing={1} alignItems="center" mb={0.5}>
                          <Chip
                            size="small"
                            label={event.type.replace(/_/g, " ")}
                            color={typeColorMap[event.type]}
                            sx={event.type === "system" || event.type === "chat"
                              ? {
                                  bgcolor: alpha(brandPrimary, 0.12),
                                  color: brandPrimary,
                                  border: `1px solid ${alpha(brandPrimary, 0.2)}`,
                                }
                              : undefined}
                          />
                      <Typography variant="caption" color="text.secondary">
                        {new Date(event.timestamp).toLocaleTimeString()}
                      </Typography>
                    </Stack>
                        <Typography
                          variant="subtitle2"
                          sx={{ color: event.type === "error" ? muiTheme.palette.error.main : brandSecondary }}
                        >
                          {event.title}
                        </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {event.description}
                    </Typography>
                  </Box>
                </Stack>
                    {index < events.length - 1 && <Divider sx={{ borderColor: alpha(brandPrimary, 0.12) }} />}
              </React.Fragment>
            ))
          )}
        </Stack>
      </CardContent>
    </Card>
  );
};

export default AgentFeed;
