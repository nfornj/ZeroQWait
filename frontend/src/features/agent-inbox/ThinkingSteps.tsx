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
  step: string;
  label: string;
  status: "pending" | "active" | "done" | "error";
  agent?: string | null;
}

interface ThinkingStepsProps {
  steps: ThinkingStep[];
  isComplete: boolean;
  accentColor?: string;
}

// The canonical node order that always appears in the pipeline UI.
const PIPELINE_ORDER = [
  "classify_intent",
  "route_to_agent",
  "execute_plan",
  "synthesize_response",
];

// Default labels shown before the server sends a real label.
const DEFAULT_LABELS: Record<string, string> = {
  classify_intent: "Classifying request",
  route_to_agent: "Selecting specialist",
  execute_plan: "Fetching data",
  synthesize_response: "Generating response",
};

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
  if (status === "done") {
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

  // Build the full ordered pipeline merging server events with defaults.
  const pipeline: ThinkingStep[] = PIPELINE_ORDER.map((key) => {
    const found = steps.find((s) => s.step === key);
    return (
      found ?? {
        step: key,
        label: DEFAULT_LABELS[key] ?? key,
        status: "pending",
      }
    );
  });

  const doneCount = pipeline.filter((s) => s.status === "done").length;

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
          {pipeline.map((s) => (
            <Box
              key={s.step}
              sx={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                bgcolor:
                  s.status === "done"
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
          {pipeline.map((step, idx) => {
            const isLast = idx === pipeline.length - 1;
            return (
              <Box
                key={step.step}
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
                  <StepIcon status={step.status} color={accent} />
                  {!isLast && (
                    <Box
                      sx={{
                        width: "2px",
                        flex: 1,
                        minHeight: 10,
                        mt: "2px",
                        mb: "2px",
                        bgcolor:
                          step.status === "done"
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
                          step.status === "done"
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
