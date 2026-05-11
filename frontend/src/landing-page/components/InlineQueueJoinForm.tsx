import React, { useCallback, useState } from "react";
import axios from "axios";
import { CheckCircle2, Loader2, Phone, User } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
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
  services = [],
  disabled = false,
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

      const response = await axios.post(`/queues/shop/${shopId}/join`, payload, { withCredentials: true });
      const result = response.data;
      onFormSubmit({
        success: true,
        queueItemId: result.id,
        position: result.position,
        serviceCost: typeof result.service_cost === "number" ? result.service_cost : selectedServiceCost,
      });
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message || "An error occurred. Please try again.";
      setError(errorMsg);
      onFormSubmit({ success: false, error: errorMsg });
    } finally {
      setIsLoading(false);
    }
  }, [name, onFormSubmit, phone, serviceValue, services, shopId]);

  if (disabled) return null;

  return (
    <Card className="w-full max-w-md">
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Complete Your Queue Entry</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <div className="flex flex-col gap-2">
          <Label htmlFor="queue-name">Your Name</Label>
          <div className="relative">
            <User className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input id="queue-name" className="pl-9" value={name} onChange={(event) => setName(event.target.value)} disabled={isLoading} autoComplete="name" />
          </div>
        </div>

        <div className="flex flex-col gap-2">
          <Label htmlFor="queue-phone">Phone Number</Label>
          <div className="relative">
            <Phone className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input id="queue-phone" className="pl-9" value={phone} onChange={(event) => setPhone(event.target.value)} disabled={isLoading} type="tel" autoComplete="tel" />
          </div>
        </div>

        <div className="flex flex-col gap-2">
          <Label htmlFor="queue-service">Service</Label>
          {services.length > 0 ? (
            <Select value={serviceValue} onValueChange={setServiceValue} disabled={isLoading}>
              <SelectTrigger id="queue-service">
                <SelectValue placeholder="Select a service" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  {services.map((svc) => (
                    <SelectItem key={svc.id} value={String(svc.id)}>
                      {svc.name} - ${svc.cost.toFixed(2)}
                    </SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
          ) : (
            <Input id="queue-service" value={serviceValue} onChange={(event) => setServiceValue(event.target.value)} disabled={isLoading} placeholder="Haircut, fade, style" />
          )}
        </div>

        <Button onClick={handleSubmit} disabled={isLoading || !name.trim() || !phone.trim()}>
          {isLoading ? <Loader2 data-icon="inline-start" className="animate-spin" /> : <CheckCircle2 data-icon="inline-start" />}
          {isLoading ? "Joining Queue..." : "Join Queue"}
        </Button>
        <p className="text-center text-xs text-muted-foreground">Your details will be saved to your queue entry.</p>
      </CardContent>
    </Card>
  );
};

export default InlineQueueJoinForm;
