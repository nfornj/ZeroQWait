import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Container,
    Box,
    Typography,
    Grid,
    Stack,
    Alert,
    CircularProgress,
    Button,
} from '@mui/material';
import LaunchIcon from '@mui/icons-material/Launch';
import TvIcon from '@mui/icons-material/Tv';
import axios from 'axios';
import EmployeeSelector from '../components/EmployeeSelector';
import StatCard, { StatCardProps } from '../components/dashboard/StatCard';
import HighlightedCard from '../components/dashboard/HighlightedCard';

// Interfaces (Successively kept from original file)
interface Shop {
    id: number;
    name: string;
    primary_color?: string;
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
            }, 5000);
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
                { headers: { Authorization: `Bearer ${token}` }, }
            );
            setQueue(response.data);
        } catch (err) { }
    };

    const fetchClockedInEmployees = async () => {
        if (!selectedShop) return;
        try {
            const token = localStorage.getItem('token');
            const response = await axios.get(
                `/shops/${selectedShop.id}/clocked-in`,
                { headers: { Authorization: `Bearer ${token}` }, }
            );
            setEmployees(response.data);
        } catch (err) { }
    };

    const handleCallNext = async () => {
        if (!queue) return;
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
                { headers: { Authorization: `Bearer ${token}` }, params: params, }
            );
            fetchQueue();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to call next customer');
        }
    };

    const waitingCustomers = queue?.queue_items.filter(
        (item) => item.status === 'waiting'
    ) || [];
    const beingServed = queue?.queue_items.filter(
        (item) => item.status === 'being_served'
    ) || [];

    // Map real data to StatCards
    const statCards: StatCardProps[] = [
        {
            title: 'Waiting Now',
            value: waitingCustomers.length.toString(),
            interval: 'Real-time',
            trend: 'neutral', // Logic can be added to detect trend
            data: [4, 3, 5, 2, 8, 6, waitingCustomers.length] // Placeholder trend data
        },
        {
            title: 'Being Served',
            value: beingServed.length.toString(),
            interval: 'Real-time',
            trend: 'up',
            data: [1, 2, 1, 3, 2, 4, beingServed.length]
        },
        {
            title: 'Staff Active',
            value: employees.length.toString(),
            interval: 'Real-time',
            trend: 'neutral',
            data: [2, 2, 3, 2, 3, 3, employees.length]
        }
    ];

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
        <Box sx={{ width: '100%', maxWidth: { sm: '100%', md: '1700px' }, mx: 'auto', p: 3 }}>

            {/* Header Section */}
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
                <Box>
                    <Typography component="h1" variant="h4" fontWeight={600}>
                        Dashboard
                    </Typography>
                    <Typography variant="body1" color="text.secondary">
                        Overview for {selectedShop?.name}
                    </Typography>
                </Box>
                <Stack direction="row" spacing={2}>
                    <Button
                        variant="outlined"
                        startIcon={<LaunchIcon />}
                        onClick={() => window.open(`/queue/${selectedShop?.id}`, '_blank')}
                        disabled={!selectedShop}
                    >
                        Live Public View
                    </Button>
                    <Button
                        variant="outlined"
                        startIcon={<TvIcon />}
                        onClick={() => window.open(`/display/${selectedShop?.id}`, '_blank')}
                        disabled={!selectedShop}
                    >
                        TV Mode
                    </Button>
                </Stack>
            </Box>

            {/* Stat Cards Grid */}
            <Typography component="h2" variant="h6" sx={{ mb: 2 }}>
                Overview
            </Typography>
            <Grid container spacing={2} columns={12} sx={{ mb: 4 }}>
                {statCards.map((card, index) => (
                    <Grid item xs={12} sm={6} lg={3} key={index}>
                        <StatCard {...card} />
                    </Grid>
                ))}
                <Grid item xs={12} sm={6} lg={3}>
                    <HighlightedCard />
                </Grid>
            </Grid>

            {/* Quick Actions (Call Next) */}
            {/* We can put the 'Call Next' button inside a prominent card or keep it simple */}
            <Stack direction="row" spacing={2} sx={{ mb: 4 }}>
                <Button
                    variant="contained"
                    size="large"
                    onClick={handleCallNext}
                    disabled={waitingCustomers.length === 0}
                    sx={{ px: 4, py: 1.5, borderRadius: 2 }}
                >
                    Call Next Customer
                </Button>
            </Stack>

            <EmployeeSelector
                open={employeeSelectorOpen}
                employees={employees}
                loading={loadingEmployees}
                onClose={() => setEmployeeSelectorOpen(false)}
                onSelect={handleEmployeeSelected}
                title="Assign Employee to Customer"
                allowRandom={true}
            />
        </Box>
    );
};

export default ShopDashboardPage;
