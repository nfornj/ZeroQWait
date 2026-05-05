import React, { useState, useEffect } from 'react';
import { Plus, Clock, Pencil, Copy, Trash2, MoreHorizontal, Scissors, TrendingUp } from 'lucide-react';
import { toast } from 'sonner';
import api from '../../../services/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Skeleton } from '@/components/ui/skeleton';
import { useShop } from '../../../contexts/ShopContext';

interface ShopService {
  id: number;
  shop_id: number;
  name: string;
  description: string;
  duration_minutes: number;
  cost: number;
  currency: string;
  is_active: boolean;
}

const emptyForm = { id: undefined as number | undefined, name: '', description: '', duration_minutes: 30, cost: 0 };

// ─── Service Card ─────────────────────────────────────────────────────────────
function ServiceCard({
  service,
  onEdit,
  onDuplicate,
  onDelete,
}: {
  service: ShopService;
  onEdit: (s: ShopService) => void;
  onDuplicate: (s: ShopService) => void;
  onDelete: (id: number) => void;
}) {
  return (
    <div className="flex flex-col rounded-2xl border border-border bg-card p-5 shadow-none transition-shadow hover:shadow-sm">
      {/* Top row: icon + price + menu */}
      <div className="mb-4 flex items-start justify-between">
        <div
          className="flex h-12 w-12 items-center justify-center rounded-full"
          style={{ backgroundColor: 'color-mix(in srgb, var(--owner-primary) 12%, transparent)' }}
        >
          <Scissors className="h-5 w-5" style={{ color: 'var(--owner-primary)' }} />
        </div>
        <div className="flex items-center gap-2">
          <span className="text-base font-semibold" style={{ color: 'var(--owner-primary)' }}>
            ${Number(service.cost).toFixed(2)}
          </span>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                className="flex h-7 w-7 items-center justify-center rounded-lg text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
              >
                <MoreHorizontal className="h-4 w-4" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => onEdit(service)}>
                <Pencil className="mr-2 h-4 w-4" />
                Edit
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => onDuplicate(service)}>
                <Copy className="mr-2 h-4 w-4" />
                Duplicate
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onClick={() => onDelete(service.id)}
                className="text-destructive focus:text-destructive"
              >
                <Trash2 className="mr-2 h-4 w-4" />
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {/* Service name */}
      <h3 className="mb-1 text-base font-semibold leading-tight text-foreground">{service.name}</h3>

      {/* Duration */}
      <div className="mb-2 flex items-center gap-1.5 text-xs text-muted-foreground">
        <Clock className="h-3.5 w-3.5" />
        {service.duration_minutes} min
      </div>

      {/* Description */}
      <p className="mb-5 flex-1 text-sm text-muted-foreground leading-relaxed line-clamp-2">
        {service.description || 'No description provided.'}
      </p>

      {/* Action bar */}
      <div className="flex items-center gap-1 border-t border-border pt-3">
        <button
          type="button"
          onClick={() => onEdit(service)}
          className="flex flex-1 items-center justify-center gap-1.5 rounded-lg px-2 py-1.5 text-xs font-medium text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
        >
          <Pencil className="h-3.5 w-3.5" />
          Edit
        </button>
        <button
          type="button"
          onClick={() => onDuplicate(service)}
          className="flex flex-1 items-center justify-center gap-1.5 rounded-lg px-2 py-1.5 text-xs font-medium text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
        >
          <Copy className="h-3.5 w-3.5" />
          Duplicate
        </button>
        <button
          type="button"
          onClick={() => onDelete(service.id)}
          className="flex flex-1 items-center justify-center gap-1.5 rounded-lg px-2 py-1.5 text-xs font-medium text-destructive hover:bg-destructive/10 transition-colors"
        >
          <Trash2 className="h-3.5 w-3.5" />
          Delete
        </button>
      </div>
    </div>
  );
}

