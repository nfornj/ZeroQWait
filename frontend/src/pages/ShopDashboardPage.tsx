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
    Paper,
    IconButton,
    Avatar,
} from '@mui/material';
import LaunchIcon from '@mui/icons-material/Launch';
import TvIcon from '@mui/icons-material/Tv';
import PersonIcon from '@mui/icons-material/Person';
import SettingsIcon from '@mui/icons-material/Settings';
import StoreIcon from '@mui/icons-material/Store';
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
            if (!token) {
                navigate('/login');
                return;
            }

            const response = await axios.get(`/shops/my-shops`, {
                headers: { Authorization: `Bearer ${token}` },
            });

            setShops(response.data);
            if (response.data.length > 0) {
                setSelectedShop(response.data[0]);
            }
            setLoading(false);
        } catch (err: any) {
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
            console.error('Failed to fetch queue');
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
            console.log('Fetched employees:', response.data);
            setEmployees(response.data);
        } catch (err) {
            console.error('Failed to fetch employees:', err);
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
            {/* Dashboard Header & Actions */}
            <Box sx={{ bgcolor: 'background.paper', borderBottom: '1px solid rgba(0,0,0,0.08)', py: 2, mb: 3 }}>
                <Container maxWidth="lg">
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <Typography variant="h5" sx={{ fontWeight: 700, color: 'text.primary' }}>
                            Overview
                        </Typography>
                        <Box sx={{ display: 'flex', gap: 1 }}>
                            <Button
                                variant="outlined"
                                startIcon={<LaunchIcon />}
                                onClick={() => window.open(`/queue/${selectedShop?.id}`, '_blank')}
                                disabled={!selectedShop}
                                size="small"
                            >
                                Public View
                            </Button>
                            <Button
                                variant="outlined"
                                startIcon={<TvIcon />}
                                onClick={() => window.open(`/display/${selectedShop?.id}`, '_blank')}
                                disabled={!selectedShop}
                                size="small"
                            >
                                TV Mode
                            </Button>
                            <Button
                                variant="contained"
                                startIcon={<SettingsIcon />}
                                onClick={() => navigate('/settings')}
                                disabled={!selectedShop}
                                size="small"
                                sx={{ bgcolor: selectedShop?.primary_color }}
                            >
                                Settings
                            </Button>
                        </Box>
                    </Box>
                </Container>
            </Box>

            <Container maxWidth="lg" sx={{ pb: 4 }}>
            {/* Mobile Actions (Visible only on small screens) */}
            {selectedShop && (
                <Box sx={{ display: { xs: 'flex', md: 'none' }, gap: 1, mb: 3, flexWrap: 'wrap' }}>
                    <Button
                        fullWidth
                        variant="outlined"
                        startIcon={<LaunchIcon />}
                        onClick={() => window.open(`/queue/${selectedShop.id}`, '_blank')}
                    >
                        Public View
                    </Button>
                    <Button
                        fullWidth
                        variant="outlined"
                        startIcon={<TvIcon />}
                        onClick={() => window.open(`/display/${selectedShop.id}`, '_blank')}
                    >
                        TV Mode
                    </Button>
                </Box>
            )}

            {error && (
                <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
                    {error}
                </Alert>
            )}

            <Grid container spacing={3}>
                {/* Currently Being Served */}
                <Grid item xs={12} md={6}>
                    <Card>
                        <CardContent>
                            <Typography variant="h6" gutterBottom>
                                Being Served
                            </Typography>
                            <Divider sx={{ mb: 2 }} />
                            {beingServed.length === 0 ? (
                                <Typography color="textSecondary">No one being served</Typography>
                            ) : (
                                <List>
                                    {beingServed.map((item) => (
                                        <ListItem
                                            key={item.id}
                                            sx={{
                                                bgcolor: 'info.light',
                                                borderRadius: 2,
                                                mb: 1,
                                            }}
                                        >
                                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flex: 1 }}>
                                                {item.assigned_employee && (
                                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                                        <Avatar
                                                            src={item.assigned_employee.profile_photo_url}
                                                            sx={{ width: 32, height: 32, bgcolor: 'primary.main' }}
                                                        >
                                                            {item.assigned_employee.username.charAt(0).toUpperCase()}
                                                        </Avatar>
                                                    </Box>
                                                )}
                                                <ListItemText
                                                    primary={item.customer_name}
                                                    secondary={
                                                        <>
                                                            {item.customer_phone && <div>{item.customer_phone}</div>}
                                                            {item.assigned_employee && (
                                                                <Box display="flex" alignItems="center" gap={0.5} mt={0.5}>
                                                                    <PersonIcon sx={{ fontSize: 14 }} />
                                                                    <Typography variant="caption">
                                                                        Served by {item.assigned_employee.username}
                                                                    </Typography>
                                                                </Box>
                                                            )}
                                                        </>
                                                    }
                                                />
                                            </Box>
                                            <Button
                                                variant="contained"
                                                color="success"
                                                onClick={() => handleCompleteCustomer(item.id)}
                                            >
                                                Complete
                                            </Button>
                                        </ListItem>
                                    ))}
                                </List>
                            )}
                        </CardContent>
                    </Card>
                </Grid>

                {/* Queue */}
                <Grid item xs={12} md={6}>
                    <Card>
                        <CardContent>
                            <Box display="flex" justifyContent="space-between" alignItems="center">
                                <Typography variant="h6">
                                    Waiting Queue ({waitingCustomers.length})
                                </Typography>
                                <Button
                                    variant="contained"
                                    color="primary"
                                    onClick={handleCallNext}
                                    disabled={waitingCustomers.length === 0}
                                >
                                    Call Next
                                </Button>
                            </Box>
                            <Divider sx={{ my: 2 }} />
                            {waitingCustomers.length === 0 ? (
                                <Typography color="textSecondary">Queue is empty</Typography>
                            ) : (
                                <List>
                                    {waitingCustomers.map((item, index) => (
                                        <ListItem
                                            key={item.id}
                                            sx={{
                                                bgcolor: index === 0 ? 'warning.light' : 'grey.100',
                                                borderRadius: 2,
                                                mb: 1,
                                            }}
                                        >
                                            <Box sx={{ mr: 2, fontWeight: 'bold' }}>#{item.position}</Box>
                                            <ListItemText
                                                primary={item.customer_name}
                                                secondary={
                                                    <>
                                                        {item.customer_phone && <div>{item.customer_phone}</div>}
                                                        {item.notes && <div>Note: {item.notes}</div>}
                                                    </>
                                                }
                                            />
                                            <Chip
                                                label={item.status}
                                                color={getStatusColor(item.status) as any}
                                                size="small"
                                            />
                                        </ListItem>
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
        </Box>
    );
};

export default ShopDashboardPage;
