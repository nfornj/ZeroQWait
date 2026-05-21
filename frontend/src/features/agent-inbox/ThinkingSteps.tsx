import React from "react";
import { cn } from "../../lib/utils";

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

const ThinkingSteps: React.FC<ThinkingStepsProps> = ({
  steps,
  isComplete,
  accentColor = "#2563EB",
  showWhenEmpty = false,
  embedded = false,
}) => {
  if (isComplete) return null;
  if (steps.length === 0 && !showWhenEmpty) return null;

  const activeStep = [...steps].reverse().find((step) => step.status === "active" || step.status === "pending");
  const label = activeStep?.label?.trim() || "Thinking";

  return (
    <>
      <style>{`
        @keyframes thinkingDot {
          0%, 100% { opacity: 0.35; transform: translateY(0); }
          50% { opacity: 1; transform: translateY(-2px); }
        }
      `}</style>
      <div
        className={cn(
          "rounded-xl border",
          embedded ? "px-3 py-2 mb-0" : "px-4 py-3 mb-2",
        )}
        style={{
          borderColor: `${accentColor}24`,
          backgroundColor: `${accentColor}0a`,
        }}
      >
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1">
            {[0, 1, 2].map((index) => (
              <span
                key={index}
                className="inline-block rounded-full w-1.5 h-1.5"
                style={{
                  backgroundColor: accentColor,
                  animation: "thinkingDot 0.9s ease-in-out infinite",
                  animationDelay: `${index * 160}ms`,
                }}
              />
            ))}
          </div>
          <span className="text-sm font-semibold text-foreground">{label}</span>
        </div>
      </div>
    </>
  );
};

export default ThinkingSteps;
