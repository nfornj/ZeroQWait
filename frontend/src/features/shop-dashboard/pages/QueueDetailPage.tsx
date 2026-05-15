import React, { useCallback, useEffect, useState } from "react";
import {
  ArrowLeft,
  CheckCircle,
  Clock,
  History,
  Play,
  Shuffle,
  Trash2,
  UserCheck,
  Users,
} from "lucide-react";
import axios from "axios";
import { useNavigate, useParams } from "react-router-dom";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import Header from "../components/Header";

interface QueueItem {
  id: number;
  queue_id: number;
  customer_name: string;
  customer_phone: string | null;
  customer_email: string | null;
  position: number;
  status: string;
  checked_in_at: string;
  service_started_at: string | null;
  completed_at: string | null;
  assigned_employee_id: number | null;
  assigned_employee: { id: number; username: string; email?: string } | null;
  notes: string | null;
}

interface ActiveEmployee {
  user_id: number;
  username: string;
  email: string;
  active_items: number;
  clock_in: string;
}

const CHECKED_OUT_MARKER_PREFIX = "CHECKED_OUT_AT:";

const dashboardSurfaceStyle = {
  "--background": "210 20% 98%",
  "--foreground": "222 47% 11%",
  "--card": "0 0% 100%",
  "--card-foreground": "222 47% 11%",
  "--popover": "0 0% 100%",
  "--popover-foreground": "222 47% 11%",
  "--muted": "210 40% 96%",
  "--muted-foreground": "215 16% 47%",
  "--border": "214 32% 91%",
  "--input": "214 32% 91%",
  "--primary": "154 40% 30%",
  "--primary-foreground": "0 0% 100%",
  "--ring": "154 40% 30%",
} as React.CSSProperties;

type QueueRow = QueueItem & {
  display_status: string;
  live_position: number;
};

