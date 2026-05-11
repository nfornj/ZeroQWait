import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { CheckCircle2, CreditCard, Loader2, Lock } from "lucide-react";
import { loadStripe, Stripe } from "@stripe/stripe-js";
import { Elements, PaymentElement, useElements, useStripe } from "@stripe/react-stripe-js";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export interface PaymentFormData {
  type: "payment_form";
  client_secret: string;
  payment_intent_id: string;
  amount: number;
  currency: string;
  shop_name: string;
  shop_id: number | string;
}

interface InlinePaymentFormProps {
  data: PaymentFormData;
  onPaymentComplete?: (result: {
    success: boolean;
    paymentIntentId?: string;
    error?: string;
  }) => void;
  submitted?: boolean;
}

let stripePromise: Promise<Stripe | null> | null = null;

async function getStripePromise(): Promise<Stripe | null> {
  if (stripePromise) return stripePromise;

  stripePromise = (async () => {
    try {
      const resp = await axios.get("/payments/config");
      const { publishable_key, configured } = resp.data;
      if (!configured || !publishable_key) return null;
      return loadStripe(publishable_key);
    } catch {
      return null;
    }
  })();

  return stripePromise;
}

function CheckoutForm({
  amount,
  currency,
  shopName,
  onPaymentComplete,
}: {
  amount: number;
  currency: string;
  shopName: string;
  onPaymentComplete?: InlinePaymentFormProps["onPaymentComplete"];
}) {
  const stripe = useStripe();
  const elements = useElements();
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [succeeded, setSucceeded] = useState(false);

  const handleSubmit = useCallback(
    async (event: React.FormEvent) => {
      event.preventDefault();
      if (!stripe || !elements) return;

      setProcessing(true);
      setError(null);

      const { error: stripeError, paymentIntent } = await stripe.confirmPayment({
        elements,
        confirmParams: { return_url: window.location.href },
        redirect: "if_required",
      });

      if (stripeError) {
        setError(stripeError.message || "Payment failed. Please try again.");
        setProcessing(false);
        onPaymentComplete?.({ success: false, error: stripeError.message });
      } else if (paymentIntent?.status === "succeeded") {
        setSucceeded(true);
        setProcessing(false);
        onPaymentComplete?.({ success: true, paymentIntentId: paymentIntent.id });
      } else {
        setProcessing(false);
      }
    },
    [stripe, elements, onPaymentComplete],
  );

  if (succeeded) {
    return (
      <div className="flex flex-col items-center gap-2 py-4 text-center">
        <CheckCircle2 className="size-10 text-primary" />
        <p className="font-bold text-primary">Payment Successful</p>
        <p className="text-sm text-muted-foreground">
          ${amount.toFixed(2)} {currency.toUpperCase()} paid to <strong>{shopName}</strong>
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <PaymentElement options={{ layout: "tabs" }} />
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      <Button type="submit" disabled={!stripe || processing}>
        {processing ? <Loader2 data-icon="inline-start" className="animate-spin" /> : <Lock data-icon="inline-start" />}
        {processing ? "Processing..." : `Pay $${amount.toFixed(2)} ${currency.toUpperCase()}`}
      </Button>
      <p className="flex items-center justify-center gap-1 text-xs text-muted-foreground">
        <Lock className="size-3" />
        Secured by Stripe
      </p>
    </form>
  );
}

export default function InlinePaymentForm({
  data,
  onPaymentComplete,
  submitted,
}: InlinePaymentFormProps) {
  const [stripeInstance, setStripeInstance] = useState<Stripe | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    getStripePromise().then((stripe) => {
      if (!mounted) return;
      if (stripe) setStripeInstance(stripe);
      else setLoadError("Payment system is not available right now.");
      setLoading(false);
    });
    return () => {
      mounted = false;
    };
  }, []);

  if (submitted) {
    return (
      <Card className="w-full max-w-md border-primary/40">
        <CardContent className="flex flex-col items-center gap-2 p-5 text-center">
          <CheckCircle2 className="size-10 text-primary" />
          <p className="font-bold text-primary">Payment Complete</p>
        </CardContent>
      </Card>
    );
  }

  if (loading) {
    return (
      <Card className="w-full max-w-md">
        <CardContent className="flex items-center gap-2 p-5 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" />
          Loading payment form...
        </CardContent>
      </Card>
    );
  }

  if (loadError || !stripeInstance) {
    return (
      <Alert>
        <AlertDescription>{loadError || "Payment form unavailable."}</AlertDescription>
      </Alert>
    );
  }

  return (
    <Card className="w-full max-w-md">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <CreditCard className="size-4 text-primary" />
          Payment
          <Badge className="ml-auto">${data.amount.toFixed(2)} {data.currency.toUpperCase()}</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <p className="text-sm text-muted-foreground">
          Paying <strong>{data.shop_name}</strong>
        </p>
        <Elements
          stripe={stripeInstance}
          options={{
            clientSecret: data.client_secret,
            appearance: {
              theme: "stripe",
              variables: {
                borderRadius: "12px",
                fontFamily: '"Inter", "Roboto", "Helvetica", sans-serif',
              },
            },
          }}
        >
          <CheckoutForm
            amount={data.amount}
            currency={data.currency}
            shopName={data.shop_name}
            onPaymentComplete={onPaymentComplete}
          />
        </Elements>
        <Badge variant="outline" className="w-fit">TEST MODE - Use card 4242 4242 4242 4242</Badge>
      </CardContent>
    </Card>
  );
}
