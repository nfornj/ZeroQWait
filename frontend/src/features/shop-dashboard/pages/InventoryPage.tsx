import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Typography,
  Button,
  Card,
  CardContent,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  MenuItem,
  Alert,
  CircularProgress,
  IconButton,
  Tooltip,
  Stack,
  Divider,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Badge,
  InputAdornment,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import RefreshIcon from '@mui/icons-material/Refresh';
import WarningAmberRoundedIcon from '@mui/icons-material/WarningAmberRounded';
import InventoryRoundedIcon from '@mui/icons-material/InventoryRounded';
import AddShoppingCartRoundedIcon from '@mui/icons-material/AddShoppingCartRounded';
import RemoveShoppingCartRoundedIcon from '@mui/icons-material/RemoveShoppingCartRounded';
import HistoryRoundedIcon from '@mui/icons-material/HistoryRounded';
import SearchRoundedIcon from '@mui/icons-material/SearchRounded';
import Header from '../components/Header';
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

// ── Category colour map ───────────────────────────────────────────────────────

const CATEGORY_COLORS: Record<string, 'default' | 'primary' | 'secondary' | 'error' | 'info' | 'success' | 'warning'> = {
  color: 'secondary',
  styling: 'primary',
  beard: 'info',
  shave: 'default',
  cleansing: 'success',
  equipment: 'warning',
  consumable: 'default',
  sanitation: 'error',
  retail: 'primary',
};

// ── Stock status helpers ──────────────────────────────────────────────────────

function stockStatus(item: InventoryItem): 'ok' | 'low' | 'out' {
  if (item.current_stock <= 0) return 'out';
  if (item.current_stock <= item.reorder_threshold) return 'low';
  return 'ok';
}

function StockBadge({ item }: { item: InventoryItem }) {
  const status = stockStatus(item);
  const color =
    status === 'out' ? 'error' : status === 'low' ? 'warning' : 'success';
  const label =
    status === 'out' ? 'Out of stock' : status === 'low' ? 'Low stock' : 'In stock';
  return (
    <Chip
      size="small"
      color={color}
      label={`${item.current_stock} ${item.unit}`}
      title={label}
      sx={{ fontWeight: 600, minWidth: 64 }}
    />
  );
}

// ── Movement history modal ────────────────────────────────────────────────────

