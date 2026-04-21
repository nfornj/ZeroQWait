import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
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
  Select,
  FormControl,
  InputLabel,
  Paper,
} from '@mui/material';
import { DataGrid, GridColDef, GridActionsCellItem } from '@mui/x-data-grid';
import EventIcon from '@mui/icons-material/Event';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import PersonOffIcon from '@mui/icons-material/PersonOff';
import RefreshIcon from '@mui/icons-material/Refresh';
import ScheduleIcon from '@mui/icons-material/Schedule';
import Header from '../components/Header';
import { useShop } from '../../../contexts/ShopContext';

interface AppointmentRow {
  id: number;
  customer_name: string;
  customer_phone: string | null;
  scheduled_start: string;
  scheduled_end: string;
  status: string;
  service_id: number | null;
  employee_id: number | null;
  service_cost: number;
  notes: string | null;
  created_at: string;
}

interface EmployeeAvailability {
  employee_id: number;
  username: string;
  is_clocked_in: boolean;
  shift_start: string | null;
  appointments_today: number;
  next_available_slot: string | null;
}

const STATUS_COLORS: Record<string, 'default' | 'primary' | 'secondary' | 'error' | 'info' | 'success' | 'warning'> = {
  scheduled: 'info',
  confirmed: 'primary',
  checked_in: 'warning',
  in_progress: 'secondary',
  completed: 'success',
  cancelled: 'error',
  no_show: 'default',
};

