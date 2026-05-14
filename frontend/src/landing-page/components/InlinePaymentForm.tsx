import React, { useState, useEffect, useCallback } from "react";
import {
  Box,
  Typography,
  Button,
  CircularProgress,
  Alert,
  Divider,
  Stack,
  Chip,
} from "@mui/material";
import CreditCardIcon from "@mui/icons-material/CreditCard";
import LockIcon from "@mui/icons-material/Lock";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import { loadStripe, Stripe, StripeElements } from "@stripe/stripe-js";
import {
  Elements,
  PaymentElement,
  useStripe,
  useElements,
} from "@stripe/react-stripe-js";
import axios from "axios";

// ── Types ──────────────────────────────────────────────────────────

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

// ── Stripe loader (singleton) ──────────────────────────────────────

let stripePromise: Promise<Stripe | null> | null = null;

async function getStripePromise(): Promise<Stripe | null> {
  if (stripePromise) return stripePromise;

  stripePromise = (async () => {
    try {
      const resp = await axios.get("/payments/config");
      const { publishable_key, configured } = resp.data;
      if (!configured || !publishable_key) {
        console.warn("Stripe not configured on backend");
        return null;
      }
      return loadStripe(publishable_key);
    } catch (err) {
      console.error("Failed to load Stripe config:", err);
      return null;
    }
  })();

  return stripePromise;
}

// ── Inner checkout form (rendered inside Elements provider) ────────

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
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!stripe || !elements) return;

      setProcessing(true);
      setError(null);

      const { error: stripeError, paymentIntent } =
        await stripe.confirmPayment({
          elements,
          confirmParams: {
            return_url: window.location.href,
          },
          redirect: "if_required",
        });

      if (stripeError) {
        setError(stripeError.message || "Payment failed. Please try again.");
        setProcessing(false);
        onPaymentComplete?.({
          success: false,
          error: stripeError.message,
        });
      } else if (paymentIntent?.status === "succeeded") {
        setSucceeded(true);
        setProcessing(false);
        onPaymentComplete?.({
          success: true,
          paymentIntentId: paymentIntent.id,
        });
      } else {
        setProcessing(false);
      }
    },
    [stripe, elements, onPaymentComplete]
  );

  if (succeeded) {
    return (
      <Box sx={{ textAlign: "center", py: 2 }}>
        <CheckCircleIcon
          sx={{ fontSize: 48, color: "success.main", mb: 1 }}
        />
        <Typography variant="h6" color="success.main" gutterBottom>
          Payment Successful!
        </Typography>
        <Typography variant="body2" color="text.secondary">
          ${amount.toFixed(2)} {currency.toUpperCase()} paid to{" "}
          <strong>{shopName}</strong>
        </Typography>
      </Box>
    );
  }

  return (
    <form onSubmit={handleSubmit}>
      <PaymentElement
        options={{
          layout: "tabs",
        }}
      />

      {error && (
        <Alert severity="error" sx={{ mt: 2, borderRadius: 2 }}>
          {error}
        </Alert>
      )}

      <Button
        type="submit"
        variant="contained"
        fullWidth
        disabled={!stripe || processing}
        sx={{
          mt: 2,
          py: 1.5,
          borderRadius: 3,
          fontWeight: 600,
          fontSize: "1rem",
          textTransform: "none",
        }}
        startIcon={
          processing ? (
            <CircularProgress size={20} color="inherit" />
          ) : (
            <LockIcon />
          )
        }
      >
        {processing
          ? "Processing..."
          : `Pay $${amount.toFixed(2)} ${currency.toUpperCase()}`}
      </Button>

      <Stack
        direction="row"
        spacing={1}
        justifyContent="center"
        alignItems="center"
        sx={{ mt: 1.5 }}
      >
        <LockIcon sx={{ fontSize: 14, color: "text.disabled" }} />
        <Typography variant="caption" color="text.disabled">
          Secured by Stripe
        </Typography>
      </Stack>
    </form>
  );
}

// ── Main exported component ────────────────────────────────────────

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
    getStripePromise().then((s) => {
      if (!mounted) return;
      if (s) {
        setStripeInstance(s);
      } else {
        setLoadError("Payment system is not available right now.");
      }
      setLoading(false);
    });
    return () => {
      mounted = false;
    };
  }, []);

  if (submitted) {
    return (
      <Box sx={{ textAlign: "center", py: 2 }}>
        <CheckCircleIcon
          sx={{ fontSize: 48, color: "success.main", mb: 1 }}
        />
        <Typography variant="h6" color="success.main">
          Payment Complete
        </Typography>
      </Box>
    );
  }

  if (loading) {
    return (
      <Box sx={{ textAlign: "center", py: 3 }}>
        <CircularProgress size={32} />
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
          Loading payment form...
        </Typography>
      </Box>
    );
  }

  if (loadError || !stripeInstance) {
    return (
      <Alert severity="warning" sx={{ borderRadius: 2 }}>
        {loadError || "Payment form unavailable."}
      </Alert>
    );
  }

  return (
    <Box
      sx={{
        mt: 1.5,
        p: 2.5,
        borderRadius: 4,
        bgcolor: "background.paper",
        border: 1,
        borderColor: "divider",
        boxShadow: (theme) =>
          theme.palette.mode === "dark"
            ? "0 2px 12px rgba(0,0,0,0.3)"
            : "0 2px 12px rgba(0,0,0,0.08)",
      }}
    >
      {/* Header */}
      <Stack
        direction="row"
        alignItems="center"
        spacing={1}
        sx={{ mb: 2 }}
      >
        <CreditCardIcon color="primary" />
        <Typography variant="subtitle1" fontWeight={600}>
          Payment
        </Typography>
        <Box sx={{ flexGrow: 1 }} />
        <Chip
          label={`$${data.amount.toFixed(2)} ${data.currency.toUpperCase()}`}
          color="primary"
          size="small"
          sx={{ fontWeight: 700 }}
        />
      </Stack>

      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Paying <strong>{data.shop_name}</strong>
      </Typography>

      <Divider sx={{ mb: 2 }} />

      {/* Stripe Elements */}
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

      {/* Test mode indicator */}
      <Box sx={{ mt: 2, textAlign: "center" }}>
        <Chip
          label="TEST MODE — Use card 4242 4242 4242 4242"
          size="small"
          variant="outlined"
          color="warning"
          sx={{ fontSize: "0.7rem" }}
        />
      </Box>
    </Box>
  );
}
