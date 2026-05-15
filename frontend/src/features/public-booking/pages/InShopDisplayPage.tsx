import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import { CheckCircle2, Clock, Loader2, Users } from "lucide-react";
import { gradientPresets, GradientPreset } from "../../../contexts/ThemeContext";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
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
  slug?: string;
  average_service_time: number;
  logo_url?: string;
  primary_color?: string;
  dashboard_gradient?: GradientPreset;
}

interface QueueItem {
  id: number;
  customer_name: string;
  position: number;
  status: string;
  checked_in_at: string;
  service_started_at?: string;
  assigned_employee?: {
    id: number;
    username: string;
    email: string;
    profile_photo_url?: string;
  };
}

interface Queue {
  id: number;
  shop_id: number;
  name: string;
  queue_items: QueueItem[];
}

const InShopDisplayPage: React.FC = () => {
  const { shopId } = useParams<{ shopId: string }>();
  const [shop, setShop] = useState<Shop | null>(null);
  const [queue, setQueue] = useState<Queue | null>(null);
  const [loading, setLoading] = useState(true);
  const [currentTime, setCurrentTime] = useState(new Date());
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void fetchShopData();

    const queueInterval = setInterval(fetchQueueData, 3000);
    const clockInterval = setInterval(() => setCurrentTime(new Date()), 1000);

    return () => {
      clearInterval(queueInterval);
      clearInterval(clockInterval);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shopId]);

  const fetchShopData = async () => {
    try {
      let response;
      const hostname = window.location.hostname;
      const isSubdomain = hostname.includes(".") && !hostname.includes("localhost") && !hostname.includes("127.0.0.1");

      if (isSubdomain) {
        const slug = hostname.split(".")[0];
        response = await axios.get(`/shops/s/${slug}`);
      } else if (shopId) {
        const isSlug = isNaN(Number(shopId));
        response = isSlug ? await axios.get(`/shops/s/${shopId}`) : await axios.get(`/shops/${shopId}`);
      } else {
        throw new Error("No shop identifier found");
      }

      setShop(response.data);
      if (response.data.id) {
        void fetchQueueForShop(response.data.id);
      }
      setLoading(false);
    } catch (err) {
      console.error(err);
      setError("Could not load shop data.");
      setLoading(false);
    }
  };

  const fetchQueueData = () => {
    if (shop?.id) {
      void fetchQueueForShop(shop.id);
    }
  };

  const fetchQueueForShop = async (id: number) => {
    try {
      const token = localStorage.getItem("token");
      const config = token ? { headers: { Authorization: `Bearer ${token}` } } : {};
      const response = await axios.get(`/queues/shop/${id}/active`, config);
      setQueue(response.data);
    } catch {
      // Silently fail on refresh
    }
  };

  const waitingCustomers = queue?.queue_items.filter((item) => item.status === "waiting") || [];
  const servingCustomers = queue?.queue_items.filter((item) => item.status === "being_served") || [];
  const estimatedWaitTime = waitingCustomers.length * (shop?.average_service_time || 30);
  const primaryColor = shop?.primary_color || "#1976d2";
  const gradientKey = shop?.dashboard_gradient || "violet";
  const bgGradient = gradientPresets[gradientKey]?.light || gradientPresets.violet.light;

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center" style={{ background: bgGradient }}>
        <Loader2 className="size-20 animate-spin text-white" />
      </div>
    );
  }

  if (error || !shop) {
    return (
      <div className="flex min-h-screen items-center justify-center p-4" style={{ background: bgGradient }}>
        <Alert variant="destructive" className="max-w-lg">
          <AlertDescription>{error || "Shop not found"}</AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <main
      className="flex h-screen min-h-screen flex-col overflow-hidden p-4 text-slate-950 md:p-8"
      style={{ background: bgGradient, backgroundSize: "cover", backgroundAttachment: "fixed" }}
    >
      <header className="mb-6 rounded-3xl border border-white/30 bg-white/85 p-4 shadow-xl backdrop-blur-xl">
        <div className="flex items-center justify-between gap-6">
          <div className="flex min-w-0 items-center gap-5">
            {shop.logo_url && (
              <Avatar className="size-20 shrink-0 border-4 shadow-md" style={{ borderColor: primaryColor }}>
                <AvatarImage src={shop.logo_url} alt={shop.name} />
                <AvatarFallback>{shop.name[0]}</AvatarFallback>
              </Avatar>
            )}
            <div className="min-w-0">
              <h1
                className="truncate text-4xl font-black tracking-tight md:text-5xl"
                style={{
                  background: `linear-gradient(45deg, ${primaryColor}, #333)`,
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                }}
              >
                {shop.name}
              </h1>
              <p className="text-xl font-medium text-slate-600">Queue Status</p>
            </div>
          </div>
          <div className="text-right">
            <p className="font-mono text-4xl font-bold md:text-5xl">
              {currentTime.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
            </p>
            <div className="mt-1 flex items-center justify-end gap-2">
              <span className="size-2.5 rounded-full bg-green-500 shadow-[0_0_10px_#22c55e]" />
              <span className="font-medium text-green-600">Live</span>
            </div>
          </div>
        </div>
      </header>

      <div className="grid min-h-0 flex-1 gap-6 md:grid-cols-[0.9fr_1.35fr]">
        <Card
          className="min-h-0 overflow-hidden border-0 backdrop-blur"
          style={{
            background: servingCustomers.length > 0 ? `linear-gradient(135deg, ${primaryColor}, #111)` : "rgba(255, 255, 255, 0.8)",
            color: servingCustomers.length > 0 ? "white" : undefined,
          }}
        >
          <CardContent className="flex h-full flex-col p-6 md:p-8">
            <div className="mb-6 flex items-center gap-3">
              <CheckCircle2 className={servingCustomers.length > 0 ? "size-10 text-green-300" : "size-10 text-muted-foreground"} />
              <h2 className="text-3xl font-extrabold tracking-wide">NOW SERVING</h2>
            </div>
            <Separator className="mb-8 bg-white/20" />

            {servingCustomers.length > 0 ? (
              <div className="flex flex-1 flex-col items-center justify-center gap-6">
                {servingCustomers.slice(0, 1).map((customer) => (
                  <div key={customer.id} className="animate-in fade-in slide-in-from-bottom-4 text-center duration-500">
                    <div className="mb-6 inline-flex size-48 animate-pulse items-center justify-center rounded-full border-8 border-white bg-white/10 md:size-56">
                      <span className="text-8xl font-black">{customer.position}</span>
                    </div>
                    <p className="text-4xl font-bold drop-shadow">{customer.customer_name}</p>

                    {customer.assigned_employee && (
                      <div className="mt-6 inline-flex items-center gap-3 rounded-2xl bg-white/15 p-3 backdrop-blur">
                        <Avatar className="size-12 border-2 border-white">
                          <AvatarImage src={customer.assigned_employee.profile_photo_url} alt={customer.assigned_employee.username} />
                          <AvatarFallback>{customer.assigned_employee.username[0]}</AvatarFallback>
                        </Avatar>
                        <div className="text-left">
                          <p className="text-xs uppercase tracking-widest opacity-80">Served By</p>
                          <p className="text-lg font-bold">{customer.assigned_employee.username}</p>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
                {servingCustomers.length > 1 && <p className="text-xl opacity-80">+ {servingCustomers.length - 1} others being served</p>}
              </div>
            ) : (
              <div className="flex flex-1 flex-col items-center justify-center text-center opacity-60">
                <Clock className="mb-4 size-20" />
                <p className="text-3xl font-semibold">Stations Available</p>
                <p className="text-xl">Next customer please step forward</p>
              </div>
            )}
          </CardContent>
        </Card>

        <section className="flex min-h-0 flex-col gap-6">
          <div className="grid gap-6 sm:grid-cols-2">
            <Card className="bg-white/90">
              <CardContent className="flex items-center gap-5 p-6">
                <div className="rounded-full p-4" style={{ backgroundColor: `${primaryColor}22` }}>
                  <Users className="size-10" style={{ color: primaryColor }} />
                </div>
                <div>
                  <p className="text-4xl font-extrabold">{waitingCustomers.length}</p>
                  <p className="font-semibold text-muted-foreground">Waiting in Queue</p>
                </div>
              </CardContent>
            </Card>
            <Card className="bg-white/90">
              <CardContent className="flex items-center gap-5 p-6">
                <div className="rounded-full bg-amber-100 p-4 text-amber-700">
                  <Clock className="size-10" />
                </div>
                <div>
                  <p className="text-4xl font-extrabold">
                    ~{estimatedWaitTime}
                    <span className="text-2xl">m</span>
                  </p>
                  <p className="font-semibold text-muted-foreground">Est. Wait Time</p>
                </div>
              </CardContent>
            </Card>
          </div>

          <Card className="min-h-0 flex-1 overflow-hidden bg-white/85 backdrop-blur">
            <CardContent className="flex h-full flex-col p-0">
              <div className="border-b bg-white/50 p-5">
                <h2 className="text-2xl font-bold">Up Next</h2>
              </div>

              <div className="min-h-0 flex-1 overflow-y-auto p-5">
                {waitingCustomers.length === 0 ? (
                  <div className="flex h-full flex-col items-center justify-center text-center opacity-50">
                    <p className="text-3xl font-semibold">Queue is Empty</p>
                    <p className="text-xl">We are ready to serve you!</p>
                  </div>
                ) : (
                  <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                    {waitingCustomers.map((customer, index) => (
                      <div
                        key={customer.id}
                        className="rounded-2xl border bg-white p-4 shadow-sm transition hover:-translate-y-0.5"
                        style={{ borderLeftWidth: 6, borderLeftColor: index === 0 ? "#4ade80" : index < 3 ? primaryColor : "#ccc" }}
                      >
                        <div className="flex items-center justify-between gap-3">
                          <div className="flex min-w-0 items-center gap-3">
                            <Avatar className="size-11 text-white" style={{ backgroundColor: index < 3 ? primaryColor : "#d1d5db" }}>
                              <AvatarFallback>{customer.position}</AvatarFallback>
                            </Avatar>
                            <div className="min-w-0">
                              <p className="truncate text-lg font-bold">{customer.customer_name}</p>
                              <p className="text-xs text-muted-foreground">
                                {new Date(customer.checked_in_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                              </p>
                            </div>
                          </div>
                          {index < 3 && (
                            <Badge variant={index === 0 ? "default" : "outline"}>{index === 0 ? "NEXT" : "SOON"}</Badge>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          <div className="text-center">
            <div className="inline-flex rounded-full bg-white/90 px-6 py-2 shadow-md">
              <p className="text-lg font-medium">
                Join the queue at{" "}
                <span className="font-bold" style={{ color: primaryColor }}>
                  {shop.slug ? `${shop.slug}.zeroqwait.com` : `zeroqwait.com/queue/${shop.id}`}
                </span>
              </p>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
};

export default InShopDisplayPage;
