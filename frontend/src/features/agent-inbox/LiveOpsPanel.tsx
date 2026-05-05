import React, { useMemo } from "react";
import {
  alpha,
  Box,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Divider,
  IconButton,
  Skeleton,
  Stack,
  Tooltip,
  Typography,
  useTheme,
} from "@mui/material";
import AccessTimeRoundedIcon from "@mui/icons-material/AccessTimeRounded";
import BoltRoundedIcon from "@mui/icons-material/BoltRounded";
import CheckCircleOutlineRoundedIcon from "@mui/icons-material/CheckCircleOutlineRounded";
import EventNoteRoundedIcon from "@mui/icons-material/EventNoteRounded";
import GroupsRoundedIcon from "@mui/icons-material/GroupsRounded";
import PeopleAltRoundedIcon from "@mui/icons-material/PeopleAltRounded";
import RefreshRoundedIcon from "@mui/icons-material/RefreshRounded";
import ScheduleRoundedIcon from "@mui/icons-material/ScheduleRounded";
import type {
  AppointmentRecord,
  EmployeeAvailabilityRecord,
  QueueMetricsSnapshot,
} from "./ownerDashboardQueries";
import { useShop } from "../../contexts/ShopContext";

interface LiveOpsPanelProps {
  queueMetrics?: QueueMetricsSnapshot;
  appointments?: AppointmentRecord[];
  employeeAvailability?: EmployeeAvailabilityRecord[];
  stats: {
    waiting: number;
    etaMinutes: number;
    clockedInEmployees: number;
    totalEmployees: number;
    confirmedAppointments: number;
    activeAppointments: number;
  };
  isLoading?: boolean;
  isFetching?: boolean;
  onRefresh?: () => void;
  /** Called when the owner clicks a contextual quick-action chip */
  onQuickAction?: (message: string) => void;
}

const APPOINTMENT_STATUS_COLOR: Record<
  string,
  "default" | "primary" | "secondary" | "success" | "warning" | "error" | "info"
> = {
  scheduled: "default",
  confirmed: "primary",
  checked_in: "warning",
  in_progress: "success",
  completed: "default",
  cancelled: "error",
  no_show: "error",
};

const APPOINTMENT_STATUS_LABEL: Record<string, string> = {
  scheduled: "Scheduled",
  confirmed: "Confirmed",
  checked_in: "Checked In",
  in_progress: "In Progress",
  completed: "Done",
  cancelled: "Cancelled",
  no_show: "No Show",
};

const formatTime = (iso: string): string => {
  try {
    return new Date(iso).toLocaleTimeString("en-CA", {
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    });
  } catch {
    return "—";
  }
};

const StatChip: React.FC<{
  label: string;
  value: number | string;
  icon: React.ReactNode;
  color?: "default" | "primary" | "success" | "warning" | "error";
}> = ({ label, value, icon, color = "default" }) => {
  const muiTheme = useTheme();
  const { shop } = useShop();
  const brandPrimary = shop?.primary_color || muiTheme.palette.primary.main;

  const bgMap = {
    default:
      muiTheme.palette.mode === "dark"
        ? "rgba(255,255,255,0.06)"
        : alpha(muiTheme.palette.grey[100], 0.8),
    primary: alpha(brandPrimary, 0.12),
    success: alpha(muiTheme.palette.success.main, 0.12),
    warning: alpha(muiTheme.palette.warning.main, 0.12),
    error: alpha(muiTheme.palette.error.main, 0.12),
  };

  const fgMap = {
    default: muiTheme.palette.text.secondary,
    primary: brandPrimary,
    success: muiTheme.palette.success.dark,
    warning: muiTheme.palette.warning.dark,
    error: muiTheme.palette.error.dark,
  };

  return (
    <Box
      sx={{
        flex: 1,
        bgcolor: bgMap[color],
        borderRadius: 2,
        px: 1.25,
        py: 1,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 0.25,
      }}
    >
      <Box sx={{ color: fgMap[color], display: "flex", alignItems: "center" }}>{icon}</Box>
      <Typography variant="h6" fontWeight={700} color={fgMap[color]} lineHeight={1}>
        {value}
      </Typography>
      <Typography variant="caption" color="text.secondary" textAlign="center" lineHeight={1.2}>
        {label}
      </Typography>
    </Box>
  );
};

