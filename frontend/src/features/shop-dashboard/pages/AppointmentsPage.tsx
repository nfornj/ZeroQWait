import React, { useCallback, useEffect, useMemo, useState } from "react";
import axios from "axios";
import {
  CheckCircle,
  CircleOff,
  Clock,
  Play,
  RefreshCw,
  UserX,
  XCircle,
} from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import Header from "../components/Header";
import { useShop } from "../../../contexts/ShopContext";

interface AppointmentRow {
  id: number;
  customer_name: string;
  customer_phone: string | null;
  scheduled_start: string;
  scheduled_end: string;
  status: string;
  service_id: number | null;
  employee_id: number | null;
  service_cost: number;
  notes: string | null;
  created_at: string;
}

interface EmployeeAvailability {
  employee_id: number;
  username: string;
  is_clocked_in: boolean;
  shift_start: string | null;
  appointments_today: number;
  next_available_slot: string | null;
}

const statusVariant = (status: string): React.ComponentProps<typeof Badge>["variant"] => {
  if (status === "cancelled" || status === "no_show") return "destructive";
  if (status === "completed" || status === "confirmed") return "default";
  return "secondary";
};

const formatStatus = (status: string) => status.replace("_", " ");

const AppointmentsPage: React.FC = () => {
  const { shop } = useShop();
  const [appointments, setAppointments] = useState<AppointmentRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedDate, setSelectedDate] = useState(() => new Date().toISOString().split("T")[0]);
  const [statusFilter, setStatusFilter] = useState("all");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [employeeAvailability, setEmployeeAvailability] = useState<EmployeeAvailability[]>([]);
  const [unavailableEmployees, setUnavailableEmployees] = useState<{ employee_id: number; username: string }[]>([]);

  const token = localStorage.getItem("token");
  const headers = useMemo(() => ({ Authorization: `Bearer ${token}` }), [token]);

  const fetchAppointments = useCallback(async () => {
    if (!shop) return;
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (selectedDate) params.date = selectedDate;
      if (statusFilter !== "all") params.status = statusFilter;

      const res = await axios.get(`/appointments/shop/${shop.id}`, { headers, params });
      setAppointments(res.data);
    } catch {
      setError("Failed to load appointments");
    } finally {
      setLoading(false);
    }
  }, [headers, shop, selectedDate, statusFilter]);

  const fetchAvailability = useCallback(async () => {
    if (!shop) return;
    try {
      const [avail, unavail] = await Promise.all([
        axios.get(`/appointments/shop/${shop.id}/employee-availability`, {
          headers,
          params: { date: selectedDate },
        }),
        axios.get(`/appointments/shop/${shop.id}/unavailable-employees`, { headers }),
      ]);
      setEmployeeAvailability(avail.data);
      setUnavailableEmployees(unavail.data);
    } catch {
      // Availability is advisory; appointment list remains the primary surface.
    }
  }, [headers, shop, selectedDate]);

  useEffect(() => {
    fetchAppointments();
    fetchAvailability();
  }, [fetchAppointments, fetchAvailability]);

  const handleStatusChange = async (appointmentId: number, newStatus: string) => {
    if (!shop) return;
    try {
      await axios.patch(`/appointments/${appointmentId}/status`, null, {
        headers,
        params: { shop_id: shop.id, new_status: newStatus },
      });
      setSuccess(`Appointment updated to ${newStatus}`);
      fetchAppointments();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to update status");
    }
  };

  const statusActions = (appointment: AppointmentRow) => {
    const status = appointment.status;
    const actions: Array<{ label: string; icon: React.ElementType; status: string; variant?: "default" | "outline" | "destructive" }> = [];

    if (status === "scheduled") {
      actions.push({ label: "Confirm", icon: CheckCircle, status: "confirmed" });
      actions.push({ label: "Cancel", icon: XCircle, status: "cancelled", variant: "destructive" });
    }
    if (status === "confirmed") {
      actions.push({ label: "Check In", icon: Clock, status: "checked_in", variant: "outline" });
      actions.push({ label: "No Show", icon: UserX, status: "no_show", variant: "outline" });
    }
    if (status === "checked_in") {
      actions.push({ label: "Start", icon: Play, status: "in_progress" });
    }
    if (status === "in_progress") {
      actions.push({ label: "Complete", icon: CheckCircle, status: "completed" });
    }

    return actions;
  };

  return (
    <div className="flex flex-col gap-4">
      <Header />
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Appointments</h1>
        <p className="mt-1 text-sm text-muted-foreground">Manage scheduled bookings and employee availability</p>
      </div>

      {unavailableEmployees.length > 0 && (
        <Alert>
          <UserX className="size-4" />
          <AlertDescription>
            <strong>Not clocked in today:</strong> {unavailableEmployees.map((employee) => employee.username).join(", ")}
          </AlertDescription>
        </Alert>
      )}

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {success && (
        <Alert>
          <AlertDescription>{success}</AlertDescription>
        </Alert>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <Input
          type="date"
          aria-label="Date"
          value={selectedDate}
          onChange={(event) => setSelectedDate(event.target.value)}
          className="w-[170px]"
        />
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              <SelectItem value="all">All</SelectItem>
              <SelectItem value="scheduled">Scheduled</SelectItem>
              <SelectItem value="confirmed">Confirmed</SelectItem>
              <SelectItem value="checked_in">Checked In</SelectItem>
              <SelectItem value="in_progress">In Progress</SelectItem>
              <SelectItem value="completed">Completed</SelectItem>
              <SelectItem value="cancelled">Cancelled</SelectItem>
              <SelectItem value="no_show">No Show</SelectItem>
            </SelectGroup>
          </SelectContent>
        </Select>
        <Button variant="outline" size="icon" onClick={() => { fetchAppointments(); fetchAvailability(); }}>
          <RefreshCw />
        </Button>
      </div>

      {employeeAvailability.length > 0 && (
        <section>
          <p className="mb-2 text-sm font-medium text-muted-foreground">Employee Load Today</p>
          <div className="flex flex-wrap gap-2">
            {employeeAvailability.map((employee) => (
              <Card key={employee.employee_id} className={employee.is_clocked_in ? "border-success" : "opacity-60"}>
                <CardContent className="p-3">
                  <div className="flex items-center gap-2">
                    <span className={employee.is_clocked_in ? "size-2 rounded-full bg-success" : "size-2 rounded-full bg-muted-foreground"} />
                    <p className="text-sm font-semibold">{employee.username}</p>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">{employee.appointments_today} appts today</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Scheduled Bookings</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex flex-col gap-2">
              {Array.from({ length: 6 }).map((_, index) => (
                <Skeleton key={index} className="h-10 w-full" />
              ))}
            </div>
          ) : appointments.length === 0 ? (
            <div className="flex h-40 flex-col items-center justify-center gap-2 text-center text-muted-foreground">
              <CircleOff className="size-8" />
              <p>No appointments found.</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>ID</TableHead>
                  <TableHead>Customer</TableHead>
                  <TableHead>Phone</TableHead>
                  <TableHead>Time</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Cost</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {appointments.map((appointment) => (
                  <TableRow key={appointment.id}>
                    <TableCell>{appointment.id}</TableCell>
                    <TableCell className="font-medium">{appointment.customer_name}</TableCell>
                    <TableCell>{appointment.customer_phone || "-"}</TableCell>
                    <TableCell>
                      {appointment.scheduled_start
                        ? `${new Date(appointment.scheduled_start).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} ${new Date(appointment.scheduled_start).toLocaleDateString([], { month: "short", day: "numeric" })}`
                        : "-"}
                    </TableCell>
                    <TableCell>
                      <Badge variant={statusVariant(appointment.status)} className="capitalize">
                        {formatStatus(appointment.status)}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      ${Number(appointment.service_cost || 0).toFixed(2)}
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {statusActions(appointment).map((action) => {
                          const Icon = action.icon;
                          return (
                            <Button
                              key={action.label}
                              type="button"
                              variant={action.variant || "outline"}
                              size="sm"
                              onClick={() => handleStatusChange(appointment.id, action.status)}
                            >
                              <Icon data-icon="inline-start" />
                              {action.label}
                            </Button>
                          );
                        })}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default AppointmentsPage;
