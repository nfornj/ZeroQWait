/**
 * InlineAppointmentForm — renders an interactive appointment booking form INSIDE chat bubbles.
 *
 * Customers select a date, available time slot, service, and enter their details
 * to schedule an appointment (as opposed to walk-in queue join).
 */
import React, { useState, useEffect, useCallback } from "react";
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
  Chip,
} from "@mui/material";
import EventIcon from "@mui/icons-material/Event";
import ScheduleIcon from "@mui/icons-material/Schedule";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import axios from "axios";

export interface AppointmentFormData {
  type: "appointment_form";
  shop_id: number;
  shop_name: string;
  services?: { id: number; name: string; cost: number; duration_minutes: number }[];
  status?: "collecting" | "booking" | "success" | "error";
  error?: string;
}

interface InlineAppointmentFormProps {
  shopId: number;
  shopName: string;
  theme: any;
  isDarkMode: boolean;
  disabled?: boolean;
  services?: { id: number; name: string; cost: number; duration_minutes: number }[];
  onFormSubmit: (result: {
    success: boolean;
    appointmentId?: number;
    scheduledStart?: string;
    error?: string;
  }) => void;
}

export const InlineAppointmentForm: React.FC<InlineAppointmentFormProps> = ({
  shopId,
  shopName,
  theme,
  isDarkMode,
  disabled = false,
  services = [],
  onFormSubmit,
}) => {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [selectedDate, setSelectedDate] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() + 1); // default to tomorrow
    return d.toISOString().split("T")[0];
  });
  const [selectedService, setSelectedService] = useState<number | "">("");
  const [availableSlots, setAvailableSlots] = useState<{ start: string; end: string }[]>([]);
  const [selectedSlot, setSelectedSlot] = useState("");
  const [loadingSlots, setLoadingSlots] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [booked, setBooked] = useState<{ id: number; time: string } | null>(null);

  // Fetch available slots when date or service changes
  useEffect(() => {
    if (!selectedDate) return;
    setLoadingSlots(true);
    setSelectedSlot("");
    const params: Record<string, string | number> = { date: selectedDate };
    if (selectedService) params.service_id = selectedService;

    axios
      .get(`/appointments/shop/${shopId}/available-slots`, { params })
      .then((res) => {
        setAvailableSlots(res.data || []);
      })
      .catch(() => {
        setAvailableSlots([]);
      })
      .finally(() => setLoadingSlots(false));
  }, [shopId, selectedDate, selectedService]);

  const handleSubmit = useCallback(async () => {
    setError(null);
    if (!name.trim()) { setError("Name is required"); return; }
    if (!phone.trim()) { setError("Phone number is required"); return; }
    if (!selectedSlot) { setError("Please select a time slot"); return; }

    setIsLoading(true);
    try {
      const res = await axios.post(`/appointments/shop/${shopId}/book`, {
        customer_name: name.trim(),
        customer_phone: phone.trim(),
        customer_email: email.trim() || undefined,
        service_id: selectedService || undefined,
        scheduled_start: selectedSlot,
      });

      if (res.data?.error) {
        setError(res.data.error);
        onFormSubmit({ success: false, error: res.data.error });
      } else {
        const time = new Date(selectedSlot).toLocaleString([], {
          month: "short",
          day: "numeric",
          hour: "2-digit",
          minute: "2-digit",
        });
        setBooked({ id: res.data.id, time });
        onFormSubmit({
          success: true,
          appointmentId: res.data.id,
          scheduledStart: selectedSlot,
        });
      }
    } catch (err: any) {
      const msg = err?.response?.data?.detail || "Failed to book appointment";
      setError(msg);
      onFormSubmit({ success: false, error: msg });
    } finally {
      setIsLoading(false);
    }
  }, [shopId, name, phone, email, selectedService, selectedSlot, onFormSubmit]);

  const formatSlotTime = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  };

  const cardBg = isDarkMode ? "rgba(30,30,40,0.85)" : "rgba(255,255,255,0.92)";
  const borderColor = isDarkMode ? "rgba(255,255,255,0.12)" : "rgba(0,0,0,0.12)";

  if (booked) {
    return (
      <Card
        sx={{
          p: 2,
          borderRadius: 3,
          bgcolor: cardBg,
          border: `1px solid ${borderColor}`,
          maxWidth: 380,
        }}
      >
        <Stack alignItems="center" spacing={1}>
          <CheckCircleIcon sx={{ fontSize: 48, color: "success.main" }} />
          <Typography variant="subtitle1" fontWeight={600}>
            Appointment Booked!
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {shopName} — {booked.time}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Appointment #{booked.id}
          </Typography>
        </Stack>
      </Card>
    );
  }

  return (
    <Card
      sx={{
        p: 2,
        borderRadius: 3,
        bgcolor: cardBg,
        border: `1px solid ${borderColor}`,
        maxWidth: 400,
      }}
    >
      <Stack spacing={1.5}>
        <Stack direction="row" alignItems="center" spacing={1}>
          <EventIcon color="primary" />
          <Typography variant="subtitle2" fontWeight={600}>
            Book Appointment — {shopName}
          </Typography>
        </Stack>

        {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}

        <TextField
          label="Your Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          size="small"
          disabled={disabled || isLoading}
          fullWidth
        />
        <TextField
          label="Phone"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          size="small"
          disabled={disabled || isLoading}
          fullWidth
        />
        <TextField
          label="Email (optional)"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          size="small"
          disabled={disabled || isLoading}
          fullWidth
        />

        {services.length > 0 && (
          <FormControl size="small" fullWidth>
            <InputLabel>Service</InputLabel>
            <Select
              value={selectedService}
              label="Service"
              onChange={(e) => setSelectedService(e.target.value as number | "")}
              disabled={disabled || isLoading}
            >
              <MenuItem value="">Any available</MenuItem>
              {services.map((s) => (
                <MenuItem key={s.id} value={s.id}>
                  {s.name} — ${s.cost.toFixed(2)} ({s.duration_minutes}min)
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        )}

        <TextField
          label="Date"
          type="date"
          value={selectedDate}
          onChange={(e) => setSelectedDate(e.target.value)}
          size="small"
          InputLabelProps={{ shrink: true }}
          inputProps={{ min: new Date().toISOString().split("T")[0] }}
          disabled={disabled || isLoading}
          fullWidth
        />

        {/* Time slot picker */}
        <Box>
          <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5, display: "block" }}>
            <ScheduleIcon sx={{ fontSize: 14, mr: 0.5, verticalAlign: "middle" }} />
            Available Slots
          </Typography>
          {loadingSlots ? (
            <CircularProgress size={20} />
          ) : availableSlots.length === 0 ? (
            <Typography variant="caption" color="text.disabled">
              No slots available for this date
            </Typography>
          ) : (
            <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.5 }}>
              {availableSlots.map((slot) => (
                <Chip
                  key={slot.start}
                  label={formatSlotTime(slot.start)}
                  size="small"
                  variant={selectedSlot === slot.start ? "filled" : "outlined"}
                  color={selectedSlot === slot.start ? "primary" : "default"}
                  onClick={() => setSelectedSlot(slot.start)}
                  disabled={disabled || isLoading}
                  sx={{ cursor: "pointer" }}
                />
              ))}
            </Box>
          )}
        </Box>

        <Button
          variant="contained"
          onClick={handleSubmit}
          disabled={disabled || isLoading || !selectedSlot}
          startIcon={isLoading ? <CircularProgress size={16} /> : <EventIcon />}
          sx={{ borderRadius: 2, textTransform: "none" }}
        >
          {isLoading ? "Booking..." : "Book Appointment"}
        </Button>
      </Stack>
    </Card>
  );
};

export default InlineAppointmentForm;
