import React, { useCallback, useEffect, useState } from "react";
import {
  CheckCircle,
  Store,
  TrendingUp,
  Users,
  X,
} from "lucide-react";
import axios from "axios";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
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
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { constructShopUrl } from "../../../utils/domainUtils";

interface DashboardStats {
  total_shops: number;
  active_shops: number;
  total_users: number;
  real_time: {
    active_customers: number;
    completed_today: number;
  };
}

interface ShopStatus {
  id: number;
  name: string;
  slug: string;
  is_active: boolean;
  waiting_count: number;
  last_activity: string | null;
}

interface FeedbackItem {
  id: number;
  ticket_id: string;
  session_id: string | null;
  name: string | null;
  email: string | null;
  description: string;
  page_context: string | null;
  screenshot_filename: string | null;
  status: "open" | "reviewed" | "closed";
  admin_notes: string | null;
  submitted_at: string;
  updated_at: string;
}

const statusVariant = (status: FeedbackItem["status"]): React.ComponentProps<typeof Badge>["variant"] => {
  if (status === "open") return "secondary";
  if (status === "reviewed") return "default";
  return "outline";
};

const MasterDashboardPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState("overview");
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [shops, setShops] = useState<ShopStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [feedbacks, setFeedbacks] = useState<FeedbackItem[]>([]);
  const [feedbackLoading, setFeedbackLoading] = useState(false);
  const [feedbackError, setFeedbackError] = useState<string | null>(null);
  const [selectedFeedback, setSelectedFeedback] = useState<FeedbackItem | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [editStatus, setEditStatus] = useState<string>("open");
  const [editNotes, setEditNotes] = useState<string>("");
  const [saving, setSaving] = useState(false);

  const authHeaders = () => ({
    Authorization: `Bearer ${localStorage.getItem("token")}`,
  });

  const fetchData = async () => {
    try {
      const [statsRes, shopsRes] = await Promise.all([
        axios.get("/admin/dashboard-stats", { headers: authHeaders() }),
        axios.get("/admin/shops-status", { headers: authHeaders() }),
      ]);
      setStats(statsRes.data);
      setShops(shopsRes.data);
      setError(null);
      setLastUpdated(new Date());
    } catch (err: any) {
      if (loading) {
        setError(err.response?.data?.detail || "Failed to fetch dashboard data");
      }
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const fetchFeedbacks = useCallback(async () => {
    setFeedbackLoading(true);
    try {
      const res = await axios.get("/api/chat-feedback/", { headers: authHeaders() });
      setFeedbacks(res.data);
      setFeedbackError(null);
    } catch (err: any) {
      setFeedbackError(err.response?.data?.detail || "Failed to load feedback");
    } finally {
      setFeedbackLoading(false);
    }
  }, []);

  useEffect(() => {
    let isMounted = true;
    const poll = async () => {
      if (!isMounted) return;
      await fetchData();
      if (isMounted) setTimeout(poll, 2000);
    };
    poll();
    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    if (activeTab === "feedback") fetchFeedbacks();
  }, [activeTab, fetchFeedbacks]);

  const openDetail = (feedback: FeedbackItem) => {
    setSelectedFeedback(feedback);
    setEditStatus(feedback.status);
    setEditNotes(feedback.admin_notes ?? "");
    setDetailOpen(true);
  };

  const saveDetail = async () => {
    if (!selectedFeedback) return;
    setSaving(true);
    try {
      await axios.patch(
        `/api/chat-feedback/${selectedFeedback.ticket_id}`,
        { status: editStatus, admin_notes: editNotes },
        { headers: authHeaders() },
      );
      setDetailOpen(false);
      fetchFeedbacks();
    } catch (err: any) {
      alert(err.response?.data?.detail || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  if (loading && !stats) {
    return (
      <div className="mx-auto flex min-h-[60vh] w-full max-w-6xl flex-col justify-center gap-4 p-6">
        <Skeleton className="h-12 w-96" />
        <Skeleton className="h-60 w-full" />
      </div>
    );
  }

  const openFeedbackCount = feedbacks.filter((feedback) => feedback.status === "open").length;

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-8">
      <div className="mb-6 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-3xl font-bold tracking-tight text-primary">Corporate Master Dashboard</h1>
            <Badge className="animate-pulse">LIVE</Badge>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">Real-time platform overview and shop performance</p>
        </div>
        {lastUpdated && (
          <p className="text-xs text-muted-foreground">Last updated: {lastUpdated.toLocaleTimeString()}</p>
        )}
      </div>

      {error && (
        <Alert variant="destructive" className="mb-4">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Tabs value={activeTab} onValueChange={setActiveTab} className="flex flex-col gap-4">
        <TabsList className="w-fit">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="feedback">
            Feedback
            {openFeedbackCount > 0 && <Badge variant="secondary">{openFeedbackCount}</Badge>}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <MetricCard title="Total Shops" value={stats?.total_shops || 0} icon={<Store />} />
            <MetricCard title="Active Customers" value={stats?.real_time.active_customers || 0} icon={<Users />} />
            <MetricCard title="Completed Today" value={stats?.real_time.completed_today || 0} icon={<CheckCircle />} />
            <MetricCard title="Platform Load" value={`${stats?.active_shops || 0} Active`} icon={<TrendingUp />} />
          </div>

          <h2 className="mb-3 text-xl font-semibold tracking-tight">Live Shop Feed</h2>
          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Shop Name</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Waiting</TableHead>
                    <TableHead>Last Activity</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {shops.map((shop) => (
                    <TableRow
                      key={shop.id}
                      className="cursor-pointer"
                      onClick={() => {
                        window.location.href = constructShopUrl(shop.slug);
                      }}
                    >
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{shop.name}</span>
                          <span className="text-xs text-muted-foreground">@{shop.slug}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant={shop.is_active ? "default" : "secondary"}>
                          {shop.is_active ? "Online" : "Offline"}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <span className="font-semibold">{shop.waiting_count}</span>{" "}
                        <span className="text-xs text-muted-foreground">customers</span>
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {shop.last_activity ? new Date(shop.last_activity).toLocaleTimeString() : "No recent activity"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="feedback">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-xl font-semibold tracking-tight">User Feedback</h2>
            <Button size="sm" variant="outline" onClick={fetchFeedbacks} disabled={feedbackLoading}>
              Refresh
            </Button>
          </div>

          {feedbackError && (
            <Alert variant="destructive" className="mb-4">
              <AlertDescription>{feedbackError}</AlertDescription>
            </Alert>
          )}

          {feedbackLoading && feedbacks.length === 0 ? (
            <Skeleton className="h-60 w-full" />
          ) : feedbacks.length === 0 ? (
            <Alert>
              <AlertDescription>No feedback submissions yet.</AlertDescription>
            </Alert>
          ) : (
            <Card>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Ticket ID</TableHead>
                      <TableHead>Name</TableHead>
                      <TableHead>Description</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Date</TableHead>
                      <TableHead>Screenshot</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {feedbacks.map((feedback) => (
                      <TableRow key={feedback.id} className="cursor-pointer" onClick={() => openDetail(feedback)}>
                        <TableCell className="font-mono text-xs font-bold">{feedback.ticket_id}</TableCell>
                        <TableCell>
                          <p className="text-sm">{feedback.name || <em>anonymous</em>}</p>
                          {feedback.email && <p className="text-xs text-muted-foreground">{feedback.email}</p>}
                        </TableCell>
                        <TableCell className="max-w-[260px] truncate" title={feedback.description}>
                          {feedback.description}
                        </TableCell>
                        <TableCell>
                          <Badge variant={statusVariant(feedback.status)}>{feedback.status}</Badge>
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {new Date(feedback.submitted_at).toLocaleDateString()}
                        </TableCell>
                        <TableCell>
                          {feedback.screenshot_filename ? <Badge variant="outline">Yes</Badge> : <span className="text-muted-foreground">-</span>}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>

      <Dialog open={detailOpen} onOpenChange={setDetailOpen}>
        <DialogContent className="sm:max-w-xl">
          <DialogHeader>
            <div className="flex items-start justify-between gap-3">
              <div>
                <DialogTitle>Feedback Detail</DialogTitle>
                <p className="mt-1 font-mono text-xs text-muted-foreground">{selectedFeedback?.ticket_id}</p>
              </div>
              <Button variant="ghost" size="icon" onClick={() => setDetailOpen(false)} aria-label="Close">
                <X />
              </Button>
            </div>
          </DialogHeader>
          {selectedFeedback && (
            <div className="flex flex-col gap-4">
              <section>
                <p className="text-xs font-semibold uppercase text-muted-foreground">Submitted by</p>
                <p className="text-sm">
                  {selectedFeedback.name || "Anonymous"}
                  {selectedFeedback.email ? ` - ${selectedFeedback.email}` : ""}
                </p>
                <p className="text-xs text-muted-foreground">{new Date(selectedFeedback.submitted_at).toLocaleString()}</p>
              </section>
              <section>
                <p className="text-xs font-semibold uppercase text-muted-foreground">Description</p>
                <p className="whitespace-pre-wrap text-sm">{selectedFeedback.description}</p>
              </section>
              {selectedFeedback.screenshot_filename && (
                <section>
                  <p className="text-xs font-semibold uppercase text-muted-foreground">Screenshot</p>
                  <img
                    src={`/api/chat-feedback/screenshot/${selectedFeedback.screenshot_filename}`}
                    alt="Feedback screenshot"
                    className="mt-2 max-h-[300px] max-w-full rounded-md border object-contain"
                  />
                </section>
              )}
              <Select value={editStatus} onValueChange={setEditStatus}>
                <SelectTrigger>
                  <SelectValue placeholder="Status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectItem value="open">Open</SelectItem>
                    <SelectItem value="reviewed">Reviewed</SelectItem>
                    <SelectItem value="closed">Closed</SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>
              <Textarea
                value={editNotes}
                onChange={(event) => setEditNotes(event.target.value)}
                placeholder="Internal notes (not visible to user)"
                rows={4}
              />
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setDetailOpen(false)}>
              Cancel
            </Button>
            <Button onClick={saveDetail} disabled={saving}>
              {saving ? "Saving..." : "Save"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

const MetricCard: React.FC<{ title: string; value: string | number; icon: React.ReactNode }> = ({ title, value, icon }) => (
  <Card>
    <CardContent className="flex items-center justify-between p-5">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</p>
        <p className="mt-1 text-3xl font-bold tracking-tight">{value}</p>
      </div>
      <Avatar className="size-14">
        <AvatarFallback>{icon}</AvatarFallback>
      </Avatar>
    </CardContent>
  </Card>
);

export default MasterDashboardPage;
