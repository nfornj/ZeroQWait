import React, { useState, useEffect, useCallback } from 'react';
import {
  AlertTriangle,
  Clock,
  History,
  Package,
  PackageMinus,
  PackagePlus,
  Plus,
  RefreshCcw,
  Search,
} from 'lucide-react';

import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';

import { useShop } from '../../../contexts/ShopContext';
import {
  getInventoryItems,
  getLowStockAlerts,
  addInventoryItem,
  restockItem,
  recordUsage,
  getItemMovementHistory,
  InventoryItem,
  InventoryMovement,
  AddItemPayload,
} from '../../../services/api';
import Header from '../components/Header';

// ── Constants ─────────────────────────────────────────────────────────────────

const CATEGORIES = [
  'color', 'styling', 'beard', 'shave', 'cleansing',
  'equipment', 'consumable', 'sanitation', 'retail', 'other',
];
const UNITS = ['piece', 'bottle', 'tube', 'pack', 'box', 'ml', 'oz', 'g', 'kg', 'litre'];

const CATEGORY_COLORS: Record<string, string> = {
  color:         'bg-purple-100 text-purple-700 border-purple-200',
  styling:       'bg-blue-100 text-blue-700 border-blue-200',
  beard:         'bg-cyan-100 text-cyan-700 border-cyan-200',
  shave:         'bg-slate-100 text-slate-700 border-slate-200',
  cleansing:     'bg-green-100 text-green-700 border-green-200',
  equipment:     'bg-amber-100 text-amber-700 border-amber-200',
  consumable:    'bg-orange-100 text-orange-700 border-orange-200',
  sanitation:    'bg-red-100 text-red-700 border-red-200',
  retail:        'bg-indigo-100 text-indigo-700 border-indigo-200',
  other:         'bg-gray-100 text-gray-600 border-gray-200',
  uncategorized: 'bg-gray-100 text-gray-500 border-gray-200',
};

// ── Helpers ────────────────────────────────────────────────────────────────────

type StockStatus = 'ok' | 'low' | 'out';

function stockStatus(item: InventoryItem): StockStatus {
  if (item.current_stock <= 0) return 'out';
  if (item.current_stock <= item.reorder_threshold) return 'low';
  return 'ok';
}

function StockBadge({ item }: { item: InventoryItem }) {
  const status = stockStatus(item);
  const cls =
    status === 'out'
      ? 'bg-red-100 text-red-700 border-red-200'
      : status === 'low'
      ? 'bg-amber-100 text-amber-700 border-amber-200'
      : 'bg-emerald-100 text-emerald-700 border-emerald-200';
  return (
    <Badge
      variant="outline"
      className={cn('rounded-full border font-semibold', cls)}
    >
      {item.current_stock} {item.unit}
    </Badge>
  );
}

// ── Movement History Modal ─────────────────────────────────────────────────────

interface HistoryModalProps {
  open: boolean;
  item: InventoryItem | null;
  shopId: number;
  onClose: () => void;
}

