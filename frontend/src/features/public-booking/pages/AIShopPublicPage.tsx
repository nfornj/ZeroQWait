import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import { Activity, Loader2, Users } from "lucide-react";
import MasterAIAgent from "../../../landing-page/components/MasterAIAgent";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface ServiceSummary {
  id: number;
  name: string;
  cost?: number;
  duration_minutes?: number;
}

interface AIShopPublicPageProps {
  shopSlug?: string;
}

interface QueueItem {
  id: number;
  customer_name?: string;
  position: number;
  status: string;
  checked_in_at?: string;
}

interface QueueSummary {
  id: number;
  is_active?: boolean;
  accepting_joins?: boolean;
  lock_reason?: string | null;
  queue_items?: QueueItem[];
}

interface WaitEstimate {
  position: number;
  people_ahead: number;
  estimated_wait_minutes: number;
  status: string;
}

interface LiveMetrics {
  estimated_wait_minutes: number;
  queue_length: number;
  people_waiting: number;
  people_being_served: number;
  active_employees: number;
  parallel_queues: number;
  effective_service_time_minutes: number;
  efficiency_factor: number;
  confidence: "low" | "medium" | "high";
  generated_at?: string;
}

const confidenceVariant = (confidence?: LiveMetrics["confidence"]) => {
  if (confidence === "high") return "default";
  if (confidence === "medium") return "secondary";
  return "outline";
};

