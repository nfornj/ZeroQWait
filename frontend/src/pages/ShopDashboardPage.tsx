import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Container,
    Box,
    Typography,
    Card,
    CardContent,
    Button,
    List,
    ListItem,
    ListItemText,
    Chip,
    Grid,
    Divider,
    Alert,
    CircularProgress,
    Stack,
    MenuItem,
    Select,
    FormControl,
    InputLabel,
    ListItemAvatar,
    Avatar,
} from '@mui/material';
import LaunchIcon from '@mui/icons-material/Launch';
import TvIcon from '@mui/icons-material/Tv';
import PersonIcon from '@mui/icons-material/Person';
import SettingsIcon from '@mui/icons-material/Settings';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import PeopleIcon from '@mui/icons-material/People';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import axios from 'axios';
import EmployeeSelector from '../components/EmployeeSelector';


interface Shop {
    id: number;
    name: string;
    shop_type: string;
    address: string;
    city: string;
    state: string;
    logo_url?: string;
    primary_color?: string;
    secondary_color?: string;
    accent_color?: string;
    background_color?: string;
}

interface QueueItem {
    id: number;
    customer_name: string;
    customer_phone?: string;
    position: number;
    status: string;
    checked_in_at: string;
    notes?: string;
    assigned_employee_id?: number;
    assigned_employee?: {
        id: number;
        username: string;
        email: string;
        profile_photo_url?: string;
    };
}

interface Employee {
    user_id: number;
    username: string;
    email: string;
    profile_photo_url?: string;
    clock_in: string;
}

interface Queue {
    id: number;
    shop_id: number;
    is_active: boolean;
    queue_items: QueueItem[];
}

