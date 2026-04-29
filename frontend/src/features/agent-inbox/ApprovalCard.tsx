import React from "react";
import {
  alpha,
  Box,
  Button,
  Card,
  Chip,
  Stack,
  Typography,
  useTheme,
} from "@mui/material";
import RocketLaunchRoundedIcon from "@mui/icons-material/RocketLaunchRounded";
import type { PendingApproval } from "./types";
import { useShop } from "../../contexts/ShopContext";

interface ApprovalCardProps {
  approval: PendingApproval;
  isSubmitting?: boolean;
  onDecision: (approval: PendingApproval, approved: boolean) => void;
}

const formatPolicyMode = (mode?: string): string => {
  switch (mode) {
    case "require_approval":
      return "Require approval";
    case "allow":
      return "Allow automatically";
    case "notify_only":
      return "Notify after auto-run";
    case "silent":
      return "Silent auto-run";
    case "forbid":
      return "Blocked by policy";
    default:
      return mode ? mode.replace(/_/g, " ") : "Policy controlled";
  }
};

const formatActionLabel = (action?: string): string => {
  if (!action) return "Approve";

  const primaryWord = action
    .replace(/[_-]+/g, " ")
    .trim()
    .split(/\s+/)[0];

  if (!primaryWord) return "Approve";
  return primaryWord.charAt(0).toUpperCase() + primaryWord.slice(1);
};

const getApprovalDescription = (approval: PendingApproval): string => {
  if (approval.summary?.trim()) return approval.summary.trim();
  if (approval.expected_impact?.trim()) return approval.expected_impact.trim();
  if (approval.reason?.trim()) return approval.reason.trim();
  return "This action is paused until you approve or deny it.";
};

const ApprovalCard: React.FC<ApprovalCardProps> = ({ approval, isSubmitting, onDecision }) => {
  const muiTheme = useTheme();
  const { shop } = useShop();
  const brandPrimary = shop?.primary_color || muiTheme.palette.primary.main;
  const brandSecondary = shop?.secondary_color || brandPrimary;
  const cardBg =
    muiTheme.palette.mode === "dark"
      ? alpha(muiTheme.palette.background.paper, 0.88)
      : alpha("#ffffff", 0.9);
  const cardBorder =
    muiTheme.palette.mode === "dark"
      ? alpha(brandPrimary, 0.24)
      : alpha(brandPrimary, 0.16);
  const riskTone = approval.risk_level === "high"
    ? muiTheme.palette.error.main
    : approval.risk_level === "medium"
      ? muiTheme.palette.warning.main
      : muiTheme.palette.success.main;
  const title = approval.title || approval.action.replace(/_/g, " ");
  const description = getApprovalDescription(approval);
  const actionLabel = formatActionLabel(approval.action);

  return (
    <Card
      variant="outlined"
      sx={{
        borderRadius: 3.5,
        borderColor: cardBorder,
        bgcolor: cardBg,
        backdropFilter: "blur(20px)",
        boxShadow: "none",
      }}
    >
      <Box
        sx={{
          px: 2,
          py: 1.75,
          display: "flex",
          flexDirection: { xs: "column", sm: "row" },
          alignItems: { xs: "stretch", sm: "center" },
          gap: 1.5,
        }}
      >
        <Stack direction="row" spacing={1.5} sx={{ flex: 1, minWidth: 0 }}>
          <Box
            sx={{
              width: 52,
              height: 52,
              borderRadius: 2.5,
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              bgcolor: alpha(brandSecondary, 0.12),
              color: brandSecondary,
              border: `1px solid ${alpha(brandSecondary, 0.18)}`,
              flexShrink: 0,
            }}
          >
            <RocketLaunchRoundedIcon sx={{ fontSize: 24 }} />
          </Box>

          <Stack spacing={0.65} sx={{ minWidth: 0, flex: 1 }}>
            <Typography variant="h6" sx={{ fontSize: "1.05rem", fontWeight: 700, color: "text.primary" }}>
              {title}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 1.5 }}>
              {description}
            </Typography>
            <Stack direction="row" spacing={0.75} useFlexGap flexWrap="wrap">
              {approval.risk_level && (
                <Chip
                  size="small"
                  label={`Risk: ${String(approval.risk_level)}`}
                  sx={{
                    bgcolor: alpha(riskTone, 0.12),
                    color: riskTone,
                    border: `1px solid ${alpha(riskTone, 0.18)}`,
                    fontWeight: 600,
                  }}
                />
              )}
              {approval.policy_mode && (
                <Chip
                  size="small"
                  label={formatPolicyMode(approval.policy_mode)}
                  sx={{
                    bgcolor: alpha(brandPrimary, 0.08),
                    color: brandPrimary,
                    border: `1px solid ${alpha(brandPrimary, 0.16)}`,
                  }}
                />
              )}
            </Stack>
          </Stack>
        </Stack>

        <Stack
          direction="row"
          spacing={1}
          justifyContent={{ xs: "flex-end", sm: "flex-start" }}
          sx={{ ml: { sm: "auto" }, flexShrink: 0 }}
        >
          <Button
            variant="text"
            color="inherit"
            disabled={isSubmitting}
            onClick={() => onDecision(approval, false)}
            sx={{
              minWidth: 72,
              borderRadius: 999,
              px: 1.5,
              color: muiTheme.palette.text.primary,
              textTransform: "none",
              fontWeight: 600,
            }}
          >
            Deny
          </Button>
          <Button
            variant="contained"
            disabled={isSubmitting}
            onClick={() => onDecision(approval, true)}
            sx={{
              minWidth: 96,
              borderRadius: 999,
              px: 2,
              bgcolor: brandPrimary,
              boxShadow: "none",
              color: muiTheme.palette.getContrastText(brandPrimary),
              textTransform: "none",
              fontWeight: 700,
              "&:hover": {
                bgcolor: brandPrimary,
                filter: "brightness(0.95)",
                boxShadow: "none",
              },
            }}
          >
            {actionLabel}
          </Button>
        </Stack>
      </Box>
    </Card>
  );
};

export default ApprovalCard;