// ─── Add New Service Card ─────────────────────────────────────────────────────
function AddServiceCard({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed border-border bg-card p-8 text-center transition-colors hover:border-muted-foreground/40 hover:bg-accent"
    >
      <div className="flex h-10 w-10 items-center justify-center rounded-full border-2 border-border bg-background">
        <Plus className="h-5 w-5 text-muted-foreground" />
      </div>
      <div>
        <p className="text-sm font-semibold text-foreground">Add a new service</p>
        <p className="mt-1 text-xs text-muted-foreground">Expand your offerings and delight your clients.</p>
      </div>
      <span
        className="inline-flex items-center gap-1 text-xs font-medium"
        style={{ color: 'var(--owner-primary)' }}
      >
        <Plus className="h-3.5 w-3.5" />
        Add Service
      </span>
    </button>
  );
}

// ─── Skeleton Cards ───────────────────────────────────────────────────────────
function ServiceCardSkeleton() {
  return (
    <div className="flex flex-col rounded-2xl border border-border bg-card p-5">
      <div className="mb-4 flex items-start justify-between">
        <Skeleton className="h-12 w-12 rounded-full" />
        <Skeleton className="h-5 w-16" />
      </div>
      <Skeleton className="mb-2 h-5 w-3/4" />
      <Skeleton className="mb-2 h-4 w-1/3" />
      <Skeleton className="mb-5 h-10 w-full" />
      <Skeleton className="h-8 w-full" />
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────
const ServicesManagementPage: React.FC = () => {
  const { shop } = useShop();
  const [services, setServices] = useState<ShopService[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleteTargetId, setDeleteTargetId] = useState<number | null>(null);
  const [formData, setFormData] = useState(emptyForm);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (shop) fetchServices();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shop]);

  const fetchServices = async () => {
    if (!shop) return;
    setLoading(true);
    try {
      const res = await api.get(`/shops/${shop.id}/services`);
      setServices(res.data);
    } catch {
      toast.error('Failed to load services');
    } finally {
      setLoading(false);
    }
  };

  const openAdd = () => {
    setFormData(emptyForm);
    setDialogOpen(true);
  };

  const openEdit = (service: ShopService) => {
    setFormData({
      id: service.id,
      name: service.name,
      description: service.description || '',
      duration_minutes: service.duration_minutes,
      cost: service.cost,
    });
    setDialogOpen(true);
  };

  const handleDuplicate = async (service: ShopService) => {
    if (!shop) return;
    try {
      await api.post(`/shops/${shop.id}/services`, {
        name: `${service.name} (copy)`,
        description: service.description,
        duration_minutes: service.duration_minutes,
        cost: service.cost,
      });
      toast.success('Service duplicated');
      fetchServices();
    } catch {
      toast.error('Failed to duplicate service');
    }
  };

  const handleSubmit = async () => {
    if (!shop || !formData.name.trim()) return;
    setSubmitting(true);
    try {
      if (formData.id) {
        await api.put(`/shops/${shop.id}/services/${formData.id}`, formData);
        toast.success('Service updated');
      } else {
        await api.post(`/shops/${shop.id}/services`, formData);
        toast.success('Service created');
      }
      setDialogOpen(false);
      fetchServices();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to save service');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteClick = (id: number) => {
    setDeleteTargetId(id);
    setDeleteDialogOpen(true);
  };

  const confirmDelete = async () => {
    if (!shop || deleteTargetId === null) return;
    try {
      await api.delete(`/shops/${shop.id}/services/${deleteTargetId}`);
      toast.success('Service deleted');
      setDeleteDialogOpen(false);
      setDeleteTargetId(null);
      fetchServices();
    } catch {
      toast.error('Failed to delete service');
    }
  };

  const activeServices = services.filter((s) => s.is_active);
  const mostBooked = services[0]?.name ?? null;

  return (
    <div className="w-full max-w-[1700px]">

      {/* Page header — 3-column row matching mockup */}
      <div className="mb-8 flex items-center gap-6">

        {/* Left: title + subtitle */}
        <div className="flex-1 min-w-0">
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Service Catalog</h1>
          <p className="mt-1.5 text-sm text-muted-foreground leading-relaxed">
            Curate your menu with pricing, duration,<br className="hidden sm:block" />
            and descriptions for your clients.
          </p>
        </div>

        {/* Center: Add Service button */}
        <div className="flex flex-shrink-0 items-center justify-center">
          <Button
            size="lg"
            onClick={openAdd}
            className="rounded-xl px-6 font-semibold shadow-none"
            style={{ backgroundColor: 'var(--owner-primary)', color: '#fff' }}
          >
            <Plus className="mr-2 h-4 w-4" />
            Add Service
          </Button>
        </div>

        {/* Right: info card — icon left, text right (matches mockup) */}
        <div className="flex w-72 flex-shrink-0 items-center gap-4 rounded-2xl border border-border bg-card px-5 py-4">
          <div
            className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full"
            style={{ backgroundColor: 'color-mix(in srgb, var(--owner-primary) 10%, #f0f0f0)' }}
          >
            <TrendingUp className="h-4 w-4" style={{ color: 'var(--owner-primary)' }} />
          </div>
          <div className="min-w-0">
            {loading ? (
              <>
                <Skeleton className="h-4 w-36 mb-1.5" />
                <Skeleton className="h-3.5 w-28 mb-2" />
                <Skeleton className="h-3.5 w-20" />
              </>
            ) : (
              <>
                <p className="text-sm font-semibold text-foreground">
                  You have {activeServices.length} active service{activeServices.length !== 1 ? 's' : ''}
                </p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  Most booked: {mostBooked ?? '—'}
                </p>
                <button
                  type="button"
                  className="mt-1.5 text-xs font-medium hover:underline"
                  style={{ color: 'var(--owner-primary)' }}
                >
                  View insights →
                </button>
              </>
            )}
          </div>
        </div>

      </div>

      {/* Services section label */}
      <div className="mb-4 flex items-center gap-2">
        <Scissors className="h-4 w-4 text-muted-foreground" />
        <h2 className="text-sm font-semibold text-foreground">
          {loading ? 'Loading…' : `All Services (${services.length})`}
        </h2>
      </div>

      {/* Card grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {loading ? (
          <>
            <ServiceCardSkeleton />
            <ServiceCardSkeleton />
            <ServiceCardSkeleton />
          </>
        ) : (
          <>
            {services.map((service) => (
              <ServiceCard
                key={service.id}
                service={service}
                onEdit={openEdit}
                onDuplicate={handleDuplicate}
                onDelete={handleDeleteClick}
              />
            ))}
            <AddServiceCard onClick={openAdd} />
          </>
        )}
      </div>

      {/* ── Add / Edit Dialog ── */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{formData.id ? 'Edit Service' : 'Add New Service'}</DialogTitle>
            <DialogDescription>
              {formData.id
                ? 'Update the details for this service.'
                : 'Fill in the details to add a new service to your catalog.'}
            </DialogDescription>
          </DialogHeader>

          <div className="flex flex-col gap-4 py-2">
            <div className="grid gap-1.5">
              <Label htmlFor="svc-name">Service name *</Label>
              <Input
                id="svc-name"
                placeholder="e.g. Deep Tissue Massage"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="grid gap-1.5">
                <Label htmlFor="svc-cost">Price ($)</Label>
                <Input
                  id="svc-cost"
                  type="number"
                  min={0}
                  step={0.01}
                  placeholder="0.00"
                  value={formData.cost}
                  onChange={(e) => setFormData({ ...formData, cost: parseFloat(e.target.value) || 0 })}
                />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="svc-duration">Duration (min)</Label>
                <Input
                  id="svc-duration"
                  type="number"
                  min={1}
                  placeholder="30"
                  value={formData.duration_minutes}
                  onChange={(e) => setFormData({ ...formData, duration_minutes: parseInt(e.target.value) || 30 })}
                />
              </div>
            </div>

            <div className="grid gap-1.5">
              <Label htmlFor="svc-desc">Description</Label>
              <Textarea
                id="svc-desc"
                placeholder="Describe what this service includes…"
                rows={3}
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)} disabled={submitting}>
              Cancel
            </Button>
            <Button
              onClick={handleSubmit}
              disabled={submitting || !formData.name.trim() || formData.cost < 0}
              style={{ backgroundColor: 'var(--owner-primary)', color: '#fff' }}
            >
              {submitting ? 'Saving…' : formData.id ? 'Save changes' : 'Add service'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Delete Confirmation Dialog ── */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Delete service?</DialogTitle>
            <DialogDescription>
              This action cannot be undone. The service will be permanently removed from your catalog.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={confirmDelete}>
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default ServicesManagementPage;
