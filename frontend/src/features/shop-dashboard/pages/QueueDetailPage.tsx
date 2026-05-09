import React, { useCallback, useEffect, useState } from "react";
import {
  ArrowLeft,
  CheckCircle,
  Clock,
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
import { Card, CardContent } from "@/components/ui/card";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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
  const headers = { Authorization: `Bearer ${token}` };

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
  }, [queueId, shopId]);

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

  const Stat = ({ icon: Icon, value, label }: { icon: React.ElementType; value: number; label: string }) => (
    <Card>
      <CardContent className="flex flex-col items-center gap-1 p-5 text-center">
        <Icon className="size-5 text-primary" />
        <p className="text-2xl font-semibold">{value}</p>
        <p className="text-sm text-muted-foreground">{label}</p>
      </CardContent>
    </Card>
  );

  return (
    <div className="w-full max-w-[1700px]">
      <Header />

      <div className="mb-4 flex items-center gap-2">
        <Button variant="ghost" size="icon" onClick={() => navigate("/queues")}>
          <ArrowLeft />
        </Button>
        <h1 className="text-2xl font-semibold tracking-tight">{queueName}</h1>
        <Badge>{activeItems.length} active</Badge>
      </div>

      {error && (
        <Alert variant="destructive" className="mb-4">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="mb-4 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat icon={Users} value={items.length} label="Total" />
        <Stat icon={Clock} value={waitingCount} label="Waiting" />
        <Stat icon={UserCheck} value={servingCount} label="Being Served" />
        <Stat icon={CheckCircle} value={completedCount} label="Completed" />
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        <Badge variant="outline">Checked Out: {checkedOutCount}</Badge>
        <Badge variant="outline">Historical (Prev Days): {historicalPreviousDaysCount}</Badge>
      </div>

      {employees.length > 0 && (
        <Card className="mb-4">
          <CardContent className="p-5">
            <p className="mb-2 text-sm font-medium text-muted-foreground">Clocked-In Employees</p>
            <div className="flex flex-wrap gap-2">
              {employees.map((employee) => (
                <Badge key={employee.user_id} variant="outline">
                  {employee.username} ({employee.active_items} customers)
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardContent className="p-4">
          <Tabs value={tableView} onValueChange={(value) => setTableView(value as "live" | "historical")}>
            <TabsList>
              <TabsTrigger value="live">Live Queue ({liveRows.length})</TabsTrigger>
              <TabsTrigger value="historical">Historical ({historicalRows.length})</TabsTrigger>
            </TabsList>
            <TabsContent value={tableView} className="mt-4">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>#</TableHead>
                    <TableHead>Customer</TableHead>
                    <TableHead>Phone</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Assigned To</TableHead>
                    <TableHead>Wait Time</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.length ? (
                    rows.map((row) => (
                      <TableRow key={row.id}>
                        <TableCell>{tableView === "live" ? row.live_position : row.position}</TableCell>
                        <TableCell className="font-medium">{row.customer_name}</TableCell>
                        <TableCell>{row.customer_phone || "-"}</TableCell>
                        <TableCell>
                          <Badge variant={statusVariant(row.display_status)} className="capitalize">
                            {row.display_status.replace("_", " ")}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Badge variant={row.assigned_employee ? "default" : "outline"}>
                            {row.assigned_employee?.username || "Unassigned"}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          {row.status === "completed" || row.status === "cancelled" ? "-" : formatWaitTime(row.checked_in_at)}
                        </TableCell>
                        <TableCell>
                          {tableView === "live" && (row.status === "waiting" || row.status === "being_served") && (
                            <div className="flex flex-wrap gap-1">
                              {row.status === "waiting" && (
                                <Button variant="outline" size="sm" onClick={() => handleServe(row.id)}>
                                  <Play data-icon="inline-start" />
                                  Serve
                                </Button>
                              )}
                              {row.status === "being_served" && (
                                <Button variant="outline" size="sm" onClick={() => handleComplete(row.id)}>
                                  <CheckCircle data-icon="inline-start" />
                                  Complete
                                </Button>
                              )}
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => openReassign(row)}
                                disabled={employees.length === 0}
                              >
                                <Shuffle data-icon="inline-start" />
                                Reassign
                              </Button>
                              <Button variant="outline" size="sm" onClick={() => handleRemove(row.id)}>
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
                      <TableCell colSpan={7} className="h-24 text-center text-muted-foreground">
                        No queue items in this view.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      <Dialog open={reassignDialogOpen} onOpenChange={setReassignDialogOpen}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Reassign Customer</DialogTitle>
          </DialogHeader>
          {reassignTarget && (
            <div className="flex flex-col gap-4">
              <p className="text-sm text-muted-foreground">
                Move <strong>{reassignTarget.customer_name}</strong> to a different employee:
              </p>
              <Select value={selectedEmployee} onValueChange={setSelectedEmployee}>
                <SelectTrigger>
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
            <Button variant="outline" onClick={() => setReassignDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleReassign} disabled={!selectedEmployee}>
              Reassign
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default QueueDetailPage;
