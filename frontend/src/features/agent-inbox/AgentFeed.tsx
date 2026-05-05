import React from "react";
import { cn } from "../../lib/utils";
import { Button } from "../../components/ui/button";
import { Skeleton } from "../../components/ui/skeleton";
import { useOwnerBrand } from "../../hooks/useOwnerBrand";
import type { AgentFeedEvent } from "./types";

type MaxHeightValue = string | number | Record<string, string | number>;

interface AgentFeedProps {
  events: AgentFeedEvent[];
  unreadCount?: number;
  isMarkingAllRead?: boolean;
  markingNotificationId?: number | null;
  onMarkAsRead?: (notificationId: number) => void;
  onMarkAllAsRead?: () => void;
  maxHeight?: MaxHeightValue;
  isLoading?: boolean;
}

const typeChipClass: Record<AgentFeedEvent["type"], string> = {
  chat: "bg-muted text-muted-foreground",
  agent_switch: "bg-blue-500/10 text-blue-400 border border-blue-500/20",
  tool_call: "bg-violet-500/10 text-violet-400 border border-violet-500/20",
  tool_result: "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20",
  approval_required: "bg-amber-500/10 text-amber-400 border border-amber-500/20",
  approval_decision: "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20",
  queue_update: "bg-blue-500/10 text-blue-400 border border-blue-500/20",
  error: "bg-red-500/10 text-red-400 border border-red-500/20",
  system: "bg-muted text-muted-foreground",
};

const maxHeightToStyle = (value: MaxHeightValue): string => {
  if (typeof value === "number") return `${value}px`;
  if (typeof value === "string") return value;
  const md = (value as Record<string, string | number>).md;
  if (md !== undefined) return typeof md === "number" ? `${md}px` : md;
  return "240px";
};

const AgentFeed: React.FC<AgentFeedProps> = ({
  events,
  unreadCount = 0,
  isMarkingAllRead = false,
  markingNotificationId = null,
  onMarkAsRead,
  onMarkAllAsRead,
  maxHeight = 160,
  isLoading = false,
}) => {
  const brand = useOwnerBrand();

  return (
    <div
      className="rounded-2xl border backdrop-blur-xl"
      style={{
        borderColor: brand.glass.border,
        backgroundColor: brand.glass.bg,
        boxShadow: brand.glass.shadow,
      }}
    >
      <div className="px-4 py-3">
        {/* Header */}
        <div className="flex items-center justify-between mb-3 gap-2">
          <p className="text-sm font-semibold">Activity Feed</p>
          <div className="flex items-center gap-2">
            {unreadCount > 0 && (
              <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20">
                {unreadCount} unread
              </span>
            )}
            {onMarkAllAsRead && unreadCount > 0 && (
              <Button
                size="sm"
                variant="ghost"
                disabled={isMarkingAllRead}
                onClick={onMarkAllAsRead}
                className="h-7 text-xs"
              >
                {isMarkingAllRead ? "Clearing..." : "Clear unread"}
              </Button>
            )}
          </div>
        </div>

        {/* Events */}
        <div
          className="flex flex-col gap-2 overflow-y-auto pr-1"
          style={{ maxHeight: maxHeightToStyle(maxHeight) }}
        >
          {events.length === 0 ? (
            isLoading ? (
              <div className="flex flex-col gap-2 py-1">
                {[0, 1, 2].map((i) => (
                  <Skeleton key={i} className="h-12 w-full rounded-xl" />
                ))}
              </div>
            ) : (
              <div className="py-4">
                <p className="text-sm text-muted-foreground">
                  No activity yet. Send a message to start the feed.
                </p>
              </div>
            )
          ) : (
            events.map((event, index) => (
              <React.Fragment key={event.id}>
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <span
                        className={cn(
                          "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium capitalize",
                          event.type === "system" || event.type === "chat"
                            ? "border"
                            : typeChipClass[event.type],
                        )}
                        style={
                          event.type === "system" || event.type === "chat"
                            ? {
                                backgroundColor: `${brand.primary}1f`,
                                color: brand.primary,
                                borderColor: `${brand.primary}33`,
                              }
                            : undefined
                        }
                      >
                        {event.type.replace(/_/g, " ")}
                      </span>
                      {event.notification_id && event.status === "unread" && (
                        <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
                          unread
                        </span>
                      )}
                      <span className="text-xs text-muted-foreground">
                        {new Date(event.timestamp).toLocaleTimeString()}
                      </span>
                    </div>
                    <p
                      className={cn(
                        "text-sm font-semibold",
                        event.type === "error" ? "text-red-400" : "",
                      )}
                      style={event.type !== "error" ? { color: brand.secondary } : undefined}
                    >
                      {event.title}
                    </p>
                    <p className="text-xs text-muted-foreground">{event.description}</p>
                  </div>
                  {event.notification_id && event.status === "unread" && onMarkAsRead && (
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={markingNotificationId === event.notification_id}
                      onClick={() => onMarkAsRead(event.notification_id as number)}
                      className="h-7 text-xs flex-shrink-0"
                    >
                      {markingNotificationId === event.notification_id ? (
                        <span className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-border border-t-primary" />
                      ) : (
                        "Mark read"
                      )}
                    </Button>
                  )}
                </div>
                {index < events.length - 1 && (
                  <hr className="border-border/40" />
                )}
              </React.Fragment>
            ))
          )}
        </div>
      </div>
    </div>
  );
};

export default AgentFeed;
