import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Box,
    Typography,
    Button,
    Card,
    CardContent,
    Alert,
    CircularProgress,
    Chip,
    Grid,
    Stack,
    List,
    ListItem,
    ListItemText,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    TextField,
    Paper,
    Tooltip,
    Skeleton,
    Tabs,
    Tab,
    Divider,
} from '@mui/material';
import { alpha, useTheme } from '@mui/material/styles';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import ExitToAppIcon from '@mui/icons-material/ExitToApp';
import PersonAddIcon from '@mui/icons-material/PersonAdd';
import PhotoCameraIcon from '@mui/icons-material/PhotoCamera';
import DeleteIcon from '@mui/icons-material/Delete';
import SkipNextIcon from '@mui/icons-material/SkipNext';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import PeopleRoundedIcon from '@mui/icons-material/PeopleRounded';
import HourglassTopRoundedIcon from '@mui/icons-material/HourglassTopRounded';
import PlayArrowRoundedIcon from '@mui/icons-material/PlayArrowRounded';
import IconButton from '@mui/material/IconButton';
import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';
import Select from '@mui/material/Select';
import MenuItem from '@mui/material/MenuItem';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import PaymentsIcon from '@mui/icons-material/Payments';
import DownloadIcon from '@mui/icons-material/Download';
import QueueIcon from '@mui/icons-material/Queue';
import api from '../../../services/api';
import { useAuth } from '../../../contexts/AuthContext';
import ProfilePhotoUploader from '../../../components/ProfilePhotoUploader';
import { useShop } from '../../../contexts/ShopContext';


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
    const [photoUrl, setPhotoUrl] = useState('');
    const [removeDialogOpen, setRemoveDialogOpen] = useState(false);
    const [selectedCustomer, setSelectedCustomer] = useState<QueueItem | null>(null);
    const [removeReason, setRemoveReason] = useState('');

    const [addDialogOpen, setAddDialogOpen] = useState(false);
    const [newCustomerName, setNewCustomerName] = useState('');
    const [newCustomerPhone, setNewCustomerPhone] = useState('');
    const [services, setServices] = useState<any[]>([]);
    const [selectedServiceId, setSelectedServiceId] = useState<number | ''>('');
    const [connectionLost, setConnectionLost] = useState(false);
    const [serveConfirmCustomer, setServeConfirmCustomer] = useState<QueueItem | null>(null);
    const [queueLoading, setQueueLoading] = useState(false);
    const [currentTab, setCurrentTab] = useState(0);
    const [payslips, setPayslips] = useState<any[]>([]);
    const [payslipsLoading, setPayslipsLoading] = useState(false);

    const { user } = useAuth();
    const navigate = useNavigate();
    const theme = useTheme();
    const { setShop } = useShop();

    useEffect(() => {
        fetchInitialData();
    }, []);

    useEffect(() => {
        if (selectedShop) {
            const interval = setInterval(fetchQueue, 5000);
            return () => clearInterval(interval);
        }
    }, [selectedShop]);

    const fetchInitialData = async () => {
        try {
            setLoading(true);

            // Fetch shops
            const shopsResponse = await api.get(`/employees/my-shops`);
            setShops(shopsResponse.data);

            // Fetch current shift
            const shiftResponse = await api.get(`/current-shift`);

            if (shiftResponse.data) {
                setCurrentShift(shiftResponse.data);
                const currentShop = shopsResponse.data.find((s: Shop) => s.id === shiftResponse.data.shop_id);
                if (currentShop) {
                    setSelectedShop(currentShop);
                    setShop({
                        id: currentShop.id,
                        name: currentShop.name,
                        slug: '',
                        city: '',
                        shop_type: '',
                    });
                    await fetchQueue(currentShop.id);

                    // Fetch services
                    try {
                        const servicesRes = await api.get(`/shops/${currentShop.id}/services`);
                        setServices(servicesRes.data.filter((s: any) => s.is_active));
                    } catch (e) {
                        console.error("Failed to fetch services", e);
                    }
                }
            }
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to load data');
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
        } catch (err) {
            setConnectionLost(true);
        } finally {
            setQueueLoading(false);
        }
    };

    const handleClockIn = async (shopId: number) => {
        try {
            setError(null);
            await api.post(`/clock-in/${shopId}`, {});
            setSuccess('Clocked in successfully!');
            await fetchInitialData();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to clock in');
        }
    };

    const handleClockOut = async () => {
        try {
            setError(null);
            await api.post(`/clock-out`, {});
            setSuccess('Clocked out successfully!');
            setCurrentShift(null);
            setSelectedShop(null);
            setQueue([]);
            setShop(null);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to clock out');
        }
    };

    const handleCallNext = async () => {
        if (!selectedShop) return;

        try {
            setError(null);
            const response = await api.get(`/queues/shop/${selectedShop.id}/active`);
            const queueId = response.data.id;
            await api.post(`/queues/${queueId}/call-next`, {});
            setSuccess('Called next customer!');
            fetchQueue();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to call next customer');
        }
    };

    const handleRemoveCustomer = async () => {
        if (!selectedCustomer || !removeReason.trim()) return;

        try {
            setError(null);
            await api.delete(`/queues/items/${selectedCustomer.id}`, {
                params: { reason: removeReason }
            });
            setSuccess('Customer removed from queue');
            setRemoveDialogOpen(false);
            setSelectedCustomer(null);
            setRemoveReason('');
            fetchQueue();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to remove customer');
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
            setError(err.response?.data?.detail || 'Failed to serve customer');
        }
    };

    const handleCompleteCustomer = async (customer: QueueItem) => {
        try {
            setError(null);
            await api.patch(`/queues/items/${customer.id}/status?new_status=completed`, {});
            setSuccess(`Completed service for ${customer.customer_name}`);
            await fetchQueue();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to complete customer');
        }
    };

    const handleUploadPhoto = async (photoDataUrl: string) => {
        try {
            await api.post(`/upload-profile-photo`,
                { photo_url: photoDataUrl },
                { params: { photo_url: photoDataUrl } }
            );
            setSuccess('Profile photo updated!');
        } catch (err: any) {
            throw new Error(err.response?.data?.detail || 'Failed to upload photo');
        }
    };

    const handleAddWalkIn = async () => {
        if (!selectedShop || !newCustomerName.trim()) return;

        try {
            setError(null);

            await api.post(`/queues/shop/${selectedShop.id}/join`, {
                customer_name: newCustomerName,
                customer_phone: newCustomerPhone,
                service_id: selectedServiceId || undefined,
                notes: "[Walk-in]"
            });

            setSuccess('Customer added to queue');
            setAddDialogOpen(false);
            setNewCustomerName('');
            setNewCustomerPhone('');
            setSelectedServiceId('');
            fetchQueue();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to add customer');
        }
    };

    const waitingCustomers = queue.filter(item => item.status === 'waiting');
    const servingCustomer = queue.find(item => item.status === 'being_served');

    const fetchMyPayslips = React.useCallback(async () => {
        setPayslipsLoading(true);
        try {
            const res = await api.get('/payroll/me/payslips?limit=30');
            setPayslips(res.data);
        } catch (err: any) {
            // silently ignore — employee may not have payslips yet
        } finally {
            setPayslipsLoading(false);
        }
    }, []);

    useEffect(() => {
        if (currentTab === 1) {
            fetchMyPayslips();
        }
    }, [currentTab, fetchMyPayslips]);

    const handleDownloadMyPayslipPdf = async (payslipId: number, period: string) => {
        try {
            const res = await api.get(`/payroll/me/payslips/${payslipId}/pdf`, {
                responseType: 'blob'
            });
            const url = URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }));
            const a = document.createElement('a');
            a.href = url;
            a.download = `my_payslip_${period}.pdf`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        } catch {
            setError('Failed to download payslip PDF');
        }
    };

    if (loading) {
        return (
            <Box display="flex" justifyContent="center" alignItems="center" minHeight="80vh">
                <CircularProgress />
            </Box>
        );
    }

    return (
        <Box sx={{ maxWidth: 1200, mx: 'auto', px: { xs: 2, md: 4 }, py: 4 }}>
            {/* Header */}
            <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" alignItems={{ sm: 'center' }} spacing={2} sx={{ mb: 3 }}>
                <Box>
                    <Typography variant="h4" fontWeight={700}>
                        Welcome, {user?.username}!
                    </Typography>
                    <Typography variant="body1" color="text.secondary">
                        {currentShift ? `Working at ${selectedShop?.name}` : 'Select a shop to clock in'}
                    </Typography>
                </Box>
                <Button
                    variant="outlined"
                    startIcon={<PhotoCameraIcon />}
                    onClick={() => setPhotoDialogOpen(true)}
                    sx={{ borderRadius: 3 }}
                >
                    Update Photo
                </Button>
            </Stack>

            {error && <Alert severity="error" sx={{ mb: 2, borderRadius: 3 }} onClose={() => setError(null)}>{error}</Alert>}
            {success && <Alert severity="success" sx={{ mb: 2, borderRadius: 3 }} onClose={() => setSuccess(null)}>{success}</Alert>}

            {/* Page-level tabs */}
            <Paper variant="outlined" sx={{ mb: 3, borderRadius: 3, overflow: 'hidden' }}>
                <Tabs value={currentTab} onChange={(_, v) => setCurrentTab(v)} aria-label="employee tabs">
                    <Tab label="Queue" icon={<QueueIcon />} iconPosition="start" />
                    <Tab label="My Pay" icon={<PaymentsIcon />} iconPosition="start" />
                </Tabs>
            </Paper>

            {!currentShift ? (
                /* ─── Not clocked in: show shop selection cards ─── */
                currentTab === 0 ? (
                <Grid container spacing={2}>
                    {shops.map((shop) => (
                        <Grid size={{ xs: 12, sm: 6, md: 4 }} key={shop.id}>
                            <Card variant="outlined" sx={{ borderRadius: 3 }}>
                                <CardContent>
                                    <Typography variant="h6" fontWeight={700} sx={{ mb: 2 }}>
                                        {shop.name}
                                    </Typography>
                                    <Button
                                        fullWidth
                                        variant="contained"
                                        startIcon={<AccessTimeIcon />}
                                        onClick={() => handleClockIn(shop.id)}
                                        sx={{ borderRadius: 3 }}
                                    >
                                        Clock In
                                    </Button>
                                </CardContent>
                            </Card>
                        </Grid>
                    ))}
                </Grid>
                ) : null
            ) : (
                /* ─── Clocked in ─── */
                currentTab === 0 ? (
                <Stack spacing={2.5}>
                    {/* Shift banner */}
                    <Card variant="outlined" sx={{ borderRadius: 3 }}>
                        <CardContent>
                            <Stack direction="row" justifyContent="space-between" alignItems="center">
                                <Stack spacing={0.5}>
                                    <Typography variant="h6" fontWeight={700}>Current Shift</Typography>
                                    <Typography variant="body2" color="text.secondary">
                                        Clocked in at {new Date(currentShift.clock_in).toLocaleTimeString()}
                                    </Typography>
                                </Stack>
                                <Button
                                    variant="outlined"
                                    color="error"
                                    startIcon={<ExitToAppIcon />}
                                    onClick={handleClockOut}
                                    sx={{ borderRadius: 3 }}
                                >
                                    Clock Out
                                </Button>
                            </Stack>
                        </CardContent>
                    </Card>

                    {/* Summary stat chips */}
                    <Grid container spacing={2}>
                        <Grid size={{ xs: 6, sm: 4 }}>
                            <Card variant="outlined" sx={{ borderRadius: 3 }}>
                                <CardContent>
                                    <Stack spacing={0.5} alignItems="center">
                                        <PeopleRoundedIcon color="primary" />
                                        <Typography variant="h4" fontWeight={700}>{queue.length}</Typography>
                                        <Typography variant="body2" color="text.secondary">Total in Queue</Typography>
                                    </Stack>
                                </CardContent>
                            </Card>
                        </Grid>
                        <Grid size={{ xs: 6, sm: 4 }}>
                            <Card variant="outlined" sx={{ borderRadius: 3 }}>
                                <CardContent>
                                    <Stack spacing={0.5} alignItems="center">
                                        <HourglassTopRoundedIcon color="warning" />
                                        <Typography variant="h4" fontWeight={700}>{waitingCustomers.length}</Typography>
                                        <Typography variant="body2" color="text.secondary">Waiting</Typography>
                                    </Stack>
                                </CardContent>
                            </Card>
                        </Grid>
                        <Grid size={{ xs: 12, sm: 4 }}>
                            <Card variant="outlined" sx={{ borderRadius: 3 }}>
                                <CardContent>
                                    <Stack spacing={0.5} alignItems="center">
                                        <PlayArrowRoundedIcon color="info" />
                                        <Typography variant="h4" fontWeight={700}>{servingCustomer ? 1 : 0}</Typography>
                                        <Typography variant="body2" color="text.secondary">Being Served</Typography>
                                    </Stack>
                                </CardContent>
                            </Card>
                        </Grid>
                    </Grid>

                    <Grid container spacing={2.5}>
                        {/* Now Serving */}
                        <Grid size={{ xs: 12, md: 6 }}>
                            <Card
                                variant="outlined"
                                sx={{
                                    borderRadius: 3,
                                    height: '100%',
                                    borderColor: servingCustomer ? alpha(theme.palette.primary.main, 0.4) : undefined,
                                    background: servingCustomer
                                        ? `linear-gradient(135deg, ${alpha(theme.palette.primary.main, 0.08)} 0%, ${alpha(theme.palette.primary.main, 0.02)} 100%)`
                                        : undefined,
                                }}
                            >
                                <CardContent>
                                    <Typography variant="h6" fontWeight={700} sx={{ mb: 2 }}>
                                        Now Serving
                                    </Typography>
                                    {servingCustomer ? (
                                        <Stack spacing={2} alignItems="center" sx={{ py: 3 }}>
                                            <Typography variant="h2" fontWeight={700} color="primary">
                                                #{servingCustomer.position}
                                            </Typography>
                                            <Typography variant="h5" fontWeight={600}>
                                                {servingCustomer.customer_name}
                                            </Typography>
                                            <Chip
                                                label="Being Served"
                                                color="info"
                                                variant="outlined"
                                                size="small"
                                            />
                                            <Stack direction="row" spacing={1.5} sx={{ mt: 1 }}>
                                                <Button
                                                    variant="contained"
                                                    color="success"
                                                    startIcon={<CheckCircleIcon />}
                                                    onClick={() => handleCompleteCustomer(servingCustomer)}
                                                    sx={{ borderRadius: 3, fontWeight: 700 }}
                                                >
                                                    Complete
                                                </Button>
                                                <Button
                                                    variant="outlined"
                                                    color="error"
                                                    size="small"
                                                    startIcon={<DeleteIcon />}
                                                    onClick={() => {
                                                        setSelectedCustomer(servingCustomer);
                                                        setRemoveDialogOpen(true);
                                                    }}
                                                    sx={{ borderRadius: 3 }}
                                                >
                                                    Remove
                                                </Button>
                                            </Stack>
                                        </Stack>
                                    ) : (
                                        <Typography color="text.secondary" sx={{ textAlign: 'center', py: 4 }}>
                                            No customer being served
                                        </Typography>
                                    )}
                                    <Button
                                        fullWidth
                                        variant="contained"
                                        size="large"
                                        startIcon={<PersonAddIcon />}
                                        onClick={handleCallNext}
                                        disabled={waitingCustomers.length === 0}
                                        sx={{ borderRadius: 3, mt: 1 }}
                                    >
                                        Call Next Customer
                                    </Button>
                                </CardContent>
                            </Card>
                        </Grid>

                        {/* Waiting Queue */}
                        <Grid size={{ xs: 12, md: 6 }}>
                            <Card variant="outlined" sx={{ borderRadius: 3, height: '100%' }}>
                                <CardContent>
                                    <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
                                        <Typography variant="h6" fontWeight={700}>
                                            Waiting Queue ({waitingCustomers.length})
                                        </Typography>
                                        {connectionLost && (
                                            <Chip icon={<WarningAmberIcon />} label="Connection lost" color="warning" size="small" />
                                        )}
                                    </Stack>
                                    <Button
                                        variant="outlined"
                                        fullWidth
                                        sx={{ mb: 2, borderRadius: 3 }}
                                        startIcon={<PersonAddIcon />}
                                        onClick={() => setAddDialogOpen(true)}
                                    >
                                        Add Walk-in Customer
                                    </Button>
                                    {queueLoading && waitingCustomers.length === 0 ? (
                                        <Stack spacing={1}>
                                            {[1, 2, 3].map(i => (
                                                <Skeleton key={i} variant="rectangular" height={56} sx={{ borderRadius: 1 }} />
                                            ))}
                                        </Stack>
                                    ) : waitingCustomers.length === 0 ? (
                                        <Typography color="text.secondary" sx={{ textAlign: 'center', py: 4 }}>
                                            No customers waiting
                                        </Typography>
                                    ) : (
                                        <List disablePadding>
                                            {waitingCustomers.slice(0, 10).map((item) => (
                                                <ListItem
                                                    key={item.id}
                                                    sx={{
                                                        borderBottom: '1px solid',
                                                        borderColor: 'divider',
                                                        py: 1.5,
                                                        px: 1,
                                                    }}
                                                    secondaryAction={
                                                        <Stack direction="row" spacing={0.5}>
                                                            <Tooltip title="Serve now">
                                                                <IconButton
                                                                    size="small"
                                                                    onClick={() => handleServeSpecific(item)}
                                                                    color="primary"
                                                                >
                                                                    <SkipNextIcon fontSize="small" />
                                                                </IconButton>
                                                            </Tooltip>
                                                            <Tooltip title="Remove">
                                                                <IconButton
                                                                    size="small"
                                                                    onClick={() => {
                                                                        setSelectedCustomer(item);
                                                                        setRemoveDialogOpen(true);
                                                                    }}
                                                                    color="error"
                                                                >
                                                                    <DeleteIcon fontSize="small" />
                                                                </IconButton>
                                                            </Tooltip>
                                                        </Stack>
                                                    }
                                                >
                                                    <Chip
                                                        label={`#${item.position}`}
                                                        size="small"
                                                        color="primary"
                                                        variant="outlined"
                                                        sx={{ mr: 2, minWidth: 40 }}
                                                    />
                                                    <ListItemText
                                                        primary={item.customer_name}
                                                        secondary={new Date(item.checked_in_at).toLocaleTimeString()}
                                                    />
                                                </ListItem>
                                            ))}
                                        </List>
                                    )}
                                </CardContent>
                            </Card>
                        </Grid>
                    </Grid>
                </Stack>
                ) : null
            )}

            {/* ─── My Pay tab ─── */}
            {currentTab === 1 && (
                <Box>
                    {payslipsLoading ? (
                        <Box display="flex" justifyContent="center" py={6}><CircularProgress /></Box>
                    ) : payslips.length === 0 ? (
                        <Paper variant="outlined" sx={{ p: 4, borderRadius: 3, textAlign: 'center' }}>
                            <PaymentsIcon sx={{ fontSize: 48, color: 'text.disabled', mb: 1 }} />
                            <Typography color="text.secondary">No payslips available yet. Your employer will generate them after each pay period.</Typography>
                        </Paper>
                    ) : (
                        <Grid container spacing={2}>
                            {payslips.map((slip: any) => (
                                <Grid size={{ xs: 12, md: 6 }} key={slip.id}>
                                    <Card variant="outlined" sx={{ borderRadius: 3 }}>
                                        <CardContent>
                                            <Stack direction="row" justifyContent="space-between" alignItems="flex-start" mb={1}>
                                                <Box>
                                                    <Typography variant="subtitle1" fontWeight={700}>{slip.shop_name || 'Your Shop'}</Typography>
                                                    <Typography variant="body2" color="text.secondary">
                                                        {slip.period_start} – {slip.period_end}
                                                    </Typography>
                                                    <Typography variant="caption" color="text.secondary">
                                                        Pay date: {slip.pay_date || '—'}
                                                    </Typography>
                                                </Box>
                                                <Chip
                                                    label={slip.status || 'draft'}
                                                    size="small"
                                                    color={slip.status === 'approved' ? 'success' : slip.status === 'paid' ? 'primary' : 'default'}
                                                />
                                            </Stack>
                                            <Divider sx={{ my: 1.5 }} />
                                            <Grid container spacing={1}>
                                                <Grid size={6}>
                                                    <Typography variant="caption" color="text.secondary">Gross Pay</Typography>
                                                    <Typography fontWeight={600}>${parseFloat(slip.gross_pay || 0).toFixed(2)}</Typography>
                                                </Grid>
                                                <Grid size={6}>
                                                    <Typography variant="caption" color="text.secondary">Net Pay</Typography>
                                                    <Typography fontWeight={700} color="success.main">${parseFloat(slip.net_pay || 0).toFixed(2)}</Typography>
                                                </Grid>
                                                <Grid size={6}>
                                                    <Typography variant="caption" color="text.secondary">CPP</Typography>
                                                    <Typography variant="body2">${parseFloat(slip.cpp_deduction || 0).toFixed(2)}</Typography>
                                                </Grid>
                                                <Grid size={6}>
                                                    <Typography variant="caption" color="text.secondary">EI</Typography>
                                                    <Typography variant="body2">${parseFloat(slip.ei_deduction || 0).toFixed(2)}</Typography>
                                                </Grid>
                                                <Grid size={6}>
                                                    <Typography variant="caption" color="text.secondary">Federal Tax</Typography>
                                                    <Typography variant="body2">${parseFloat(slip.fed_tax || 0).toFixed(2)}</Typography>
                                                </Grid>
                                                <Grid size={6}>
                                                    <Typography variant="caption" color="text.secondary">Provincial Tax</Typography>
                                                    <Typography variant="body2">${parseFloat(slip.prov_tax || 0).toFixed(2)}</Typography>
                                                </Grid>
                                            </Grid>
                                            <Divider sx={{ my: 1.5 }} />
                                            <Button
                                                fullWidth
                                                variant="outlined"
                                                size="small"
                                                startIcon={<DownloadIcon />}
                                                onClick={() => handleDownloadMyPayslipPdf(slip.id, slip.period_start)}
                                                sx={{ borderRadius: 2 }}
                                            >
                                                Download PDF
                                            </Button>
                                        </CardContent>
                                    </Card>
                                </Grid>
                            ))}
                        </Grid>
                    )}
                </Box>
            )}

            {/* Photo Upload Dialog */}
            <ProfilePhotoUploader
                open={photoDialogOpen}
                onClose={() => setPhotoDialogOpen(false)}
                onUpload={handleUploadPhoto}
            />

            {/* Add Walk-in Dialog */}
            <Dialog open={addDialogOpen} onClose={() => setAddDialogOpen(false)} PaperProps={{ sx: { borderRadius: 3 } }}>
                <DialogTitle>Add Walk-in Customer</DialogTitle>
                <DialogContent>
                    <TextField
                        autoFocus
                        margin="dense"
                        label="Customer Name"
                        fullWidth
                        value={newCustomerName}
                        onChange={(e) => setNewCustomerName(e.target.value)}
                        placeholder="e.g. John Doe"
                    />
                    <TextField
                        margin="dense"
                        label="Phone (Optional)"
                        fullWidth
                        value={newCustomerPhone}
                        onChange={(e) => setNewCustomerPhone(e.target.value)}
                    />
                    <FormControl fullWidth margin="dense" sx={{ mt: 2 }}>
                        <InputLabel id="walkin-service-label">Service (Optional)</InputLabel>
                        <Select
                            labelId="walkin-service-label"
                            value={selectedServiceId}
                            label="Service (Optional)"
                            onChange={(e) => setSelectedServiceId(e.target.value as number)}
                        >
                            <MenuItem value=""><em>None</em></MenuItem>
                            {services.map((s) => (
                                <MenuItem key={s.id} value={s.id}>
                                    {s.name} - ${s.cost}
                                </MenuItem>
                            ))}
                        </Select>
                    </FormControl>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setAddDialogOpen(false)}>Cancel</Button>
                    <Button onClick={handleAddWalkIn} variant="contained" disabled={!newCustomerName.trim()} sx={{ borderRadius: 3 }}>Add</Button>
                </DialogActions>
            </Dialog>

            {/* Remove Customer Dialog */}
            <Dialog open={removeDialogOpen} onClose={() => setRemoveDialogOpen(false)} PaperProps={{ sx: { borderRadius: 3 } }}>
                <DialogTitle>Remove Customer from Queue</DialogTitle>
                <DialogContent>
                    <Typography variant="body1" sx={{ mb: 2 }}>
                        Why are you removing <strong>{selectedCustomer?.customer_name}</strong>?
                    </Typography>
                    <TextField
                        fullWidth
                        multiline
                        rows={3}
                        label="Reason for removal"
                        value={removeReason}
                        onChange={(e) => setRemoveReason(e.target.value)}
                        placeholder="e.g., Did not appear when called, Left the premises, etc."
                        sx={{ mt: 2 }}
                    />
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => {
                        setRemoveDialogOpen(false);
                        setSelectedCustomer(null);
                        setRemoveReason('');
                    }}>Cancel</Button>
                    <Button
                        onClick={handleRemoveCustomer}
                        variant="contained"
                        color="error"
                        disabled={!removeReason.trim()}
                        sx={{ borderRadius: 3 }}
                    >
                        Remove
                    </Button>
                </DialogActions>
            </Dialog>

            {/* Serve Customer Confirmation Dialog */}
            <Dialog open={serveConfirmCustomer !== null} onClose={() => setServeConfirmCustomer(null)} PaperProps={{ sx: { borderRadius: 3 } }}>
                <DialogTitle>Serve Customer Out of Order</DialogTitle>
                <DialogContent>
                    <Typography>
                        Serve <strong>{serveConfirmCustomer?.customer_name}</strong> now, skipping ahead in the queue?
                    </Typography>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setServeConfirmCustomer(null)}>Cancel</Button>
                    <Button variant="contained" onClick={confirmServeSpecific} sx={{ borderRadius: 3 }}>
                        Serve Now
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
};

export default EmployeeQueuePage;
