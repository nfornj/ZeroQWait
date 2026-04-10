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
  onFormSubmit: (result: {
    success: boolean;
    queueItemId?: number;
    position?: number;
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
  onFormSubmit,
}) => {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [service, setService] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = useCallback(async () => {
    setError(null);

    // Validate inputs
    if (!name.trim()) {
      setError("Name is required");
      return;
    }
    if (!phone.trim()) {
      setError("Phone number is required");
      return;
    }

    setIsLoading(true);

    try {
      // Call backend to join queue with collected details
      const response = await axios.post(
        "/api/agent/master/chat",
        {
          message: `My name is ${name.trim()} and phone is ${phone.trim()}${
            service ? ` and service is ${service.trim()}` : ""
          }`,
          session_id: sessionId,
          context: {
            shop_id: shopId,
            shop_name: shopName,
            submit_form: true, // Flag to indicate form submission
          },
        },
        { withCredentials: true }
      );

      const result = response.data;

      // Check if join was successful
      if (
        result.actions &&
        result.actions.some(
          (a: any) =>
            a.tool === "join_queue" && a.result && a.result.success === true
        )
      ) {
        const joinAction = result.actions.find(
          (a: any) => a.tool === "join_queue"
        );
        onFormSubmit({
          success: true,
          queueItemId: joinAction.result.queue_item_id,
          position: joinAction.result.position,
        });
      } else {
        // Extract error message if available
        const errorMsg =
          result.response ||
          error ||
          "Failed to join queue. Please try again.";
        setError(errorMsg);
        onFormSubmit({
          success: false,
          error: errorMsg,
        });
      }
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
  }, [name, phone, service, shopId, shopName, sessionId, onFormSubmit, error]);

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
            pattern: "[0-9+()\\-\\s]*",
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

        {/* Optional Service Field */}
        <TextField
          label="Service (Optional)"
          placeholder="e.g., Haircut, Fade, Style"
          value={service}
          onChange={(e) => setService(e.target.value)}
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