const AIShopPublicPage: React.FC<AIShopPublicPageProps> = ({ shopSlug }) => {
  const { shopId } = useParams<{ shopId: string }>();
  const effectiveId = shopSlug || shopId;

  const [shop, setShop] = useState<any>(null);
  const [queueItems, setQueueItems] = useState<QueueItem[]>([]);
  const [myQueueItem, setMyQueueItem] = useState<QueueItem | null>(null);
  const [waitEstimate, setWaitEstimate] = useState<WaitEstimate | null>(null);
  const [liveMetrics, setLiveMetrics] = useState<LiveMetrics | null>(null);
  const [services, setServices] = useState<ServiceSummary[]>([]);
  const [etaTrend, setEtaTrend] = useState<"up" | "down" | "flat">("flat");
  const [receptionAction, setReceptionAction] = useState<{ id: string; payload: string } | null>(null);
  const [lastLiveUpdateAt, setLastLiveUpdateAt] = useState<Date | null>(null);
  const [secondsSinceUpdate, setSecondsSinceUpdate] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [queueOpen, setQueueOpen] = useState(true);
  const [queueStatusMessage, setQueueStatusMessage] = useState("");

  const applyLiveMetrics = useCallback((incoming: LiveMetrics) => {
    let trend: "up" | "down" | "flat" = "flat";
    setLiveMetrics((prev) => {
      if (prev) {
        if (incoming.estimated_wait_minutes > prev.estimated_wait_minutes) trend = "up";
        else if (incoming.estimated_wait_minutes < prev.estimated_wait_minutes) trend = "down";
      }
      return incoming;
    });
    setEtaTrend(trend);
    setLastLiveUpdateAt(incoming.generated_at ? new Date(incoming.generated_at) : new Date());
  }, []);

  const reconcileMyQueueItem = useCallback(async (items: QueueItem[], resolvedShopId: number) => {
    const savedItemId =
      localStorage.getItem(`queue_item_${resolvedShopId}`) ||
      (shopId ? localStorage.getItem(`queue_item_${shopId}`) : null);

    if (!savedItemId) {
      setMyQueueItem(null);
      return;
    }

    const numericId = parseInt(savedItemId, 10);
    const found = items.find((i) => i.id === numericId);

    if (found) {
      setMyQueueItem(found);
      localStorage.setItem(`queue_item_${resolvedShopId}`, String(numericId));
      return;
    }

    setMyQueueItem(null);
    localStorage.removeItem(`queue_item_${resolvedShopId}`);
    if (shopId) {
      localStorage.removeItem(`queue_item_${shopId}`);
    }
  }, [shopId]);

  const waitingCustomers = useMemo(
    () =>
      queueItems
        .filter((item) => item.status === "waiting" || item.status === "being_served")
        .sort((a, b) => (a.position || 0) - (b.position || 0)),
    [queueItems],
  );

  const getDisplayFirstName = (fullName?: string) => {
    const trimmed = (fullName || "").trim();
    if (!trimmed) return "Customer";
    return trimmed.split(/\s+/)[0];
  };

  const triggerReceptionAction = (payload: string) => {
    setReceptionAction({
      id: `reception_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
      payload,
    });
  };

  const receptionActions = useMemo(() => {
    const base = [
      { label: "Show Services", payload: `What services does ${shop?.name || "this shop"} offer today?` },
      { label: "Book Appointment", payload: `I want to book an appointment at ${shop?.name || "this shop"}.` },
      { label: "Check Wait Time", payload: `What is the current wait time at ${shop?.name || "this shop"}?` },
      { label: "Join Queue", payload: `I want to join the queue at ${shop?.name || "this shop"}.` },
    ];

    if (myQueueItem) {
      return [
        { label: "Check My Place", payload: "What is my current queue status and estimated wait time?" },
        { label: "What Happens Next", payload: "Explain what happens next in the queue and when I should be ready." },
        ...base.slice(0, 2),
      ];
    }

    return base;
  }, [myQueueItem, shop?.name]);

  useEffect(() => {
    const fetchShopData = async () => {
      if (!effectiveId) {
        setError("Shop not found");
        setLoading(false);
        return;
      }

      try {
        const isSlug = isNaN(Number(effectiveId));
        const endpoint = isSlug ? `/shops/s/${effectiveId}` : `/shops/${effectiveId}`;
        const response = await axios.get(endpoint);
        setShop(response.data);
        const activeQueue = (response.data?.queues || []).find((entry: QueueSummary) => entry.is_active);
        if (activeQueue) {
          setQueueOpen(activeQueue.accepting_joins !== false);
          setQueueStatusMessage(activeQueue.lock_reason || "");
        } else {
          setQueueOpen(false);
          setQueueStatusMessage("Queue is currently closed. Please check back during operating hours.");
        }
      } catch {
        setError("Could not load shop details");
      } finally {
        setLoading(false);
      }
    };

    void fetchShopData();
  }, [effectiveId]);

  useEffect(() => {
    if (!shop?.id) return;

    const fetchServices = async () => {
      try {
        const response = await axios.get(`/shops/${shop.id}/services`);
        setServices(Array.isArray(response.data) ? response.data.slice(0, 4) : []);
      } catch {
        setServices([]);
      }
    };

    const fetchQueue = async () => {
      try {
        const response = await axios.get(`/queues/shop/${shop.id}/active`);
        setQueueOpen(response.data?.is_active && response.data?.accepting_joins !== false);
        setQueueStatusMessage(response.data?.lock_reason || "");
        const items: QueueItem[] = response.data?.queue_items || [];
        setQueueItems(items);

        try {
          const metricsRes = await axios.get(`/queues/shop/${shop.id}/live-metrics`);
          applyLiveMetrics(metricsRes.data as LiveMetrics);
        } catch {
          // keep previous metrics if temporary failure
        }

        await reconcileMyQueueItem(items, shop.id);
      } catch (err: any) {
        if (err.response?.status === 404) {
          setQueueOpen(false);
          setQueueStatusMessage(err.response?.data?.detail || "Queue is currently closed. Please check back during operating hours.");
          setQueueItems([]);
          setLiveMetrics(null);
          await reconcileMyQueueItem([], shop.id);
          return;
        }
        // keep previous state; polling will retry
      }
    };

    void fetchServices();
    void fetchQueue();
    const interval = setInterval(fetchQueue, 20000);
    return () => clearInterval(interval);
  }, [applyLiveMetrics, reconcileMyQueueItem, shop?.id, shopId]);

  useEffect(() => {
    if (!shop?.id) return;

    const wsProtocol = window.location.protocol === "https:" ? "wss" : "ws";
    let pingTimer: number | undefined;
    let reconnectTimer: number | undefined;
    let cancelled = false;
    let socket: WebSocket | null = null;

    const connect = () => {
      if (cancelled) return;
      socket = new WebSocket(`${wsProtocol}://${window.location.host}/api/ws/${shop.id}`);

      socket.onopen = () => {
        pingTimer = window.setInterval(() => {
          if (socket?.readyState === WebSocket.OPEN) {
            socket.send("ping");
          }
        }, 20000);
      };

      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload?.type !== "shop_live_snapshot") return;

          const incomingItems: QueueItem[] = Array.isArray(payload.queue_items) ? payload.queue_items : [];
          setQueueItems(incomingItems);
          void reconcileMyQueueItem(incomingItems, shop.id);

          if (payload.live_metrics && !payload.live_metrics.error) {
            applyLiveMetrics(payload.live_metrics as LiveMetrics);
          }
        } catch {
          // ignore malformed socket payloads
        }
      };

      socket.onclose = () => {
        if (pingTimer) window.clearInterval(pingTimer);
        if (!cancelled) {
          reconnectTimer = window.setTimeout(connect, 3000);
        }
      };
    };

    connect();

    return () => {
      cancelled = true;
      if (pingTimer) window.clearInterval(pingTimer);
      if (reconnectTimer) window.clearTimeout(reconnectTimer);
      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.close();
      }
    };
  }, [applyLiveMetrics, reconcileMyQueueItem, shop?.id]);

  useEffect(() => {
    if (!lastLiveUpdateAt) {
      setSecondsSinceUpdate(0);
      return;
    }

    const tick = () => {
      const deltaSec = Math.max(0, Math.floor((Date.now() - lastLiveUpdateAt.getTime()) / 1000));
      setSecondsSinceUpdate(deltaSec);
    };

    tick();
    const interval = window.setInterval(tick, 1000);
    return () => window.clearInterval(interval);
  }, [lastLiveUpdateAt]);

  useEffect(() => {
    if (!myQueueItem?.id) {
      setWaitEstimate(null);
      return;
    }

    const fetchEstimate = async () => {
      try {
        const response = await axios.get(`/queues/items/${myQueueItem.id}/estimate`);
        setWaitEstimate(response.data);
      } catch {
        // retry on next poll
      }
    };

    void fetchEstimate();
    const interval = setInterval(fetchEstimate, 10000);
    return () => clearInterval(interval);
  }, [myQueueItem?.id]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="size-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error || !shop) {
    return (
      <main className="mx-auto max-w-xl px-4 py-20">
        <Alert variant="destructive">
          <AlertDescription>{error || "Shop not found"}</AlertDescription>
        </Alert>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-muted/30 py-3 md:py-6">
      <div className="mx-auto flex max-w-7xl flex-col gap-4 px-3 md:px-6">
        <header className="flex flex-col gap-2 rounded-2xl border bg-card px-4 py-3 shadow-sm sm:flex-row sm:items-center">
          <span className="font-extrabold text-primary">ZeroQwait</span>
          <span className="hidden h-5 w-px bg-border sm:block" />
          <span className="font-bold">{shop.name}</span>
          <span className="text-sm text-muted-foreground">{[shop.city, shop.shop_type].filter(Boolean).join(" • ")}</span>
          <Badge className="w-fit sm:ml-auto" variant={queueOpen ? "default" : "secondary"}>
            {queueOpen ? "Open now" : "Closed now"}
          </Badge>
        </header>

        <div className="grid gap-4 lg:grid-cols-[minmax(320px,0.72fr)_minmax(0,1fr)]">
          <aside className="order-2 flex flex-col gap-4 lg:order-1">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm uppercase tracking-widest text-muted-foreground">Live Queue Status</CardTitle>
              </CardHeader>
              <CardContent>
                {!queueOpen && (
                  <Alert className="mb-4">
                    <AlertDescription>
                      {queueStatusMessage || "Queue is currently closed. Please check back during operating hours."}
                    </AlertDescription>
                  </Alert>
                )}

                {myQueueItem ? (
                  <div className="flex flex-col gap-4">
                    <div>
                      <div className="text-5xl font-black leading-none">#{waitEstimate?.position ?? myQueueItem.position}</div>
                      <p className="mt-2 font-bold">You are in the queue</p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Badge variant="outline">Ahead: {waitEstimate?.people_ahead ?? "-"}</Badge>
                      <Badge>ETA: {waitEstimate?.estimated_wait_minutes ?? liveMetrics?.estimated_wait_minutes ?? "-"} min</Badge>
                      <Badge variant="secondary">
                        {etaTrend === "up" ? "Trend: Rising" : etaTrend === "down" ? "Trend: Improving" : "Trend: Stable"}
                      </Badge>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Badge variant="outline">Employees: {liveMetrics?.active_employees ?? "-"}</Badge>
                      <Badge variant="outline">Queues: {liveMetrics?.parallel_queues ?? "-"}</Badge>
                      <Badge variant={confidenceVariant(liveMetrics?.confidence)}>Confidence: {liveMetrics?.confidence ?? "-"}</Badge>
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-col gap-3">
                    <div>
                      <div className="text-5xl font-black leading-none">
                        {liveMetrics?.people_waiting ?? waitingCustomers.length ?? 0}
                      </div>
                      <p className="mt-2 font-bold">{queueOpen ? "People currently waiting" : "Queue currently closed"}</p>
                    </div>
                    <p className="text-sm text-muted-foreground">
                      {queueOpen
                        ? "Use the AI panel to the right to join the queue instantly."
                        : "The AI panel can still answer questions, but new queue joins are currently unavailable."}
                    </p>
                    <div className="flex flex-wrap gap-2">
                      <Badge>ETA: {liveMetrics?.estimated_wait_minutes ?? 0} min</Badge>
                      <Badge variant="outline">Waiting: {liveMetrics?.people_waiting ?? waitingCustomers.length ?? 0}</Badge>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      AI model factors: active staff, parallel queues, historical service analytics, and real-time throughput.
                    </p>
                    <p className="text-xs text-muted-foreground">Live update: {secondsSinceUpdate}s ago</p>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Reception Desk</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                <p className="text-sm text-muted-foreground">
                  {queueOpen
                    ? "Start with the AI receptionist for discovery, booking, or queue help."
                    : "The AI receptionist can explain hours, services, and when the queue will reopen."}
                </p>
                <div className="flex flex-wrap gap-2">
                  {receptionActions.map((action) => (
                    <Button key={action.label} type="button" size="sm" variant="outline" onClick={() => triggerReceptionAction(action.payload)}>
                      {action.label}
                    </Button>
                  ))}
                </div>
                {services.length > 0 && (
                  <div className="flex flex-col gap-2">
                    {services.map((service) => (
                      <div key={service.id} className="rounded-lg border bg-primary/5 p-3">
                        <p className="font-semibold">{service.name}</p>
                        <p className="text-xs text-muted-foreground">
                          {typeof service.cost === "number" ? `$${service.cost}` : "Price on request"}
                          {service.duration_minutes ? ` • ${service.duration_minutes} min` : ""}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Users className="size-5" />
                  Active Queue
                </CardTitle>
              </CardHeader>
              <CardContent>
                {!queueOpen ? (
                  <p className="text-muted-foreground">Queue is currently closed.</p>
                ) : waitingCustomers.length === 0 ? (
                  <p className="text-muted-foreground">Queue is currently empty.</p>
                ) : (
                  <div className="flex flex-col gap-2">
                    {waitingCustomers.slice(0, 8).map((item) => {
                      const isMe = myQueueItem?.id === item.id;
                      return (
                        <div
                          key={item.id}
                          className="flex items-center justify-between gap-3 rounded-lg border bg-card p-3 data-[me=true]:border-primary data-[me=true]:bg-primary/5"
                          data-me={isMe}
                        >
                          <div className="flex items-center gap-3">
                            <Avatar className="size-8">
                              <AvatarFallback>{isMe ? "Y" : "?"}</AvatarFallback>
                            </Avatar>
                            <div>
                              <p className="font-bold">#{item.position}</p>
                              <p className="text-xs text-muted-foreground">
                                {isMe ? "You" : getDisplayFirstName(item.customer_name)}
                              </p>
                            </div>
                          </div>
                          <Badge variant={item.status === "being_served" ? "default" : "outline"}>
                            {item.status === "being_served" ? "SERVING" : "WAITING"}
                          </Badge>
                        </div>
                      );
                    })}
                  </div>
                )}
              </CardContent>
            </Card>
          </aside>

          <section className="order-1 min-h-[74vh] lg:order-2 lg:h-[calc(100dvh-156px)] lg:min-h-0 xl:h-[86vh]">
            <div className="h-full overflow-hidden rounded-2xl border bg-card shadow-sm">
              <MasterAIAgent
                forceOpen={true}
                hideCloseButton={true}
                initialInteractionMode="voice"
                embedded={true}
                shopContext={{
                  id: shop.id,
                  slug: shop.slug,
                  name: shop.name,
                  city: shop.city,
                  shopType: shop.shop_type,
                }}
                externalActionRequest={receptionAction}
                onExternalActionHandled={() => setReceptionAction(null)}
              />
            </div>
          </section>
        </div>

        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Activity className="size-3" />
          Live queue data updates automatically while this page is open.
        </div>
      </div>
    </main>
  );
};

export default AIShopPublicPage;
