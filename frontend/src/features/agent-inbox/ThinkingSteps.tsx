import React, { useEffect, useState } from "react";
import {
  alpha,
  Box,
  CircularProgress,
  Collapse,
  Stack,
  Tooltip,
  Typography,
  useTheme,
} from "@mui/material";
import CheckCircleRoundedIcon from "@mui/icons-material/CheckCircleRounded";
import RadioButtonUncheckedRoundedIcon from "@mui/icons-material/RadioButtonUncheckedRounded";
import ErrorRoundedIcon from "@mui/icons-material/ErrorRounded";
import KeyboardArrowDownRoundedIcon from "@mui/icons-material/KeyboardArrowDownRounded";
import KeyboardArrowUpRoundedIcon from "@mui/icons-material/KeyboardArrowUpRounded";

export interface ThinkingStep {
  id: string;
  label: string;
  status: "pending" | "active" | "completed" | "error";
  agent?: string | null;
  toolName?: string | null;
}

interface ThinkingStepsProps {
  steps: ThinkingStep[];
  isComplete: boolean;
  accentColor?: string;
}

const PROCESSING_COLOR = "#eab308";
const COMPLETE_COLOR = "#22c55e";
const ERROR_COLOR = "#ef4444";

const StepIcon: React.FC<{ status: ThinkingStep["status"]; color: string }> = ({
  status,
  color,
}) => {
  if (status === "active") {
    return <CircularProgress size={14} thickness={5} sx={{ color }} />;
  }
  if (status === "completed") {
    return (
      <CheckCircleRoundedIcon sx={{ fontSize: 15, color: COMPLETE_COLOR }} />
    );
  }
  if (status === "error") {
    return <ErrorRoundedIcon sx={{ fontSize: 15, color: ERROR_COLOR }} />;
  }
  // pending
  return (
    <RadioButtonUncheckedRoundedIcon
      sx={{ fontSize: 15, color: "action.disabled" }}
    />
  );
};

