import React from "react";
import { Rocket } from "lucide-react";
import { Button } from "../../components/ui/button";
import { Badge } from "../../components/ui/badge";
import { cn } from "../../lib/utils";
import type { PendingApproval } from "./types";
import { useOwnerBrand } from "../../hooks/useOwnerBrand";

interface ApprovalCardProps {
  approval: PendingApproval;
  isSubmitting?: boolean;
  onDecision: (approval: PendingApproval, approved: boolean) => void;
}

const formatPolicyMode = (mode?: string): string => {
  switch (mode) {
    case "require_approval": return "Require approval";
    case "allow": return "Allow automatically";
    case "notify_only": return "Notify after auto-run";
    case "silent": return "Silent auto-run";
    case "forbid": return "Blocked by policy";
    default: return mode ? mode.replace(/_/g, " ") : "Policy controlled";
  }
};

const formatActionLabel = (action?: string): string => {
  if (!action) return "Approve";
  const primaryWord = action.replace(/[_-]+/g, " ").trim().split(/\s+/)[0];
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
  const brand = useOwnerBrand();

  const riskColor =
    approval.risk_level === "high"
      ? "#ef4444"
      : approval.risk_level === "medium"
      ? "#f59e0b"
      : "#22c55e";

  const title = approval.title || approval.action.replace(/_/g, " ");
  const description = getApprovalDescription(approval);
  const actionLabel = formatActionLabel(approval.action);

  return (
    <div
      className="rounded-2xl border backdrop-blur-xl"
      style={{
        borderColor: brand.glass.border,
        backgroundColor: brand.glass.bg,
      }}
    >
      <div className="flex flex-col sm:flex-row sm:items-center gap-4 px-4 py-4">
        {/* Icon + Info */}
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <div
            className="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0 border"
            style={{
              backgroundColor: `${brand.secondary}1f`,
              borderColor: `${brand.secondary}2e`,
              color: brand.secondary,
            }}
          >
            <Rocket className="h-5 w-5" />
          </div>

          <div className="flex flex-col gap-1 min-w-0 flex-1">
            <p className="text-base font-bold text-foreground leading-snug">{title}</p>
            <p className="text-sm text-muted-foreground leading-relaxed">{description}</p>
            <div className="flex flex-wrap gap-1.5 mt-0.5">
              {approval.risk_level && (
                <span
                  className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold border"
                  style={{
                    backgroundColor: `${riskColor}1f`,
                    color: riskColor,
                    borderColor: `${riskColor}2e`,
                  }}
                >
                  Risk: {approval.risk_level}
                </span>
              )}
              {approval.policy_mode && (
                <span
                  className="inline-flex items-center rounded-full px-2 py-0.5 text-xs border"
                  style={{
                    backgroundColor: `${brand.primary}14`,
                    color: brand.primary,
                    borderColor: `${brand.primary}29`,
                  }}
                >
                  {formatPolicyMode(approval.policy_mode)}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-2 justify-end sm:justify-start flex-shrink-0 sm:ml-auto">
          <Button
            variant="ghost"
            size="sm"
            disabled={isSubmitting}
            onClick={() => onDecision(approval, false)}
            className="rounded-full font-semibold"
          >
            Deny
          </Button>
          <Button
            size="sm"
            disabled={isSubmitting}
            onClick={() => onDecision(approval, true)}
            className="rounded-full font-bold"
            style={{ backgroundColor: brand.primary }}
          >
            {actionLabel}
          </Button>
        </div>
      </div>
    </div>
  );
};

export default ApprovalCard;
