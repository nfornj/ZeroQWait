import React, { useEffect, useState } from "react";
import {
  Camera,
  CheckCircle,
  Clock,
  LogOut,
  Plus,
  SkipForward,
  Trash2,
  UserPlus,
  Users,
  AlertTriangle,
  Play,
} from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import api from "../../../services/api";
import { useAuth } from "../../../contexts/AuthContext";
import ProfilePhotoUploader from "../../../components/ProfilePhotoUploader";
import { useShop } from "../../../contexts/ShopContext";

interface Shop {
  id: number;
  name: string;
}

interface QueueItem {
  id: number;
  customer_name: string;
  position: number;
  status: string;
  checked_in_at: string;
}

interface Shift {
  id: number;
  shop_id: number;
  clock_in: string;
  clock_out: string | null;
}

const EmployeeQueuePage: React.FC = () => {
  const [shops, setShops] = useState<Shop[]>([]);
  const [selectedShop, setSelectedShop] = useState<Shop | null>(null);
  const [currentShift, setCurrentShift] = useState<Shift | null>(null);
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [photoDialogOpen, setPhotoDialogOpen] = useState(false);
  const [removeDialogOpen, setRemoveDialogOpen] = useState(false);
  const [selectedCustomer, setSelectedCustomer] = useState<QueueItem | null>(null);
  const [removeReason, setRemoveReason] = useState("");
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [newCustomerName, setNewCustomerName] = useState("");
  const [newCustomerPhone, setNewCustomerPhone] = useState("");
  const [services, setServices] = useState<any[]>([]);
  const [selectedServiceId, setSelectedServiceId] = useState<string>("");
  const [connectionLost, setConnectionLost] = useState(false);
  const [serveConfirmCustomer, setServeConfirmCustomer] = useState<QueueItem | null>(null);
  const [queueLoading, setQueueLoading] = useState(false);

  const { user } = useAuth();
  const { setShop } = useShop();

  useEffect(() => {
    fetchInitialData();
  }, []);

  useEffect(() => {
    if (selectedShop) {
      const interval = setInterval(fetchQueue, 5000);
      return () => clearInterval(interval);
    }
    return undefined;
  }, [selectedShop]);

  const fetchInitialData = async () => {
    try {
      setLoading(true);
      const shopsResponse = await api.get(`/employees/my-shops`);
      setShops(shopsResponse.data);

      const shiftResponse = await api.get(`/current-shift`);
      if (shiftResponse.data) {
        setCurrentShift(shiftResponse.data);
        const currentShop = shopsResponse.data.find((shop: Shop) => shop.id === shiftResponse.data.shop_id);
        if (currentShop) {
          setSelectedShop(currentShop);
          setShop({
            id: currentShop.id,
            name: currentShop.name,
            slug: "",
            city: "",
            shop_type: "",
          });
          await fetchQueue(currentShop.id);

          try {
            const servicesRes = await api.get(`/shops/${currentShop.id}/services`);
            setServices(servicesRes.data.filter((service: any) => service.is_active));
          } catch (e) {
            console.error("Failed to fetch services", e);
          }
        }
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to load data");
    } finally {
      setLoading(false);
    }
  };

  const fetchQueue = async (shopId?: number) => {
    const id = shopId || selectedShop?.id;
    if (!id) return;

    setQueueLoading(true);
    try {
      const response = await api.get(`/queues/shop/${id}/active`);
      setQueue(response.data.queue_items || []);
      setConnectionLost(false);
    } catch {
      setConnectionLost(true);
    } finally {
      setQueueLoading(false);
    }
  };

  const handleClockIn = async (shopId: number) => {
    try {
      setError(null);
      await api.post(`/clock-in/${shopId}`, {});
      setSuccess("Clocked in successfully!");
      await fetchInitialData();
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to clock in");
    }
  };

  const handleClockOut = async () => {
    try {
      setError(null);
      await api.post(`/clock-out`, {});
      setSuccess("Clocked out successfully!");
      setCurrentShift(null);
      setSelectedShop(null);
      setQueue([]);
      setShop(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to clock out");
    }
  };

  const handleCallNext = async () => {
    if (!selectedShop) return;

    try {
      setError(null);
      const response = await api.get(`/queues/shop/${selectedShop.id}/active`);
      const queueId = response.data.id;
      await api.post(`/queues/${queueId}/call-next`, {});
      setSuccess("Called next customer!");
      fetchQueue();
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to call next customer");
    }
  };

  const handleRemoveCustomer = async () => {
    if (!selectedCustomer || !removeReason.trim()) return;

    try {
      setError(null);
      await api.delete(`/queues/items/${selectedCustomer.id}`, {
        params: { reason: removeReason },
      });
      setSuccess("Customer removed from queue");
      setRemoveDialogOpen(false);
      setSelectedCustomer(null);
      setRemoveReason("");
      fetchQueue();
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to remove customer");
    }
  };

  const handleServeSpecific = (customer: QueueItem) => {
    setServeConfirmCustomer(customer);
  };

  const confirmServeSpecific = async () => {
    if (!serveConfirmCustomer) return;
    const customer = serveConfirmCustomer;
    setServeConfirmCustomer(null);
    try {
      setError(null);
      await api.post(`/queues/items/${customer.id}/serve`, {});
      setSuccess(`Now serving ${customer.customer_name}`);
      await fetchQueue();
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to serve customer");
    }
  };

  const handleCompleteCustomer = async (customer: QueueItem) => {
    try {
      setError(null);
      await api.patch(`/queues/items/${customer.id}/status?new_status=completed`, {});
      setSuccess(`Completed service for ${customer.customer_name}`);
      await fetchQueue();
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to complete customer");
    }
  };

  const handleUploadPhoto = async (photoDataUrl: string) => {
    try {
      await api.post(`/upload-profile-photo`, { photo_url: photoDataUrl }, { params: { photo_url: photoDataUrl } });
      setSuccess("Profile photo updated!");
    } catch (err: any) {
      throw new Error(err.response?.data?.detail || "Failed to upload photo");
    }
  };

  const handleAddWalkIn = async () => {
    if (!selectedShop || !newCustomerName.trim()) return;

    try {
      setError(null);
      await api.post(`/queues/shop/${selectedShop.id}/join`, {
        customer_name: newCustomerName,
        customer_phone: newCustomerPhone,
        service_id: selectedServiceId ? Number(selectedServiceId) : undefined,
        notes: "[Walk-in]",
      });

      setSuccess("Customer added to queue");
      setAddDialogOpen(false);
      setNewCustomerName("");
      setNewCustomerPhone("");
      setSelectedServiceId("");
      fetchQueue();
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to add customer");
    }
  };

  const waitingCustomers = queue.filter((item) => item.status === "waiting");
  const servingCustomer = queue.find((item) => item.status === "being_served");

  if (loading) {
    return (
      <div className="mx-auto flex min-h-[80vh] w-full max-w-6xl flex-col justify-center gap-4 p-6">
        <Skeleton className="h-12 w-80" />
        <Skeleton className="h-56 w-full" />
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-6">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Welcome, {user?.username}!</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {currentShift ? `Working at ${selectedShop?.name}` : "Select a shop to clock in"}
          </p>
        </div>
        <Button variant="outline" onClick={() => setPhotoDialogOpen(true)}>
          <Camera data-icon="inline-start" />
          Update Photo
        </Button>
      </div>

      {error && (
        <Alert variant="destructive" className="mb-3">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {success && (
        <Alert className="mb-3">
          <AlertDescription>{success}</AlertDescription>
        </Alert>
      )}

      {!currentShift ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {shops.map((shop) => (
            <Card key={shop.id}>
              <CardContent className="flex flex-col gap-4 p-5">
                <h2 className="text-lg font-semibold">{shop.name}</h2>
                <Button onClick={() => handleClockIn(shop.id)}>
                  <Clock data-icon="inline-start" />
                  Clock In
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          <Card>
            <CardContent className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h2 className="text-lg font-semibold">Current Shift</h2>
                <p className="text-sm text-muted-foreground">
                  Clocked in at {new Date(currentShift.clock_in).toLocaleTimeString()}
                </p>
              </div>
              <Button variant="outline" onClick={handleClockOut}>
                <LogOut data-icon="inline-start" />
                Clock Out
              </Button>
            </CardContent>
          </Card>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <Card>
              <CardContent className="flex flex-col items-center gap-1 p-5 text-center">
                <Users className="size-5 text-primary" />
                <p className="text-3xl font-semibold">{queue.length}</p>
                <p className="text-sm text-muted-foreground">Total in Queue</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="flex flex-col items-center gap-1 p-5 text-center">
                <Clock className="size-5 text-warning" />
                <p className="text-3xl font-semibold">{waitingCustomers.length}</p>
                <p className="text-sm text-muted-foreground">Waiting</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="flex flex-col items-center gap-1 p-5 text-center">
                <Play className="size-5 text-primary" />
                <p className="text-3xl font-semibold">{servingCustomer ? 1 : 0}</p>
                <p className="text-sm text-muted-foreground">Being Served</p>
              </CardContent>
            </Card>
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card className={servingCustomer ? "border-primary" : undefined}>
              <CardHeader>
                <CardTitle>Now Serving</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                {servingCustomer ? (
                  <div className="flex flex-col items-center gap-3 py-6 text-center">
                    <p className="text-6xl font-semibold text-primary">#{servingCustomer.position}</p>
                    <p className="text-2xl font-semibold">{servingCustomer.customer_name}</p>
                    <Badge variant="secondary">Being Served</Badge>
                    <div className="mt-2 flex flex-wrap justify-center gap-2">
                      <Button onClick={() => handleCompleteCustomer(servingCustomer)}>
                        <CheckCircle data-icon="inline-start" />
                        Complete
                      </Button>
                      <Button
                        variant="outline"
                        onClick={() => {
                          setSelectedCustomer(servingCustomer);
                          setRemoveDialogOpen(true);
                        }}
                      >
                        <Trash2 data-icon="inline-start" />
                        Remove
                      </Button>
                    </div>
                  </div>
                ) : (
                  <p className="py-10 text-center text-sm text-muted-foreground">No customer being served</p>
                )}
                <Button size="lg" onClick={handleCallNext} disabled={waitingCustomers.length === 0}>
                  <UserPlus data-icon="inline-start" />
                  Call Next Customer
                </Button>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <div className="flex items-center justify-between gap-3">
                  <CardTitle>Waiting Queue ({waitingCustomers.length})</CardTitle>
                  {connectionLost && (
                    <Badge variant="secondary" className="gap-1">
                      <AlertTriangle className="size-3.5" />
                      Connection lost
                    </Badge>
                  )}
                </div>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <Button variant="outline" onClick={() => setAddDialogOpen(true)}>
                  <Plus data-icon="inline-start" />
                  Add Walk-in Customer
                </Button>
                {queueLoading && waitingCustomers.length === 0 ? (
                  <div className="flex flex-col gap-2">
                    {[1, 2, 3].map((item) => (
                      <Skeleton key={item} className="h-14 w-full" />
                    ))}
                  </div>
                ) : waitingCustomers.length === 0 ? (
                  <p className="py-10 text-center text-sm text-muted-foreground">No customers waiting</p>
                ) : (
                  <div className="flex flex-col divide-y rounded-lg border">
                    {waitingCustomers.slice(0, 10).map((item) => (
                      <div key={item.id} className="flex items-center gap-3 p-3">
                        <Badge variant="outline" className="min-w-10 justify-center">
                          #{item.position}
                        </Badge>
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium">{item.customer_name}</p>
                          <p className="text-xs text-muted-foreground">
                            {new Date(item.checked_in_at).toLocaleTimeString()}
                          </p>
                        </div>
                        <div className="flex gap-1">
                          <Button variant="ghost" size="icon" onClick={() => handleServeSpecific(item)} aria-label={`Serve ${item.customer_name}`}>
                            <SkipForward />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => {
                              setSelectedCustomer(item);
                              setRemoveDialogOpen(true);
                            }}
                            aria-label={`Remove ${item.customer_name}`}
                          >
                            <Trash2 className="text-destructive" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      <ProfilePhotoUploader
        open={photoDialogOpen}
        onClose={() => setPhotoDialogOpen(false)}
        onUpload={handleUploadPhoto}
      />

      <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Walk-in Customer</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-2">
              <Label htmlFor="walkin-name">Customer Name</Label>
              <Input id="walkin-name" autoFocus value={newCustomerName} onChange={(event) => setNewCustomerName(event.target.value)} placeholder="e.g. John Doe" />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="walkin-phone">Phone (Optional)</Label>
              <Input id="walkin-phone" value={newCustomerPhone} onChange={(event) => setNewCustomerPhone(event.target.value)} />
            </div>
            <div className="flex flex-col gap-2">
              <Label>Service (Optional)</Label>
              <Select value={selectedServiceId || "none"} onValueChange={(value) => setSelectedServiceId(value === "none" ? "" : value)}>
                <SelectTrigger>
                  <SelectValue placeholder="None" />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectItem value="none">None</SelectItem>
                    {services.map((service) => (
                      <SelectItem key={service.id} value={String(service.id)}>
                        {service.name} - ${service.cost}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleAddWalkIn} disabled={!newCustomerName.trim()}>
              Add
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={removeDialogOpen} onOpenChange={setRemoveDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Remove Customer from Queue</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Why are you removing <strong>{selectedCustomer?.customer_name}</strong>?
          </p>
          <Textarea
            rows={3}
            value={removeReason}
            onChange={(event) => setRemoveReason(event.target.value)}
            placeholder="e.g., did not appear when called, left the premises"
          />
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setRemoveDialogOpen(false);
                setSelectedCustomer(null);
                setRemoveReason("");
              }}
            >
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleRemoveCustomer} disabled={!removeReason.trim()}>
              Remove
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={serveConfirmCustomer !== null} onOpenChange={(open) => !open && setServeConfirmCustomer(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Serve Customer Out of Order</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Serve <strong>{serveConfirmCustomer?.customer_name}</strong> now, skipping ahead in the queue?
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setServeConfirmCustomer(null)}>
              Cancel
            </Button>
            <Button onClick={confirmServeSpecific}>Serve Now</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default EmployeeQueuePage;
