import React, { useState } from "react";
import axios from "axios";
import { CheckCircle2, CreditCard, Loader2, ShoppingCart } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { PaymentFormData } from "./InlinePaymentForm";

export interface CheckoutCardData {
  queueItemId: number;
  customerName: string;
  serviceName: string | null;
  serviceCost: number;
  shopId: number;
  shopName: string;
}

interface InlineCheckoutCardProps {
  data: CheckoutCardData;
  onPayNow?: (paymentFormData: PaymentFormData) => void;
  paid?: boolean;
  compact?: boolean;
}

const InlineCheckoutCard: React.FC<InlineCheckoutCardProps> = ({
  data,
  onPayNow,
  paid,
  compact,
}) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handlePayNow = async () => {
    if (paid || loading) return;

    if (data.serviceCost <= 0) {
      onPayNow?.({
        type: "payment_form",
        client_secret: "",
        payment_intent_id: "free",
        amount: 0,
        currency: "usd",
        shop_name: data.shopName,
        shop_id: data.shopId,
      });
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const resp = await axios.post("/payments/create-payment-intent", {
        amount: data.serviceCost,
        currency: "usd",
        description: `Payment for ${data.serviceName || "service"} at ${data.shopName}`,
        shop_id: data.shopId,
      });

      const { payment_intent_id, client_secret, amount, currency } = resp.data;
      onPayNow?.({
        type: "payment_form",
        client_secret,
        payment_intent_id,
        amount,
        currency,
        shop_name: data.shopName,
        shop_id: data.shopId,
      });
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      const msg =
        typeof detail === "string"
          ? detail
          : Array.isArray(detail)
            ? detail.map((item: any) => item.msg || String(item)).join("; ")
            : err?.message || "Payment setup failed";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const formattedAmount = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(data.serviceCost);

  if (paid) {
    return (
      <Card className="w-full max-w-sm border-primary/40">
        <CardContent className="flex items-center gap-2 p-3 text-sm font-semibold text-primary">
          <CheckCircle2 className="size-4" />
          Payment completed
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={compact ? "w-full max-w-sm" : "w-full max-w-md"}>
      {!compact && (
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <ShoppingCart className="size-4 text-primary" />
            Service Complete
          </CardTitle>
        </CardHeader>
      )}
      <CardContent className="flex flex-col gap-3 p-4">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="font-bold">{data.customerName}</p>
            {data.serviceName && (
              <Badge variant="secondary" className="mt-1 max-w-full truncate">
                {data.serviceName}
              </Badge>
            )}
          </div>
          <p className="shrink-0 text-lg font-black text-primary">{formattedAmount}</p>
        </div>

        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <Button size={compact ? "sm" : "default"} onClick={handlePayNow} disabled={loading}>
          {loading ? <Loader2 data-icon="inline-start" className="animate-spin" /> : <CreditCard data-icon="inline-start" />}
          {loading ? "Setting up..." : `Pay ${formattedAmount}`}
        </Button>
      </CardContent>
    </Card>
  );
};

export default InlineCheckoutCard;
