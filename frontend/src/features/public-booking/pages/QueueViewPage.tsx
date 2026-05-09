import React, { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import axios from "axios";
import { ArrowLeft, Bot, Loader2 } from "lucide-react";
import { useAuth } from "../../../contexts/AuthContext";
import { constructShopUrl } from "../../../utils/domainUtils";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";

interface Shop {
  id: number;
  name: string;
  description?: string;
  shop_type: string;
  address: string;
  city: string;
  state: string;
  phone: string;
  average_service_time: number;
  slug?: string;
  ai_agent_name?: string;
  primary_color?: string;
}

interface QueueItem {
  id: number;
  customer_name: string;
  position: number;
  status: string;
  checked_in_at: string;
}

interface Queue {
  id: number;
  shop_id: number;
  queue_items: QueueItem[];
}

interface WaitEstimate {
  position: number;
  people_ahead: number;
  estimated_wait_minutes: number;
  status: string;
}

const getStatusVariant = (status: string): "default" | "secondary" | "outline" => {
  if (status === "being_served") return "default";
  if (status === "waiting") return "secondary";
  return "outline";
};

const QueueViewPage: React.FC = () => {
  const { shopId } = useParams<{ shopId: string }>();
  const navigate = useNavigate();
  const { user, isAuthenticated } = useAuth();
  const [shop, setShop] = useState<Shop | null>(null);
  const [queue, setQueue] = useState<Queue | null>(null);
  const [myQueueItem, setMyQueueItem] = useState<QueueItem | null>(null);
  const [waitEstimate, setWaitEstimate] = useState<WaitEstimate | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [leaveQueueDialogOpen, setLeaveQueueDialogOpen] = useState(false);

  const fetchShop = useCallback(async () => {
    try {
      const isSlug = isNaN(Number(shopId));
      const endpoint = isSlug ? `/shops/s/${shopId}` : `/shops/${shopId}`;
      const response = await axios.get(endpoint);
      setShop(response.data);
      setLoading(false);
    } catch {
      setError("Failed to load shop details");
      setLoading(false);
    }
  }, [shopId]);

  const fetchQueue = useCallback(async () => {
    if (!shop) return;
    try {
      const response = await axios.get(`/queues/shop/${shop.id}/active`);
      setQueue(response.data);

      const savedItemId = localStorage.getItem(`queue_item_${shop.id}`) || localStorage.getItem(`queue_item_${shopId}`);

      if (savedItemId) {
        const item = response.data.queue_items.find((i: QueueItem) => i.id === parseInt(savedItemId));

        if (item) {
          if (item.status === "completed" || item.status === "cancelled") {
            localStorage.removeItem(`queue_item_${shop.id}`);
            localStorage.removeItem(`queue_item_${shopId}`);
            setMyQueueItem(null);
          } else {
            setMyQueueItem(item);
            localStorage.setItem(`queue_item_${shop.id}`, savedItemId);
          }
        } else {
          try {
            const checkRes = await axios.get(`/queues/items/${savedItemId}/estimate`);
            if (checkRes.data && checkRes.data.status !== "completed" && checkRes.data.status !== "cancelled") {
              setMyQueueItem({
                id: parseInt(savedItemId),
                status: checkRes.data.status,
                position: checkRes.data.position,
                customer_name: "You",
              } as any);
            }
          } catch {
            // keep current client state until the next poll can verify it
          }
        }
      }
    } catch {
      // retry on next interval
    }
  }, [shop, shopId]);

  const fetchWaitEstimate = useCallback(async () => {
    if (!myQueueItem) return;

    try {
      const response = await axios.get(`/queues/items/${myQueueItem.id}/estimate`);
      setWaitEstimate(response.data);
    } catch {
      // retry on next interval
    }
  }, [myQueueItem]);

  useEffect(() => {
    if (shopId) {
      void fetchShop();
    }
  }, [fetchShop, shopId]);

  useEffect(() => {
    if (shop) {
      void fetchQueue();
      const interval = setInterval(fetchQueue, 5000);
      return () => clearInterval(interval);
    }
  }, [fetchQueue, shop]);

  useEffect(() => {
    if (myQueueItem) {
      void fetchWaitEstimate();
      const interval = setInterval(fetchWaitEstimate, 10000);
      return () => clearInterval(interval);
    }
  }, [fetchWaitEstimate, myQueueItem]);

  const handleLeaveQueue = () => {
    if (!myQueueItem) return;
    setLeaveQueueDialogOpen(true);
  };

  const confirmLeaveQueue = async () => {
    if (!myQueueItem) return;
    setLeaveQueueDialogOpen(false);
    try {
      await axios.delete(`/queues/items/${myQueueItem.id}/leave`);
      setSuccess("You have left the queue");
      localStorage.removeItem(`queue_item_${shopId}`);
      setMyQueueItem(null);
      setWaitEstimate(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to leave queue");
    }
  };

  const waitingCustomers =
    queue?.queue_items
      .filter((item) => item.status === "waiting" || item.status === "being_served")
      .sort((a, b) => (a.position || 0) - (b.position || 0)) || [];

  if (loading) {
    return (
      <div className="flex min-h-[80vh] items-center justify-center">
        <Loader2 className="size-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!shop) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-16">
        <Alert variant="destructive">
          <AlertDescription>Shop not found</AlertDescription>
        </Alert>
      </main>
    );
  }

  const queueCount = waitingCustomers.length;
  const averageServiceTime = Math.max(shop.average_service_time || 0, 15);
  const fallbackEtaMinutes = myQueueItem ? Math.max((myQueueItem.position - 1) * averageServiceTime, 0) : queueCount * averageServiceTime;
  const liveEtaMinutes = waitEstimate?.estimated_wait_minutes ?? fallbackEtaMinutes;
  const canReturnToShop =
    isAuthenticated && (user?.role === "shop_owner" || user?.role === "employee" || user?.role === "manager");

  return (
    <>
      <main className="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-4 md:px-6 md:py-6">
        <header className="sticky top-3 z-10 flex flex-col gap-3 rounded-2xl border bg-card/85 px-4 py-3 shadow-lg backdrop-blur md:top-5 md:flex-row md:items-center md:justify-between md:px-6">
          <div className="flex flex-wrap items-center gap-3">
            <span className="font-extrabold tracking-tight text-primary">ZeroQwait</span>
            <span className="hidden h-5 w-px bg-border sm:block" />
            <span className="font-semibold">{shop.name}</span>
          </div>
          {canReturnToShop && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => { window.location.href = constructShopUrl(shop.slug || `shop-${shop.id}`); }}
            >
              <ArrowLeft data-icon="inline-start" />
              Back to Shop
            </Button>
          )}
        </header>

        <button
          type="button"
          className="flex cursor-pointer flex-col gap-3 rounded-2xl border border-primary/20 bg-primary/5 p-4 text-left transition hover:bg-primary/10 sm:flex-row sm:items-center sm:justify-between"
          onClick={() => navigate(`/shop-ai/${shopId}`)}
        >
          <div className="flex items-center gap-3">
            <Bot className="size-7 text-primary" />
            <div>
              <p className="font-extrabold text-primary">Talk to our AI Concierge</p>
              <p className="text-sm text-muted-foreground">
                Questions about your wait? Tap to chat with {shop.ai_agent_name || shop.name}.
              </p>
            </div>
          </div>
          <span className="text-sm font-semibold text-primary">Open</span>
        </button>

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

        <section className="grid gap-6 lg:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.9fr)]">
          <Card className="overflow-hidden border-0 bg-[linear-gradient(145deg,#0f172a_0%,#17324d_48%,#1d5d86_100%)] text-white shadow-2xl">
            <CardContent className="relative flex min-h-[460px] flex-col justify-between gap-8 p-6 md:p-8">
              <div className="pointer-events-none absolute -bottom-28 -right-20 size-64 rounded-full bg-sky-300/20 blur-3xl" />
              <div className="relative flex flex-col gap-6">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.22em] text-white/70">Live Queue Board</p>
                    <h1 className="mt-2 text-4xl font-black tracking-tight md:text-5xl">{shop.name}</h1>
                    <p className="mt-2 text-white/70">
                      {shop.city} • {shop.shop_type}
                    </p>
                  </div>
                  <Badge className="w-fit border-white/20 bg-white/10 text-white hover:bg-white/10">{queueCount} waiting now</Badge>
                </div>

                <div className="flex flex-wrap gap-2">
                  <Badge className="bg-amber-400 text-slate-950 hover:bg-amber-400">ETA {liveEtaMinutes} min</Badge>
                  <Badge className="border-white/20 bg-white/10 text-white hover:bg-white/10">Avg service {averageServiceTime} min</Badge>
                  <Badge className="border-white/20 bg-white/10 text-white hover:bg-white/10">Refreshes every 5 seconds</Badge>
                </div>

                {myQueueItem ? (
                  <div className="grid gap-6 sm:grid-cols-[0.65fr_1fr] sm:items-end">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-white/70">Your Position</p>
                      <div className="mt-2 text-7xl font-black leading-none md:text-8xl">{myQueueItem.position}</div>
                    </div>
                    <div className="flex flex-col gap-4">
                      <h2 className="text-2xl font-bold tracking-tight">You're checked in and moving through the line.</h2>
                      <p className="max-w-md text-white/80">
                        We'll keep this board current while the queue moves. Use the AI concierge if you need to update details or add another guest.
                      </p>
                      <div className="flex flex-col gap-2 sm:flex-row">
                        <Button variant="secondary" className="rounded-full font-bold" onClick={() => navigate(`/shop-ai/${shopId}`)}>
                          Open AI Concierge
                        </Button>
                        <Button variant="ghost" className="rounded-full text-white hover:bg-white/10 hover:text-white" onClick={handleLeaveQueue}>
                          Leave queue
                        </Button>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="flex max-w-xl flex-col gap-4">
                    <h2 className="text-3xl font-bold tracking-tight">Track the line first, then join when you're ready.</h2>
                    <p className="text-white/80">
                      The live board gives you the queue depth instantly. When you want to jump in, the AI concierge can collect details and confirm your place in one flow.
                    </p>
                    <div className="flex flex-col gap-2 sm:flex-row">
                      <Button variant="secondary" className="rounded-full font-bold" onClick={() => navigate(`/shop-ai/${shopId}`)}>
                        Join with AI Concierge
                      </Button>
                      <Button
                        variant="outline"
                        className="rounded-full border-white/30 bg-transparent text-white hover:bg-white/10 hover:text-white"
                        onClick={() => { window.location.href = constructShopUrl(shop.slug || `shop-${shop.id}`); }}
                      >
                        <ArrowLeft data-icon="inline-start" />
                        Back to Shop Page
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          <div className="flex flex-col gap-6">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm uppercase tracking-widest text-muted-foreground">Reception Desk</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                <div>
                  <h2 className="text-2xl font-extrabold tracking-tight">Need help before you join?</h2>
                  <p className="mt-2 text-muted-foreground">
                    Start with the AI receptionist for services, wait times, bookings, or queue check-in.
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {["Show Services", "Book Appointment", "Check Wait Time", "Join Queue"].map((label) => (
                    <Badge key={label} variant="outline" className="rounded-full px-3 py-1">
                      {label}
                    </Badge>
                  ))}
                </div>
                <Button className="rounded-full" onClick={() => navigate(`/shop-ai/${shopId}`)}>
                  <Bot data-icon="inline-start" />
                  Open AI Concierge
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => { window.location.href = constructShopUrl(shop.slug || `shop-${shop.id}`); }}
                >
                  Visit full shop page
                </Button>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-sm uppercase tracking-widest text-muted-foreground">Visit Details</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-3 text-muted-foreground">
                <p className="font-bold text-foreground">{shop.address}</p>
                <p>
                  {shop.city}, {shop.state}
                </p>
                <Separator />
                <p>Phone: {shop.phone}</p>
                <p>Average service window: {averageServiceTime} minutes</p>
                <p>Customer names remain blurred until it's your turn, so the board stays useful without exposing full queue details.</p>
              </CardContent>
            </Card>
          </div>
        </section>

        <Card>
          <CardHeader className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <CardTitle>Active Queue</CardTitle>
              <p className="mt-1 text-sm text-muted-foreground">
                The board refreshes continuously so you can gauge the line before you head over.
              </p>
            </div>
            {myQueueItem && <Badge>You are #{myQueueItem.position}</Badge>}
          </CardHeader>
          <CardContent>
            {waitingCustomers.length === 0 ? (
              <div className="rounded-2xl bg-muted/40 py-12 text-center text-muted-foreground">No one is waiting right now.</div>
            ) : (
              <div className="flex flex-col gap-3">
                {waitingCustomers.slice(0, 15).map((item) => {
                  const isMe = myQueueItem?.id === item.id;
                  return (
                    <div
                      key={item.id}
                      className="grid gap-3 rounded-2xl border bg-muted/30 p-4 data-[me=true]:border-primary data-[me=true]:bg-primary/5 sm:grid-cols-[72px_minmax(0,1fr)_auto_auto] sm:items-center"
                      data-me={isMe}
                    >
                      <p className="text-xl font-black tracking-tight">#{item.position}</p>
                      <div className="flex min-w-0 items-center gap-3">
                        <Avatar className="size-9">
                          <AvatarFallback>{isMe ? item.customer_name?.[0] || "Y" : "?"}</AvatarFallback>
                        </Avatar>
                        <div className="min-w-0">
                          {isMe ? (
                            <div className="flex flex-wrap items-center gap-2">
                              <p className="font-extrabold">{item.customer_name}</p>
                              <Badge>YOU</Badge>
                            </div>
                          ) : (
                            <p className="select-none truncate font-medium opacity-60 blur-[5px]">{item.customer_name}</p>
                          )}
                        </div>
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {new Date(item.checked_in_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                      </p>
                      <Badge variant={getStatusVariant(item.status)}>
                        {item.status === "being_served" ? "SERVING" : "WAITING"}
                      </Badge>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>
      </main>

      <Dialog open={leaveQueueDialogOpen} onOpenChange={setLeaveQueueDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Leave Queue</DialogTitle>
            <DialogDescription>Are you sure you want to leave the queue? You will lose your position.</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setLeaveQueueDialogOpen(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={confirmLeaveQueue}>
              Leave Queue
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default QueueViewPage;
