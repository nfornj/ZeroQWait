import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowUpRight,
  Bot,
  CheckCircle,
  ExternalLink,
  ListOrdered,
  MonitorUp,
  Plus,
  SlidersHorizontal,
  Tv,
  Users,
} from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import api from "../../../services/api";
import Header from "../components/Header";
import QueueDataGrid from "../components/QueueDataGrid";
import { useShop } from "../../../contexts/ShopContext";

const dashboardSurfaceStyle = {
  "--background": "210 20% 98%",
  "--foreground": "222 47% 11%",
  "--card": "0 0% 100%",
  "--card-foreground": "222 47% 11%",
  "--popover": "0 0% 100%",
  "--popover-foreground": "222 47% 11%",
  "--muted": "210 40% 96%",
  "--muted-foreground": "215 16% 47%",
  "--border": "214 32% 91%",
  "--input": "214 32% 91%",
  "--primary": "154 40% 30%",
  "--primary-foreground": "0 0% 100%",
  "--ring": "154 40% 30%",
} as React.CSSProperties;

const queueSections = [
  { label: "Queues", sub: "Active lines", icon: ListOrdered },
  { label: "Displays", sub: "Public screens", icon: MonitorUp },
  { label: "Staffing", sub: "Coverage context", icon: Users },
  { label: "Controls", sub: "Reset and edit", icon: SlidersHorizontal },
];

