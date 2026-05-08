import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  alpha,
  Box,
  ButtonBase,
  Collapse,
  Stack,
  Typography,
  useTheme,
} from "@mui/material";
import ExpandMoreRoundedIcon from "@mui/icons-material/ExpandMoreRounded";
import type { PendingApproval } from "./types";
import { useShop } from "../../contexts/ShopContext";

interface ApprovalCardProps {
  approval: PendingApproval;
  isSubmitting?: boolean;
  onDecision: (approval: PendingApproval, approved: boolean) => void;
  /** If true the card is resolved (read-only, no buttons) */
  resolved?: boolean;
  resolvedOutcome?: "approved" | "denied";
}

const getApprovalDescription = (approval: PendingApproval): string => {
  if (approval.summary?.trim()) return approval.summary.trim();
  if (approval.expected_impact?.trim()) return approval.expected_impact.trim();
  if (approval.reason?.trim()) return approval.reason.trim();
  return "This action is paused until you approve or deny it.";
};

const ApprovalCard: React.FC<ApprovalCardProps> = ({
  approval,
  isSubmitting,
  onDecision,
  resolved,
  resolvedOutcome,
}) => {
  const muiTheme = useTheme();
  const { shop } = useShop();
  const brandPrimary = shop?.primary_color || muiTheme.palette.primary.main;
  const [expanded, setExpanded] = useState(true);
  const cardRef = useRef<HTMLDivElement>(null);

  const title = (approval.title || approval.action.replace(/[_-]+/g, " ")).trim();
  const description = getApprovalDescription(approval);

  const handleDeny = useCallback(() => {
    if (!isSubmitting && !resolved) {
      onDecision(approval, false);
    }
  }, [approval, isSubmitting, onDecision, resolved]);

  const handleApprove = useCallback(() => {
    if (!isSubmitting && !resolved) {
      onDecision(approval, true);
    }
  }, [approval, isSubmitting, onDecision, resolved]);

  // Keyboard shortcuts: Enter = approve, Esc = deny
  useEffect(() => {
    const el = cardRef.current;
    if (!el || resolved) return;

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleApprove();
      } else if (e.key === "Escape") {
        e.preventDefault();
        handleDeny();
      }
    };

    el.addEventListener("keydown", onKey);
    return () => el.removeEventListener("keydown", onKey);
  }, [handleApprove, handleDeny, resolved]);

  const isDark = muiTheme.palette.mode === "dark";
  const borderColor = resolved
    ? alpha(muiTheme.palette.divider, 0.8)
    : alpha(brandPrimary, isDark ? 0.22 : 0.16);

  return (
    <Box
      ref={cardRef}
      tabIndex={resolved ? -1 : 0}
      aria-label={`Approval request: ${title}`}
      data-approval-id={approval.action_id || approval.action}
      sx={{
        borderRadius: 2,
        border: "1px solid",
        borderColor,
        bgcolor: isDark
          ? alpha(muiTheme.palette.background.paper, 0.9)
          : muiTheme.palette.background.paper,
        overflow: "hidden",
        outline: "none",
        maxWidth: 520,
        "&:focus-visible": {
          boxShadow: `0 0 0 2px ${alpha(brandPrimary, 0.5)}`,
        },
      }}
    >
      {/* Title row */}
      <ButtonBase
        component="div"
        onClick={() => setExpanded((v) => !v)}
        sx={{
          display: "flex",
          width: "100%",
          alignItems: "center",
          gap: 0.75,
          px: 1.75,
          py: 1.1,
          textAlign: "left",
          cursor: "pointer",
          "&:hover": {
            bgcolor: alpha(brandPrimary, 0.04),
          },
        }}
      >
        {/* Bullet */}
        <Box
          sx={{
            width: 8,
            height: 8,
            borderRadius: "50%",
            flexShrink: 0,
            bgcolor: resolved
              ? resolvedOutcome === "approved"
                ? muiTheme.palette.success.main
                : muiTheme.palette.text.disabled
              : brandPrimary,
          }}
        />

        <Typography
          variant="body2"
          sx={{
            flex: 1,
            fontWeight: 600,
            color: resolved ? "text.secondary" : brandPrimary,
            lineHeight: 1.4,
          }}
        >
          {title}
          {resolved && resolvedOutcome && (
            <Typography
              component="span"
              variant="caption"
              sx={{
                ml: 1,
                px: 0.75,
                py: 0.2,
                borderRadius: 999,
                bgcolor: alpha(
                  resolvedOutcome === "approved"
                    ? muiTheme.palette.success.main
                    : muiTheme.palette.text.disabled,
                  0.12,
                ),
                color:
                  resolvedOutcome === "approved"
                    ? muiTheme.palette.success.main
                    : "text.secondary",
                fontWeight: 600,
              }}
            >
              {resolvedOutcome === "approved" ? "Approved" : "Denied"}
            </Typography>
          )}
        </Typography>

        <ExpandMoreRoundedIcon
          sx={{
            fontSize: 18,
            color: "text.secondary",
            flexShrink: 0,
            transition: muiTheme.transitions.create("transform", { duration: 180 }),
            transform: expanded ? "rotate(180deg)" : "rotate(0deg)",
          }}
        />
      </ButtonBase>

      {/* Expandable body */}
      <Collapse in={expanded} unmountOnExit>
        <Box
          sx={{
            px: 1.75,
            pt: 0.25,
            pb: resolved ? 1.5 : 1,
            borderTop: "1px solid",
            borderColor: alpha(muiTheme.palette.divider, 0.6),
          }}
        >
          <Typography
            variant="body2"
            sx={{
              color: "text.secondary",
              lineHeight: 1.6,
              py: 0.75,
            }}
          >
            {description}
          </Typography>

          {/* Action buttons — only when not resolved */}
          {!resolved && (
            <Stack
              direction="row"
              spacing={0.75}
              justifyContent="flex-end"
              sx={{
                pt: 0.75,
                borderTop: "1px solid",
                borderColor: alpha(muiTheme.palette.divider, 0.5),
              }}
            >
              <ButtonBase
                disabled={isSubmitting}
                onClick={handleDeny}
                sx={{
                  px: 1.5,
                  py: 0.6,
                  borderRadius: 999,
                  fontFamily: "inherit",
                  fontSize: "0.8125rem",
                  fontWeight: 600,
                  color: "text.primary",
                  opacity: isSubmitting ? 0.5 : 1,
                  cursor: isSubmitting ? "not-allowed" : "pointer",
                  "&:hover:not(:disabled)": {
                    bgcolor: alpha(muiTheme.palette.text.primary, 0.06),
                  },
                }}
              >
                Deny
                <Typography
                  component="span"
                  variant="caption"
                  sx={{
                    ml: 0.6,
                    px: 0.55,
                    py: 0.1,
                    borderRadius: 0.75,
                    bgcolor: alpha(muiTheme.palette.text.primary, 0.08),
                    color: "text.secondary",
                    fontFamily: "monospace",
                    fontSize: "0.7rem",
                  }}
                >
                  ^ Esc
                </Typography>
              </ButtonBase>

              <ButtonBase
                disabled={isSubmitting}
                onClick={handleApprove}
                sx={{
                  px: 1.75,
                  py: 0.6,
                  borderRadius: 999,
                  fontFamily: "inherit",
                  fontSize: "0.8125rem",
                  fontWeight: 700,
                  bgcolor: isDark
                    ? muiTheme.palette.common.white
                    : muiTheme.palette.grey[900],
                  color: isDark
                    ? muiTheme.palette.grey[900]
                    : muiTheme.palette.common.white,
                  opacity: isSubmitting ? 0.5 : 1,
                  cursor: isSubmitting ? "not-allowed" : "pointer",
                  transition: muiTheme.transitions.create(["opacity", "filter"], {
                    duration: 150,
                  }),
                  "&:hover:not(:disabled)": {
                    filter: "brightness(0.88)",
                  },
                }}
              >
                Approve
                <Typography
                  component="span"
                  variant="caption"
                  sx={{
                    ml: 0.6,
                    px: 0.55,
                    py: 0.1,
                    borderRadius: 0.75,
                    bgcolor: alpha(
                      isDark
                        ? muiTheme.palette.grey[800]
                        : muiTheme.palette.common.white,
                      0.18,
                    ),
                    color: "inherit",
                    fontFamily: "monospace",
                    fontSize: "0.7rem",
                    opacity: 0.75,
                  }}
                >
                  ^ Enter
                </Typography>
              </ButtonBase>
            </Stack>
          )}
        </Box>
      </Collapse>
    </Box>
  );
};

export default ApprovalCard;
