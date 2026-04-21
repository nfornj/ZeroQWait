import React from "react";
import {
  alpha,
  Alert,
  Box,
  Button,
  Card,
  CardActions,
  CardContent,
  Chip,
  Stack,
  Typography,
  useTheme,
} from "@mui/material";
import WarningAmberRoundedIcon from "@mui/icons-material/WarningAmberRounded";
import type { PendingApproval } from "./types";
import { useShop } from "../../contexts/ShopContext";

interface ApprovalCardProps {
  approval: PendingApproval;
  isSubmitting?: boolean;
  onDecision: (approval: PendingApproval, approved: boolean) => void;
}

const formatValue = (value: unknown): string => {
  if (value === null || value === undefined) return "-";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
};

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

const ApprovalCard: React.FC<ApprovalCardProps> = ({ approval, isSubmitting, onDecision }) => {
  const muiTheme = useTheme();
  const { shop } = useShop();
  const brandPrimary = shop?.primary_color || muiTheme.palette.primary.main;
  const brandSecondary = shop?.secondary_color || brandPrimary;
  const detailEntries = Object.entries(approval.details || {});
  const cardBg =
    muiTheme.palette.mode === "dark"
      ? "rgba(255, 255, 255, 0.05)"
      : alpha("#ffffff", 0.72);
  const cardBorder =
    muiTheme.palette.mode === "dark"
      ? alpha(brandPrimary, 0.24)
      : alpha(brandPrimary, 0.16);
  const riskTone = approval.risk_level === "high"
    ? muiTheme.palette.error.main
    : approval.risk_level === "medium"
      ? muiTheme.palette.warning.main
      : muiTheme.palette.success.main;

  return (
    <Card
      variant="outlined"
      sx={{
        borderRadius: 3,
        borderColor: cardBorder,
        bgcolor: cardBg,
        backdropFilter: "blur(20px)",
      }}
    >
      <CardContent>
        <Stack direction="row" spacing={1} alignItems="center" mb={1.5}>
          <Chip
            size="small"
            label="Approval Required"
            sx={{
              bgcolor: alpha(brandSecondary, 0.18),
              color: brandSecondary,
              border: `1px solid ${alpha(brandSecondary, 0.28)}`,
              fontWeight: 700,
            }}
          />
          <Typography variant="subtitle2" color="text.secondary">
            Action ID: {approval.action_id || "pending"}
          </Typography>
        </Stack>

        <Typography variant="h6" sx={{ textTransform: "capitalize", mb: 1, color: brandPrimary }}>
          {approval.title || approval.action.replace(/_/g, " ")}
        </Typography>

        <Typography variant="body2" color="text.secondary" mb={1.5}>
          {approval.summary || "This action is paused until you approve or reject it."}
        </Typography>

        <Stack direction="row" spacing={0.75} useFlexGap flexWrap="wrap" mb={1.5}>
          {approval.policy_mode && (
            <Chip
              size="small"
              label={formatPolicyMode(approval.policy_mode)}
              sx={{
                bgcolor: alpha(brandPrimary, 0.12),
                color: brandPrimary,
                border: `1px solid ${alpha(brandPrimary, 0.2)}`,
              }}
            />
          )}
          {approval.category && <Chip size="small" variant="outlined" label={approval.category} />}
          {approval.urgency && <Chip size="small" variant="outlined" label={`Urgency: ${approval.urgency}`} />}
        </Stack>

        <Stack spacing={1.25} mb={1.5}>
          <Alert
            icon={<WarningAmberRoundedIcon fontSize="inherit" />}
            severity={approval.risk_level === "high" ? "error" : approval.risk_level === "medium" ? "warning" : "info"}
            sx={{ borderRadius: 2 }}
          >
            <Typography variant="subtitle2">Risk: {(approval.risk_level || "medium").toUpperCase()}</Typography>
            <Typography variant="body2">{approval.expected_impact || "This changes live shop operations once approved."}</Typography>
          </Alert>
          <Alert icon={false} severity="info" sx={{ borderRadius: 2 }}>
            <Typography variant="caption" color="text.secondary">
              Reason
            </Typography>
            <Typography variant="body2">{approval.reason || "No explicit reason was provided."}</Typography>
          </Alert>
          {approval.recommended_decision && (
            <Alert icon={false} severity="success" sx={{ borderRadius: 2 }}>
              <Typography variant="caption" color="text.secondary">
                Recommended handling
              </Typography>
              <Typography variant="body2">{approval.recommended_decision}</Typography>
            </Alert>
          )}
        </Stack>

        {detailEntries.length > 0 ? (
          <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" }, gap: 1 }}>
            {detailEntries.map(([key, value]) => (
              <Alert
                key={key}
                icon={false}
                severity="info"
                sx={{
                  py: 0.5,
                  border: `1px solid ${alpha(brandPrimary, 0.16)}`,
                  bgcolor: alpha(brandPrimary, 0.06),
                }}
              >
                <Typography variant="caption" color="text.secondary">
                  {key}
                </Typography>
                <Typography variant="body2">{formatValue(value)}</Typography>
              </Alert>
            ))}
          </Box>
        ) : (
          <Typography variant="body2" color="text.secondary">
            No additional details supplied.
          </Typography>
        )}
      </CardContent>

      <CardActions sx={{ justifyContent: "flex-end", px: 2, pb: 2 }}>
        <Button
          variant="outlined"
          color="inherit"
          disabled={isSubmitting}
          onClick={() => onDecision(approval, false)}
          sx={{
            borderColor: alpha(brandPrimary, 0.25),
            color: muiTheme.palette.text.primary,
          }}
        >
          Reject
        </Button>
        <Button
          variant="contained"
          disabled={isSubmitting}
          onClick={() => onDecision(approval, true)}
          sx={{
            bgcolor: brandPrimary,
            boxShadow: `0 10px 30px ${alpha(riskTone, 0.18)}`,
            color: muiTheme.palette.getContrastText(brandPrimary),
            "&:hover": {
              bgcolor: brandPrimary,
              filter: "brightness(0.95)",
            },
          }}
        >
          Approve
        </Button>
      </CardActions>
    </Card>
  );
};

export default ApprovalCard;
