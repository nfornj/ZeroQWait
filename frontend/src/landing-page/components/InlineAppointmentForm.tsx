import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { CalendarClock, CheckCircle2, Loader2 } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

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
  disabled = false,
  services = [],
  onFormSubmit,
}) => {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [selectedDate, setSelectedDate] = useState(() => {
    const date = new Date();
    date.setDate(date.getDate() + 1);
    return date.toISOString().split("T")[0];
  });
  const [selectedService, setSelectedService] = useState("");
  const [availableSlots, setAvailableSlots] = useState<{ start: string; end: string }[]>([]);
  const [selectedSlot, setSelectedSlot] = useState("");
  const [loadingSlots, setLoadingSlots] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [booked, setBooked] = useState<{ id: number; time: string } | null>(null);

  useEffect(() => {
    if (!selectedDate) return;
    setLoadingSlots(true);
    setSelectedSlot("");
    const params: Record<string, string | number> = { date: selectedDate };
    if (selectedService) params.service_id = Number(selectedService);

    axios
      .get(`/appointments/shop/${shopId}/available-slots`, { params })
      .then((res) => setAvailableSlots(res.data || []))
      .catch(() => setAvailableSlots([]))
      .finally(() => setLoadingSlots(false));
  }, [shopId, selectedDate, selectedService]);

  const handleSubmit = useCallback(async () => {
    setError(null);
    if (!name.trim()) {
      setError("Name is required");
      return;
    }
    if (!phone.trim()) {
      setError("Phone number is required");
      return;
    }
    if (!selectedSlot) {
      setError("Please select a time slot");
      return;
    }

    setIsLoading(true);
    try {
      const res = await axios.post(`/appointments/shop/${shopId}/book`, {
        customer_name: name.trim(),
        customer_phone: phone.trim(),
        customer_email: email.trim() || undefined,
        service_id: selectedService ? Number(selectedService) : undefined,
        scheduled_start: selectedSlot,
      });

      if (res.data?.error) {
        setError(res.data.error);
        onFormSubmit({ success: false, error: res.data.error });
        return;
      }

      const time = new Date(selectedSlot).toLocaleString([], {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
      setBooked({ id: res.data.id, time });
      onFormSubmit({ success: true, appointmentId: res.data.id, scheduledStart: selectedSlot });
    } catch (err: any) {
      const msg = err?.response?.data?.detail || "Failed to book appointment";
      setError(msg);
      onFormSubmit({ success: false, error: msg });
    } finally {
      setIsLoading(false);
    }
  }, [shopId, name, phone, email, selectedService, selectedSlot, onFormSubmit]);

  const formatSlotTime = (iso: string) => new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  if (booked) {
    return (
      <Card className="w-full max-w-md border-primary/40">
        <CardContent className="flex flex-col items-center gap-2 p-5 text-center">
          <CheckCircle2 className="size-10 text-primary" />
          <p className="font-bold">Appointment Booked</p>
          <p className="text-sm text-muted-foreground">{shopName} - {booked.time}</p>
          <Badge variant="secondary">Appointment #{booked.id}</Badge>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="w-full max-w-md">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <CalendarClock className="size-4 text-primary" />
          Book Appointment - {shopName}
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <div className="grid gap-3 sm:grid-cols-2">
          <div className="flex flex-col gap-2">
            <Label htmlFor="appt-name">Your Name</Label>
            <Input id="appt-name" value={name} onChange={(event) => setName(event.target.value)} disabled={disabled || isLoading} />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="appt-phone">Phone</Label>
            <Input id="appt-phone" value={phone} onChange={(event) => setPhone(event.target.value)} disabled={disabled || isLoading} type="tel" />
          </div>
        </div>

        <div className="flex flex-col gap-2">
          <Label htmlFor="appt-email">Email (optional)</Label>
          <Input id="appt-email" value={email} onChange={(event) => setEmail(event.target.value)} disabled={disabled || isLoading} type="email" />
        </div>

        {services.length > 0 && (
          <div className="flex flex-col gap-2">
            <Label>Service</Label>
            <Select value={selectedService} onValueChange={setSelectedService} disabled={disabled || isLoading}>
              <SelectTrigger>
                <SelectValue placeholder="Any available" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  {services.map((service) => (
                    <SelectItem key={service.id} value={String(service.id)}>
                      {service.name} - ${service.cost.toFixed(2)} ({service.duration_minutes} min)
                    </SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
          </div>
        )}

        <div className="flex flex-col gap-2">
          <Label htmlFor="appt-date">Date</Label>
          <Input id="appt-date" type="date" value={selectedDate} onChange={(event) => setSelectedDate(event.target.value)} min={new Date().toISOString().split("T")[0]} disabled={disabled || isLoading} />
        </div>

        <div className="flex flex-col gap-2">
          <Label>Available Slots</Label>
          {loadingSlots ? (
            <p className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="size-4 animate-spin" />
              Loading slots...
            </p>
          ) : availableSlots.length === 0 ? (
            <p className="text-sm text-muted-foreground">No slots available for this date.</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {availableSlots.map((slot) => (
                <Button
                  key={slot.start}
                  type="button"
                  variant={selectedSlot === slot.start ? "default" : "outline"}
                  size="sm"
                  onClick={() => setSelectedSlot(slot.start)}
                  disabled={disabled || isLoading}
                >
                  {formatSlotTime(slot.start)}
                </Button>
              ))}
            </div>
          )}
        </div>

        <Button onClick={handleSubmit} disabled={disabled || isLoading || !selectedSlot}>
          {isLoading ? <Loader2 data-icon="inline-start" className="animate-spin" /> : <CalendarClock data-icon="inline-start" />}
          {isLoading ? "Booking..." : "Book Appointment"}
        </Button>
      </CardContent>
    </Card>
  );
};

export default InlineAppointmentForm;
