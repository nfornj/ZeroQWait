import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import axios from "axios";
import { Bot, Clock, Loader2, Users } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";

interface PublicShopPageProps {
  shopSlug?: string;
}

const PublicShopPage: React.FC<PublicShopPageProps> = ({ shopSlug }) => {
  const { slug } = useParams<{ slug: string }>();
  const effectiveSlug = shopSlug || slug;
  const navigate = useNavigate();
  const [shop, setShop] = useState<any>(null);
  const [queues, setQueues] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [services, setServices] = useState<any[]>([]);
  const [customerName, setCustomerName] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [customerEmail, setCustomerEmail] = useState("");
  const [notes, setNotes] = useState("");
  const [selectedServiceId, setSelectedServiceId] = useState<string>("");
  const [joinLoading, setJoinLoading] = useState(false);
  const [joinError, setJoinError] = useState("");

  useEffect(() => {
    const fetchShopAndQueues = async () => {
      try {
        if (!effectiveSlug) return;
        setLoading(true);
        const response = await axios.get(`/shops/s/${effectiveSlug}`);
        setShop(response.data);

        const savedItemId = localStorage.getItem(`queue_item_${response.data.id}`);
        if (savedItemId) {
          navigate(`/queue/${response.data.id}`);
          return;
        }

        setQueues(response.data.queues ? response.data.queues.filter((q: any) => q.is_active) : []);

        try {
          const servicesRes = await axios.get(`/shops/${response.data.id}/services`);
          setServices(servicesRes.data.filter((s: any) => s.is_active));
        } catch (e) {
          console.warn("Failed to fetch services", e);
          setServices([]);
        }

        setLoading(false);
      } catch (err) {
        console.error(err);
        setError("Shop not found");
        setLoading(false);
      }
    };

    void fetchShopAndQueues();
  }, [effectiveSlug, navigate]);

  const handleJoinQueue = async (e: React.FormEvent) => {
    e.preventDefault();
    setJoinError("");
    setJoinLoading(true);

    if (!customerName.trim()) {
      setJoinError("Please enter your name");
      setJoinLoading(false);
      return;
    }

    try {
      const response = await axios.post(`/queues/shop/${shop.id}/join`, {
        customer_name: customerName,
        customer_phone: customerPhone,
        customer_email: customerEmail,
        notes,
        service_id: selectedServiceId ? Number(selectedServiceId) : undefined,
      });

      localStorage.setItem(`queue_item_${shop.id}`, response.data.id.toString());
      navigate(`/queue/${shop.id}`);
    } catch (err: any) {
      setJoinError(err.response?.data?.detail || "Failed to join queue");
      setJoinLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-[80vh] items-center justify-center">
        <Loader2 className="size-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error || !shop) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-16">
        <Alert variant="destructive">
          <AlertDescription>Shop not found</AlertDescription>
        </Alert>
      </main>
    );
  }

  const waitingItems = queues[0]?.queue_items?.filter((i: any) => i.status === "waiting") || [];
  const brandGradient = `linear-gradient(90deg, ${shop.primary_color || "#1976d2"}, #000)`;

  return (
    <main className="min-h-screen bg-background pb-12">
      <header className="border-b bg-card">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-4 md:flex-row md:items-center md:justify-between md:px-6">
          <div className="flex items-center gap-3">
            {shop.logo_url && (
              <Avatar className="size-12 rounded-lg border">
                <AvatarImage src={shop.logo_url} alt={shop.name} />
                <AvatarFallback>{shop.name?.[0] || "S"}</AvatarFallback>
              </Avatar>
            )}
            <div>
              <h1 className="text-xl font-bold leading-tight">{shop.name}</h1>
              <p className="text-sm text-muted-foreground">
                {shop.address}, {shop.city}, {shop.state}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
            {shop.phone && <span>{shop.phone}</span>}
            <button className="hover:text-foreground" onClick={() => { window.location.href = "https://zeroqwait.com"; }}>
              Powered by ZeroQWait
            </button>
          </div>
        </div>
      </header>

      <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-8 md:px-6">
        <section
          className="flex flex-col gap-4 rounded-2xl p-6 text-white shadow-lg md:flex-row md:items-center md:justify-between"
          style={{ background: brandGradient }}
        >
          <div>
            <h2 className="text-2xl font-bold">Try our Intelligent Concierge</h2>
            <p className="mt-1 text-white/80">
              Talk to {shop.ai_agent_name || shop.name} to join the queue or check wait times instantly.
            </p>
          </div>
          <Button variant="secondary" className="rounded-full font-bold" onClick={() => navigate(`/shop-ai/${shop.id}`)}>
            <Bot data-icon="inline-start" />
            START CHAT
          </Button>
        </section>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.9fr)]">
          <Card>
            <CardHeader>
              <CardTitle>Join Queue</CardTitle>
            </CardHeader>
            <CardContent>
              {joinError && (
                <Alert variant="destructive" className="mb-4">
                  <AlertDescription>{joinError}</AlertDescription>
                </Alert>
              )}

              <form onSubmit={handleJoinQueue} className="flex flex-col gap-4">
                <div className="flex flex-col gap-2">
                  <Label htmlFor="customerName">Your Name</Label>
                  <Input id="customerName" required value={customerName} onChange={(e) => setCustomerName(e.target.value)} />
                </div>
                <div className="flex flex-col gap-2">
                  <Label htmlFor="customerPhone">Phone Number</Label>
                  <Input id="customerPhone" value={customerPhone} onChange={(e) => setCustomerPhone(e.target.value)} />
                </div>
                <div className="flex flex-col gap-2">
                  <Label htmlFor="customerEmail">Email (optional)</Label>
                  <Input
                    id="customerEmail"
                    type="email"
                    value={customerEmail}
                    onChange={(e) => setCustomerEmail(e.target.value)}
                  />
                </div>
                <div className="flex flex-col gap-2">
                  <Label htmlFor="notes">Notes (optional)</Label>
                  <Textarea id="notes" rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} />
                </div>
                <div className="flex flex-col gap-2">
                  <Label>Service (Optional)</Label>
                  <Select value={selectedServiceId} onValueChange={setSelectedServiceId}>
                    <SelectTrigger>
                      <SelectValue placeholder="None" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectGroup>
                        {services.map((service) => (
                          <SelectItem key={service.id} value={String(service.id)}>
                            {service.name} - ${service.cost} ({service.duration_minutes} min)
                          </SelectItem>
                        ))}
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                </div>

                <Button type="submit" size="lg" disabled={joinLoading}>
                  {joinLoading && <Loader2 data-icon="inline-start" className="animate-spin" />}
                  JOIN QUEUE
                </Button>
              </form>
            </CardContent>
          </Card>

          <div className="flex flex-col gap-4">
            <Card>
              <CardHeader>
                <CardTitle>Current Queue</CardTitle>
              </CardHeader>
              <CardContent>
                {waitingItems.length > 0 ? (
                  <div className="flex flex-col gap-4">
                    <div className="flex items-center gap-2 text-lg font-semibold">
                      <Users className="size-5 text-muted-foreground" />
                      {waitingItems.length} people waiting
                    </div>
                    <div className="flex flex-col gap-2">
                      {waitingItems.slice(0, 5).map((item: any, idx: number) => (
                        <div
                          key={item.id}
                          className="flex items-center gap-3 rounded-lg border bg-muted/40 p-3"
                          style={idx === 0 ? { borderLeftColor: shop.primary_color || "#1976d2", borderLeftWidth: 4 } : undefined}
                        >
                          <span className="font-bold text-muted-foreground">#{idx + 1}</span>
                          <div>
                            <p className="font-medium">{item.customer_name}</p>
                            <p className="text-sm text-muted-foreground">
                              {new Date(item.checked_in_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                    {waitingItems.length > 5 && <p className="text-center text-sm text-muted-foreground">... and more</p>}
                  </div>
                ) : (
                  <p className="py-8 text-center text-muted-foreground">Queue is empty. Join now!</p>
                )}
              </CardContent>
            </Card>

            <Card className="bg-muted/50">
              <CardContent className="flex flex-col gap-2 p-4">
                <div className="flex items-center gap-2 font-semibold">
                  <Clock className="size-4" />
                  Estimated Wait Time
                </div>
                <Separator />
                <p className="text-sm text-muted-foreground">
                  Each service takes about {shop.average_service_time} minutes on average.
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </main>
  );
};

export default PublicShopPage;