const ThinkingSteps: React.FC<ThinkingStepsProps> = ({
  steps,
  isComplete,
  accentColor,
}) => {
  const muiTheme = useTheme();
  const [expanded, setExpanded] = useState(true);

  const accent = accentColor || muiTheme.palette.primary.main;
  const processingColor = PROCESSING_COLOR;

  // Auto-collapse 1.8 s after the whole pipeline completes.
  useEffect(() => {
    if (!isComplete) {
      setExpanded(true);
      return;
    }
    const t = setTimeout(() => setExpanded(false), 1800);
    return () => clearTimeout(t);
  }, [isComplete]);

  if (steps.length === 0) return null;

  // Build the pipeline from incoming dynamic steps.
  // Strip any arrow-like symbols from label and agent fields before rendering.
  // Handles: →, ⇒, ➔, ➡, and similar Unicode arrows.
  const stripArrows = (text: string | null | undefined) =>
    (text || "").replace(/[\s\u2190-\u21FF\u27A1\u2794\u279C\u27B2\u27A4\u27B3\u2B05-\u2B07\u279E\u279F\u27A0\u27A2\u27A3\u27A5\u27A6\u27A7\u27A8\u27A9\u27AB\u27AD\u27AF\u27B1\u27B4\u27B5\u27B6\u27B7\u27B8\u27B9\u27BA\u27BB\u27BC\u27BD\u27BE\u27BF\u27C0\u27C1\u27C2\u27C3\u27C4\u27C5\u27C6\u27C7\u27C8\u27C9\u27CA\u27CB\u27CC\u27CD\u27CE\u27CF\u27D0\u27D1\u27D2\u27D3\u27D4\u27D5\u27D6\u27D7\u27D8\u27D9\u27DA\u27DB\u27DC\u27DD\u27DE\u27DF\u27E0\u27E1\u27E2\u27E3\u27E4\u27E5\u27E6\u27E7\u27E8\u27E9\u27EA\u27EB\u27EC\u27ED\u27EE\u27EF\u27F0\u27F1\u27F2\u27F3\u27F4\u27F5\u27F6\u27F7\u27F8\u27F9\u27FA\u27FB\u27FC\u27FD\u27FE\u27FF]+/g, " ").replace(/\s+/g, " ").trim();
  const pipeline: ThinkingStep[] = (steps || []).map((s) => ({
    ...s,
    label: stripArrows(s.label),
    agent: stripArrows(s.agent),
  }));

  // Some streams move a step from pending->done too quickly to ever paint "active".
  // Keep the first pending step visibly active while the pipeline is in progress.
  const hasActiveStep = pipeline.some((s) => s.status === "active");
  const displayPipeline: ThinkingStep[] = !isComplete && !hasActiveStep
    ? (() => {
        const firstPendingIndex = pipeline.findIndex((s) => s.status === "pending");
        if (firstPendingIndex < 0) return pipeline;
        return pipeline.map((s, idx) =>
          idx === firstPendingIndex ? { ...s, status: "active" as const } : s,
        );
      })()
    : pipeline;

  const doneCount = displayPipeline.filter((s) => s.status === "completed").length;

  return (
    <Box
      sx={{
        mb: 1,
        borderRadius: "10px",
        border: `1px solid ${alpha(isComplete ? COMPLETE_COLOR : processingColor, 0.26)}`,
        bgcolor: alpha(
          isComplete ? COMPLETE_COLOR : processingColor,
          muiTheme.palette.mode === "dark" ? 0.08 : 0.06,
        ),
        overflow: "hidden",
      }}
    >
      {/* Header row — always visible, toggles expanded state */}
      <Stack
        direction="row"
        alignItems="center"
        justifyContent="space-between"
        onClick={() => setExpanded((v) => !v)}
        sx={{
          px: 1.5,
          py: 0.75,
          cursor: "pointer",
          userSelect: "none",
          "&:hover": {
            bgcolor: alpha(isComplete ? COMPLETE_COLOR : processingColor, 0.08),
          },
        }}
      >
        <Stack direction="row" spacing={0.6} alignItems="center">
          {/* Compact dot-row summary */}
          {displayPipeline.map((s) => (
            <Box
              key={s.id}
              sx={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                bgcolor:
                  s.status === "completed"
                    ? COMPLETE_COLOR
                    : s.status === "active"
                      ? processingColor
                      : s.status === "error"
                        ? ERROR_COLOR
                        : alpha(muiTheme.palette.text.primary, 0.18),
                transition: "background-color 0.4s ease",
                ...(s.status === "active" && {
                  boxShadow: `0 0 0 3px ${alpha(processingColor, 0.28)}`,
                  animation: "pulse 1.4s ease-in-out infinite",
                }),
              }}
            />
          ))}
          <Typography
            variant="caption"
            sx={{
              ml: 0.5,
              fontWeight: 600,
              color: isComplete ? COMPLETE_COLOR : processingColor,
              fontSize: "0.7rem",
            }}
          >
            {isComplete ? `${doneCount} steps complete` : "Thinking\u2026"}
          </Typography>
        </Stack>
        <Box sx={{ color: "text.secondary", display: "flex" }}>
          {expanded ? (
            <KeyboardArrowUpRoundedIcon sx={{ fontSize: 16 }} />
          ) : (
            <KeyboardArrowDownRoundedIcon sx={{ fontSize: 16 }} />
          )}
        </Box>
      </Stack>

      {/* Expandable pipeline steps */}
      <Collapse in={expanded}>
        <Box sx={{ px: 1.5, pt: 0.5, pb: 1.25 }}>
          {displayPipeline.map((step, idx) => {
            const isLast = idx === displayPipeline.length - 1;
            return (
              <Box
                key={step.id}
                sx={{
                  display: "flex",
                  alignItems: "flex-start",
                  minHeight: 28,
                }}
              >
                {/* Left column: icon + connector line */}
                <Box
                  sx={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    mr: 1.25,
                    mt: "3px",
                    flexShrink: 0,
                  }}
                >
                  <StepIcon status={step.status} color={processingColor} />
                  {!isLast && (
                    <Box
                      sx={{
                        width: "2px",
                        flex: 1,
                        minHeight: 10,
                        mt: "2px",
                        mb: "2px",
                        bgcolor:
                          step.status === "completed"
                            ? alpha(COMPLETE_COLOR, 0.45)
                            : step.status === "active"
                              ? alpha(PROCESSING_COLOR, 0.4)
                            : alpha(muiTheme.palette.text.primary, 0.12),
                        borderRadius: "1px",
                        transition: "background-color 0.4s ease",
                      }}
                    />
                  )}
                </Box>

                {/* Right column: step label */}
                <Tooltip
                  title={step.agent ? `Handled by: ${step.agent}` : ""}
                  placement="right"
                  disableHoverListener={!step.agent}
                >
                  <Box sx={{ pt: "1px", pb: isLast ? 0 : 1 }}>
                    <Typography
                      variant="caption"
                      sx={{
                        display: "block",
                        fontWeight: step.status === "active" ? 700 : 500,
                        color:
                          step.status === "completed"
                            ? muiTheme.palette.text.primary
                            : step.status === "active"
                              ? processingColor
                              : step.status === "error"
                                ? ERROR_COLOR
                                : muiTheme.palette.text.disabled,
                        fontSize: "0.72rem",
                        lineHeight: 1.4,
                        transition: "color 0.3s ease, font-weight 0.2s ease",
                      }}
                    >
                      {step.label}
                    </Typography>
                    {step.agent && step.status !== "pending" && (
                      <Typography
                        variant="caption"
                        sx={{
                          fontSize: "0.65rem",
                          color: "text.disabled",
                          display: "block",
                          lineHeight: 1.2,
                        }}
                      >
                        {step.agent}
                      </Typography>
                    )}
                  </Box>
                </Tooltip>
              </Box>
            );
          })}
        </Box>
      </Collapse>

      {/* Keyframe for the active-dot pulse */}
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.45; }
        }
      `}</style>
    </Box>
  );
};

export default ThinkingSteps;