/** Derive up to 3 contextually relevant quick-action prompts from live ops stats. */
function buildQuickActions(stats: LiveOpsPanelProps["stats"]): { label: string; prompt: string }[] {
  const actions: { label: string; prompt: string }[] = [];

  if (stats.clockedInEmployees === 0 && stats.totalEmployees > 0) {
    actions.push({
      label: "No staff clocked in",
      prompt: "No staff are clocked in right now. What are my options to handle service today?",
    });
  }

  if (stats.waiting >= 8) {
    actions.push({
      label: "Queue is very long",
      prompt: `The queue has ${stats.waiting} people waiting. What should I do to manage this backlog?`,
    });
  } else if (stats.waiting >= 4) {
    actions.push({
      label: "Queue is building up",
      prompt: `There are ${stats.waiting} people waiting in the queue. Should I notify them about the wait?`,
    });
  }

  if (stats.etaMinutes > 25) {
    actions.push({
      label: `ETA ${stats.etaMinutes} min — notify?`,
      prompt: `Wait time is currently ${stats.etaMinutes} minutes. Can you send a friendly heads-up to customers in the queue?`,
    });
  }

  if (stats.waiting === 0 && stats.clockedInEmployees > 0) {
    actions.push({
      label: "Queue empty — promote walk-ins",
      prompt: "The queue is empty but staff are available. How can I attract more walk-in customers right now?",
    });
  }

  if (stats.confirmedAppointments > 0) {
    actions.push({
      label: `${stats.confirmedAppointments} appointment${stats.confirmedAppointments === 1 ? "" : "s"} today`,
      prompt: "Give me a quick rundown of today's scheduled appointments.",
    });
  }

  // Always offer a revenue check
  actions.push({
    label: "Today's revenue so far",
    prompt: "What's today's revenue so far?",
  });

  return actions.slice(0, 3);
}