function HistoryModal({ open, item, shopId, onClose }: HistoryModalProps) {
  const [movements, setMovements] = useState<InventoryMovement[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open || !item) return;
    setLoading(true);
    getItemMovementHistory(shopId, item.id)
      .then((r) => setMovements(r.data.movements))
      .catch(() => setMovements([]))
      .finally(() => setLoading(false));
  }, [open, item, shopId]);

  const movementLabel: Record<string, string> = {
    restock: 'Restock',
    usage: 'Usage',
    adjust: 'Adjustment',
    initial: 'Initial',
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <History className="h-4 w-4" />
            History — {item?.name}
          </DialogTitle>
        </DialogHeader>

        {loading ? (
          <div className="space-y-2 py-4">
            {[1, 2, 3].map((n) => <Skeleton key={n} className="h-8 w-full" />)}
          </div>
        ) : movements.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            No movements recorded yet.
          </p>
        ) : (
          <div className="max-h-72 overflow-y-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead className="text-right">Qty</TableHead>
                  <TableHead>Notes</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {movements.map((m) => (
                  <TableRow key={m.id}>
                    <TableCell className="whitespace-nowrap text-xs text-muted-foreground">
                      {new Date(m.created_at).toLocaleString(undefined, {
                        month: 'short', day: 'numeric',
                        hour: '2-digit', minute: '2-digit',
                      })}
                    </TableCell>
                    <TableCell className="text-sm">
                      {movementLabel[m.movement_type] ?? m.movement_type}
                    </TableCell>
                    <TableCell
                      className={cn(
                        'text-right text-sm font-bold',
                        m.quantity >= 0 ? 'text-emerald-600' : 'text-red-600',
                      )}
                    >
                      {m.quantity >= 0 ? '+' : ''}{m.quantity}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {m.notes ?? '—'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Close</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ── Restock / Usage Modal ──────────────────────────────────────────────────────

interface StockActionModalProps {
  open: boolean;
  mode: 'restock' | 'usage';
  item: InventoryItem | null;
  shopId: number;
  onClose: () => void;
  onDone: () => void;
}

function StockActionModal({ open, mode, item, shopId, onClose, onDone }: StockActionModalProps) {
  const [qty, setQty] = useState('');
  const [notes, setNotes] = useState('');
  const [unitCost, setUnitCost] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (open) { setQty(''); setNotes(''); setUnitCost(''); setError(''); }
  }, [open]);

  const handleSubmit = async () => {
    const qtyNum = parseFloat(qty);
    if (!qtyNum || qtyNum <= 0) { setError('Quantity must be a positive number'); return; }
    setSaving(true);
    try {
      if (mode === 'restock') {
        const uc = unitCost ? parseFloat(unitCost) : undefined;
        await restockItem(shopId, item!.id, qtyNum, notes || undefined, uc);
      } else {
        await recordUsage(shopId, item!.id, qtyNum, notes || undefined);
      }
      onDone();
      onClose();
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Operation failed');
    } finally {
      setSaving(false);
    }
  };

  const isRestock = mode === 'restock';

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {isRestock
              ? <PackagePlus className="h-4 w-4 text-emerald-600" />
              : <PackageMinus className="h-4 w-4 text-amber-600" />}
            {isRestock ? 'Restock' : 'Record usage'} — {item?.name}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <div className="space-y-1.5">
            <Label htmlFor="qty">
              Quantity <span className="text-muted-foreground">({item?.unit})</span>
            </Label>
            <Input
              id="qty"
              type="number"
              min={0.01}
              step={0.01}
              placeholder="0"
              value={qty}
              onChange={(e) => setQty(e.target.value)}
            />
          </div>

          {isRestock && (
            <div className="space-y-1.5">
              <Label htmlFor="unitCost">Unit cost (optional)</Label>
              <div className="relative">
                <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sm text-muted-foreground">$</span>
                <Input
                  id="unitCost"
                  type="number"
                  min={0}
                  step={0.01}
                  placeholder="0.00"
                  value={unitCost}
                  onChange={(e) => setUnitCost(e.target.value)}
                  className="pl-7"
                />
              </div>
            </div>
          )}

          <div className="space-y-1.5">
            <Label htmlFor="notes">Notes (optional)</Label>
            <Textarea
              id="notes"
              rows={2}
              placeholder="e.g. Ordered from supplier..."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={saving}>Cancel</Button>
          <Button onClick={handleSubmit} disabled={saving}>
            {saving ? 'Saving...' : isRestock ? 'Restock' : 'Record'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ── Add Item Modal ─────────────────────────────────────────────────────────────

interface AddItemModalProps {
  open: boolean;
  shopId: number;
  onClose: () => void;
  onDone: () => void;
}

function AddItemModal({ open, shopId, onClose, onDone }: AddItemModalProps) {
  const emptyForm: AddItemPayload = {
    name: '', unit: 'piece', category: '', sku: '',
    initial_stock: 0, reorder_threshold: 0, cost_per_unit: undefined, supplier: '',
  };
  const [form, setForm] = useState<AddItemPayload>(emptyForm);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (open) { setForm(emptyForm); setError(''); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const set = <K extends keyof AddItemPayload>(field: K, value: AddItemPayload[K]) =>
    setForm((f) => ({ ...f, [field]: value }));

  const handleSubmit = async () => {
    if (!form.name.trim()) { setError('Name is required'); return; }
    setSaving(true);
    try {
      await addInventoryItem(shopId, {
        ...form,
        category: form.category || undefined,
        sku: form.sku || undefined,
        supplier: form.supplier || undefined,
      });
      onDone();
      onClose();
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Failed to add item');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Package className="h-4 w-4" />
            Add inventory item
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <div className="space-y-1.5">
            <Label htmlFor="itemName">Item name *</Label>
            <Input
              id="itemName"
              placeholder="e.g. Pomade"
              value={form.name}
              onChange={(e) => set('name', e.target.value)}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label>Unit</Label>
              <Select value={form.unit} onValueChange={(v) => set('unit', v)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {UNITS.map((u) => <SelectItem key={u} value={u}>{u}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Category</Label>
              <Select value={form.category ?? 'none'} onValueChange={(v) => set('category', v === 'none' ? undefined : v)}>
                <SelectTrigger>
                  <SelectValue placeholder="— none —" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">— none —</SelectItem>
                  {CATEGORIES.map((c) => (
                    <SelectItem key={c} value={c} className="capitalize">{c}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="sku">SKU (optional)</Label>
              <Input
                id="sku"
                placeholder="SKU-001"
                value={form.sku ?? ''}
                onChange={(e) => set('sku', e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="supplier">Supplier (optional)</Label>
              <Input
                id="supplier"
                placeholder="Supplier name"
                value={form.supplier ?? ''}
                onChange={(e) => set('supplier', e.target.value)}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="initialStock">Initial stock</Label>
              <Input
                id="initialStock"
                type="number"
                min={0}
                step={0.01}
                value={form.initial_stock ?? 0}
                onChange={(e) => set('initial_stock', parseFloat(e.target.value) || 0)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="reorderThreshold">Reorder threshold</Label>
              <Input
                id="reorderThreshold"
                type="number"
                min={0}
                step={0.01}
                value={form.reorder_threshold ?? 0}
                onChange={(e) => set('reorder_threshold', parseFloat(e.target.value) || 0)}
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="costPerUnit">Cost per unit (optional)</Label>
            <div className="relative">
              <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sm text-muted-foreground">$</span>
              <Input
                id="costPerUnit"
                type="number"
                min={0}
                step={0.01}
                placeholder="0.00"
                value={form.cost_per_unit ?? ''}
                onChange={(e) =>
                  set('cost_per_unit', e.target.value ? parseFloat(e.target.value) : undefined)
                }
                className="pl-7"
              />
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={saving}>Cancel</Button>
          <Button onClick={handleSubmit} disabled={saving}>
            {saving ? 'Adding...' : 'Add item'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ── Loading skeleton ───────────────────────────────────────────────────────────

function InventorySkeleton() {
  return (
    <div className="space-y-3 px-4">
      {[1, 2, 3, 4, 5].map((n) => (
        <Skeleton key={n} className="h-10 w-full rounded-xl" />
      ))}
    </div>
  );
}

// ── CSS variables ──────────────────────────────────────────────────────────────

const surfaceStyle = {
  '--background': '210 20% 98%',
  '--foreground': '222 47% 11%',
  '--card': '0 0% 100%',
  '--card-foreground': '222 47% 11%',
  '--border': '214 32% 91%',
  '--muted': '210 40% 96%',
  '--muted-foreground': '215 16% 47%',
  '--primary': '154 40% 30%',
  '--primary-foreground': '0 0% 100%',
} as React.CSSProperties;

// ── Main page ──────────────────────────────────────────────────────────────────

export default function InventoryPage() {
  const { shop } = useShop();
  const shopId = shop?.id;

  const [items, setItems] = useState<InventoryItem[]>([]);
  const [alertCount, setAlertCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [addOpen, setAddOpen] = useState(false);
  const [actionItem, setActionItem] = useState<InventoryItem | null>(null);
  const [actionMode, setActionMode] = useState<'restock' | 'usage'>('restock');
  const [historyItem, setHistoryItem] = useState<InventoryItem | null>(null);

  const load = useCallback(async () => {
    if (!shopId) return;
    setLoading(true);
    setError('');
    try {
      const [itemsRes, alertsRes] = await Promise.all([
        getInventoryItems(shopId),
        getLowStockAlerts(shopId),
      ]);
      setItems(itemsRes.data.items);
      setAlertCount(alertsRes.data.count);
    } catch {
      setError('Failed to load inventory. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [shopId]);

  useEffect(() => { load(); }, [load]);

  const openAction = (item: InventoryItem, mode: 'restock' | 'usage') => {
    setActionItem(item);
    setActionMode(mode);
  };

  const filteredItems = search
    ? items.filter(
        (i) =>
          i.name.toLowerCase().includes(search.toLowerCase()) ||
          (i.category ?? '').toLowerCase().includes(search.toLowerCase()) ||
          (i.supplier ?? '').toLowerCase().includes(search.toLowerCase()) ||
          (i.sku ?? '').toLowerCase().includes(search.toLowerCase()),
      )
    : items;

  const grouped = filteredItems.reduce<Record<string, InventoryItem[]>>((acc, item) => {
    const cat = item.category ?? 'uncategorized';
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(item);
    return acc;
  }, {});

  const totalValue = items.reduce(
    (sum, i) => sum + i.current_stock * (i.cost_per_unit ?? 0),
    0,
  );

  if (!shopId) {
    return (
      <div className="p-6">
        <Alert>
          <AlertDescription>No shop selected. Please select a shop first.</AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="w-full" style={surfaceStyle}>
      <Header />

      {/* Page header */}
      <div className="flex items-center justify-between px-4 pb-4 pt-2">
        <div className="flex items-center gap-2">
          <Package className="h-5 w-5 text-primary" />
          <h1 className="text-xl font-bold tracking-tight text-foreground">Inventory</h1>
          {alertCount > 0 && (
            <Badge
              variant="outline"
              className="rounded-full border-amber-200 bg-amber-100 font-semibold text-amber-700"
            >
              <AlertTriangle className="mr-1 h-3 w-3" />
              {alertCount} low-stock
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            className="gap-1.5"
            onClick={load}
            disabled={loading}
          >
            <RefreshCcw className={cn('h-3.5 w-3.5', loading && 'animate-spin')} />
            Refresh
          </Button>
          <Button size="sm" className="gap-1.5" onClick={() => setAddOpen(true)}>
            <Plus className="h-3.5 w-3.5" />
            Add item
          </Button>
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-3 px-4 pb-4">
        <Card className="rounded-2xl border-border bg-card shadow-none">
          <CardContent className="p-4">
            <p className="text-2xl font-bold tracking-tight text-foreground">{items.length}</p>
            <p className="mt-0.5 text-xs text-muted-foreground">Total items</p>
          </CardContent>
        </Card>
        <Card
          className={cn(
            'rounded-2xl border-border bg-card shadow-none',
            alertCount > 0 && 'border-amber-200 bg-amber-50',
          )}
        >
          <CardContent className="p-4">
            <p className={cn(
              'text-2xl font-bold tracking-tight',
              alertCount > 0 ? 'text-amber-700' : 'text-foreground',
            )}>
              {alertCount}
            </p>
            <p className="mt-0.5 text-xs text-muted-foreground">Low / out of stock</p>
          </CardContent>
        </Card>
        <Card className="rounded-2xl border-border bg-card shadow-none">
          <CardContent className="p-4">
            <p className="text-2xl font-bold tracking-tight text-foreground">
              ${totalValue.toFixed(2)}
            </p>
            <p className="mt-0.5 text-xs text-muted-foreground">Estimated stock value</p>
          </CardContent>
        </Card>
      </div>

      {error && (
        <div className="px-4 pb-3">
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        </div>
      )}

      {/* Search */}
      <div className="px-4 pb-4">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search by name, category, supplier, or SKU..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
      </div>

      {/* Items by category */}
      {loading && items.length === 0 ? (
        <InventorySkeleton />
      ) : Object.entries(grouped).length === 0 ? (
        <div className="px-4 py-12 text-center">
          <Package className="mx-auto mb-3 h-10 w-10 text-muted-foreground/40" />
          <p className="text-sm text-muted-foreground">
            {search
              ? 'No items match your search.'
              : 'No inventory items yet. Add your first item.'}
          </p>
        </div>
      ) : (
        <div className="space-y-6 px-4 pb-8">
          {Object.entries(grouped)
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([category, catItems]) => (
              <div key={category}>
                <div className="mb-2 flex items-center gap-2">
                  <span
                    className={cn(
                      'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold capitalize',
                      CATEGORY_COLORS[category] ?? CATEGORY_COLORS.other,
                    )}
                  >
                    {category}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {catItems.length} item{catItems.length !== 1 ? 's' : ''}
                  </span>
                </div>

                <div className="overflow-hidden rounded-2xl border border-border bg-card">
                  <Table>
                    <TableHeader>
                      <TableRow className="bg-muted/40">
                        <TableHead className="font-semibold">Name</TableHead>
                        <TableHead className="font-semibold">SKU</TableHead>
                        <TableHead className="font-semibold">Supplier</TableHead>
                        <TableHead className="text-center font-semibold">Stock</TableHead>
                        <TableHead className="text-center font-semibold">Reorder at</TableHead>
                        <TableHead className="text-right font-semibold">Cost/unit</TableHead>
                        <TableHead className="text-center font-semibold">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {catItems.map((item) => {
                        const status = stockStatus(item);
                        return (
                          <TableRow
                            key={item.id}
                            className={cn(
                              status === 'out' && 'bg-red-50/60',
                              status === 'low' && 'bg-amber-50/60',
                            )}
                          >
                            <TableCell>
                              <div className="flex items-center gap-2">
                                {status !== 'ok' && (
                                  <AlertTriangle
                                    className={cn(
                                      'h-3.5 w-3.5 flex-shrink-0',
                                      status === 'out' ? 'text-red-500' : 'text-amber-500',
                                    )}
                                  />
                                )}
                                <span className="text-sm font-semibold text-foreground">
                                  {item.name}
                                </span>
                              </div>
                            </TableCell>
                            <TableCell>
                              <span className="text-xs text-muted-foreground">
                                {item.sku ?? '—'}
                              </span>
                            </TableCell>
                            <TableCell>
                              <span className="text-xs text-muted-foreground">
                                {item.supplier ?? '—'}
                              </span>
                            </TableCell>
                            <TableCell className="text-center">
                              <StockBadge item={item} />
                            </TableCell>
                            <TableCell className="text-center text-sm">
                              {item.reorder_threshold} {item.unit}
                            </TableCell>
                            <TableCell className="text-right text-sm">
                              {item.cost_per_unit != null
                                ? '$' + item.cost_per_unit.toFixed(2)
                                : '—'}
                            </TableCell>
                            <TableCell>
                              <div className="flex items-center justify-center gap-1">
                                <Button
                                  size="icon"
                                  variant="ghost"
                                  className="h-7 w-7 text-emerald-600 hover:bg-emerald-50 hover:text-emerald-700"
                                  title="Restock"
                                  onClick={() => openAction(item, 'restock')}
                                >
                                  <PackagePlus className="h-4 w-4" />
                                </Button>
                                <Button
                                  size="icon"
                                  variant="ghost"
                                  className="h-7 w-7 text-amber-600 hover:bg-amber-50 hover:text-amber-700"
                                  title="Record usage"
                                  onClick={() => openAction(item, 'usage')}
                                >
                                  <PackageMinus className="h-4 w-4" />
                                </Button>
                                <Button
                                  size="icon"
                                  variant="ghost"
                                  className="h-7 w-7 text-muted-foreground hover:text-foreground"
                                  title="Movement history"
                                  onClick={() => setHistoryItem(item)}
                                >
                                  <Clock className="h-4 w-4" />
                                </Button>
                              </div>
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </div>
              </div>
            ))}
        </div>
      )}

      {/* Modals */}
      <AddItemModal
        open={addOpen}
        shopId={shopId}
        onClose={() => setAddOpen(false)}
        onDone={load}
      />
      <StockActionModal
        open={Boolean(actionItem)}
        mode={actionMode}
        item={actionItem}
        shopId={shopId}
        onClose={() => setActionItem(null)}
        onDone={load}
      />
      <HistoryModal
        open={Boolean(historyItem)}
        item={historyItem}
        shopId={shopId}
        onClose={() => setHistoryItem(null)}
      />
    </div>
  );
}
