import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import {
    Container,
    Box,
    Typography,
    Card,
    CardContent,
    Grid,
    Chip,
    Avatar,
    CircularProgress,
    Alert,
    Paper,
    Divider,
} from '@mui/material';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import PeopleIcon from '@mui/icons-material/People';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import axios from 'axios';


interface Shop {
    id: number;
    name: string;
    description?: string;
    shop_type: string;
    address: string;
    city: string;
    state: string;
    phone: string;
    average_service_time: number;
    logo_url?: string;
    primary_color?: string;
}

interface QueueItem {
    id: number;
    customer_name: string;
    position: number;
    status: string;
    checked_in_at: string;
    service_started_at?: string;
    assigned_employee?: {
        id: number;
        username: string;
        email: string;
        profile_photo_url?: string;
    };
}

interface Queue {
    id: number;
    shop_id: number;
    name: string;
    queue_items: QueueItem[];
}

const InShopDisplayPage: React.FC = () => {
    const { shopId } = useParams<{ shopId: string }>();
    const [shop, setShop] = useState<Shop | null>(null);
    const [queue, setQueue] = useState<Queue | null>(null);
    const [loading, setLoading] = useState(true);
    const [currentTime, setCurrentTime] = useState(new Date());

    useEffect(() => {
        if (shopId) {
            fetchShop();
            fetchQueue();
            // Refresh queue every 3 seconds for real-time updates
            const queueInterval = setInterval(fetchQueue, 3000);
            // Update clock every second
            const clockInterval = setInterval(() => setCurrentTime(new Date()), 1000);

            return () => {
                clearInterval(queueInterval);
                clearInterval(clockInterval);
            };
        }
    }, [shopId]);

    const fetchShop = async () => {
        try {
            const response = await axios.get(`/shops/${shopId}`);
            setShop(response.data);
            setLoading(false);
        } catch (err) {
            setLoading(false);
        }
    };

    const fetchQueue = async () => {
        try {
            // Try to get token from localStorage for authenticated display
            // This allows shop staff to see full customer names on the in-shop display
            const token = localStorage.getItem('token');
            const config = token ? {
                headers: { Authorization: `Bearer ${token}` }
            } : {};

            const response = await axios.get(`/queues/shop/${shopId}/active`, config);
            setQueue(response.data);
        } catch (err) {
            // Silently fail - retry on next interval
        }
    };

    const waitingCustomers = queue?.queue_items.filter(
        (item) => item.status === 'waiting'
    ) || [];

    const servingCustomers = queue?.queue_items.filter(
        (item) => item.status === 'being_served'
    ) || [];

    const estimatedWaitTime = waitingCustomers.length * (shop?.average_service_time || 30);

    if (loading) {
        return (
            <Box display="flex" justifyContent="center" alignItems="center" minHeight="100vh">
                <CircularProgress size={80} />
            </Box>
        );
    }

    if (!shop) {
        return (
            <Container maxWidth="md" sx={{ mt: 8 }}>
                <Alert severity="error">Shop not found</Alert>
            </Container>
        );
    }

    const primaryColor = shop.primary_color || '#1976d2';

    return (
        <Box
            sx={{
                minHeight: '100vh',
                height: '100vh',
                bgcolor: '#f5f5f5',
                p: 3,
                overflow: 'hidden',
            }}
        >
            {/* Header */}
            <Paper
                elevation={3}
                sx={{
                    p: 2,
                    mb: 3,
                    bgcolor: primaryColor,
                    color: 'white',
                }}
            >
                <Grid container alignItems="center" spacing={2}>
                    <Grid item>
                        {shop.logo_url && (
                            <Avatar
                                src={shop.logo_url}
                                sx={{ width: 70, height: 70, border: '2px solid white' }}
                            />
                        )}
                    </Grid>
                    <Grid item xs>
                        <Typography variant="h3" fontWeight="bold">
                            {shop.name}
                        </Typography>
                        <Typography variant="h6" sx={{ opacity: 0.9, mt: 0.5 }}>
                            Queue Status
                        </Typography>
                    </Grid>
                    <Grid item>
                        <Typography variant="h4" fontWeight="bold" textAlign="right">
                            {currentTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </Typography>
                        <Typography variant="caption" textAlign="right" display="block">
                            {currentTime.toLocaleDateString([], { weekday: 'long', month: 'short', day: 'numeric' })}
                        </Typography>
                    </Grid>
                </Grid>
            </Paper>

            {/* Main Content */}
            <Grid container spacing={4}>
                {/* Now Serving Section */}
                <Grid item xs={12} md={5}>
                    <Card
                        elevation={3}
                        sx={{
                            minHeight: 400,
                            bgcolor: servingCustomers.length > 0 ? primaryColor : 'grey.300',
                            color: servingCustomers.length > 0 ? 'white' : 'text.secondary',
                        }}
                    >
                        <CardContent sx={{ p: 4 }}>
                            <Box display="flex" alignItems="center" mb={3}>
                                <CheckCircleIcon sx={{ fontSize: 50, mr: 2 }} />
                                <Typography variant="h3" fontWeight="bold">
                                    NOW SERVING
                                </Typography>
                            </Box>
                            <Divider sx={{ my: 3, bgcolor: servingCustomers.length > 0 ? 'white' : 'grey.500' }} />

                            {servingCustomers.length > 0 ? (
                                <Box textAlign="center" py={4}>
                                    {servingCustomers.map((customer) => (
                                        <Box key={customer.id} mb={3}>
                                            <Typography variant="h1" sx={{ fontSize: '8rem', fontWeight: 'bold' }}>
                                                #{customer.position}
                                            </Typography>
                                            <Typography variant="h4" sx={{ mt: 2, opacity: 0.9 }}>
                                                {customer.customer_name}
                                            </Typography>
                                            {customer.assigned_employee && (
                                                <Box display="flex" justifyContent="center" alignItems="center" gap={2} mt={3}>
                                                    <Avatar
                                                        src={customer.assigned_employee.profile_photo_url}
                                                        sx={{ width: 60, height: 60, border: '3px solid white' }}
                                                    >
                                                        {customer.assigned_employee.username.charAt(0).toUpperCase()}
                                                    </Avatar>
                                                    <Box textAlign="left">
                                                        <Typography variant="h6" sx={{ opacity: 0.8 }}>
                                                            Served by
                                                        </Typography>
                                                        <Typography variant="h5" fontWeight="bold">
                                                            {customer.assigned_employee.username}
                                                        </Typography>
                                                    </Box>
                                                </Box>
                                            )}
                                        </Box>
                                    ))}
                                </Box>
                            ) : (
                                <Box textAlign="center" py={6}>
                                    <Typography variant="h4" sx={{ opacity: 0.7 }}>
                                        No one being served
                                    </Typography>
                                    <Typography variant="h6" sx={{ mt: 2, opacity: 0.5 }}>
                                        {waitingCustomers.length > 0 ? 'Next customer will be called soon' : 'Queue is empty'}
                                    </Typography>
                                </Box>
                            )}
                        </CardContent>
                    </Card>
                </Grid>

                {/* Queue Information Section */}
                <Grid item xs={12} md={7}>
                    <Grid container spacing={3}>
                        {/* Queue Stats */}
                        <Grid item xs={12}>
                            <Card elevation={3}>
                                <CardContent sx={{ p: 4 }}>
                                    <Grid container spacing={3}>
                                        <Grid item xs={6}>
                                            <Box display="flex" alignItems="center">
                                                <PeopleIcon sx={{ fontSize: 60, mr: 2, color: primaryColor }} />
                                                <Box>
                                                    <Typography variant="h2" fontWeight="bold">
                                                        {waitingCustomers.length}
                                                    </Typography>
                                                    <Typography variant="h6" color="text.secondary">
                                                        In Queue
                                                    </Typography>
                                                </Box>
                                            </Box>
                                        </Grid>
                                        <Grid item xs={6}>
                                            <Box display="flex" alignItems="center">
                                                <AccessTimeIcon sx={{ fontSize: 60, mr: 2, color: primaryColor }} />
                                                <Box>
                                                    <Typography variant="h2" fontWeight="bold">
                                                        ~{estimatedWaitTime}
                                                    </Typography>
                                                    <Typography variant="h6" color="text.secondary">
                                                        Minutes Wait
                                                    </Typography>
                                                </Box>
                                            </Box>
                                        </Grid>
                                    </Grid>
                                </CardContent>
                            </Card>
                        </Grid>

                        {/* Waiting List */}
                        <Grid item xs={12}>
                            <Card elevation={3} sx={{ minHeight: 400 }}>
                                <CardContent sx={{ p: 4 }}>
                                    <Typography variant="h4" fontWeight="bold" gutterBottom>
                                        Waiting List
                                    </Typography>
                                    <Divider sx={{ mb: 3 }} />

                                    {waitingCustomers.length === 0 ? (
                                        <Box textAlign="center" py={6}>
                                            <Typography variant="h5" color="text.secondary">
                                                No one waiting
                                            </Typography>
                                            <Typography variant="body1" color="text.secondary" sx={{ mt: 2 }}>
                                                Queue is empty - you can walk in!
                                            </Typography>
                                        </Box>
                                    ) : (
                                        <Grid container spacing={2}>
                                            {waitingCustomers.slice(0, 8).map((customer, index) => (
                                                <Grid item xs={12} sm={6} key={customer.id}>
                                                    <Paper
                                                        elevation={1}
                                                        sx={{
                                                            p: 2,
                                                            bgcolor: index < 2 ? 'primary.light' : 'grey.100',
                                                            color: index < 2 ? 'white' : 'text.primary',
                                                            border: index < 2 ? `2px solid ${primaryColor}` : 'none',
                                                        }}
                                                    >
                                                        <Box display="flex" alignItems="center" justifyContent="space-between">
                                                            <Box display="flex" alignItems="center">
                                                                <Chip
                                                                    label={`#${customer.position}`}
                                                                    sx={{
                                                                        mr: 2,
                                                                        fontWeight: 'bold',
                                                                        fontSize: '1.2rem',
                                                                        bgcolor: index < 2 ? 'white' : primaryColor,
                                                                        color: index < 2 ? primaryColor : 'white',
                                                                    }}
                                                                />
                                                                <Typography variant="h6">
                                                                    {customer.customer_name}
                                                                </Typography>
                                                            </Box>
                                                            {index < 2 && (
                                                                <Chip
                                                                    label="Up Next"
                                                                    size="small"
                                                                    sx={{
                                                                        bgcolor: 'rgba(255,255,255,0.3)',
                                                                        color: 'white',
                                                                        fontWeight: 'bold',
                                                                    }}
                                                                />
                                                            )}
                                                        </Box>
                                                    </Paper>
                                                </Grid>
                                            ))}
                                            {waitingCustomers.length > 8 && (
                                                <Grid item xs={12}>
                                                    <Typography variant="h6" color="text.secondary" textAlign="center">
                                                        ... and {waitingCustomers.length - 8} more waiting
                                                    </Typography>
                                                </Grid>
                                            )}
                                        </Grid>
                                    )}
                                </CardContent>
                            </Card>
                        </Grid>
                    </Grid>
                </Grid>
            </Grid>

            {/* Footer */}
            <Paper
                elevation={3}
                sx={
                    {
                        mt: 3,
                        p: 2,
                        bgcolor: 'white',
                        textAlign: 'center',
                    }}
            >
                <Typography variant="h6" color="text.secondary">
                    📱 Join online at <strong style={{ color: primaryColor }}>nowait.app/{shop.id}</strong>
                </Typography>
            </Paper>
        </Box>
    );
};

export default InShopDisplayPage;
