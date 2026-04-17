import React, { useEffect, useState, useCallback } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  Grid,
  IconButton,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Tab,
  Tabs,
  Tooltip,
  Typography,
} from '@mui/material';
import { alpha, useTheme } from '@mui/material/styles';
import {
  DataGrid,
  GridColDef,
  GridRenderCellParams,
  GridActionsCellItem,
} from '@mui/x-data-grid';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import DeleteIcon from '@mui/icons-material/Delete';
import SwapHorizIcon from '@mui/icons-material/SwapHoriz';
import PeopleRoundedIcon from '@mui/icons-material/PeopleRounded';
import HourglassTopRoundedIcon from '@mui/icons-material/HourglassTopRounded';
import CheckCircleRoundedIcon from '@mui/icons-material/CheckCircleRounded';
import PersonOffRoundedIcon from '@mui/icons-material/PersonOffRounded';
import axios from 'axios';
import { useNavigate, useParams } from 'react-router-dom';
import Header from '../components/Header';

interface QueueItem {
  id: number;
  queue_id: number;
  customer_name: string;
  customer_phone: string | null;
  customer_email: string | null;
  position: number;
  status: string;
  checked_in_at: string;
  service_started_at: string | null;
  completed_at: string | null;
  assigned_employee_id: number | null;
  assigned_employee: { id: number; username: string; email?: string } | null;
  notes: string | null;
}

interface ActiveEmployee {
  user_id: number;
  username: string;
  email: string;
  active_items: number;
  clock_in: string;
}

const statusColors: Record<string, 'warning' | 'info' | 'success' | 'default'> = {
  waiting: 'warning',
  being_served: 'info',
  completed: 'success',
  checked_out: 'success',
  cancelled: 'default',
};

const CHECKED_OUT_MARKER_PREFIX = 'CHECKED_OUT_AT:';

type QueueRow = QueueItem & {
  display_status: string;
  live_position: number;
};

