import React, { useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import axios from "axios";
import { CheckCircle2, Clock, Loader2, Users } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";

const API_BASE_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";

interface Shop {
  id: number;
  name: string;
  logo_url?: string;
  average_service_time: number;
  primary_color?: string;
  queues?: Queue[];
}

interface Queue {
  id: number;
  queue_items: QueueItem[];
}

interface QueueItem {
  id: number;
  status: string;
  position: number;
}

const WidgetPage: React.FC = () => {
  const { shopId } = useParams<{ shopId: string }>();
  const [searchParams] = useSearchParams();
  const [shop, setShop] = useState<Shop | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [queuePosition, setQueuePosition] = useState<number | null>(null);
  const [estimatedWait, setEstimatedWait] = useState<number | null>(null);
  const [customerName, setCustomerName] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");

  const primaryColor = searchParams.get("primary") ? `#${searchParams.get("primary")}` : undefined;
  const secondaryColor = searchParams.get("secondary") ? `#${searchParams.get("secondary")}` : "#ffffff";

  const getQueueStats = () => {
    if (!shop?.queues || shop.queues.length === 0) {
      return { waiting: 0, serving: 0, totalWait: 0 };
    }

    const allItems = shop.queues.flatMap((q) => q.queue_items);
    const waiting = allItems.filter((item) => item.status === "waiting").length;
    const serving = allItems.filter((item) => item.status === "being_served").length;
    const totalWait = waiting * shop.average_service_time;

    return { waiting, serving, totalWait };
  };

  useEffect(() => {
    const fetchShop = async () => {
      try {
        setLoading(true);
        const response = await axios.get(`${API_BASE_URL}/api/shops/${shopId}`);
        setShop(response.data);
        setError(null);
      } catch (err: any) {
        setError(err.response?.data?.detail || "Failed to load shop information");
      } finally {
        setLoading(false);
      }
    };

    if (shopId) {
      void fetchShop();
    }
  }, [shopId]);

  const handleJoinQueue = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!customerName.trim() || !customerPhone.trim()) {
      setError("Please enter your name and phone number");
      return;
    }

    try {
      setSubmitting(true);
      setError(null);

      await axios.post(`${API_BASE_URL}/api/queues/shop/${shopId}/join`, {
        customer_name: customerName.trim(),
        customer_phone: customerPhone.trim(),
      });

      const stats = getQueueStats();
      setQueuePosition(stats.waiting + stats.serving + 1);
      setEstimatedWait(stats.totalWait + shop!.average_service_time);
      setSuccess(true);
    } catch (err: any) {
      if (err.response?.status === 429) {
        setError("Queue is currently full. Please try again later.");
      } else {
        setError(err.response?.data?.detail || "Failed to join queue. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  const brandColor = primaryColor || shop?.primary_color || "#1976d2";

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center" style={{ backgroundColor: secondaryColor }}>
        <Loader2 className="size-8 animate-spin" style={{ color: brandColor }} />
      </div>
    );
  }

  if (error && !shop) {
    return (
      <div className="flex min-h-screen items-center justify-center p-4" style={{ backgroundColor: secondaryColor }}>
        <Alert variant="destructive" className="max-w-md">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      </div>
    );
  }

  if (!shop) return null;

  const stats = getQueueStats();

  if (success) {
    return (
      <div className="flex min-h-screen items-center justify-center p-4" style={{ backgroundColor: secondaryColor }}>
        <Card className="w-full max-w-md text-center">
          <CardContent className="flex flex-col items-center p-8">
            <CheckCircle2 className="size-20" style={{ color: brandColor }} />
            <h1 className="mt-4 text-3xl font-bold">You're in Line!</h1>
            <p className="mt-2 text-xl text-muted-foreground">Position #{queuePosition}</p>
            <Separator className="my-6" />
            <p className="text-lg font-semibold">Estimated Wait Time</p>
            <p className="mt-1 text-4xl font-bold" style={{ color: brandColor }}>
              ~{estimatedWait} min
            </p>
            <p className="mt-6 text-sm text-muted-foreground">
              Please arrive at {shop.name} when your turn is near. We'll serve you as soon as possible!
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4" style={{ backgroundColor: secondaryColor }}>
      <Card className="w-full max-w-md overflow-hidden">
        <div className="flex flex-col items-center p-6 text-center text-white" style={{ backgroundColor: brandColor }}>
          {shop.logo_url && (
            <Avatar className="mb-4 size-20 border-4 border-white">
              <AvatarImage src={shop.logo_url} alt={shop.name} />
              <AvatarFallback>{shop.name[0]}</AvatarFallback>
            </Avatar>
          )}
          <h1 className="text-2xl font-bold">{shop.name}</h1>
          <p className="text-sm opacity-90">Join the Queue</p>
        </div>

        <CardContent className="p-6">
          <div className="mb-6 grid grid-cols-2 gap-3">
            <Badge variant="secondary" className="justify-center gap-1 py-2">
              <Users className="size-4" />
              {stats.waiting + stats.serving} in queue
            </Badge>
            <Badge variant="secondary" className="justify-center gap-1 py-2">
              <Clock className="size-4" />~{stats.totalWait} min wait
            </Badge>
          </div>

          {error && (
            <Alert variant="destructive" className="mb-4">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <form onSubmit={handleJoinQueue} className="flex flex-col gap-4">
            <div className="flex flex-col gap-2">
              <Label htmlFor="widgetName">Your Name</Label>
              <Input
                id="widgetName"
                value={customerName}
                onChange={(e) => setCustomerName(e.target.value)}
                required
                disabled={submitting}
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="widgetPhone">Phone Number</Label>
              <Input
                id="widgetPhone"
                value={customerPhone}
                onChange={(e) => setCustomerPhone(e.target.value)}
                required
                disabled={submitting}
                type="tel"
                placeholder="(555) 123-4567"
              />
            </div>
            <Button type="submit" size="lg" disabled={submitting} style={{ backgroundColor: brandColor }}>
              {submitting && <Loader2 data-icon="inline-start" className="animate-spin" />}
              Join Queue
            </Button>
          </form>

          <p className="mt-4 text-center text-xs text-muted-foreground">Served by ZeroQwait</p>
        </CardContent>
      </Card>
    </div>
  );
};

export default WidgetPage;
