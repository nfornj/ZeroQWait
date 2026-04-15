import React, { useEffect, useState } from "react";
import {
  alpha,
  Box,
  Collapse,
  Stack,
  Tooltip,
  Typography,
  useTheme,
} from "@mui/material";
import CheckCircleRoundedIcon from "@mui/icons-material/CheckCircleRounded";
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

const COMPLETE_COLOR = "#22c55e";
const ERROR_COLOR = "#ef4444";

const ThinkingSteps: React.FC<ThinkingStepsProps> = ({
  steps,
  isComplete,
  accentColor,
}) => {
  const muiTheme = useTheme();
  const [expanded, setExpanded] = useState(true);

  const accent = accentColor || "#2563EB";

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
        overflow: "hidden",
        bgcolor: "transparent",
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
            bgcolor: "rgba(0,0,0,0.03)",
          },
        }}
      >
        <Stack direction="row" spacing={0.6} alignItems="center">
          {!isComplete ? (
            <>
              <Stack direction="row" spacing={0.5} alignItems="center">
                <Box
                  sx={{
                    width: 5,
                    height: 5,
                    borderRadius: "50%",
                    bgcolor: accent,
                    animation: "thinkingDot 0.9s ease-in-out infinite",
                    animationDelay: "0ms",
                  }}
                />
                <Box
                  sx={{
                    width: 5,
                    height: 5,
                    borderRadius: "50%",
                    bgcolor: accent,
                    animation: "thinkingDot 0.9s ease-in-out infinite",
                    animationDelay: "160ms",
                  }}
                />
                <Box
                  sx={{
                    width: 5,
                    height: 5,
                    borderRadius: "50%",
                    bgcolor: accent,
                    animation: "thinkingDot 0.9s ease-in-out infinite",
                    animationDelay: "320ms",
                  }}
                />
              </Stack>
              <Typography
                variant="caption"
                sx={{
                  ml: 0.4,
                  fontWeight: 500,
                  color: "text.secondary",
                  fontSize: "0.7rem",
                }}
              >
                Thinking...
              </Typography>
            </>
          ) : (
            <>
              <CheckCircleRoundedIcon sx={{ fontSize: 14, color: COMPLETE_COLOR }} />
              <Typography
                variant="caption"
                sx={{
                  ml: 0.4,
                  fontWeight: 600,
                  color: COMPLETE_COLOR,
                  fontSize: "0.7rem",
                }}
              >
                {doneCount} steps
              </Typography>
            </>
          )}
        </Stack>
        <Box sx={{ color: "text.disabled", display: "flex" }}>
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
            const lineColor =
              step.status === "completed"
                ? "rgba(34,197,94,0.5)"
                : step.status === "active"
                  ? alpha(accent, 0.6)
                  : step.status === "error"
                    ? "rgba(239,68,68,0.5)"
                    : alpha(muiTheme.palette.text.primary, 0.1);
            return (
              <Box
                key={step.id}
                sx={{
                  display: "flex",
                  alignItems: "flex-start",
                  minHeight: 30,
                  animation: "stepSlideIn 0.25s ease forwards",
                  animationDelay: `${idx * 40}ms`,
                }}
              >
                {/* Left column: timeline track + status dot */}
                <Box
                  sx={{
                    position: "relative",
                    width: 14,
                    minHeight: 28,
                    mr: 1.1,
                    flexShrink: 0,
                  }}
                >
                  {!isLast && (
                    <Box
                      sx={{
                        position: "absolute",
                        top: 5,
                        bottom: -11,
                        left: 5.25,
                        width: "1.5px",
                        bgcolor: lineColor,
                        transition: "background-color 0.3s ease",
                      }}
                    />
                  )}
                  <Box
                    sx={{
                      position: "absolute",
                      top: 2,
                      left: 3,
                      width: 6,
                      height: 6,
                      borderRadius: "50%",
                      bgcolor:
                        step.status === "completed"
                          ? COMPLETE_COLOR
                          : step.status === "active"
                            ? accent
                            : step.status === "error"
                              ? ERROR_COLOR
                              : alpha(muiTheme.palette.text.primary, 0.1),
                      ...(step.status === "active" && {
                        animation: "dotPulse 1.2s ease-in-out infinite",
                      }),
                    }}
                  />
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
                        display: "inline-block",
                        fontWeight:
                          step.status === "active"
                            ? 600
                            : step.status === "pending"
                              ? 400
                              : 500,
                        color:
                          step.status === "completed"
                            ? muiTheme.palette.text.primary
                            : step.status === "active"
                              ? accent
                              : step.status === "error"
                                ? ERROR_COLOR
                                : muiTheme.palette.text.disabled,
                        fontSize: "0.72rem",
                        lineHeight: 1.4,
                        transition: "color 0.3s ease",
                      }}
                    >
                      {step.status === "completed" && (
                        <Box component="span" sx={{ color: COMPLETE_COLOR, mr: 0.4 }}>
                          ✓
                        </Box>
                      )}
                      {step.label}
                      {step.status === "active" && (
                        <Box component="span" sx={{ ml: 0.4 }}>
                          <Box
                            component="span"
                            sx={{
                              animation: "ellipsisDot 1.2s infinite",
                              animationDelay: "0s",
                            }}
                          >
                            .
                          </Box>
                          <Box
                            component="span"
                            sx={{
                              animation: "ellipsisDot 1.2s infinite",
                              animationDelay: "0.2s",
                            }}
                          >
                            .
                          </Box>
                          <Box
                            component="span"
                            sx={{
                              animation: "ellipsisDot 1.2s infinite",
                              animationDelay: "0.4s",
                            }}
                          >
                            .
                          </Box>
                        </Box>
                      )}
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

      {/* Keyframes */}
      <style>{`
        @keyframes thinkingDot {
          0%, 100% { opacity: 0.35; transform: translateY(0); }
          50% { opacity: 1; transform: translateY(-2px); }
        }
        @keyframes dotPulse {
          0%, 100% { transform: scale(1); }
          50% { transform: scale(1.6); }
        }
        @keyframes stepSlideIn {
          from { opacity: 0; transform: translateX(-8px); }
          to { opacity: 1; transform: translateX(0); }
        }
        @keyframes ellipsisDot {
          0%, 80%, 100% { opacity: 0; }
          40% { opacity: 1; }
        }
      `}</style>
    </Box>
  );
};

export default ThinkingSteps;