function formatWaitTime(checkedInAt: string): string {
  const diff = Date.now() - new Date(checkedInAt).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins}m`;
  return `${Math.floor(mins / 60)}h ${mins % 60}m`;
}

const QueueDetailPage: React.FC = () => {
  const theme = useTheme();
  const navigate = useNavigate();
  const { queueId } = useParams<{ queueId: string }>();

  const [items, setItems] = useState<QueueItem[]>([]);
  const [employees, setEmployees] = useState<ActiveEmployee[]>([]);
  const [shopId, setShopId] = useState<number | null>(null);
  const [queueName, setQueueName] = useState('Queue');
  const [error, setError] = useState('');
  const [tableView, setTableView] = useState<'live' | 'historical'>('live');
  const [reassignDialogOpen, setReassignDialogOpen] = useState(false);
  const [reassignTarget, setReassignTarget] = useState<QueueItem | null>(null);
  const [selectedEmployee, setSelectedEmployee] = useState<number | ''>('');

  const token = localStorage.getItem('token');
  const headers = { Authorization: `Bearer ${token}` };

  const fetchData = useCallback(async () => {
    if (!queueId) return;
    try {
      // Get queue items
      const itemsRes = await axios.get(`/queues/${queueId}/items`, { headers });
      setItems(itemsRes.data);

      // Get shop from my-shops for employee list
      if (!shopId) {
        const shopRes = await axios.get('/shops/my-shops', { headers });
        if (shopRes.data.length > 0) {
          const sid = shopRes.data[0].id;
          setShopId(sid);
          // Get queue name from all queues
          const queuesRes = await axios.get(`/queues/shop/${sid}/all`, { headers });
          const q = queuesRes.data.find((q: any) => q.id === Number(queueId));
          if (q) setQueueName(q.name);
        }
      }

      if (shopId) {
        const empRes = await axios.get(`/queues/shop/${shopId}/active-employees`, { headers });
        setEmployees(empRes.data);
      }
    } catch {
      // silent — keep UI usable
    }
  }, [queueId, shopId]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const handleServe = async (itemId: number) => {
    try {
      await axios.post(`/queues/items/${itemId}/serve`, {}, { headers });
      setError('');
      fetchData();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to serve customer');
    }
  };

  const handleComplete = async (itemId: number) => {
    try {
      await axios.patch(`/queues/items/${itemId}/status?new_status=completed`, {}, { headers });
      setError('');
      fetchData();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to complete customer');
    }
  };

  const handleRemove = async (itemId: number) => {
    try {
      await axios.delete(`/queues/items/${itemId}`, { headers });
      setError('');
      fetchData();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to remove customer');
    }
  };

  const openReassign = (item: QueueItem) => {
    setReassignTarget(item);
    setSelectedEmployee(item.assigned_employee_id || '');
    setReassignDialogOpen(true);
  };

  const handleReassign = async () => {
    if (!reassignTarget || !selectedEmployee) return;
    try {
      await axios.patch(
        `/queues/items/${reassignTarget.id}/reassign`,
        { employee_id: selectedEmployee },
        { headers },
      );
      setReassignDialogOpen(false);
      setReassignTarget(null);
      setError('');
      fetchData();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to reassign');
    }
  };

  const isCheckedOut = (item: QueueItem) =>
    typeof item.notes === 'string' && item.notes.includes(CHECKED_OUT_MARKER_PREFIX);

  const activeItems = items.filter((i) => i.status === 'waiting' || i.status === 'being_served');
  const liveRows: QueueRow[] = activeItems
    .slice()
    .sort((a, b) => (a.position || 0) - (b.position || 0))
    .map((item, idx) => ({
      ...item,
      display_status: item.status,
      live_position: idx + 1,
    }));

  const historicalRows: QueueRow[] = items
    .filter((i) => i.status !== 'waiting' && i.status !== 'being_served')
    .slice()
    .sort((a, b) => {
      const aTs = new Date(a.completed_at || a.checked_in_at).getTime();
      const bTs = new Date(b.completed_at || b.checked_in_at).getTime();
      return bTs - aTs;
    })
    .map((item) => ({
      ...item,
      display_status: isCheckedOut(item) ? 'checked_out' : item.status,
      live_position: item.position,
    }));

  const waitingCount = items.filter((i) => i.status === 'waiting').length;
  const servingCount = items.filter((i) => i.status === 'being_served').length;
  const checkedOutCount = items.filter((i) => isCheckedOut(i)).length;
  const completedCount = items.filter((i) => i.status === 'completed' && !isCheckedOut(i)).length;

  const startOfToday = new Date();
  startOfToday.setHours(0, 0, 0, 0);
  const historicalPreviousDaysCount = historicalRows.filter(
    (item) => new Date(item.checked_in_at).getTime() < startOfToday.getTime(),
  ).length;

  const columns: GridColDef<QueueRow>[] = [
    {
      field: 'live_position',
      headerName: '#',
      width: 60,
      valueGetter: (_value, row) =>
        tableView === 'live' ? row.live_position : row.position,
    },
    { field: 'customer_name', headerName: 'Customer', flex: 1, minWidth: 140 },
    { field: 'customer_phone', headerName: 'Phone', width: 130 },
    {
      field: 'display_status',
      headerName: 'Status',
      width: 130,
      renderCell: (params: GridRenderCellParams) => (
        <Chip
          label={params.value?.replace('_', ' ')}
          color={statusColors[params.value as string] || 'default'}
          size="small"
          variant="outlined"
          sx={{ textTransform: 'capitalize' }}
        />
      ),
    },
    {
      field: 'assigned_employee',
      headerName: 'Assigned To',
      width: 160,
      valueGetter: (value: any) => value?.username || 'Unassigned',
      renderCell: (params: GridRenderCellParams) => {
        const name = params.value as string;
        return (
          <Chip
            label={name}
            size="small"
            color={name === 'Unassigned' ? 'default' : 'primary'}
            variant={name === 'Unassigned' ? 'outlined' : 'filled'}
          />
        );
      },
    },
    {
      field: 'checked_in_at',
      headerName: 'Wait Time',
      width: 110,
      valueGetter: (value: string) => value,
      renderCell: (params: GridRenderCellParams) => {
        const row = params.row as QueueItem;
        if (row.status === 'completed' || row.status === 'cancelled') return '—';
        return formatWaitTime(params.value as string);
      },
    },
    {
      field: 'actions',
      headerName: 'Actions',
      type: 'actions',
      width: 160,
      getActions: (params) => {
        const row = params.row as QueueItem;
        if (row.status !== 'waiting' && row.status !== 'being_served') return [];
        if (tableView !== 'live') return [];
        const actions = [];
        if (row.status === 'waiting') {
          actions.push(
            <GridActionsCellItem
              key="serve"
              icon={<Tooltip title="Serve Now"><PlayArrowIcon /></Tooltip>}
              label="Serve"
              onClick={() => handleServe(row.id)}
            />,
          );
        }
        if (row.status === 'being_served') {
          actions.push(
            <GridActionsCellItem
              key="complete"
              icon={<Tooltip title="Complete"><CheckCircleRoundedIcon color="success" /></Tooltip>}
              label="Complete"
              onClick={() => handleComplete(row.id)}
            />,
          );
        }
        actions.push(
          <GridActionsCellItem
            key="reassign"
            icon={<Tooltip title="Reassign"><SwapHorizIcon /></Tooltip>}
            label="Reassign"
            onClick={() => openReassign(row)}
            disabled={employees.length === 0}
          />,
          <GridActionsCellItem
            key="remove"
            icon={<Tooltip title="Remove"><DeleteIcon color="error" /></Tooltip>}
            label="Remove"
            onClick={() => handleRemove(row.id)}
          />,
        );
        return actions;
      },
    },
  ];

  return (
    <Box sx={{ width: '100%', maxWidth: { sm: '100%', md: '1700px' } }}>
      <Header />

      <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 2 }}>
        <IconButton onClick={() => navigate('/queues')}>
          <ArrowBackIcon />
        </IconButton>
        <Typography variant="h5" fontWeight={700}>
          {queueName}
        </Typography>
        <Chip label={`${activeItems.length} active`} color="primary" size="small" />
      </Stack>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      <Grid container spacing={2} sx={{ mb: 2 }}>
        <Grid size={{ xs: 6, sm: 3 }}>
          <Card variant="outlined" sx={{ borderRadius: 3 }}>
            <CardContent>
              <Stack spacing={0.5} alignItems="center">
                <PeopleRoundedIcon color="primary" />
                <Typography variant="h5" fontWeight={700}>{items.length}</Typography>
                <Typography variant="body2" color="text.secondary">Total</Typography>
              </Stack>
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ xs: 6, sm: 3 }}>
          <Card variant="outlined" sx={{ borderRadius: 3 }}>
            <CardContent>
              <Stack spacing={0.5} alignItems="center">
                <HourglassTopRoundedIcon color="warning" />
                <Typography variant="h5" fontWeight={700}>{waitingCount}</Typography>
                <Typography variant="body2" color="text.secondary">Waiting</Typography>
              </Stack>
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ xs: 6, sm: 3 }}>
          <Card variant="outlined" sx={{ borderRadius: 3 }}>
            <CardContent>
              <Stack spacing={0.5} alignItems="center">
                <CheckCircleRoundedIcon color="info" />
                <Typography variant="h5" fontWeight={700}>{servingCount}</Typography>
                <Typography variant="body2" color="text.secondary">Being Served</Typography>
              </Stack>
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ xs: 6, sm: 3 }}>
          <Card variant="outlined" sx={{ borderRadius: 3 }}>
            <CardContent>
              <Stack spacing={0.5} alignItems="center">
                <PersonOffRoundedIcon color="success" />
                <Typography variant="h5" fontWeight={700}>{completedCount}</Typography>
                <Typography variant="body2" color="text.secondary">Completed</Typography>
              </Stack>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} sx={{ mb: 1.5 }}>
        <Chip label={`Checked Out: ${checkedOutCount}`} color="success" variant="outlined" size="small" />
        <Chip label={`Historical (Prev Days): ${historicalPreviousDaysCount}`} color="default" variant="outlined" size="small" />
      </Stack>

      {employees.length > 0 && (
        <Card variant="outlined" sx={{ borderRadius: 3, mb: 2 }}>
          <CardContent>
            <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1 }}>
              Clocked-In Employees
            </Typography>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              {employees.map((emp) => (
                <Chip
                  key={emp.user_id}
                  label={`${emp.username} (${emp.active_items} customers)`}
                  color="primary"
                  variant="outlined"
                  size="small"
                />
              ))}
            </Stack>
          </CardContent>
        </Card>
      )}

      <Paper sx={{ width: '100%', overflow: 'hidden', borderRadius: 3 }} variant="outlined">
        <Tabs
          value={tableView}
          onChange={(_e, value) => setTableView(value)}
          sx={{ px: 1.5, pt: 1 }}
        >
          <Tab value="live" label={`Live Queue (${liveRows.length})`} />
          <Tab value="historical" label={`Historical (${historicalRows.length})`} />
        </Tabs>
        <DataGrid
          autoHeight
          rows={tableView === 'live' ? liveRows : historicalRows}
          columns={columns}
          initialState={{
            pagination: { paginationModel: { pageSize: 20 } },
            sorting: { sortModel: [{ field: 'live_position', sort: 'asc' }] },
          }}
          pageSizeOptions={[10, 20, 50]}
          disableRowSelectionOnClick
          density="compact"
          sx={{
            border: 0,
            backgroundColor: 'background.paper',
            '& .MuiDataGrid-columnHeaders': {
              bgcolor: 'background.default',
              borderBottom: '1px solid',
              borderColor: 'divider',
            },
            '& .MuiDataGrid-cell:focus, & .MuiDataGrid-columnHeader:focus': {
              outline: 'none',
            },
          }}
        />
      </Paper>

      {/* Reassign Dialog */}
      <Dialog
        open={reassignDialogOpen}
        onClose={() => setReassignDialogOpen(false)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>Reassign Customer</DialogTitle>
        <DialogContent>
          {reassignTarget && (
            <Stack spacing={2} sx={{ mt: 1 }}>
              <Typography variant="body2" color="text.secondary">
                Move <strong>{reassignTarget.customer_name}</strong> to a different employee:
              </Typography>
              <FormControl fullWidth size="small">
                <InputLabel>Employee</InputLabel>
                <Select
                  value={selectedEmployee}
                  label="Employee"
                  onChange={(e) => setSelectedEmployee(e.target.value as number)}
                >
                  {employees.map((emp) => (
                    <MenuItem key={emp.user_id} value={emp.user_id}>
                      {emp.username} — {emp.active_items} customer{emp.active_items !== 1 ? 's' : ''}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setReassignDialogOpen(false)}>Cancel</Button>
          <Button
            onClick={handleReassign}
            variant="contained"
            disabled={!selectedEmployee}
          >
            Reassign
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default QueueDetailPage;