const AppointmentsPage: React.FC = () => {
  const { shop } = useShop();
  const [appointments, setAppointments] = useState<AppointmentRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedDate, setSelectedDate] = useState(() => {
    const d = new Date();
    return d.toISOString().split('T')[0];
  });
  const [statusFilter, setStatusFilter] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [employeeAvailability, setEmployeeAvailability] = useState<EmployeeAvailability[]>([]);
  const [unavailableEmployees, setUnavailableEmployees] = useState<{ employee_id: number; username: string }[]>([]);

  const token = localStorage.getItem('token');
  const headers = { Authorization: `Bearer ${token}` };

  const fetchAppointments = useCallback(async () => {
    if (!shop) return;
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (selectedDate) params.date = selectedDate;
      if (statusFilter) params.status = statusFilter;

      const res = await axios.get(`/appointments/shop/${shop.id}`, { headers, params });
      setAppointments(res.data);
    } catch {
      setError('Failed to load appointments');
    } finally {
      setLoading(false);
    }
  }, [shop, selectedDate, statusFilter]);

  const fetchAvailability = useCallback(async () => {
    if (!shop) return;
    try {
      const [avail, unavail] = await Promise.all([
        axios.get(`/appointments/shop/${shop.id}/employee-availability`, {
          headers,
          params: { date: selectedDate },
        }),
        axios.get(`/appointments/shop/${shop.id}/unavailable-employees`, { headers }),
      ]);
      setEmployeeAvailability(avail.data);
      setUnavailableEmployees(unavail.data);
    } catch {
      // non-critical
    }
  }, [shop, selectedDate]);

  useEffect(() => {
    fetchAppointments();
    fetchAvailability();
  }, [fetchAppointments, fetchAvailability]);

  const handleStatusChange = async (appointmentId: number, newStatus: string) => {
    if (!shop) return;
    try {
      await axios.patch(
        `/appointments/${appointmentId}/status`,
        null,
        { headers, params: { shop_id: shop.id, new_status: newStatus } }
      );
      setSuccess(`Appointment updated to ${newStatus}`);
      fetchAppointments();
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to update status');
    }
  };

  const columns: GridColDef[] = [
    { field: 'id', headerName: 'ID', width: 60 },
    { field: 'customer_name', headerName: 'Customer', flex: 1, minWidth: 130 },
    { field: 'customer_phone', headerName: 'Phone', width: 130 },
    {
      field: 'scheduled_start',
      headerName: 'Time',
      width: 160,
      valueFormatter: (value: string) => {
        if (!value) return '';
        const d = new Date(value);
        return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) +
          ' ' + d.toLocaleDateString([], { month: 'short', day: 'numeric' });
      },
    },
    {
      field: 'status',
      headerName: 'Status',
      width: 130,
      renderCell: (params) => (
        <Chip
          label={params.value?.replace('_', ' ')}
          color={STATUS_COLORS[params.value as string] || 'default'}
          size="small"
          sx={{ textTransform: 'capitalize' }}
        />
      ),
    },
    {
      field: 'service_cost',
      headerName: 'Cost',
      width: 90,
      valueFormatter: (value: number) => value ? `$${value.toFixed(2)}` : '$0.00',
    },
    {
      field: 'actions',
      type: 'actions',
      headerName: 'Actions',
      width: 160,
      getActions: (params) => {
        const status = params.row.status;
        const actions = [];

        if (status === 'scheduled') {
          actions.push(
            <GridActionsCellItem
              key="confirm"
              icon={<Tooltip title="Confirm"><CheckCircleIcon color="primary" /></Tooltip>}
              label="Confirm"
              onClick={() => handleStatusChange(params.row.id, 'confirmed')}
            />,
            <GridActionsCellItem
              key="cancel"
              icon={<Tooltip title="Cancel"><CancelIcon color="error" /></Tooltip>}
              label="Cancel"
              onClick={() => handleStatusChange(params.row.id, 'cancelled')}
            />
          );
        }
        if (status === 'confirmed') {
          actions.push(
            <GridActionsCellItem
              key="checkin"
              icon={<Tooltip title="Check In"><EventIcon color="warning" /></Tooltip>}
              label="Check In"
              onClick={() => handleStatusChange(params.row.id, 'checked_in')}
            />,
            <GridActionsCellItem
              key="noshow"
              icon={<Tooltip title="No Show"><PersonOffIcon /></Tooltip>}
              label="No Show"
              onClick={() => handleStatusChange(params.row.id, 'no_show')}
            />
          );
        }
        if (status === 'checked_in') {
          actions.push(
            <GridActionsCellItem
              key="start"
              icon={<Tooltip title="Start Service"><PlayArrowIcon color="secondary" /></Tooltip>}
              label="Start"
              onClick={() => handleStatusChange(params.row.id, 'in_progress')}
            />
          );
        }
        if (status === 'in_progress') {
          actions.push(
            <GridActionsCellItem
              key="complete"
              icon={<Tooltip title="Complete"><CheckCircleIcon color="success" /></Tooltip>}
              label="Complete"
              onClick={() => handleStatusChange(params.row.id, 'completed')}
            />
          );
        }

        return actions;
      },
    },
  ];

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Header />
      <Box>
        <Typography variant="h4" gutterBottom>
          Appointments
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Manage scheduled bookings and employee availability
        </Typography>
      </Box>

      {/* Unavailable employees alert */}
      {unavailableEmployees.length > 0 && (
        <Alert severity="warning" icon={<PersonOffIcon />}>
          <strong>Not clocked in today:</strong>{' '}
          {unavailableEmployees.map((e) => e.username).join(', ')}
        </Alert>
      )}

      {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}
      {success && <Alert severity="success" onClose={() => setSuccess(null)}>{success}</Alert>}

      {/* Filters */}
      <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap">
        <TextField
          type="date"
          label="Date"
          value={selectedDate}
          onChange={(e) => setSelectedDate(e.target.value)}
          size="small"
          InputLabelProps={{ shrink: true }}
        />
        <FormControl size="small" sx={{ minWidth: 140 }}>
          <InputLabel>Status</InputLabel>
          <Select
            value={statusFilter}
            label="Status"
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <MenuItem value="">All</MenuItem>
            <MenuItem value="scheduled">Scheduled</MenuItem>
            <MenuItem value="confirmed">Confirmed</MenuItem>
            <MenuItem value="checked_in">Checked In</MenuItem>
            <MenuItem value="in_progress">In Progress</MenuItem>
            <MenuItem value="completed">Completed</MenuItem>
            <MenuItem value="cancelled">Cancelled</MenuItem>
            <MenuItem value="no_show">No Show</MenuItem>
          </Select>
        </FormControl>
        <IconButton onClick={() => { fetchAppointments(); fetchAvailability(); }}>
          <RefreshIcon />
        </IconButton>
      </Stack>

      {/* Employee availability cards */}
      {employeeAvailability.length > 0 && (
        <Box>
          <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1 }}>
            Employee Load Today
          </Typography>
          <Stack direction="row" spacing={1.5} flexWrap="wrap" useFlexGap>
            {employeeAvailability.map((emp) => (
              <Card
                key={emp.employee_id}
                variant="outlined"
                sx={{
                  minWidth: 160,
                  borderColor: emp.is_clocked_in ? 'success.main' : 'text.disabled',
                  opacity: emp.is_clocked_in ? 1 : 0.6,
                }}
              >
                <CardContent sx={{ py: 1, px: 1.5, '&:last-child': { pb: 1 } }}>
                  <Stack direction="row" alignItems="center" spacing={0.5}>
                    <Box
                      sx={{
                        width: 8,
                        height: 8,
                        borderRadius: '50%',
                        bgcolor: emp.is_clocked_in ? 'success.main' : 'text.disabled',
                      }}
                    />
                    <Typography variant="body2" fontWeight={600}>
                      {emp.username}
                    </Typography>
                  </Stack>
                  <Typography variant="caption" color="text.secondary">
                    {emp.appointments_today} appts today
                  </Typography>
                </CardContent>
              </Card>
            ))}
          </Stack>
        </Box>
      )}

      {/* Appointments grid */}
      <Paper
        sx={{
          height: 500,
          bgcolor: 'var(--owner-glass-bg)',
          border: '1px solid var(--owner-glass-border)',
          borderRadius: 3,
        }}
      >
        <DataGrid
          rows={appointments}
          columns={columns}
          loading={loading}
          pageSizeOptions={[10, 25, 50]}
          initialState={{ pagination: { paginationModel: { pageSize: 25 } } }}
          disableRowSelectionOnClick
          sx={{
            border: 'none',
            '& .MuiDataGrid-cell': { borderColor: 'var(--owner-glass-border)' },
            '& .MuiDataGrid-columnHeaders': { borderColor: 'var(--owner-glass-border)' },
          }}
        />
      </Paper>
    </Box>
  );
};

export default AppointmentsPage;