function HistoryModal({
  open,
  item,
  shopId,
  onClose,
}: {
  open: boolean;
  item: InventoryItem | null;
  shopId: number;
  onClose: () => void;
}) {
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

  const movementLabel = (type: string) => {
    const map: Record<string, string> = {
      restock: 'Restock',
      usage: 'Usage',
      adjust: 'Adjustment',
      initial: 'Initial stock',
    };
    return map[type] ?? type;
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        Movement history — {item?.name}
      </DialogTitle>
      <DialogContent>
        {loading ? (
          <Box display="flex" justifyContent="center" py={3}>
            <CircularProgress size={32} />
          </Box>
        ) : movements.length === 0 ? (
          <Typography color="text.secondary">No movements recorded yet.</Typography>
        ) : (
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Date</TableCell>
                  <TableCell>Type</TableCell>
                  <TableCell align="right">Qty</TableCell>
                  <TableCell>Notes</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {movements.map((m) => (
                  <TableRow key={m.id}>
                    <TableCell sx={{ whiteSpace: 'nowrap' }}>
                      {new Date(m.created_at).toLocaleString(undefined, {
                        month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
                      })}
                    </TableCell>
                    <TableCell>{movementLabel(m.movement_type)}</TableCell>
                    <TableCell
                      align="right"
                      sx={{
                        fontWeight: 700,
                        color: m.quantity >= 0 ? 'success.main' : 'error.main',
                      }}
                    >
                      {m.quantity >= 0 ? '+' : ''}{m.quantity}
                    </TableCell>
                    <TableCell sx={{ color: 'text.secondary', fontSize: '0.78rem' }}>
                      {m.notes ?? '—'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
}

// ── Restock / Usage modal ─────────────────────────────────────────────────────

function StockActionModal({
  open,
  mode,
  item,
  shopId,
  onClose,
  onDone,
}: {
  open: boolean;
  mode: 'restock' | 'usage';
  item: InventoryItem | null;
  shopId: number;
  onClose: () => void;
  onDone: () => void;
}) {
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

  const title = mode === 'restock' ? `Restock — ${item?.name}` : `Record usage — ${item?.name}`;

  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>{title}</DialogTitle>
      <DialogContent>
        <Stack spacing={2} mt={1}>
          {error && <Alert severity="error">{error}</Alert>}
          <TextField
            label="Quantity"
            type="number"
            value={qty}
            onChange={(e) => setQty(e.target.value)}
            inputProps={{ min: 0.01, step: 0.01 }}
            InputProps={{ endAdornment: <InputAdornment position="end">{item?.unit}</InputAdornment> }}
            required
            fullWidth
          />
          {mode === 'restock' && (
            <TextField
              label="Unit cost (optional)"
              type="number"
              value={unitCost}
              onChange={(e) => setUnitCost(e.target.value)}
              inputProps={{ min: 0, step: 0.01 }}
              InputProps={{ startAdornment: <InputAdornment position="start">$</InputAdornment> }}
              fullWidth
            />
          )}
          <TextField
            label="Notes (optional)"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            multiline
            rows={2}
            fullWidth
          />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={saving}>Cancel</Button>
        <Button
          variant="contained"
          onClick={handleSubmit}
          disabled={saving}
          startIcon={saving ? <CircularProgress size={16} /> : undefined}
        >
          {mode === 'restock' ? 'Restock' : 'Record'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

// ── Add item modal ────────────────────────────────────────────────────────────

const CATEGORIES = ['color', 'styling', 'beard', 'shave', 'cleansing', 'equipment', 'consumable', 'sanitation', 'retail', 'other'];
const UNITS = ['piece', 'bottle', 'tube', 'pack', 'box', 'ml', 'oz', 'g', 'kg', 'litre'];

function AddItemModal({
  open,
  shopId,
  onClose,
  onDone,
}: {
  open: boolean;
  shopId: number;
  onClose: () => void;
  onDone: () => void;
}) {
  const [form, setForm] = useState<AddItemPayload>({
    name: '', unit: 'piece', category: '', sku: '', initial_stock: 0,
    reorder_threshold: 0, cost_per_unit: undefined, supplier: '',
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (open) {
      setForm({ name: '', unit: 'piece', category: '', sku: '', initial_stock: 0, reorder_threshold: 0, cost_per_unit: undefined, supplier: '' });
      setError('');
    }
  }, [open]);

  const set = (field: keyof AddItemPayload, value: any) =>
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
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Add inventory item</DialogTitle>
      <DialogContent>
        <Stack spacing={2} mt={1}>
          {error && <Alert severity="error">{error}</Alert>}
          <TextField
            label="Item name"
            value={form.name}
            onChange={(e) => set('name', e.target.value)}
            required fullWidth
          />
          <Stack direction="row" spacing={2}>
            <TextField
              select label="Unit" value={form.unit}
              onChange={(e) => set('unit', e.target.value)}
              fullWidth
            >
              {UNITS.map((u) => <MenuItem key={u} value={u}>{u}</MenuItem>)}
            </TextField>
            <TextField
              select label="Category" value={form.category}
              onChange={(e) => set('category', e.target.value)}
              fullWidth
            >
              <MenuItem value="">— none —</MenuItem>
              {CATEGORIES.map((c) => <MenuItem key={c} value={c}>{c}</MenuItem>)}
            </TextField>
          </Stack>
          <Stack direction="row" spacing={2}>
            <TextField
              label="SKU (optional)" value={form.sku}
              onChange={(e) => set('sku', e.target.value)}
              fullWidth
            />
            <TextField
              label="Supplier (optional)" value={form.supplier}
              onChange={(e) => set('supplier', e.target.value)}
              fullWidth
            />
          </Stack>
          <Stack direction="row" spacing={2}>
            <TextField
              label="Initial stock" type="number" value={form.initial_stock}
              onChange={(e) => set('initial_stock', parseFloat(e.target.value) || 0)}
              inputProps={{ min: 0, step: 0.01 }} fullWidth
            />
            <TextField
              label="Reorder threshold" type="number" value={form.reorder_threshold}
              onChange={(e) => set('reorder_threshold', parseFloat(e.target.value) || 0)}
              inputProps={{ min: 0, step: 0.01 }} fullWidth
            />
          </Stack>
          <TextField
            label="Cost per unit (optional)" type="number"
            value={form.cost_per_unit ?? ''}
            onChange={(e) => set('cost_per_unit', e.target.value ? parseFloat(e.target.value) : undefined)}
            inputProps={{ min: 0, step: 0.01 }}
            InputProps={{ startAdornment: <InputAdornment position="start">$</InputAdornment> }}
            fullWidth
          />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={saving}>Cancel</Button>
        <Button
          variant="contained"
          onClick={handleSubmit}
          disabled={saving}
          startIcon={saving ? <CircularProgress size={16} /> : <AddIcon />}
        >
          Add item
        </Button>
      </DialogActions>
    </Dialog>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

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

  // Group by category
  const grouped = filteredItems.reduce<Record<string, InventoryItem[]>>((acc, item) => {
    const cat = item.category ?? 'uncategorized';
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(item);
    return acc;
  }, {});

  const totalValue = items.reduce(
    (sum, i) => sum + (i.current_stock * (i.cost_per_unit ?? 0)), 0,
  );

  if (!shopId) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="warning">No shop selected. Please select a shop first.</Alert>
      </Box>
    );
  }

  return (
    <Box sx={{ width: '100%', maxWidth: { sm: '100%', md: '1200px' }, mx: 'auto' }}>
      <Header />

      {/* Page title + actions */}
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ px: 2, pt: 2, pb: 1 }}>
        <Stack direction="row" alignItems="center" spacing={1.5}>
          <InventoryRoundedIcon color="primary" />
          <Typography variant="h5" fontWeight={700}>Inventory</Typography>
          {alertCount > 0 && (
            <Chip
              icon={<WarningAmberRoundedIcon fontSize="small" />}
              label={`${alertCount} low-stock`}
              color="warning"
              size="small"
              sx={{ fontWeight: 700 }}
            />
          )}
        </Stack>
        <Stack direction="row" spacing={1}>
          <Tooltip title="Refresh">
            <IconButton onClick={load} disabled={loading} size="small">
              {loading ? <CircularProgress size={18} /> : <RefreshIcon />}
            </IconButton>
          </Tooltip>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => setAddOpen(true)}
            size="small"
            sx={{ borderRadius: 3 }}
          >
            Add item
          </Button>
        </Stack>
      </Stack>

      {/* Summary cards */}
      <Stack direction="row" spacing={2} sx={{ px: 2, pb: 2 }} flexWrap="wrap" useFlexGap>
        <Card sx={{ flex: '1 1 140px', borderRadius: 3 }}>
          <CardContent sx={{ pb: '12px !important' }}>
            <Typography variant="caption" color="text.secondary">Total items</Typography>
            <Typography variant="h4" fontWeight={700}>{items.length}</Typography>
          </CardContent>
        </Card>
        <Card sx={{ flex: '1 1 140px', borderRadius: 3, bgcolor: alertCount > 0 ? 'warning.light' : undefined }}>
          <CardContent sx={{ pb: '12px !important' }}>
            <Typography variant="caption" color="text.secondary">Low / out of stock</Typography>
            <Typography variant="h4" fontWeight={700} color={alertCount > 0 ? 'warning.dark' : 'text.primary'}>
              {alertCount}
            </Typography>
          </CardContent>
        </Card>
        <Card sx={{ flex: '1 1 160px', borderRadius: 3 }}>
          <CardContent sx={{ pb: '12px !important' }}>
            <Typography variant="caption" color="text.secondary">Estimated stock value</Typography>
            <Typography variant="h4" fontWeight={700}>
              ${totalValue.toFixed(2)}
            </Typography>
          </CardContent>
        </Card>
      </Stack>

      {error && (
        <Alert severity="error" sx={{ mx: 2, mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {/* Search */}
      <Box sx={{ px: 2, pb: 2 }}>
        <TextField
          placeholder="Search by name, category, supplier, or SKU…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          size="small"
          fullWidth
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchRoundedIcon fontSize="small" />
              </InputAdornment>
            ),
          }}
          sx={{ '& .MuiOutlinedInput-root': { borderRadius: 3 } }}
        />
      </Box>

      {/* Items table grouped by category */}
      {loading && items.length === 0 ? (
        <Box display="flex" justifyContent="center" py={6}>
          <CircularProgress />
        </Box>
      ) : Object.entries(grouped).length === 0 ? (
        <Box sx={{ px: 2, py: 4, textAlign: 'center' }}>
          <Typography color="text.secondary">
            {search ? 'No items match your search.' : 'No inventory items yet. Add your first item.'}
          </Typography>
        </Box>
      ) : (
        Object.entries(grouped).sort(([a], [b]) => a.localeCompare(b)).map(([category, catItems]) => (
          <Box key={category} sx={{ px: 2, mb: 3 }}>
            <Stack direction="row" alignItems="center" spacing={1} mb={1}>
              <Chip
                label={category}
                size="small"
                color={CATEGORY_COLORS[category] ?? 'default'}
                sx={{ fontWeight: 700, textTransform: 'capitalize' }}
              />
              <Typography variant="caption" color="text.secondary">
                {catItems.length} item{catItems.length !== 1 ? 's' : ''}
              </Typography>
            </Stack>
            <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 3 }}>
              <Table size="small">
                <TableHead>
                  <TableRow sx={{ bgcolor: 'action.hover' }}>
                    <TableCell sx={{ fontWeight: 700 }}>Name</TableCell>
                    <TableCell sx={{ fontWeight: 700 }}>SKU</TableCell>
                    <TableCell sx={{ fontWeight: 700 }}>Supplier</TableCell>
                    <TableCell sx={{ fontWeight: 700 }} align="center">Stock</TableCell>
                    <TableCell sx={{ fontWeight: 700 }} align="center">Reorder at</TableCell>
                    <TableCell sx={{ fontWeight: 700 }} align="right">Cost/unit</TableCell>
                    <TableCell sx={{ fontWeight: 700 }} align="center">Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {catItems.map((item) => {
                    const status = stockStatus(item);
                    return (
                      <TableRow
                        key={item.id}
                        sx={{
                          bgcolor: status === 'out' ? 'error.lighter' : status === 'low' ? 'warning.lighter' : undefined,
                          '&:last-child td, &:last-child th': { border: 0 },
                        }}
                      >
                        <TableCell>
                          <Stack direction="row" alignItems="center" spacing={1}>
                            {status !== 'ok' && (
                              <WarningAmberRoundedIcon
                                fontSize="small"
                                color={status === 'out' ? 'error' : 'warning'}
                              />
                            )}
                            <Typography variant="body2" fontWeight={600}>
                              {item.name}
                            </Typography>
                          </Stack>
                        </TableCell>
                        <TableCell>
                          <Typography variant="caption" color="text.secondary">
                            {item.sku ?? '—'}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Typography variant="caption" color="text.secondary">
                            {item.supplier ?? '—'}
                          </Typography>
                        </TableCell>
                        <TableCell align="center">
                          <StockBadge item={item} />
                        </TableCell>
                        <TableCell align="center">
                          <Typography variant="body2">
                            {item.reorder_threshold} {item.unit}
                          </Typography>
                        </TableCell>
                        <TableCell align="right">
                          <Typography variant="body2">
                            {item.cost_per_unit != null ? `$${item.cost_per_unit.toFixed(2)}` : '—'}
                          </Typography>
                        </TableCell>
                        <TableCell align="center">
                          <Stack direction="row" spacing={0.5} justifyContent="center">
                            <Tooltip title="Restock">
                              <IconButton
                                size="small"
                                color="success"
                                onClick={() => openAction(item, 'restock')}
                              >
                                <AddShoppingCartRoundedIcon fontSize="small" />
                              </IconButton>
                            </Tooltip>
                            <Tooltip title="Record usage">
                              <IconButton
                                size="small"
                                color="warning"
                                onClick={() => openAction(item, 'usage')}
                              >
                                <RemoveShoppingCartRoundedIcon fontSize="small" />
                              </IconButton>
                            </Tooltip>
                            <Tooltip title="Movement history">
                              <IconButton
                                size="small"
                                onClick={() => setHistoryItem(item)}
                              >
                                <HistoryRoundedIcon fontSize="small" />
                              </IconButton>
                            </Tooltip>
                          </Stack>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </TableContainer>
          </Box>
        ))
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
    </Box>
  );
}
