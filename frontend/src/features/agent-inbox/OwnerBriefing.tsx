import React from "react";
import {
  Alert,
  alpha,
  Button,
  Card,
  CardContent,
  Chip,
  Grid,
  Stack,
  Typography,
  useTheme,
} from "@mui/material";
import AccessTimeRoundedIcon from "@mui/icons-material/AccessTimeRounded";
import GroupsRoundedIcon from "@mui/icons-material/GroupsRounded";
import PendingActionsRoundedIcon from "@mui/icons-material/PendingActionsRounded";
import PointOfSaleRoundedIcon from "@mui/icons-material/PointOfSaleRounded";
import type { BriefingAction, OwnerBriefing as OwnerBriefingData } from "./types";
import { useShop } from "../../contexts/ShopContext";

interface OwnerBriefingProps {
  briefing: OwnerBriefingData | null;
  onAction?: (action: BriefingAction) => void;
}

const formatCurrency = (value: number) =>
  new Intl.NumberFormat("en-CA", {
    style: "currency",
    currency: "CAD",
    maximumFractionDigits: 0,
  }).format(value || 0);

const OwnerBriefingCard: React.FC<{ label: string; value: string; icon: React.ReactNode }> = ({
  label,
  value,
  icon,
}) => {
  const muiTheme = useTheme();
  const { shop } = useShop();
  const brandPrimary = shop?.primary_color || muiTheme.palette.primary.main;

  return (
    <Card
      variant="outlined"
      sx={{
        borderRadius: 2.5,
        borderColor: alpha(brandPrimary, 0.14),
        bgcolor:
          muiTheme.palette.mode === "dark"
            ? "rgba(255,255,255,0.03)"
            : alpha("#ffffff", 0.78),
      }}
    >
      <CardContent sx={{ py: 1.5 }}>
        <Stack direction="row" spacing={1} alignItems="center" mb={0.5}>
          {icon}
          <Typography variant="caption" color="text.secondary">
            {label}
          </Typography>
        </Stack>
        <Typography variant="h6">{value}</Typography>
      </CardContent>
    </Card>
  );
};

const OwnerBriefingPanel: React.FC<OwnerBriefingProps> = ({ briefing, onAction }) => {
  const muiTheme = useTheme();
  const { shop } = useShop();
  const brandPrimary = shop?.primary_color || muiTheme.palette.primary.main;
  const brandSecondary = shop?.secondary_color || brandPrimary;

  if (!briefing) {
    return null;
  }

  return (
    <Card
      variant="outlined"
      sx={{
        borderRadius: 3,
        borderColor: alpha(brandPrimary, 0.16),
        bgcolor:
          muiTheme.palette.mode === "dark"
            ? "rgba(255, 255, 255, 0.05)"
            : alpha("#ffffff", 0.72),
        backdropFilter: "blur(20px)",
      }}
    >
      <CardContent>
        <Stack direction="row" justifyContent="space-between" alignItems="center" mb={1}>
          <Typography variant="h6">Daily Briefing</Typography>
          <Chip
            size="small"
            label={briefing.source === "scheduled" ? "Scheduled" : "Live"}
            sx={{
              bgcolor: alpha(brandSecondary, 0.18),
              color: brandSecondary,
              border: `1px solid ${alpha(brandSecondary, 0.24)}`,
              fontWeight: 700,
            }}
          />
        </Stack>

        <Typography variant="body2" color="text.secondary" mb={2}>
          {briefing.summary}
        </Typography>

        <Grid container spacing={1.25} mb={2}>
          <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
            <OwnerBriefingCard
              label="Queue"
              value={`${briefing.metrics.queue_length} waiting`}
              icon={<AccessTimeRoundedIcon fontSize="small" sx={{ color: brandPrimary }} />}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
            <OwnerBriefingCard
              label="Wait Time"
              value={`${briefing.metrics.estimated_wait_minutes} min`}
              icon={<AccessTimeRoundedIcon fontSize="small" sx={{ color: brandSecondary }} />}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
            <OwnerBriefingCard
              label="Active Staff"
              value={String(briefing.metrics.active_employees)}
              icon={<GroupsRoundedIcon fontSize="small" sx={{ color: brandPrimary }} />}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
            <OwnerBriefingCard
              label="Today Revenue"
              value={formatCurrency(briefing.metrics.today_revenue)}
              icon={<PointOfSaleRoundedIcon fontSize="small" sx={{ color: brandSecondary }} />}
            />
          </Grid>
        </Grid>

        <Stack spacing={1} mb={2}>
          {briefing.alerts.map((alert, index) => (
            <Alert key={`${alert.title}_${index}`} severity={alert.severity} sx={{ borderRadius: 2 }}>
              <Typography variant="subtitle2">{alert.title}</Typography>
              <Typography variant="body2">{alert.body}</Typography>
            </Alert>
          ))}
        </Stack>

        {briefing.actions.length > 0 && (
          <Stack spacing={1.25} mb={2}>
            <Typography variant="subtitle2">Recommended actions</Typography>
            <Stack direction="row" flexWrap="wrap" gap={1}>
              {briefing.actions.map((action, index) => (
                <Button
                  key={`${action.label}_${index}`}
                  size="small"
                  variant="outlined"
                  onClick={() => onAction?.(action)}
                  sx={{
                    borderRadius: 999,
                    borderColor: alpha(brandPrimary, 0.25),
                    color: brandPrimary,
                    textTransform: "none",
                    fontWeight: 700,
                    "&:hover": {
                      borderColor: brandPrimary,
                      bgcolor: alpha(brandPrimary, 0.06),
                    },
                  }}
                >
                  {action.label}
                </Button>
              ))}
            </Stack>
          </Stack>
        )}

        <Stack spacing={0.75}>
          <Stack direction="row" spacing={1} alignItems="center">
            <PendingActionsRoundedIcon fontSize="small" sx={{ color: brandPrimary }} />
            <Typography variant="subtitle2">Recommended next steps</Typography>
          </Stack>
          {briefing.recommendations.map((item, index) => (
            <Typography key={`${item}_${index}`} variant="body2" color="text.secondary">
              {index + 1}. {item}
            </Typography>
          ))}
        </Stack>

        {briefing.alert_history && briefing.alert_history.length > 1 && (
          <Stack spacing={0.5} mt={2}>
            <Typography variant="caption" color="text.secondary">
              Recent operational alerts
            </Typography>
            {briefing.alert_history.slice(0, 2).map((alert, index) => (
              <Typography key={`${alert.title}_${index}_history`} variant="caption" color="text.secondary">
                {alert.title}
              </Typography>
            ))}
          </Stack>
        )}
      </CardContent>
    </Card>
  );
};

export default OwnerBriefingPanel;