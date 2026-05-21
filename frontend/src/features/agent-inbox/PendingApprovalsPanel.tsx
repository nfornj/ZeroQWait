import React, { useEffect, useMemo, useState } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "../../lib/utils";
import GlassCard from "../../components/GlassCard";
import useOwnerBrand from "../../hooks/useOwnerBrand";
import ApprovalCard from "./ApprovalCard";
import type { PendingApproval } from "./types";

interface PendingApprovalsPanelProps {
  approvals: PendingApproval[];
  isApproving: boolean;
  onDecision: (approval: PendingApproval, approved: boolean) => void;
}

const PendingApprovalsPanel: React.FC<PendingApprovalsPanelProps> = ({
  approvals,
  isApproving,
  onDecision,
}) => {
  const brand = useOwnerBrand();
  const [open, setOpen] = useState(true);
  const latestApprovals = useMemo(() => approvals.slice(0, 3), [approvals]);

  useEffect(() => {
    if (approvals.length > 0) {
      setOpen(true);
    }
  }, [approvals.length]);

  return (
    <GlassCard className="rounded-2xl">
      <div className="px-4 py-3">
        <div className="flex flex-col gap-2">
          {/* Header */}
          <div className="flex items-center justify-between">
            <p className="text-base font-semibold">Pending Approvals</p>
            <div className="flex items-center gap-1.5">
              <span
                className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-bold border"
                style={{
                  backgroundColor: `${brand.primary}24`,
                  color: brand.primary,
                  borderColor: `${brand.primary}38`,
                }}
              >
                {latestApprovals.length}
              </span>
              <button
                type="button"
                onClick={() => setOpen((prev) => !prev)}
                className="flex h-7 w-7 items-center justify-center rounded-lg hover:bg-muted transition-colors"
                style={{ color: brand.primary }}
              >
                <ChevronDown
                  className={cn("h-4 w-4 transition-transform duration-200", open && "rotate-180")}
                  style={{ fontSize: 18 }}
                />
              </button>
            </div>
          </div>

          <hr style={{ borderColor: `${brand.primary}1f` }} />

          {/* Body */}
          {open && (
            <div className="flex flex-col gap-3">
              {latestApprovals.length === 0 ? (
                <p className="text-sm text-muted-foreground py-1">
                  No approvals are waiting right now.
                </p>
              ) : (
                latestApprovals.map((approval) => (
                  <ApprovalCard
                    key={approval.action_id || `${approval.action}_${approval.shop_id}`}
                    approval={approval}
                    isSubmitting={isApproving}
                    onDecision={onDecision}
                  />
                ))
              )}
            </div>
          )}
        </div>
      </div>
    </GlassCard>
  );
};

export default PendingApprovalsPanel;