function MetricCard({ icon: Icon, value, label }: { icon: React.ElementType; value: number; label: string }) {
  return (
    <div className="rounded-2xl border border-border bg-card p-5 shadow-none">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-2xl font-bold tracking-tight text-foreground">{value}</p>
          <p className="mt-1 text-sm text-muted-foreground">{label}</p>
        </div>
        <span className="flex h-9 w-9 items-center justify-center rounded-full border border-border bg-background text-primary">
          <Icon className="h-4 w-4" />
        </span>
      </div>
    </div>
  );
}

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

  return (
    <div className="flex min-h-full w-full flex-col bg-[#f9fafb] px-3 pb-16 md:px-6" style={dashboardSurfaceStyle}>
      <Header />

      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Queue operations</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Manage walk-ins, public displays, and queue controls from one focused workspace.
          </p>
        </div>
        <Button
          onClick={() => setOpen(true)}
          className="w-full rounded-xl bg-primary text-primary-foreground shadow-none hover:bg-primary/90 sm:w-auto"
        >
          <Plus data-icon="inline-start" />
          Create queue
        </Button>
      </div>

      <nav className="mb-6 rounded-2xl border border-border bg-card p-1.5">
        <div className="grid grid-cols-1 gap-1 sm:grid-cols-2 xl:grid-cols-4">
          {queueSections.map((item, index) => {
            const Icon = item.icon;
            return (
              <button
                key={item.label}
                type="button"
                className="relative flex items-center gap-3 rounded-xl px-4 py-3.5 text-left transition-all hover:bg-muted/45"
              >
                <span className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full border border-border bg-background text-muted-foreground">
                  <Icon className="h-4 w-4" />
                </span>
                <span className="min-w-0">
                  <span className="block truncate text-sm font-semibold text-foreground">{item.label}</span>
                  <span className="block truncate text-xs text-muted-foreground">{item.sub}</span>
                </span>
                {index === 0 && <span className="absolute bottom-0 left-4 right-4 h-0.5 rounded-full bg-primary" />}
              </button>
            );
          })}
        </div>
      </nav>

      {error && (
        <Alert variant="destructive" className="mb-4 rounded-2xl">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-12">
        <div className="rounded-2xl border border-border bg-card p-6 shadow-none lg:col-span-8">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-border bg-background px-3 py-1 text-xs font-semibold text-muted-foreground">
                <Bot className="h-3.5 w-3.5 text-primary" />
                Queue workspace
              </div>
              <h2 className="mt-4 text-2xl font-bold tracking-tight text-foreground">Live queue control</h2>
              <p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">
                Keep every queue visible, route customers into the right line, and open display modes for the front desk.
              </p>
            </div>
            <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
              <ArrowUpRight className="h-5 w-5" />
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3 lg:col-span-4 lg:grid-cols-1">
          <MetricCard icon={ListOrdered} value={queues.length} label="Total queues" />
          <MetricCard icon={CheckCircle} value={activeQueues} label="Active queues" />
          <MetricCard icon={Users} value={shop ? 1 : 0} label="Connected shops" />
        </div>
      </div>

      {shop && (
        <div
          className="mb-6 rounded-2xl border border-border bg-card p-5 shadow-none"
          style={{
            borderLeftColor: brandPrimary,
            borderLeftWidth: 3,
            background: `linear-gradient(135deg, color-mix(in srgb, ${brandPrimary} 8%, white) 0%, color-mix(in srgb, ${brandSecondary} 5%, white) 100%)`,
          }}
        >
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex items-start gap-3">
              <span className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-card text-primary shadow-sm">
                <Tv className="h-5 w-5" />
              </span>
              <div>
                <h2 className="text-base font-semibold tracking-tight text-foreground">Public display surfaces</h2>
                <p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">
                  Launch the standard lobby display or the AI-powered customer experience in a new tab.
                </p>
              </div>
            </div>
            <div className="flex flex-col gap-2 sm:flex-row">
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="rounded-xl border-border bg-card shadow-none"
                onClick={() => window.open(`/display/${shop.id}`, "_blank")}
              >
                <MonitorUp data-icon="inline-start" />
                Standard display
                <ExternalLink data-icon="inline-end" />
              </Button>
              <Button
                type="button"
                size="sm"
                className="rounded-xl text-white shadow-none hover:opacity-90"
                onClick={() => window.open(`/shop-ai/${shop.id}`, "_blank")}
                style={{ background: `linear-gradient(135deg, ${brandPrimary}, ${brandSecondary})` }}
              >
                <Bot data-icon="inline-start" />
                Launch AI agent
                <ExternalLink data-icon="inline-end" />
              </Button>
            </div>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <Badge variant="outline" className="rounded-full border-border bg-card text-muted-foreground">
              Display ready
            </Badge>
            <Badge variant="outline" className="rounded-full border-border bg-card text-muted-foreground">
              Uses live queue data
            </Badge>
          </div>
        </div>
      )}

      <QueueDataGrid
        rows={queues}
        onEdit={(queue) => {
          console.log("Edit queue", queue);
        }}
        onDelete={(id) => setDeleteConfirmId(id)}
        onReset={(id) => setResetConfirmId(id)}
        onRowClick={(queue) => navigate(`/queues/${queue.id}`)}
      />

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="rounded-2xl">
          <DialogHeader>
            <DialogTitle>Create New Queue</DialogTitle>
          </DialogHeader>
          <Input
            autoFocus
            value={newQueueName}
            onChange={(event) => setNewQueueName(event.target.value)}
            placeholder="e.g., Barber 2, Walk-ins"
            className="rounded-xl border-border bg-background"
          />
          <DialogFooter>
            <Button variant="outline" className="rounded-xl" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button className="rounded-xl" onClick={handleCreateQueue} disabled={!newQueueName.trim()}>
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={deleteConfirmId !== null} onOpenChange={(next) => !next && setDeleteConfirmId(null)}>
        <DialogContent className="rounded-2xl">
          <DialogHeader>
            <DialogTitle>Delete Queue</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Permanently delete <strong>{queueNameForId(deleteConfirmId)}</strong> and all its history? This cannot be undone.
          </p>
          <DialogFooter>
            <Button variant="outline" className="rounded-xl" onClick={() => setDeleteConfirmId(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              className="rounded-xl"
              onClick={() => deleteConfirmId !== null && handleDeleteQueue(deleteConfirmId)}
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={resetConfirmId !== null} onOpenChange={(next) => !next && setResetConfirmId(null)}>
        <DialogContent className="rounded-2xl">
          <DialogHeader>
            <DialogTitle>Reset Queue Data</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Remove all customers from <strong>{queueNameForId(resetConfirmId)}</strong>? The queue itself will remain, but all queue items will be deleted.
          </p>
          <DialogFooter>
            <Button variant="outline" className="rounded-xl" onClick={() => setResetConfirmId(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              className="rounded-xl"
              onClick={() => resetConfirmId !== null && handleResetQueue(resetConfirmId)}
            >
              Reset
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default QueueManagementPage;
