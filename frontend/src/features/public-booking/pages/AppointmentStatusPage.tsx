import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Loader2, CheckCircle2, Calendar, Clock, XCircle, AlertCircle } from "lucide-react";

interface AppointmentStatus {
  appointment_id: number;
  status: string;
  customer_name: string;
  scheduled_start: string | null;
  scheduled_end: string | null;
  service_name: string | null;
  shop_name: string;
  shop_slug: string | null;
}

const statusConfig: Record<
  string,
  { label: string; color: "default" | "secondary" | "destructive" | "outline"; icon: React.ReactNode }
> = {
  scheduled: {
    label: "Confirmed",
    color: "default",
    icon: <CheckCircle2 className="h-4 w-4" />,
  },
  confirmed: {
    label: "Confirmed",
    color: "default",
    icon: <CheckCircle2 className="h-4 w-4" />,
  },
  in_progress: {
    label: "In Progress — You're being served",
    color: "default",
    icon: <Clock className="h-4 w-4" />,
  },
  completed: {
    label: "Completed",
    color: "outline",
    icon: <CheckCircle2 className="h-4 w-4" />,
  },
  cancelled: {
    label: "Cancelled",
    color: "destructive",
    icon: <XCircle className="h-4 w-4" />,
  },
  no_show: {
    label: "No Show",
    color: "destructive",
    icon: <AlertCircle className="h-4 w-4" />,
  },
};

function formatDateTime(iso: string) {
  const d = new Date(iso);
  return {
    date: d.toLocaleDateString("en-CA", { weekday: "long", year: "numeric", month: "long", day: "numeric" }),
    time: d.toLocaleTimeString("en-CA", { hour: "2-digit", minute: "2-digit" }),
  };
}

export default function AppointmentStatusPage() {
  const { token } = useParams<{ token: string }>();
  const [data, setData] = useState<AppointmentStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [cancelled, setCancelled] = useState(false);

  useEffect(() => {
    if (!token) return;
    axios
      .get(`/api/v1/book/status/${token}`)
      .then((res) => setData(res.data as AppointmentStatus))
      .catch(() => setError("Appointment not found or the link has expired."))
      .finally(() => setLoading(false));
  }, [token]);

  const handleCancel = async () => {
    if (!token) return;
    setCancelling(true);
    try {
      await axios.get(`/api/v1/book/cancel/${token}`);
      setCancelled(true);
      setData((prev) => (prev ? { ...prev, status: "cancelled" } : prev));
    } catch {
      setError("Could not cancel the appointment. Please contact the shop directly.");
    } finally {
      setCancelling(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle className="text-destructive">Appointment Not Found</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground text-sm">{error ?? "This link may be invalid or expired."}</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const cfg = statusConfig[data.status] ?? { label: data.status, color: "secondary" as const, icon: null };
  const scheduled = data.scheduled_start ? formatDateTime(data.scheduled_start) : null;
  const isActive = !["cancelled", "completed", "no_show"].includes(data.status);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-gray-50 px-4 py-12">
      <Card className="w-full max-w-md shadow-md">
        <CardHeader className="rounded-t-xl bg-teal-600 pb-4 pt-5 text-white">
          <div className="flex items-center gap-3">
            <Calendar className="h-6 w-6 flex-shrink-0" />
            <div>
              <CardTitle className="text-xl font-semibold">Appointment Status</CardTitle>
              <p className="mt-0.5 text-sm text-teal-100">{data.shop_name}</p>
            </div>
          </div>
        </CardHeader>

        <CardContent className="space-y-5 pt-5">
          {/* Status badge */}
          <div className="flex items-center gap-2">
            <Badge variant={cfg.color} className="gap-1.5 px-3 py-1 text-sm">
              {cfg.icon}
              {cfg.label}
            </Badge>
          </div>

          {/* Appointment details */}
          <div className="rounded-lg border bg-muted/30 divide-y text-sm">
            {data.service_name && (
              <div className="flex justify-between px-4 py-3">
                <span className="text-muted-foreground">Service</span>
                <span className="font-medium">{data.service_name}</span>
              </div>
            )}
            {scheduled && (
              <>
                <div className="flex justify-between px-4 py-3">
                  <span className="text-muted-foreground">Date</span>
                  <span className="font-medium">{scheduled.date}</span>
                </div>
                <div className="flex justify-between px-4 py-3">
                  <span className="text-muted-foreground">Time</span>
                  <span className="font-medium">{scheduled.time}</span>
                </div>
              </>
            )}
            <div className="flex justify-between px-4 py-3">
              <span className="text-muted-foreground">Name</span>
              <span className="font-medium">{data.customer_name}</span>
            </div>
          </div>

          {/* Reminder */}
          {data.status === "scheduled" || data.status === "confirmed" ? (
            <p className="text-sm text-muted-foreground">
              You will receive a reminder email when it is almost your turn.
            </p>
          ) : null}

          {/* Cancel button — only shown while appointment is still active */}
          {isActive && !cancelled && (
            <Button
              variant="outline"
              className="w-full border-destructive text-destructive hover:bg-destructive hover:text-white"
              onClick={() => void handleCancel()}
              disabled={cancelling}
            >
              {cancelling ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              Cancel Appointment
            </Button>
          )}

          {cancelled && (
            <p className="text-center text-sm text-muted-foreground">
              Your appointment has been cancelled.
            </p>
          )}
        </CardContent>
      </Card>

      <p className="mt-6 text-xs text-muted-foreground">Powered by ZeroQwait</p>
    </div>
  );
}