function formatWaitTime(checkedInAt: string): string {
  const diff = Date.now() - new Date(checkedInAt).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins}m`;
  return `${Math.floor(mins / 60)}h ${mins % 60}m`;
}

const statusVariant = (status: string): React.ComponentProps<typeof Badge>["variant"] => {
  if (status === "waiting" || status === "being_served") return "secondary";
  if (status === "completed" || status === "checked_out") return "default";
  return "outline";
};

function MetricCard({ icon: Icon, value, label }: { icon: React.ElementType; value: number; label: string }) {
  return (
    <div className="rounded-2xl border border-border bg-card p-5 shadow-none">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-2xl font-bold tracking-tight text-foreground">{value}</p>
          <p className="mt-1 text-sm text-muted-foreground">{label}</p>
        </div>
        <span className="flex h-9 w-9 items-center justify-center rounded-full border border-border bg-background text-primary">
          <Icon className="h-4 w-4" />
        </span>
      </div>
    </div>
  );
}

const QueueDetailPage: React.FC = () => {
  const navigate = useNavigate();
  const { queueId } = useParams<{ queueId: string }>();

  const [items, setItems] = useState<QueueItem[]>([]);
  const [employees, setEmployees] = useState<ActiveEmployee[]>([]);
  const [shopId, setShopId] = useState<number | null>(null);
  const [queueName, setQueueName] = useState("Queue");
  const [error, setError] = useState("");
  const [tableView, setTableView] = useState<"live" | "historical">("live");
  const [reassignDialogOpen, setReassignDialogOpen] = useState(false);
  const [reassignTarget, setReassignTarget] = useState<QueueItem | null>(null);
  const [selectedEmployee, setSelectedEmployee] = useState<string>("");

  const token = localStorage.getItem("token");
  const headers = React.useMemo(() => ({ Authorization: `Bearer ${token}` }), [token]);

  const fetchData = useCallback(async () => {
    if (!queueId) return;
    try {
      const itemsRes = await axios.get(`/queues/${queueId}/items`, { headers });
      setItems(itemsRes.data);

      if (!shopId) {
        const shopRes = await axios.get("/shops/my-shops", { headers });
        if (shopRes.data.length > 0) {
          const sid = shopRes.data[0].id;
          setShopId(sid);
          const queuesRes = await axios.get(`/queues/shop/${sid}/all`, { headers });
          const queue = queuesRes.data.find((candidate: any) => candidate.id === Number(queueId));
          if (queue) setQueueName(queue.name);
        }
      }

      if (shopId) {
        const empRes = await axios.get(`/queues/shop/${shopId}/active-employees`, { headers });
        setEmployees(empRes.data);
      }
    } catch {
      // Keep the last successful snapshot visible while polling continues.
    }
  }, [headers, queueId, shopId]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const handleServe = async (itemId: number) => {
    try {
      await axios.post(`/queues/items/${itemId}/serve`, {}, { headers });
      setError("");
      fetchData();
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to serve customer");
    }
  };

  const handleComplete = async (itemId: number) => {
    try {
      await axios.patch(`/queues/items/${itemId}/status?new_status=completed`, {}, { headers });
      setError("");
      fetchData();
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to complete customer");
    }
  };

  const handleRemove = async (itemId: number) => {
    try {
      await axios.delete(`/queues/items/${itemId}`, { headers });
      setError("");
      fetchData();
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to remove customer");
    }
  };

  const openReassign = (item: QueueItem) => {
    setReassignTarget(item);
    setSelectedEmployee(item.assigned_employee_id ? String(item.assigned_employee_id) : "");
    setReassignDialogOpen(true);
  };

  const handleReassign = async () => {
    if (!reassignTarget || !selectedEmployee) return;
    try {
      await axios.patch(
        `/queues/items/${reassignTarget.id}/reassign`,
        { employee_id: Number(selectedEmployee) },
        { headers },
      );
      setReassignDialogOpen(false);
      setReassignTarget(null);
      setError("");
      fetchData();
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to reassign");
    }
  };

  const isCheckedOut = (item: QueueItem) =>
    typeof item.notes === "string" && item.notes.includes(CHECKED_OUT_MARKER_PREFIX);

  const activeItems = items.filter((item) => item.status === "waiting" || item.status === "being_served");
  const liveRows: QueueRow[] = activeItems
    .slice()
    .sort((a, b) => (a.position || 0) - (b.position || 0))
    .map((item, index) => ({
      ...item,
      display_status: item.status,
      live_position: index + 1,
    }));

  const historicalRows: QueueRow[] = items
    .filter((item) => item.status !== "waiting" && item.status !== "being_served")
    .slice()
    .sort((a, b) => {
      const aTs = new Date(a.completed_at || a.checked_in_at).getTime();
      const bTs = new Date(b.completed_at || b.checked_in_at).getTime();
      return bTs - aTs;
    })
    .map((item) => ({
      ...item,
      display_status: isCheckedOut(item) ? "checked_out" : item.status,
      live_position: item.position,
    }));

  const waitingCount = items.filter((item) => item.status === "waiting").length;
  const servingCount = items.filter((item) => item.status === "being_served").length;
  const checkedOutCount = items.filter((item) => isCheckedOut(item)).length;
  const completedCount = items.filter((item) => item.status === "completed" && !isCheckedOut(item)).length;

  const startOfToday = new Date();
  startOfToday.setHours(0, 0, 0, 0);
  const historicalPreviousDaysCount = historicalRows.filter(
    (item) => new Date(item.checked_in_at).getTime() < startOfToday.getTime(),
  ).length;

  const rows = tableView === "live" ? liveRows : historicalRows;

  return (
    <div className="flex min-h-full w-full flex-col bg-[#f9fafb] px-3 pb-16 md:px-6" style={dashboardSurfaceStyle}>
      <Header />

      <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="mb-3 flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              className="h-9 w-9 rounded-xl text-muted-foreground hover:bg-muted/70 hover:text-foreground"
              onClick={() => navigate("/queues")}
            >
              <ArrowLeft className="h-4 w-4" />
            </Button>
            <Badge className="rounded-full bg-primary/10 text-primary hover:bg-primary/10">
              {activeItems.length} active
            </Badge>
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">{queueName}</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Monitor live customers, assignments, and completion flow for this queue.
          </p>
        </div>
        <div className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap">
          <Badge variant="outline" className="rounded-full border-border bg-card px-3 py-1 text-muted-foreground">
            Checked out: {checkedOutCount}
          </Badge>
          <Badge variant="outline" className="rounded-full border-border bg-card px-3 py-1 text-muted-foreground">
            Previous days: {historicalPreviousDaysCount}
          </Badge>
        </div>
      </div>

      {error && (
        <Alert variant="destructive" className="mb-4 rounded-2xl">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <MetricCard icon={Users} value={items.length} label="Total customers" />
        <MetricCard icon={Clock} value={waitingCount} label="Waiting" />
        <MetricCard icon={UserCheck} value={servingCount} label="Being served" />
        <MetricCard icon={CheckCircle} value={completedCount} label="Completed" />
      </div>

      <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-12">
        <div className="rounded-2xl border border-border bg-card p-5 shadow-none lg:col-span-8">
          <div className="flex items-start gap-3">
            <span className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full border border-border bg-background text-primary">
              <Users className="h-5 w-5" />
            </span>
            <div>
              <h2 className="text-base font-semibold tracking-tight text-foreground">Clocked-in employees</h2>
              <p className="mt-1 text-sm leading-6 text-muted-foreground">
                Current coverage and active customer load for this queue.
              </p>
            </div>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            {employees.length > 0 ? (
              employees.map((employee) => (
                <Badge key={employee.user_id} variant="outline" className="rounded-full border-border bg-background px-3 py-1 text-foreground">
                  {employee.username} ({employee.active_items} customer{employee.active_items !== 1 ? "s" : ""})
                </Badge>
              ))
            ) : (
              <div className="rounded-xl border border-dashed border-border bg-background px-4 py-3 text-sm text-muted-foreground">
                No clocked-in employees are assigned right now.
              </div>
            )}
          </div>
        </div>

        <div className="rounded-2xl border border-border bg-card p-5 shadow-none lg:col-span-4">
          <div className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-border bg-background text-primary">
            <History className="h-5 w-5" />
          </div>
          <h2 className="mt-4 text-base font-semibold tracking-tight text-foreground">Queue history</h2>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">
            Switch between the live queue and completed or checked-out customers without leaving this page.
          </p>
        </div>
      </div>

      <div className="rounded-2xl border border-border bg-card p-4 shadow-none">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 className="text-base font-semibold tracking-tight text-foreground">Customer flow</h2>
            <p className="mt-1 text-sm text-muted-foreground">Serve, complete, reassign, or remove live customers.</p>
          </div>
          <Tabs value={tableView} onValueChange={(value) => setTableView(value as "live" | "historical")}>
            <TabsList className="rounded-xl bg-muted p-1">
              <TabsTrigger
                value="live"
                className="rounded-lg px-3 data-[state=active]:bg-card data-[state=active]:shadow-sm"
              >
                Live queue ({liveRows.length})
              </TabsTrigger>
              <TabsTrigger
                value="historical"
                className="rounded-lg px-3 data-[state=active]:bg-card data-[state=active]:shadow-sm"
              >
                Historical ({historicalRows.length})
              </TabsTrigger>
            </TabsList>
          </Tabs>
        </div>

        <div className="mt-4 overflow-x-auto rounded-xl border border-border bg-background">
          <Table>
            <TableHeader className="bg-muted/35">
              <TableRow>
                <TableHead className="h-11 text-xs font-semibold uppercase tracking-wide text-muted-foreground">#</TableHead>
                <TableHead className="h-11 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Customer</TableHead>
                <TableHead className="h-11 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Phone</TableHead>
                <TableHead className="h-11 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Status</TableHead>
                <TableHead className="h-11 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Assigned to</TableHead>
                <TableHead className="h-11 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Wait time</TableHead>
                <TableHead className="h-11 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.length ? (
                rows.map((row) => (
                  <TableRow key={row.id} className="hover:bg-muted/35">
                    <TableCell>{tableView === "live" ? row.live_position : row.position}</TableCell>
                    <TableCell className="font-medium text-foreground">{row.customer_name}</TableCell>
                    <TableCell className="whitespace-nowrap">{row.customer_phone || "-"}</TableCell>
                    <TableCell>
                      <Badge variant={statusVariant(row.display_status)} className="rounded-full capitalize">
                        {row.display_status.replace("_", " ")}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={row.assigned_employee ? "default" : "outline"}
                        className="rounded-full"
                      >
                        {row.assigned_employee?.username || "Unassigned"}
                      </Badge>
                    </TableCell>
                    <TableCell className="whitespace-nowrap">
                      {row.status === "completed" || row.status === "cancelled" ? "-" : formatWaitTime(row.checked_in_at)}
                    </TableCell>
                    <TableCell>
                      {tableView === "live" && (row.status === "waiting" || row.status === "being_served") && (
                        <div className="flex min-w-max flex-wrap gap-2">
                          {row.status === "waiting" && (
                            <Button
                              variant="outline"
                              size="sm"
                              className="rounded-xl border-border bg-card shadow-none"
                              onClick={() => handleServe(row.id)}
                            >
                              <Play data-icon="inline-start" />
                              Serve
                            </Button>
                          )}
                          {row.status === "being_served" && (
                            <Button
                              variant="outline"
                              size="sm"
                              className="rounded-xl border-border bg-card shadow-none"
                              onClick={() => handleComplete(row.id)}
                            >
                              <CheckCircle data-icon="inline-start" />
                              Complete
                            </Button>
                          )}
                          <Button
                            variant="outline"
                            size="sm"
                            className="rounded-xl border-border bg-card shadow-none"
                            onClick={() => openReassign(row)}
                            disabled={employees.length === 0}
                          >
                            <Shuffle data-icon="inline-start" />
                            Reassign
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            className="rounded-xl border-border bg-card text-destructive shadow-none hover:bg-destructive/10 hover:text-destructive"
                            onClick={() => handleRemove(row.id)}
                          >
                            <Trash2 data-icon="inline-start" />
                            Remove
                          </Button>
                        </div>
                      )}
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={7} className="h-28 text-center text-muted-foreground">
                    No queue items in this view.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </div>

      <Dialog open={reassignDialogOpen} onOpenChange={setReassignDialogOpen}>
        <DialogContent className="rounded-2xl sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Reassign Customer</DialogTitle>
          </DialogHeader>
          {reassignTarget && (
            <div className="flex flex-col gap-4">
              <p className="text-sm text-muted-foreground">
                Move <strong>{reassignTarget.customer_name}</strong> to a different employee:
              </p>
              <Select value={selectedEmployee} onValueChange={setSelectedEmployee}>
                <SelectTrigger className="rounded-xl border-border bg-background">
                  <SelectValue placeholder="Employee" />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    {employees.map((employee) => (
                      <SelectItem key={employee.user_id} value={String(employee.user_id)}>
                        {employee.username} - {employee.active_items} customer{employee.active_items !== 1 ? "s" : ""}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" className="rounded-xl" onClick={() => setReassignDialogOpen(false)}>
              Cancel
            </Button>
            <Button className="rounded-xl" onClick={handleReassign} disabled={!selectedEmployee}>
              Reassign
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default QueueDetailPage;
