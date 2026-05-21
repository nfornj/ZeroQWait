import React, { useState } from "react";
import { ChevronDown } from "lucide-react";
import { Button } from "../../components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../../components/ui/select";
import { cn } from "../../lib/utils";
import GlassCard from "../../components/GlassCard";
import useOwnerBrand from "../../hooks/useOwnerBrand";
import { labelForPolicyMode } from "./agentInboxShared";
import type { ShopPolicy } from "./types";

interface PoliciesPanelProps {
  policies: ShopPolicy[];
  savingPolicyKey: string | null;
  onModeChange: (policy: ShopPolicy, nextMode: string) => void;
  onRetry?: () => void;
}

const PoliciesPanel: React.FC<PoliciesPanelProps> = ({
  policies,
  savingPolicyKey,
  onModeChange,
  onRetry,
}) => {
  const brand = useOwnerBrand();
  const [open, setOpen] = useState(false);

  return (
    <GlassCard className="rounded-2xl">
      <div className="px-4 py-3">
        <div className="flex flex-col gap-3">
          {/* Header */}
          <div className="flex items-start justify-between gap-2">
            <div>
              <p className="text-base font-semibold">Approval Policies</p>
              <p className="text-sm text-muted-foreground">
                Choose what the agent team can run automatically for this shop.
              </p>
            </div>
            <div className="flex items-center gap-1.5 flex-shrink-0">
              {savingPolicyKey ? (
                <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-border border-t-primary" />
              ) : (
                <span
                  className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-bold border"
                  style={{
                    backgroundColor: `${brand.primary}24`,
                    color: brand.primary,
                    borderColor: `${brand.primary}38`,
                  }}
                >
                  {policies.length} actions
                </span>
              )}
              <button
                type="button"
                onClick={() => setOpen((prev) => !prev)}
                className="flex h-7 w-7 items-center justify-center rounded-lg hover:bg-muted transition-colors"
                style={{ color: brand.primary }}
              >
                <ChevronDown
                  className={cn("h-4 w-4 transition-transform duration-200", open && "rotate-180")}
                />
              </button>
            </div>
          </div>

          {/* Collapsible body */}
          {open && (
            <div className="flex flex-col gap-3">
              <hr style={{ borderColor: `${brand.primary}1f` }} />

              {policies.length === 0 ? (
                <div className="flex flex-col gap-2">
                  <p className="text-sm text-muted-foreground">
                    No approval policies are available for this shop yet.
                  </p>
                  {onRetry && (
                    <Button size="sm" variant="ghost" onClick={onRetry} className="self-start">
                      Retry
                    </Button>
                  )}
                </div>
              ) : (
                policies.map((policy) => {
                  const isSaving = savingPolicyKey === policy.policy_key;
                  return (
                    <div
                      key={policy.policy_key}
                      className="rounded-xl border p-3"
                      style={{
                        borderColor: `${brand.primary}1f`,
                        backgroundColor: `${brand.primary}0a`,
                      }}
                    >
                      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-2">
                        <div className="min-w-0">
                          <p className="text-sm font-semibold" style={{ color: brand.primary }}>
                            {policy.title}
                          </p>
                          <div className="flex flex-wrap gap-1.5 mt-1">
                            <span className="inline-flex items-center rounded-full border px-2 py-0.5 text-xs text-muted-foreground">
                              {policy.category}
                            </span>
                            <span className="inline-flex items-center rounded-full border px-2 py-0.5 text-xs text-muted-foreground">
                              {policy.risk_level || "medium"} risk
                            </span>
                            <span className="inline-flex items-center rounded-full border px-2 py-0.5 text-xs text-muted-foreground">
                              {policy.explicit
                                ? "Custom mode"
                                : `Default: ${labelForPolicyMode(policy.default_mode)}`}
                            </span>
                          </div>
                        </div>

                        <Select
                          value={policy.mode}
                          disabled={isSaving}
                          onValueChange={(value) => onModeChange(policy, value)}
                        >
                          <SelectTrigger className="w-full lg:w-52 h-8 text-sm">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {(policy.supported_modes || []).map((mode) => (
                              <SelectItem key={mode} value={mode}>
                                {labelForPolicyMode(mode)}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>

                      <p className="text-xs text-muted-foreground mt-1.5">
                        Current mode: {labelForPolicyMode(policy.mode)}
                        {isSaving ? " · Saving..." : ""}
                      </p>
                    </div>
                  );
                })
              )}
            </div>
          )}
        </div>
      </div>
    </GlassCard>
  );
};

export default PoliciesPanel;
