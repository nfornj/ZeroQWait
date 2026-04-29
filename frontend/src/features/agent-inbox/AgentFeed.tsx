import React from "react";
import {
  alpha,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Divider,
  Skeleton,
  Stack,
  Typography,
  useTheme,
} from "@mui/material";
import type { AgentFeedEvent } from "./types";
import { useShop } from "../../contexts/ShopContext";

type MaxHeightValue = string | number | Record<string, string | number>;

interface AgentFeedProps {
  events: AgentFeedEvent[];
  unreadCount?: number;
  isMarkingAllRead?: boolean;
  markingNotificationId?: number | null;
  onMarkAsRead?: (notificationId: number) => void;
  onMarkAllAsRead?: () => void;
  maxHeight?: MaxHeightValue;
  isLoading?: boolean;
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

const AgentFeed: React.FC<AgentFeedProps> = ({
  events,
  unreadCount = 0,
  isMarkingAllRead = false,
  markingNotificationId = null,
  onMarkAsRead,
  onMarkAllAsRead,
  maxHeight = 160,
  isLoading = false,
}) => {
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
        borderColor: cardBorder,
        bgcolor: cardBg,
        backdropFilter: "blur(20px)",
        boxShadow: `0 18px 50px ${alpha(brandPrimary, 0.08)}`,
      }}
    >
      <CardContent sx={{ py: 1.25, "&:last-child": { pb: 1.25 } }}>
        <Stack direction="row" justifyContent="space-between" alignItems="center" mb={1} spacing={1}>
          <Typography variant="subtitle2" fontWeight={600}>
            Activity Feed
          </Typography>
          <Stack direction="row" spacing={1} alignItems="center">
            {unreadCount > 0 && (
              <Chip
                size="small"
                color="warning"
                label={`${unreadCount} unread`}
                sx={{ fontWeight: 700 }}
              />
            )}
            {onMarkAllAsRead && unreadCount > 0 && (
              <Button
                size="small"
                variant="text"
                disabled={isMarkingAllRead}
                onClick={onMarkAllAsRead}
              >
                {isMarkingAllRead ? "Clearing..." : "Clear unread"}
              </Button>
            )}
          </Stack>
        </Stack>

        <Stack spacing={1} sx={{ maxHeight, overflowY: "auto", pr: 0.5 }}>
          {events.length === 0 ? (
            isLoading ? (
              <Stack spacing={1} py={0.5}>
                {[0, 1, 2].map((i) => <Skeleton key={i} variant="rounded" height={52} sx={{ borderRadius: 1.5 }} />)}
              </Stack>
            ) : (
              <Box py={2}>
                <Typography variant="body2" color="text.secondary">
                  No activity yet. Send a message to start the feed.
                </Typography>
              </Box>
            )
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
                      {event.notification_id && event.status === "unread" && (
                        <Chip size="small" label="unread" color="warning" variant="outlined" />
                      )}
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
                  {event.notification_id && event.status === "unread" && onMarkAsRead && (
                    <Button
                      size="small"
                      variant="text"
                      disabled={markingNotificationId === event.notification_id}
                      onClick={() => onMarkAsRead(event.notification_id as number)}
                      sx={{ minWidth: 90 }}
                    >
                      {markingNotificationId === event.notification_id ? (
                        <CircularProgress size={14} />
                      ) : (
                        "Mark read"
                      )}
                    </Button>
                  )}
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
