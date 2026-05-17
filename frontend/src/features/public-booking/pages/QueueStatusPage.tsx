import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Loader2, CheckCircle2, Clock, UserCheck } from "lucide-react";

interface QueueStatus {
  customer_name: string;
  position: number | null;
  status: string;
  estimated_wait_minutes: number | null;
  shop_name: string;
  service_name: string | null;
  checked_in_at: string | null;
}

const POLL_INTERVAL_MS = 30_000;

const statusConfig: Record<string, { label: string; color: "default" | "secondary" | "destructive" | "outline"; icon: React.ReactNode }> = {
  waiting: {
    label: "Waiting",
    color: "secondary",
    icon: <Clock className="h-4 w-4" />,
  },
  being_served: {
    label: "Being Served — Head to the counter!",
    color: "default",
    icon: <UserCheck className="h-4 w-4" />,
  },
  completed: {
    label: "Service Completed",
    color: "outline",
    icon: <CheckCircle2 className="h-4 w-4" />,
  },
  cancelled: {
    label: "Cancelled",
    color: "destructive",
    icon: <CheckCircle2 className="h-4 w-4" />,
  },
};

export default function QueueStatusPage() {
  const { token } = useParams<{ token: string }>();
  const [data, setData] = useState<QueueStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchStatus = async () => {
    if (!token) return;
    try {
      const res = await axios.get(`/api/queues/status/${token}`);
      setData(res.data);
      setError(null);
      setLastUpdated(new Date());
    } catch (err: any) {
      if (err.response?.status === 404) {
        setError("Queue status not found. This link may be invalid or expired.");
      } else {
        setError("Unable to load queue status. Please try again in a moment.");
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    const timer = setInterval(fetchStatus, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const isTerminal = data?.status === "completed" || data?.status === "cancelled";

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "linear-gradient(135deg, #f0f4ff 0%, #e8f5e9 100%)",
        padding: "24px",
      }}
    >
      <Card style={{ maxWidth: 440, width: "100%", borderRadius: 20 }}>
        <CardHeader style={{ textAlign: "center", paddingBottom: 8 }}>
          <div
            style={{
              fontSize: 13,
              fontWeight: 600,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              color: "#888",
              marginBottom: 4,
            }}
          >
            ZeroQwait
          </div>
          <CardTitle style={{ fontSize: 22 }}>
            {data ? data.shop_name : "Queue Status"}
          </CardTitle>
          {data?.service_name && (
            <div style={{ color: "#666", fontSize: 14, marginTop: 4 }}>
              {data.service_name}
            </div>
          )}
        </CardHeader>

        <CardContent>
          {loading && (
            <div style={{ textAlign: "center", padding: "32px 0" }}>
              <Loader2
                className="animate-spin"
                style={{ margin: "0 auto 12px", color: "#1976d2" }}
                size={32}
              />
              <div style={{ color: "#666" }}>Loading your queue status…</div>
            </div>
          )}

          {error && !loading && (
            <div
              style={{
                background: "#fff3f3",
                border: "1px solid #ffcccc",
                borderRadius: 12,
                padding: 16,
                color: "#c62828",
                textAlign: "center",
              }}
            >
              {error}
            </div>
          )}

          {data && !loading && (
            <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
              {/* Greeting */}
              <div style={{ textAlign: "center", fontSize: 18, fontWeight: 500 }}>
                Hi, {data.customer_name}!
              </div>

              {/* Status badge */}
              <div style={{ display: "flex", justifyContent: "center" }}>
                {(() => {
                  const cfg = statusConfig[data.status] ?? statusConfig.waiting;
                  return (
                    <Badge
                      variant={cfg.color}
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: 6,
                        fontSize: 14,
                        padding: "8px 16px",
                        borderRadius: 999,
                      }}
                    >
                      {cfg.icon}
                      {cfg.label}
                    </Badge>
                  );
                })()}
              </div>

              {/* Position + wait */}
              {!isTerminal && (
                <div
                  style={{
                    display: "flex",
                    gap: 12,
                    justifyContent: "center",
                  }}
                >
                  {data.position !== null && data.position !== undefined && (
                    <div
                      style={{
                        flex: 1,
                        background: "#f5f7ff",
                        borderRadius: 16,
                        padding: "16px 12px",
                        textAlign: "center",
                      }}
                    >
                      <div
                        style={{
                          fontSize: 36,
                          fontWeight: 700,
                          color: "#1565c0",
                          lineHeight: 1,
                        }}
                      >
                        #{data.position}
                      </div>
                      <div style={{ fontSize: 12, color: "#888", marginTop: 4 }}>
                        Your position
                      </div>
                    </div>
                  )}

                  {data.estimated_wait_minutes !== null &&
                    data.estimated_wait_minutes !== undefined && (
                      <div
                        style={{
                          flex: 1,
                          background: "#f5f7ff",
                          borderRadius: 16,
                          padding: "16px 12px",
                          textAlign: "center",
                        }}
                      >
                        <div
                          style={{
                            fontSize: 36,
                            fontWeight: 700,
                            color: "#1565c0",
                            lineHeight: 1,
                          }}
                        >
                          {data.estimated_wait_minutes}
                        </div>
                        <div style={{ fontSize: 12, color: "#888", marginTop: 4 }}>
                          Est. minutes
                        </div>
                      </div>
                    )}
                </div>
              )}

              {/* Terminal state message */}
              {isTerminal && (
                <div
                  style={{
                    background: "#f1f8e9",
                    borderRadius: 12,
                    padding: 16,
                    textAlign: "center",
                    color: "#33691e",
                    fontSize: 15,
                  }}
                >
                  {data.status === "completed"
                    ? "Your service is complete. Thank you for visiting!"
                    : "This queue entry has been cancelled."}
                </div>
              )}

              {/* Last updated + auto-refresh note */}
              {!isTerminal && lastUpdated && (
                <div
                  style={{
                    fontSize: 11,
                    color: "#bbb",
                    textAlign: "center",
                    marginTop: -8,
                  }}
                >
                  Updated {lastUpdated.toLocaleTimeString()} · refreshes every 30s
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
