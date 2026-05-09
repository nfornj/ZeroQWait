import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CheckCircle, ListOrdered, Plus, Tv, Users } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import api from "../../../services/api";
import Header from "../components/Header";
import QueueDataGrid from "../components/QueueDataGrid";
import { useShop } from "../../../contexts/ShopContext";

const QueueManagementPage: React.FC = () => {
  const navigate = useNavigate();
  const { shop: contextShop } = useShop();

  const [queues, setQueues] = useState<any[]>([]);
  const [shop, setShop] = useState<any>(null);
  const [open, setOpen] = useState(false);
  const [newQueueName, setNewQueueName] = useState("");
  const [error, setError] = useState("");
  const [deleteConfirmId, setDeleteConfirmId] = useState<number | null>(null);
  const [resetConfirmId, setResetConfirmId] = useState<number | null>(null);

  useEffect(() => {
    fetchShopAndQueues();
  }, []);

  const fetchShopAndQueues = async () => {
    try {
      const shopRes = await api.get(`/shops/my-shops`);

      if (shopRes.data.length > 0) {
        const currentShop = shopRes.data[0];
        setShop(currentShop);

        const queueRes = await api.get(`/queues/shop/${currentShop.id}/all`);
        setQueues(queueRes.data);
      }
    } catch {
      // Keep UI usable even if initial fetch fails.
    }
  };

  const handleCreateQueue = async () => {
    try {
      setError("");
      await api.post(`/queues/shop/${shop.id}`, { name: newQueueName });
      setOpen(false);
      setNewQueueName("");
      fetchShopAndQueues();
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to create queue");
      setOpen(false);
    }
  };

  const handleDeleteQueue = async (id: number) => {
    try {
      await api.delete(`/queues/${id}`);
      setDeleteConfirmId(null);
      fetchShopAndQueues();
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to delete queue");
      setDeleteConfirmId(null);
    }
  };

  const handleResetQueue = async (id: number) => {
    try {
      await api.post(`/queues/${id}/reset`, {});
      setResetConfirmId(null);
      fetchShopAndQueues();
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to reset queue");
      setResetConfirmId(null);
    }
  };

  const activeQueues = queues.filter((q) => q.is_active).length;
  const brandPrimary = contextShop?.primary_color || shop?.primary_color || "hsl(var(--primary))";
  const brandSecondary = contextShop?.secondary_color || shop?.secondary_color || brandPrimary;
  const queueNameForId = (id: number | null) => queues.find((q) => q.id === id)?.name ?? "";

  const Stat = ({ icon: Icon, value, label }: { icon: React.ElementType; value: number; label: string }) => (
    <Card className="h-full">
      <CardContent className="flex flex-col gap-2 p-5">
        <Icon className="size-5 text-primary" />
        <p className="text-2xl font-semibold tracking-tight">{value}</p>
        <p className="text-sm text-muted-foreground">{label}</p>
      </CardContent>
    </Card>
  );

  return (
    <div className="w-full max-w-[1700px]">
      <Header />

      <div className="mb-4 grid grid-cols-1 gap-4 lg:grid-cols-12">
        <Card className="lg:col-span-8">
          <CardContent className="p-6">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div>
                <h1 className="text-2xl font-semibold tracking-tight">Queue Operations</h1>
                <p className="mt-1 text-sm text-muted-foreground">
                  Manage your queues, launch public display modes, and monitor queue status in real time.
                </p>
              </div>
              <Button onClick={() => setOpen(true)} className="self-start md:self-center">
                <Plus data-icon="inline-start" />
                Create Queue
              </Button>
            </div>
          </CardContent>
        </Card>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3 lg:col-span-4">
          <Stat icon={ListOrdered} value={queues.length} label="Total Queues" />
          <Stat icon={CheckCircle} value={activeQueues} label="Active Queues" />
          <Stat icon={Users} value={shop ? 1 : 0} label="Connected Shops" />
        </div>
      </div>

      {error && (
        <Alert variant="destructive" className="mb-4">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {shop && (
        <Card
          className="mb-4 overflow-hidden border"
          style={{
            borderColor: brandPrimary,
            background: `linear-gradient(135deg, color-mix(in srgb, ${brandPrimary} 18%, transparent) 0%, color-mix(in srgb, ${brandSecondary} 12%, transparent) 100%)`,
          }}
        >
          <CardContent className="flex flex-col gap-4 p-5">
            <div className="flex items-center gap-2">
              <Tv className="size-5" style={{ color: brandPrimary }} />
              <h2 className="font-semibold">AI Public Shop Display</h2>
            </div>
            <p className="text-sm text-muted-foreground">
              Launch your public queue display or open the AI-powered customer experience surface.
            </p>
            <Separator />
            <div className="flex flex-col gap-2 sm:flex-row">
              <Button type="button" variant="outline" size="sm" onClick={() => window.open(`/display/${shop.id}`, "_blank")}>
                <Tv data-icon="inline-start" />
                Standard Display
              </Button>
              <Button
                type="button"
                size="sm"
                onClick={() => window.open(`/shop-ai/${shop.id}`, "_blank")}
                style={{ background: `linear-gradient(135deg, ${brandPrimary}, ${brandSecondary})` }}
              >
                <Tv data-icon="inline-start" />
                Launch AI Agent
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardContent className="p-0">
          <QueueDataGrid
            rows={queues}
            onEdit={(queue) => {
              console.log("Edit queue", queue);
            }}
            onDelete={(id) => setDeleteConfirmId(id)}
            onReset={(id) => setResetConfirmId(id)}
            onRowClick={(queue) => navigate(`/queues/${queue.id}`)}
          />
        </CardContent>
      </Card>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create New Queue</DialogTitle>
          </DialogHeader>
          <Input
            autoFocus
            value={newQueueName}
            onChange={(event) => setNewQueueName(event.target.value)}
            placeholder="e.g., Barber 2, Walk-ins"
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreateQueue} disabled={!newQueueName.trim()}>
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={deleteConfirmId !== null} onOpenChange={(next) => !next && setDeleteConfirmId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Queue</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Permanently delete <strong>{queueNameForId(deleteConfirmId)}</strong> and all its history? This cannot be undone.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteConfirmId(null)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={() => deleteConfirmId !== null && handleDeleteQueue(deleteConfirmId)}>
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={resetConfirmId !== null} onOpenChange={(next) => !next && setResetConfirmId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reset Queue Data</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Remove all customers from <strong>{queueNameForId(resetConfirmId)}</strong>? The queue itself will remain, but all queue items will be deleted.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setResetConfirmId(null)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={() => resetConfirmId !== null && handleResetQueue(resetConfirmId)}>
              Reset
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default QueueManagementPage;
