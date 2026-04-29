/**
 * InlineQueueJoinForm — renders interactive queue join form INSIDE chat bubbles.
 *
 * Mirrors InlineRegistrationForm pattern but for collecting customer details
 * (name, phone, optional service) before joining a queue.
 */
import React, { useState, useCallback } from "react";
import {
  Box,
  Button,
  Card,
  TextField,
  Stack,
  Typography,
  CircularProgress,
  Alert,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
} from "@mui/material";
import PersonIcon from "@mui/icons-material/Person";
import PhoneIcon from "@mui/icons-material/Phone";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import ErrorIcon from "@mui/icons-material/Error";
import axios from "axios";

export interface QueueJoinFormData {
  type: "queue_join_form";
  shop_id: number;
  shop_name: string;
  city?: string;
  shop_type?: string;
  services?: { id: number; name: string; cost: number }[];
  status?: "collecting" | "joining" | "success" | "error";
  error?: string;
}

interface InlineQueueJoinFormProps {
  shopId: number;
  shopName: string;
  shopType?: string;
  sessionId: string;
  theme: any;
  isDarkMode: boolean;
  disabled?: boolean;
  services?: { id: number; name: string; cost: number }[];
  onFormSubmit: (result: {
    success: boolean;
    queueItemId?: number;
    position?: number;
    serviceCost?: number;
    error?: string;
  }) => void;
}

