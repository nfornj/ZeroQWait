import React, { useState } from "react";
import {
  Box,
  Typography,
  Button,
  CircularProgress,
  Stack,
  Chip,
  alpha,
} from "@mui/material";
import ShoppingCartCheckoutIcon from "@mui/icons-material/ShoppingCartCheckout";
import PaymentIcon from "@mui/icons-material/Payment";
import CheckCircleOutlineIcon from "@mui/icons-material/CheckCircleOutline";
import axios from "axios";
import type { PaymentFormData } from "./InlinePaymentForm";

// ── Types ──────────────────────────────────────────────────────────

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

// ── Component ──────────────────────────────────────────────────────

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
    setLoading(true);
    setError(null);

    try {
      const resp = await axios.post("/payments/create-payment-intent", {
        amount: data.serviceCost,
        currency: "USD",
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
      const msg =
        err?.response?.data?.detail || err?.message || "Payment setup failed";
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
      <Box
        sx={{
          p: compact ? 1 : 2,
          borderRadius: compact ? "12px" : "16px",
          border: "1px solid",
          borderColor: "success.main",
          bgcolor: (t) => alpha(t.palette.success.main, 0.06),
          maxWidth: compact ? 220 : 340,
        }}
      >
        <Stack direction="row" spacing={0.75} alignItems="center">
          <CheckCircleOutlineIcon color="success" sx={{ fontSize: compact ? 16 : 24 }} />
          <Typography variant={compact ? "caption" : "body2"} sx={{ fontWeight: 600, color: "success.main" }}>
            Payment completed
          </Typography>
        </Stack>
      </Box>
    );
  }

  return (
    <Box
      sx={{
        p: compact ? 1.5 : 2.5,
        borderRadius: compact ? "12px" : "18px",
        border: "1px solid",
        borderColor: "primary.main",
        bgcolor: (t) => alpha(t.palette.primary.main, 0.04),
        maxWidth: compact ? 260 : 360,
      }}
    >
      <Stack spacing={compact ? 0.75 : 1.5}>
        {/* Header — hide in compact mode */}
        {!compact && (
          <Stack direction="row" spacing={1} alignItems="center">
            <ShoppingCartCheckoutIcon color="primary" fontSize="small" />
            <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
              Service Complete
            </Typography>
          </Stack>
        )}

        {/* Customer & amount in one row for compact */}
        {compact ? (
          <Stack direction="row" spacing={1} alignItems="center" justifyContent="space-between">
            <Box sx={{ minWidth: 0 }}>
              <Typography variant="body2" sx={{ fontWeight: 700, lineHeight: 1.2 }} noWrap>
                {data.customerName}
              </Typography>
              {data.serviceName && (
                <Typography variant="caption" color="text.secondary" noWrap>
                  {data.serviceName}
                </Typography>
              )}
            </Box>
            <Typography variant="body2" sx={{ fontWeight: 800, color: "primary.main", flexShrink: 0 }}>
              {formattedAmount}
            </Typography>
          </Stack>
        ) : (
          <Box>
            <Typography variant="h6" sx={{ fontWeight: 800, lineHeight: 1.2, mb: 0.5 }}>
              {data.customerName}
            </Typography>
            {data.serviceName && (
              <Chip label={data.serviceName} size="small" variant="outlined" sx={{ borderRadius: "8px" }} />
            )}
          </Box>
        )}

        {/* Amount — only for non-compact */}
        {!compact && (
          <Typography variant="h5" sx={{ fontWeight: 900, color: "primary.main" }}>
            {formattedAmount}
          </Typography>
        )}

        {/* Error */}
        {error && (
          <Typography variant="caption" color="error">
            {error}
          </Typography>
        )}

        {/* Pay button */}
        <Button
          variant="contained"
          size={compact ? "small" : "large"}
          onClick={handlePayNow}
          disabled={loading}
          startIcon={
            loading ? (
              <CircularProgress size={compact ? 14 : 18} color="inherit" />
            ) : (
              <PaymentIcon sx={{ fontSize: compact ? 16 : 20 }} />
            )
          }
          sx={{
            borderRadius: compact ? "10px" : "14px",
            fontWeight: 700,
            textTransform: "none",
            py: compact ? 0.5 : 1.2,
            fontSize: compact ? "0.8rem" : undefined,
          }}
        >
          {loading ? "Setting up\u2026" : `Pay ${formattedAmount}`}
        </Button>
      </Stack>
    </Box>
  );
};

export default InlineCheckoutCard;