const LiveOpsPanel: React.FC<LiveOpsPanelProps> = ({
  queueMetrics,
  appointments = [],
  employeeAvailability = [],
  stats,
  isLoading = false,
  isFetching = false,
  onRefresh,
  onQuickAction,
}) => {
  const muiTheme = useTheme();
  const { shop } = useShop();
  const brandPrimary = shop?.primary_color || muiTheme.palette.primary.main;

  const upcomingAppointments = useMemo(
    () =>
      appointments
        .filter((a) =>
          ["scheduled", "confirmed", "checked_in", "in_progress"].includes(a.status)
        )
        .sort(
          (a, b) =>
            new Date(a.scheduled_start).getTime() - new Date(b.scheduled_start).getTime()
        )
        .slice(0, 5),
    [appointments]
  );

  const peopleBeingServed = queueMetrics?.people_being_served ?? 0;

  const quickActions = useMemo(() => buildQuickActions(stats), [stats]);

  return (
    <Card
      variant="outlined"
      sx={{
        borderRadius: 3,
        borderColor: alpha(brandPrimary, 0.14),
        bgcolor:
          muiTheme.palette.mode === "dark"
            ? "rgba(255,255,255,0.03)"
            : alpha("#ffffff", 0.78),
        flexShrink: 0,
      }}
    >
      <CardContent sx={{ p: "12px !important" }}>
        {/* Header */}
        <Stack direction="row" alignItems="center" justifyContent="space-between" mb={1.25}>
          <Stack direction="row" spacing={0.75} alignItems="center">
            <PeopleAltRoundedIcon sx={{ fontSize: 15, color: brandPrimary }} />
            <Typography variant="caption" fontWeight={700} color="text.primary" letterSpacing={0.5}>
              LIVE OPERATIONS
            </Typography>
            {isFetching && !isLoading && (
              <CircularProgress size={10} thickness={5} sx={{ color: brandPrimary }} />
            )}
          </Stack>
          {onRefresh && (
            <Tooltip title="Refresh">
              <IconButton size="small" onClick={onRefresh} sx={{ p: 0.25 }}>
                <RefreshRoundedIcon sx={{ fontSize: 14 }} />
              </IconButton>
            </Tooltip>
          )}
        </Stack>

        {/* Queue stat chips */}
        {isLoading ? (
          <Stack direction="row" spacing={0.75} mb={1.25}>
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} variant="rounded" width="100%" height={60} sx={{ borderRadius: 2 }} />
            ))}
          </Stack>
        ) : (
          <Stack direction="row" spacing={0.75} mb={1.25}>
            <StatChip
              label="Waiting"
              value={stats.waiting}
              icon={<ScheduleRoundedIcon sx={{ fontSize: 14 }} />}
              color={stats.waiting > 5 ? "warning" : "primary"}
            />
            <StatChip
              label="Serving"
              value={peopleBeingServed}
              icon={<CheckCircleOutlineRoundedIcon sx={{ fontSize: 14 }} />}
              color={peopleBeingServed > 0 ? "success" : "default"}
            />
            <StatChip
              label="ETA (min)"
              value={stats.etaMinutes > 0 ? stats.etaMinutes : "—"}
              icon={<AccessTimeRoundedIcon sx={{ fontSize: 14 }} />}
              color="default"
            />
            <StatChip
              label="Staff In"
              value={`${stats.clockedInEmployees}/${stats.totalEmployees}`}
              icon={<GroupsRoundedIcon sx={{ fontSize: 14 }} />}
              color={stats.clockedInEmployees === 0 && stats.totalEmployees > 0 ? "error" : "default"}
            />
          </Stack>
        )}

        {/* Today's Appointments */}
        <Stack direction="row" spacing={0.5} alignItems="center" mb={0.75}>
          <EventNoteRoundedIcon sx={{ fontSize: 13, color: "text.secondary" }} />
          <Typography variant="caption" color="text.secondary" fontWeight={600}>
            Today's Appointments
          </Typography>
          <Chip
            label={stats.confirmedAppointments}
            size="small"
            sx={{ height: 16, fontSize: 10, "& .MuiChip-label": { px: 0.75 } }}
          />
        </Stack>

        {isLoading ? (
          <Stack spacing={0.5} mb={1}>
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} variant="rounded" width="100%" height={32} sx={{ borderRadius: 1.5 }} />
            ))}
          </Stack>
        ) : upcomingAppointments.length === 0 ? (
          <Typography variant="caption" color="text.disabled" sx={{ display: "block", mb: 1, pl: 0.5 }}>
            No upcoming appointments today
          </Typography>
        ) : (
          <Stack spacing={0.5} mb={1}>
            {upcomingAppointments.map((appt) => (
              <Stack
                key={appt.id}
                direction="row"
                alignItems="center"
                justifyContent="space-between"
                sx={{
                  px: 1,
                  py: 0.5,
                  borderRadius: 1.5,
                  bgcolor:
                    muiTheme.palette.mode === "dark"
                      ? "rgba(255,255,255,0.04)"
                      : alpha(muiTheme.palette.grey[100], 0.6),
                }}
              >
                <Box sx={{ minWidth: 0, flex: 1 }}>
                  <Typography variant="caption" fontWeight={600} noWrap>
                    {appt.customer_name}
                  </Typography>
                  <Typography variant="caption" color="text.secondary" display="block">
                    {formatTime(appt.scheduled_start)}
                  </Typography>
                </Box>
                <Chip
                  label={APPOINTMENT_STATUS_LABEL[appt.status] ?? appt.status}
                  color={APPOINTMENT_STATUS_COLOR[appt.status] ?? "default"}
                  size="small"
                  sx={{
                    height: 18,
                    fontSize: 9,
                    fontWeight: 600,
                    "& .MuiChip-label": { px: 0.75 },
                  }}
                />
              </Stack>
            ))}
          </Stack>
        )}

        {/* Employee availability */}
        {employeeAvailability.length > 0 && (
          <>
            <Divider sx={{ my: 0.75 }} />
            <Typography variant="caption" color="text.secondary" fontWeight={600} sx={{ display: "block", mb: 0.5 }}>
              Team
            </Typography>
            <Stack spacing={0.5}>
              {employeeAvailability.slice(0, 4).map((emp) => (
                <Stack
                  key={emp.employee_id}
                  direction="row"
                  alignItems="center"
                  justifyContent="space-between"
                >
                  <Typography variant="caption" noWrap sx={{ flex: 1 }}>
                    {emp.username}
                  </Typography>
                  <Stack direction="row" spacing={0.5} alignItems="center">
                    {emp.appointments_today > 0 && (
                      <Typography variant="caption" color="text.disabled">
                        {emp.appointments_today} appt{emp.appointments_today !== 1 ? "s" : ""}
                      </Typography>
                    )}
                    <Box
                      sx={{
                        width: 7,
                        height: 7,
                        borderRadius: "50%",
                        bgcolor: emp.is_clocked_in
                          ? muiTheme.palette.success.main
                          : muiTheme.palette.grey[400],
                      }}
                    />
                  </Stack>
                </Stack>
              ))}
              {employeeAvailability.length > 4 && (
                <Typography variant="caption" color="text.disabled">
                  +{employeeAvailability.length - 4} more
                </Typography>
              )}
            </Stack>
          </>
        )}

        {/* Contextual quick-action prompts */}
        {!isLoading && onQuickAction && quickActions.length > 0 && (
          <>
            <Divider sx={{ my: 0.75 }} />
            <Stack direction="row" spacing={0.5} alignItems="center" mb={0.5}>
              <BoltRoundedIcon sx={{ fontSize: 12, color: brandPrimary }} />
              <Typography variant="caption" color="text.secondary" fontWeight={600}>
                Quick actions
              </Typography>
            </Stack>
            <Stack direction="row" flexWrap="wrap" gap={0.5}>
              {quickActions.map((action) => (
                <Chip
                  key={action.label}
                  label={action.label}
                  size="small"
                  clickable
                  onClick={() => onQuickAction(action.prompt)}
                  sx={{
                    height: 22,
                    fontSize: 10,
                    fontWeight: 600,
                    borderRadius: 999,
                    bgcolor: alpha(brandPrimary, 0.09),
                    color: brandPrimary,
                    border: `1px solid ${alpha(brandPrimary, 0.2)}`,
                    "& .MuiChip-label": { px: 1 },
                    "&:hover": { bgcolor: alpha(brandPrimary, 0.16) },
                    cursor: "pointer",
                  }}
                />
              ))}
            </Stack>
          </>
        )}
      </CardContent>
    </Card>
  );
};

export default LiveOpsPanel;
