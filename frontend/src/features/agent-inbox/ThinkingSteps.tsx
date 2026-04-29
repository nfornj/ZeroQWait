import React from "react";
import {
  alpha,
  Box,
  Stack,
  Typography,
} from "@mui/material";

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
  showWhenEmpty?: boolean;
  embedded?: boolean;
}

const COMPLETE_COLOR = "#22c55e";
const ERROR_COLOR = "#ef4444";

const ThinkingSteps: React.FC<ThinkingStepsProps> = ({
  steps,
  isComplete,
  accentColor,
  showWhenEmpty = false,
  embedded = false,
}) => {
  const accent = accentColor || "#2563EB";
  if (isComplete) return null;
  if (steps.length === 0 && !showWhenEmpty) return null;

  const activeStep = [...steps].reverse().find((step) => step.status === "active" || step.status === "pending");
  const label = activeStep?.label?.trim() || "Thinking";

  return (
    <Box
      sx={{
        mb: embedded ? 0 : 1,
        px: embedded ? 1 : 1.25,
        py: embedded ? 0.85 : 1,
        borderRadius: 3,
        border: `1px solid ${alpha(accent, 0.14)}`,
        bgcolor: alpha(accent, 0.04),
      }}
    >
      <Stack direction="row" spacing={0.8} alignItems="center">
        <Stack direction="row" spacing={0.45} alignItems="center">
          {[0, 1, 2].map((index) => (
            <Box
              key={index}
              sx={{
                width: 6,
                height: 6,
                borderRadius: "50%",
                bgcolor: accent,
                animation: "thinkingDot 0.9s ease-in-out infinite",
                animationDelay: `${index * 160}ms`,
              }}
            />
          ))}
        </Stack>
        <Typography variant="body2" sx={{ fontWeight: 600, color: "text.primary" }}>
          {label}
        </Typography>
      </Stack>
      <style>{`
        @keyframes thinkingDot {
          0%, 100% { opacity: 0.35; transform: translateY(0); }
          50% { opacity: 1; transform: translateY(-2px); }
        }
      `}</style>
    </Box>
  );
};

export default ThinkingSteps;
