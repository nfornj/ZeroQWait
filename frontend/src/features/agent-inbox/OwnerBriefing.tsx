import React from "react";
import { Clock, Users, DollarSign, AlertTriangle, CheckSquare } from "lucide-react";
import { Skeleton } from "../../components/ui/skeleton";
import { Button } from "../../components/ui/button";
import { useOwnerBrand } from "../../hooks/useOwnerBrand";
import type { BriefingAction, OwnerBriefing as OwnerBriefingData } from "./types";

interface OwnerBriefingProps {
  briefing: OwnerBriefingData | null;
  onAction?: (action: BriefingAction) => void;
  isLoading?: boolean;
}

const formatCurrency = (value: number) =>
  new Intl.NumberFormat("en-CA", {
    style: "currency",
    currency: "CAD",
    maximumFractionDigits: 0,
  }).format(value || 0);

const severityClasses: Record<string, string> = {
  error: "bg-red-500/10 border-red-500/20 text-red-400",
  warning: "bg-amber-500/10 border-amber-500/20 text-amber-400",
  info: "bg-blue-500/10 border-blue-500/20 text-blue-400",
  success: "bg-emerald-500/10 border-emerald-500/20 text-emerald-400",
};

const StatCard: React.FC<{
  label: string;
  value: string;
  icon: React.ReactNode;
  brand: ReturnType<typeof useOwnerBrand>;
}> = ({ label, value, icon, brand }) => (
  <div
    className="rounded-xl border p-3"
    style={{
      borderColor: `${brand.primary}24`,
      backgroundColor: `${brand.primary}08`,
    }}
  >
    <div className="flex items-center gap-1.5 mb-1">
      {icon}
      <span className="text-xs text-muted-foreground">{label}</span>
    </div>
    <p className="text-base font-semibold text-foreground">{value}</p>
  </div>
);

const OwnerBriefingPanel: React.FC<OwnerBriefingProps> = ({ briefing, onAction, isLoading }) => {
  const brand = useOwnerBrand();

  if (!briefing) {
    if (isLoading) {
      return <Skeleton className="h-48 w-full rounded-2xl" />;
    }
    return null;
  }

  return (
    <div
      className="rounded-2xl border backdrop-blur-xl"
      style={{
        borderColor: brand.glass.border,
        backgroundColor: brand.glass.bg,
      }}
    >
      <div className="px-4 py-4">
        {/* Header */}
        <div className="flex items-center justify-between mb-2">
          <p className="text-base font-semibold">Daily Briefing</p>
          <span
            className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-bold border"
            style={{
              backgroundColor: `${brand.secondary}2e`,
              color: brand.secondary,
              borderColor: `${brand.secondary}3d`,
            }}
          >
            {briefing.source === "scheduled" ? "Scheduled" : "Live"}
          </span>
        </div>

        <p className="text-sm text-muted-foreground mb-3 leading-relaxed">{briefing.summary}</p>

        {/* Stat cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-2 mb-3">
          <StatCard
            label="Queue"
            value={`${briefing.metrics.queue_length} waiting`}
            icon={<Clock className="h-3.5 w-3.5" style={{ color: brand.primary }} />}
            brand={brand}
          />
          <StatCard
            label="Wait Time"
            value={`${briefing.metrics.estimated_wait_minutes} min`}
            icon={<Clock className="h-3.5 w-3.5" style={{ color: brand.secondary }} />}
            brand={brand}
          />
          <StatCard
            label="Active Staff"
            value={String(briefing.metrics.active_employees)}
            icon={<Users className="h-3.5 w-3.5" style={{ color: brand.primary }} />}
            brand={brand}
          />
          <StatCard
            label="Today Revenue"
            value={formatCurrency(briefing.metrics.today_revenue)}
            icon={<DollarSign className="h-3.5 w-3.5" style={{ color: brand.secondary }} />}
            brand={brand}
          />
        </div>

        {/* Alerts */}
        {briefing.alerts.length > 0 && (
          <div className="flex flex-col gap-1.5 mb-3">
            {briefing.alerts.map((alert, index) => (
              <div
                key={`${alert.title}_${index}`}
                className={`rounded-xl border px-3 py-2 ${severityClasses[alert.severity] || severityClasses.info}`}
              >
                <p className="text-xs font-semibold">{alert.title}</p>
                <p className="text-xs opacity-80">{alert.body}</p>
              </div>
            ))}
          </div>
        )}

        {/* Recommended actions */}
        {briefing.actions.length > 0 && (
          <div className="mb-3">
            <p className="text-xs font-semibold mb-2 text-muted-foreground uppercase tracking-wide">
              Recommended actions
            </p>
            <div className="flex flex-wrap gap-1.5">
              {briefing.actions.map((action, index) => (
                <Button
                  key={`${action.label}_${index}`}
                  size="sm"
                  variant="outline"
                  onClick={() => onAction?.(action)}
                  className="rounded-full h-7 text-xs font-semibold"
                  style={{
                    borderColor: `${brand.primary}40`,
                    color: brand.primary,
                  }}
                >
                  {action.label}
                </Button>
              ))}
            </div>
          </div>
        )}

        {/* Recommendations */}
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-1.5 mb-1">
            <CheckSquare className="h-3.5 w-3.5" style={{ color: brand.primary }} />
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              Recommended next steps
            </p>
          </div>
          {briefing.recommendations.map((item, index) => (
            <p key={`${item}_${index}`} className="text-xs text-muted-foreground">
              {index + 1}. {item}
            </p>
          ))}
        </div>

        {/* Alert history */}
        {briefing.alert_history && briefing.alert_history.length > 1 && (
          <div className="mt-3 flex flex-col gap-0.5">
            <p className="text-xs text-muted-foreground/60">Recent operational alerts</p>
            {briefing.alert_history.slice(0, 2).map((alert, index) => (
              <p key={`${alert.title}_${index}_history`} className="text-xs text-muted-foreground/60">
                {alert.title}
              </p>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default OwnerBriefingPanel;