export const InlineQueueJoinForm: React.FC<InlineQueueJoinFormProps> = ({
  shopId,
  shopName,
  shopType,
  sessionId,
  theme,
  isDarkMode,
  disabled = false,
  services = [],
  onFormSubmit,
}) => {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [serviceValue, setServiceValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = useCallback(async () => {
    setError(null);
    const trimmedName = name.trim();
    const trimmedPhone = phone.trim();

    // Validate inputs
    if (!trimmedName) {
      setError("Name is required");
      return;
    }
    if (!trimmedPhone) {
      setError("Phone number is required");
      return;
    }

    setIsLoading(true);

    try {
      const payload: Record<string, unknown> = {
        customer_name: trimmedName,
        customer_phone: trimmedPhone,
      };

      let selectedServiceCost: number | undefined;
      if (services.length > 0) {
        const selectedServiceId = Number(serviceValue);
        if (Number.isFinite(selectedServiceId) && selectedServiceId > 0) {
          payload.service_id = selectedServiceId;
          selectedServiceCost = services.find((svc) => svc.id === selectedServiceId)?.cost;
        }
      } else if (serviceValue.trim()) {
        payload.notes = `Requested service: ${serviceValue.trim()}`;
      }

      const response = await axios.post(
        `/queues/shop/${shopId}/join`,
        payload,
        { withCredentials: true }
      );

      const result = response.data;
      onFormSubmit({
        success: true,
        queueItemId: result.id,
        position: result.position,
        serviceCost:
          typeof result.service_cost === "number"
            ? result.service_cost
            : selectedServiceCost,
      });
    } catch (err: any) {
      const errorMsg =
        err.response?.data?.detail ||
        err.message ||
        "An error occurred. Please try again.";
      setError(errorMsg);
      onFormSubmit({
        success: false,
        error: errorMsg,
      });
    } finally {
      setIsLoading(false);
    }
  }, [name, onFormSubmit, phone, serviceValue, services, shopId]);

  if (disabled) {
    return null;
  }

  return (
    <Card
      sx={{
        bgcolor: isDarkMode ? theme.cardBg : "#fafafa",
        border: `1px solid ${theme.cardBorder}`,
        borderRadius: "16px",
        p: 2,
      }}
    >
      <Stack spacing={2}>
        {/* Title */}
        <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
          Complete Your Queue Entry
        </Typography>

        {/* Error Alert */}
        {error && (
          <Alert severity="error" sx={{ fontSize: "0.9rem" }}>
            {error}
          </Alert>
        )}

        {/* Name Field */}
        <TextField
          label="Your Name"
          placeholder="e.g., John Smith"
          value={name}
          onChange={(e) => setName(e.target.value)}
          disabled={isLoading}
          fullWidth
          size="small"
          variant="outlined"
          autoComplete="name"
          inputProps={{
            enterKeyHint: "next",
            autoCapitalize: "words",
          }}
          InputProps={{
            startAdornment: <PersonIcon sx={{ mr: 1, color: theme.accent, fontSize: "1.2rem" }} />,
          }}
          sx={{
            "& .MuiOutlinedInput-root": {
              borderRadius: "12px",
              bgcolor: isDarkMode ? theme.inputBg : "#fff",
              "& fieldset": { borderColor: theme.cardBorder },
              "&:hover fieldset": { borderColor: theme.accent },
              "&.Mui-focused fieldset": { borderColor: theme.accent },
            },
          }}
        />

        {/* Phone Field */}
        <TextField
          label="Phone Number"
          placeholder="e.g., (416) 555-0123"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          disabled={isLoading}
          fullWidth
          size="small"
          variant="outlined"
          type="tel"
          autoComplete="tel"
          inputProps={{
            inputMode: "tel",
            enterKeyHint: "done",
            maxLength: 24,
          }}
          InputProps={{
            startAdornment: <PhoneIcon sx={{ mr: 1, color: theme.accent, fontSize: "1.2rem" }} />,
          }}
          sx={{
            "& .MuiOutlinedInput-root": {
              borderRadius: "12px",
              bgcolor: isDarkMode ? theme.inputBg : "#fff",
              "& fieldset": { borderColor: theme.cardBorder },
              "&:hover fieldset": { borderColor: theme.accent },
              "&.Mui-focused fieldset": { borderColor: theme.accent },
            },
          }}
        />

        {/* Service Selection */}
        {services.length > 0 ? (
          <FormControl fullWidth size="small">
            <InputLabel>Service</InputLabel>
            <Select
              value={serviceValue}
              label="Service"
              onChange={(e) => setServiceValue(e.target.value)}
              disabled={isLoading}
              sx={{
                borderRadius: "12px",
                bgcolor: isDarkMode ? theme.inputBg : "#fff",
                "& .MuiOutlinedInput-notchedOutline": { borderColor: theme.cardBorder },
                "&:hover .MuiOutlinedInput-notchedOutline": { borderColor: theme.accent },
                "&.Mui-focused .MuiOutlinedInput-notchedOutline": { borderColor: theme.accent },
              }}
            >
              {services.map((svc) => (
                <MenuItem key={svc.id} value={String(svc.id)}>
                  {svc.name} — ${svc.cost.toFixed(2)}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        ) : (
          <TextField
            label="Service (Optional)"
            placeholder="e.g., Haircut, Fade, Style"
            value={serviceValue}
            onChange={(e) => setServiceValue(e.target.value)}
            disabled={isLoading}
            fullWidth
            size="small"
            variant="outlined"
            autoComplete="off"
            inputProps={{
              enterKeyHint: "done",
            }}
            sx={{
              "& .MuiOutlinedInput-root": {
                borderRadius: "12px",
                bgcolor: isDarkMode ? theme.inputBg : "#fff",
                "& fieldset": { borderColor: theme.cardBorder },
                "&:hover fieldset": { borderColor: theme.accent },
                "&.Mui-focused fieldset": { borderColor: theme.accent },
              },
            }}
          />
        )}

        {/* Submit Button */}
        <Button
          variant="contained"
          onClick={handleSubmit}
          disabled={isLoading || !name.trim() || !phone.trim()}
          fullWidth
          sx={{
            bgcolor: theme.accent,
            color: isDarkMode ? "#000" : "#fff",
            borderRadius: "12px",
            fontWeight: 600,
            py: 1.2,
            "&:hover": {
              bgcolor: isDarkMode ? theme.accentHover || theme.accent : theme.accent,
              opacity: 0.9,
            },
            "&:disabled": {
              bgcolor: theme.cardBorder,
              color: theme.textSecondary,
            },
            textTransform: "none",
            fontSize: "0.95rem",
          }}
        >
          {isLoading ? (
            <>
              <CircularProgress size={18} sx={{ mr: 1 }} />
              Joining Queue...
            </>
          ) : (
            <>
              <CheckCircleIcon sx={{ mr: 1, fontSize: "1.1rem" }} />
              Join Queue
            </>
          )}
        </Button>

        {/* Helper text */}
        <Typography
          variant="caption"
          sx={{
            color: theme.textSecondary,
            textAlign: "center",
            fontSize: "0.8rem",
          }}
        >
          Your details will be saved to your queue entry
        </Typography>
      </Stack>
    </Card>
  );
};

export default InlineQueueJoinForm;