const ShopDashboardPage: React.FC = () => {
    const navigate = useNavigate();
    const [shops, setShops] = useState<Shop[]>([]);
    const [selectedShop, setSelectedShop] = useState<Shop | null>(null);
    const [queue, setQueue] = useState<Queue | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [employees, setEmployees] = useState<Employee[]>([]);
    const [employeeSelectorOpen, setEmployeeSelectorOpen] = useState(false);
    const [loadingEmployees, setLoadingEmployees] = useState(false);

    useEffect(() => {
        console.log("[ShopDashboardPage] Mounted");
        fetchShops();
    }, []);

    useEffect(() => {
        if (selectedShop) {
            fetchQueue();
            fetchClockedInEmployees();
            const interval = setInterval(() => {
                fetchQueue();
                fetchClockedInEmployees();
            }, 5000); // Refresh every 5 seconds
            return () => clearInterval(interval);
        }
    }, [selectedShop]);

    const fetchShops = async () => {
        try {
            const token = localStorage.getItem('token');
            console.log("[ShopDashboardPage] fetchShops - token exists:", !!token);
            if (!token) {
                console.log("[ShopDashboardPage] No token, redirecting to login");
                navigate('/login');
                return;
            }

            console.log("[ShopDashboardPage] Fetching shops...");
            const response = await axios.get(`/shops/my-shops`, {
                headers: { Authorization: `Bearer ${token}` },
            });

            console.log("[ShopDashboardPage] Shops received:", response.data);
            setShops(response.data);
            if (response.data.length > 0) {
                console.log("[ShopDashboardPage] Setting selected shop:", response.data[0]);
                setSelectedShop(response.data[0]);
            } else {
                console.log("[ShopDashboardPage] No shops found");
            }
            setLoading(false);
        } catch (err: any) {
            console.error("[ShopDashboardPage] Error loading shops:", err.response?.status, err.response?.data);
            setError('Failed to load shops');
            setLoading(false);
        }
    };

    const fetchQueue = async () => {
        if (!selectedShop) return;

        try {
            const token = localStorage.getItem('token');
            const response = await axios.get(
                `/queues/shop/${selectedShop.id}/active`,
                {
                    headers: { Authorization: `Bearer ${token}` },
                }
            );
            setQueue(response.data);
        } catch (err) {
            // Silently fail - retry on next interval
        }
    };

    const fetchClockedInEmployees = async () => {
        if (!selectedShop) return;

        try {
            const token = localStorage.getItem('token');
            const response = await axios.get(
                `/shops/${selectedShop.id}/clocked-in`,
                {
                    headers: { Authorization: `Bearer ${token}` },
                }
            );
            setEmployees(response.data);
        } catch (err) {
            // Silently fail - retry on next interval
        }
    };

    const handleCallNext = async () => {
        if (!queue) return;
        // Fetch latest employee list before opening dialog
        setLoadingEmployees(true);
        await fetchClockedInEmployees();
        setLoadingEmployees(false);
        setEmployeeSelectorOpen(true);
    };

    const handleEmployeeSelected = async (employeeId: number | null) => {
        if (!queue) return;

        try {
            const token = localStorage.getItem('token');
            const params = employeeId ? { employee_id: employeeId } : {};
            await axios.post(
                `/queues/${queue.id}/call-next`,
                {},
                {
                    headers: { Authorization: `Bearer ${token}` },
                    params: params,
                }
            );
            fetchQueue();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to call next customer');
        }
    };

    const handleCompleteCustomer = async (itemId: number) => {
        try {
            const token = localStorage.getItem('token');
            await axios.patch(
                `/queues/items/${itemId}/status?new_status=completed`,
                {},
                {
                    headers: { Authorization: `Bearer ${token}` },
                }
            );
            fetchQueue();
        } catch (err) {
            setError('Failed to update customer status');
        }
    };

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'waiting':
                return 'warning';
            case 'being_served':
                return 'info';
            case 'completed':
                return 'success';
            default:
                return 'default';
        }
    };

    const waitingCustomers = queue?.queue_items.filter(
        (item) => item.status === 'waiting'
    ) || [];
    const beingServed = queue?.queue_items.filter(
        (item) => item.status === 'being_served'
    ) || [];

    if (loading) {
        return (
            <Box display="flex" justifyContent="center" alignItems="center" minHeight="80vh">
                <CircularProgress />
            </Box>
        );
    }

    if (shops.length === 0) {
        return (
            <Container maxWidth="md" sx={{ mt: 8 }}>
                <Alert severity="info">
                    You don't have any shops yet.{' '}
                    <Button color="primary" onClick={() => navigate('/register-shop')}>
                        Create one now
                    </Button>
                </Alert>
            </Container>
        );
    }

    return (
        <Box sx={{ bgcolor: 'background.default', minHeight: '100vh' }}>
            <Container maxWidth="xl" sx={{ pb: 4, pt: 2 }}>
                {/* Header Section */}
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
                    <Box>
                        <Typography variant="h4" fontWeight={700} sx={{ mb: 0.5 }}>
                            Dashboard
                        </Typography>
                        <Typography variant="body1" color="text.secondary">
                            Overview for {selectedShop?.name} • {new Date().toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
                        </Typography>
                    </Box>
                    <Stack direction="row" spacing={2}>
                        <Button
                            variant="outlined"
                            startIcon={<LaunchIcon />}
                            onClick={() => window.open(`/queue/${selectedShop?.id}`, '_blank')}
                            disabled={!selectedShop}
                        >
                            Public View
                        </Button>
                        <Button
                            variant="outlined"
                            startIcon={<TvIcon />}
                            onClick={() => window.open(`/display/${selectedShop?.id}`, '_blank')}
                            disabled={!selectedShop}
                        >
                            TV Mode
                        </Button>
                        <Button
                            variant="contained"
                            startIcon={<SettingsIcon />}
                            onClick={() => navigate('/settings')}
                            disabled={!selectedShop}
                            sx={{ bgcolor: selectedShop?.primary_color }}
                        >
                            Settings
                        </Button>
                    </Stack>
                </Box>

                {error && (
                    <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError('')}>
                        {error}
                    </Alert>
                )}

                {/* KPI Cards Row */}
                <Grid container spacing={3} sx={{ mb: 4 }}>
                    <Grid xs={12} sm={6} md={3}>
                        <Card sx={{ height: '100%' }}>
                            <CardContent>
                                <Typography color="textSecondary" gutterBottom variant="overline">
                                    Waiting Now
                                </Typography>
                                <Typography variant="h3" fontWeight="bold">
                                    {waitingCustomers.length}
                                </Typography>
                                <Box sx={{ display: 'flex', alignItems: 'center', mt: 1, color: 'text.secondary' }}>
                                    <PeopleIcon fontSize="small" sx={{ mr: 0.5 }} />
                                    <Typography variant="body2">Customers in queue</Typography>
                                </Box>
                            </CardContent>
                        </Card>
                    </Grid>
                    <Grid xs={12} sm={6} md={3}>
                        <Card sx={{ height: '100%' }}>
                            <CardContent>
                                <Typography color="textSecondary" gutterBottom variant="overline">
                                    Being Served
                                </Typography>
                                <Typography variant="h3" fontWeight="bold">
                                    {beingServed.length}
                                </Typography>
                                <Box sx={{ display: 'flex', alignItems: 'center', mt: 1, color: 'success.main' }}>
                                    <CheckCircleIcon fontSize="small" sx={{ mr: 0.5 }} />
                                    <Typography variant="body2">Currently active</Typography>
                                </Box>
                            </CardContent>
                        </Card>
                    </Grid>
                    <Grid xs={12} sm={6} md={3}>
                        <Card sx={{ height: '100%' }}>
                            <CardContent>
                                <Typography color="textSecondary" gutterBottom variant="overline">
                                    Staff Active
                                </Typography>
                                <Typography variant="h3" fontWeight="bold">
                                    {employees.length}
                                </Typography>
                                <Box sx={{ display: 'flex', alignItems: 'center', mt: 1, color: 'info.main' }}>
                                    <PersonIcon fontSize="small" sx={{ mr: 0.5 }} />
                                    <Typography variant="body2">Clocked in</Typography>
                                </Box>
                            </CardContent>
                        </Card>
                    </Grid>
                    {/* Placeholder for future stat or quick action */}
                    <Grid xs={12} sm={6} md={3}>
                        <Card sx={{ height: '100%', bgcolor: 'primary.main', color: 'primary.contrastText' }}>
                            <CardContent sx={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', height: '100%' }}>
                                <Button
                                    color="inherit"
                                    variant="outlined"
                                    onClick={handleCallNext}
                                    disabled={waitingCustomers.length === 0}
                                    sx={{ borderColor: 'rgba(255,255,255,0.5)', borderWidth: 2, '&:hover': { borderColor: 'white', bgcolor: 'rgba(255,255,255,0.1)' } }}
                                >
                                    Call Next Customer
                                </Button>
                            </CardContent>
                        </Card>
                    </Grid>
                </Grid>

                <Grid container spacing={3}>
                    {/* Currently Being Served */}
                    <Grid xs={12} md={6}>
                        <Card sx={{ height: '100%' }}>
                            <CardContent>
                                <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                                    <CheckCircleIcon color="success" sx={{ mr: 1 }} />
                                    <Typography variant="h6" fontWeight={600}>
                                        Being Served
                                    </Typography>
                                </Box>
                                <Divider sx={{ mb: 2 }} />
                                {beingServed.length === 0 ? (
                                    <Box sx={{ py: 4, textAlign: 'center', color: 'text.secondary', bgcolor: 'action.hover', borderRadius: 2 }}>
                                        <Typography>No one is currently being served</Typography>
                                    </Box>
                                ) : (
                                    <List disablePadding>
                                        {beingServed.map((item, index) => (
                                            <React.Fragment key={item.id}>
                                                {index > 0 && <Divider component="li" />}
                                                <ListItem
                                                    sx={{
                                                        py: 2,
                                                        px: 0,
                                                    }}
                                                >
                                                    <ListItemAvatar>
                                                        <Avatar sx={{ bgcolor: 'success.light', color: 'success.dark' }}>
                                                            {item.customer_name.charAt(0).toUpperCase()}
                                                        </Avatar>
                                                    </ListItemAvatar>
                                                    <ListItemText
                                                        primary={
                                                            <Typography variant="subtitle1" fontWeight={600}>
                                                                {item.customer_name}
                                                            </Typography>
                                                        }
                                                        secondary={
                                                            <Box sx={{ mt: 0.5 }}>
                                                                {item.customer_phone && (
                                                                    <Typography variant="body2" color="text.secondary" component="span" display="block">
                                                                        {item.customer_phone}
                                                                    </Typography>
                                                                )}
                                                                {item.assigned_employee && (
                                                                    <Box display="flex" alignItems="center" gap={0.5} mt={0.5}>
                                                                        <Chip
                                                                            avatar={<Avatar src={item.assigned_employee.profile_photo_url}>{item.assigned_employee.username.charAt(0)}</Avatar>}
                                                                            label={`Served by ${item.assigned_employee.username}`}
                                                                            size="small"
                                                                            variant="outlined"
                                                                        />
                                                                    </Box>
                                                                )}
                                                            </Box>
                                                        }
                                                    />
                                                    <Button
                                                        variant="text"
                                                        color="success"
                                                        onClick={() => handleCompleteCustomer(item.id)}
                                                    >
                                                        Complete
                                                    </Button>
                                                </ListItem>
                                            </React.Fragment>
                                        ))}
                                    </List>
                                )}
                            </CardContent>
                        </Card>
                    </Grid>

                    {/* Queue */}
                    <Grid xs={12} md={6}>
                        <Card sx={{ height: '100%' }}>
                            <CardContent>
                                <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                                        <PeopleIcon color="primary" sx={{ mr: 1 }} />
                                        <Typography variant="h6" fontWeight={600}>
                                            Waiting Queue
                                        </Typography>
                                        <Chip label={waitingCustomers.length} color="primary" size="small" sx={{ ml: 1.5, fontWeight: 'bold' }} />
                                    </Box>
                                </Box>
                                <Divider sx={{ mb: 2 }} />
                                {waitingCustomers.length === 0 ? (
                                    <Box sx={{ py: 4, textAlign: 'center', color: 'text.secondary', bgcolor: 'action.hover', borderRadius: 2 }}>
                                        <Typography>Queue is empty</Typography>
                                    </Box>
                                ) : (
                                    <List disablePadding>
                                        {waitingCustomers.map((item, index) => (
                                            <React.Fragment key={item.id}>
                                                {index > 0 && <Divider component="li" />}
                                                <ListItem
                                                    sx={{
                                                        py: 2,
                                                        px: 0,
                                                    }}
                                                    secondaryAction={
                                                        <Box sx={{ textAlign: 'right' }}>
                                                            <Typography variant="h6" color="primary.main" fontWeight="bold">
                                                                #{item.position}
                                                            </Typography>
                                                            <Typography variant="caption" color="text.secondary">
                                                                Position
                                                            </Typography>
                                                        </Box>
                                                    }
                                                >
                                                    <ListItemText
                                                        primary={
                                                            <Typography variant="subtitle1" fontWeight={600}>
                                                                {item.customer_name}
                                                            </Typography>
                                                        }
                                                        secondary={
                                                            <Box sx={{ mt: 0.5 }}>
                                                                {item.customer_phone && (
                                                                    <Typography variant="body2" color="text.secondary" noWrap>
                                                                        {item.customer_phone}
                                                                    </Typography>
                                                                )}
                                                                {item.notes && (
                                                                    <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic', mt: 0.5 }}>
                                                                        "{item.notes}"
                                                                    </Typography>
                                                                )}
                                                                <Box sx={{ mt: 1 }}>
                                                                    <Chip
                                                                        label="Waiting"
                                                                        size="small"
                                                                        sx={{ bgcolor: 'warning.light', color: 'warning.contrastText', fontWeight: 600, height: 24 }}
                                                                    />
                                                                </Box>
                                                            </Box>
                                                        }
                                                    />
                                                </ListItem>
                                            </React.Fragment>
                                        ))}
                                    </List>
                                )}
                            </CardContent>
                        </Card>
                    </Grid>
                </Grid>

                {/* Employee Selector Dialog */}
                <EmployeeSelector
                    open={employeeSelectorOpen}
                    employees={employees}
                    loading={loadingEmployees}
                    onClose={() => setEmployeeSelectorOpen(false)}
                    onSelect={handleEmployeeSelected}
                    title="Assign Employee to Customer"
                    allowRandom={true}
                />
            </Container>
        </Box >
    );
};

export default ShopDashboardPage;
