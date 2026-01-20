import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import {
    Box,
    Typography,
    Card,
    CardContent,
    Chip,
    Avatar,
    CircularProgress,
    Alert,
    Paper,
    Divider,
    Stack,
    keyframes,
    useMediaQuery,
    useTheme
} from '@mui/material';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import PeopleIcon from '@mui/icons-material/People';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import axios from 'axios';
import { gradientPresets, GradientPreset } from '../contexts/ThemeContext';

// Define animations
const pulse = keyframes`
  0% { transform: scale(1); box-shadow: 0 0 0 0 rgba(255, 255, 255, 0.7); }
  70% { transform: scale(1.05); box-shadow: 0 0 0 10px rgba(255, 255, 255, 0); }
  100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(255, 255, 255, 0); }
`;

const fadeIn = keyframes`
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
`;

interface Shop {
    id: number;
    name: string;
    description?: string;
    shop_type: string;
    address: string;
    city: string;
    state: string;
    phone: string;
    slug?: string;
    average_service_time: number;
    logo_url?: string;
    primary_color?: string;
    dashboard_gradient?: GradientPreset;
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
    const [error, setError] = useState<string | null>(null);
    const theme = useTheme();
    const isMdUp = useMediaQuery(theme.breakpoints.up('md'));

    useEffect(() => {
        fetchShopData();

        // Refresh queue every 3 seconds for real-time updates
        const queueInterval = setInterval(fetchQueueData, 3000);
        // Update clock every second
        const clockInterval = setInterval(() => setCurrentTime(new Date()), 1000);

        return () => {
            clearInterval(queueInterval);
            clearInterval(clockInterval);
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [shopId]);

    const fetchShopData = async () => {
        try {
            let response;
            const hostname = window.location.hostname;
            const isSubdomain = hostname.includes('.') && !hostname.includes('localhost') && !hostname.includes('127.0.0.1');

            if (isSubdomain) {
                const slug = hostname.split('.')[0];
                response = await axios.get(`/shops/public/${slug}`);
            } else if (shopId) {
                // Determine if shopId is a slug or an ID
                const isSlug = isNaN(Number(shopId));
                if (isSlug) {
                    response = await axios.get(`/shops/public/${shopId}`);
                } else {
                    response = await axios.get(`/shops/${shopId}`);
                }
            } else {
                throw new Error("No shop identifier found");
            }

            setShop(response.data);
            if (response.data.id) {
                fetchQueueForShop(response.data.id);
            }
            setLoading(false);
        } catch (err) {
            console.error(err);
            setError("Could not load shop data.");
            setLoading(false);
        }
    };

    const fetchQueueData = () => {
        if (shop?.id) {
            fetchQueueForShop(shop.id);
        }
    };

    const fetchQueueForShop = async (id: number) => {
        try {
            const token = localStorage.getItem('token');
            const config = token ? { headers: { Authorization: `Bearer ${token}` } } : {};
            const response = await axios.get(`/queues/shop/${id}/active`, config);
            setQueue(response.data);
        } catch (err) {
            // Silently fail on refresh
        }
    };

    const waitingCustomers = queue?.queue_items.filter(item => item.status === 'waiting') || [];
    const servingCustomers = queue?.queue_items.filter(item => item.status === 'being_served') || [];
    const estimatedWaitTime = waitingCustomers.length * (shop?.average_service_time || 30);
    const primaryColor = shop?.primary_color || '#1976d2';

    // Determine background gradient
    const gradientKey = shop?.dashboard_gradient || 'violet';
    const bgGradient = gradientPresets[gradientKey]?.light || gradientPresets.violet.light;

    if (loading) {
        return (
            <Box display="flex" justifyContent="center" alignItems="center" minHeight="100vh" sx={{ background: bgGradient }}>
                <CircularProgress sx={{ color: 'white' }} size={80} />
            </Box>
        );
    }

    if (error || !shop) {
        return (
            <Box display="flex" justifyContent="center" alignItems="center" minHeight="100vh" sx={{ background: bgGradient }}>
                <Alert severity="error" variant="filled">{error || "Shop not found"}</Alert>
            </Box>
        );
    }

    return (
        <Box
            sx={{
                minHeight: '100vh',
                height: '100vh',
                background: bgGradient,
                backgroundSize: 'cover',
                backgroundAttachment: 'fixed',
                p: { xs: 2, md: 4 },
                overflow: 'hidden',
                display: 'flex',
                flexDirection: 'column',
                color: '#1a1a1a',
            }}
        >
            {/* Glassmorphic Header */}
            <Paper
                component="header"
                elevation={4}
                sx={{
                    p: 2,
                    mb: 3,
                    borderRadius: 3,
                    background: 'rgba(255, 255, 255, 0.85)',
                    backdropFilter: 'blur(12px)',
                    border: '1px solid rgba(255, 255, 255, 0.3)',
                    boxShadow: '0 8px 32px 0 rgba(31, 38, 135, 0.1)',
                }}
            >
                <Stack direction="row" alignItems="center" justifyContent="space-between">
                    <Stack direction="row" alignItems="center" spacing={3}>
                        {shop.logo_url && (
                            <Avatar
                                src={shop.logo_url}
                                sx={{ width: 80, height: 80, border: `3px solid ${primaryColor}`, boxShadow: 2 }}
                            />
                        )}
                        <Box>
                            <Typography variant="h3" fontWeight="900" sx={{ background: `linear-gradient(45deg, ${primaryColor}, #333)`, WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                                {shop.name}
                            </Typography>
                            <Typography variant="h6" color="text.secondary" fontWeight="500">
                                Queue Status
                            </Typography>
                        </Box>
                    </Stack>
                    <Box textAlign="right">
                        <Typography variant="h3" fontWeight="bold" sx={{ fontFamily: 'monospace' }}>
                            {currentTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </Typography>
                        <Stack direction="row" alignItems="center" justifyContent="flex-end" spacing={1}>
                            <Box sx={{ width: 10, height: 10, borderRadius: '50%', bgcolor: 'success.main', boxShadow: '0 0 10px #2e7d32' }} />
                            <Typography variant="subtitle1" fontWeight="500" color="success.main">
                                Live
                            </Typography>
                        </Stack>
                    </Box>
                </Stack>
            </Paper>

            {/* Main Content Flex Layout (Replacing Grid) */}
            <Box sx={{ display: 'flex', flexDirection: { xs: 'column', md: 'row' }, gap: 3, flex: 1, overflow: 'hidden' }}>

                {/* Left Column: Now Serving */}
                <Box sx={{ width: { xs: '100%', md: '40%' }, height: '100%' }}>
                    <Card
                        elevation={6}
                        sx={{
                            height: '100%',
                            borderRadius: 4,
                            background: servingCustomers.length > 0 ? `linear-gradient(135deg, ${primaryColor}, #111)` : 'rgba(255, 255, 255, 0.8)',
                            backdropFilter: 'blur(10px)',
                            color: servingCustomers.length > 0 ? 'white' : 'text.primary',
                            display: 'flex',
                            flexDirection: 'column',
                            position: 'relative',
                            overflow: 'hidden',
                            transition: 'all 0.5s ease',
                        }}
                    >
                        <CardContent sx={{ flex: 1, display: 'flex', flexDirection: 'column', p: 4 }}>
                            <Stack direction="row" alignItems="center" spacing={2} mb={2}>
                                <CheckCircleIcon sx={{ fontSize: 40, color: servingCustomers.length > 0 ? '#4ade80' : 'text.secondary' }} />
                                <Typography variant="h4" fontWeight="800" letterSpacing={1}>
                                    NOW SERVING
                                </Typography>
                            </Stack>
                            <Divider sx={{ mb: 4, borderColor: 'rgba(255,255,255,0.2)' }} />

                            {servingCustomers.length > 0 ? (
                                <Stack spacing={4} alignItems="center" justifyContent="center" sx={{ flex: 1 }}>
                                    {servingCustomers.slice(0, 1).map((customer) => (
                                        <Box key={customer.id} textAlign="center" sx={{ animation: `${fadeIn} 0.5s ease-out` }}>
                                            <Box
                                                sx={{
                                                    display: 'inline-flex',
                                                    justifyContent: 'center',
                                                    alignItems: 'center',
                                                    width: 200,
                                                    height: 200,
                                                    borderRadius: '50%',
                                                    border: '8px solid white',
                                                    mb: 3,
                                                    animation: `${pulse} 2s infinite`,
                                                    bgcolor: 'rgba(255,255,255,0.1)'
                                                }}
                                            >
                                                <Typography variant="h1" fontWeight="900" sx={{ fontSize: '8rem' }}>
                                                    {customer.position}
                                                </Typography>
                                            </Box>
                                            <Typography variant="h3" fontWeight="bold" sx={{ textShadow: '0 2px 10px rgba(0,0,0,0.3)' }}>
                                                {customer.customer_name}
                                            </Typography>

                                            {customer.assigned_employee && (
                                                <Paper sx={{ mt: 4, p: 2, borderRadius: 3, bgcolor: 'rgba(255,255,255,0.15)', backdropFilter: 'blur(5px)', display: 'inline-flex', alignItems: 'center', gap: 2 }}>
                                                    <Avatar src={customer.assigned_employee.profile_photo_url} sx={{ width: 50, height: 50, border: '2px solid white' }} />
                                                    <Box textAlign="left">
                                                        <Typography variant="caption" display="block" sx={{ opacity: 0.8, textTransform: 'uppercase', letterSpacing: 1 }}>Served By</Typography>
                                                        <Typography variant="h6" fontWeight="bold">{customer.assigned_employee.username}</Typography>
                                                    </Box>
                                                </Paper>
                                            )}
                                        </Box>
                                    ))}
                                    {servingCustomers.length > 1 && (
                                        <Typography variant="h6" sx={{ opacity: 0.8 }}>+ {servingCustomers.length - 1} others being served</Typography>
                                    )}
                                </Stack>
                            ) : (
                                <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', opacity: 0.6 }}>
                                    <AccessTimeIcon sx={{ fontSize: 80, mb: 2 }} />
                                    <Typography variant="h4">Stations Available</Typography>
                                    <Typography variant="h6">Next customer please step forward</Typography>
                                </Box>
                            )}
                        </CardContent>
                    </Card>
                </Box>

                {/* Right Column: Queue Stats and List */}
                <Box sx={{ width: { xs: '100%', md: '60%' }, height: '100%', display: 'flex', flexDirection: 'column' }}>

                    {/* Stats Row */}
                    <Box sx={{ display: 'flex', gap: 3, mb: 3 }}>
                        <Box sx={{ flex: 1 }}>
                            <Card elevation={2} sx={{ borderRadius: 3, bgcolor: 'rgba(255, 255, 255, 0.9)' }}>
                                <CardContent sx={{ display: 'flex', alignItems: 'center', py: 3 }}>
                                    <Box sx={{ p: 2, borderRadius: '50%', bgcolor: `${primaryColor}22`, mr: 3 }}>
                                        <PeopleIcon sx={{ fontSize: 40, color: primaryColor }} />
                                    </Box>
                                    <Box>
                                        <Typography variant="h3" fontWeight="800" color="text.primary">
                                            {waitingCustomers.length}
                                        </Typography>
                                        <Typography variant="subtitle1" color="text.secondary" fontWeight="600">
                                            Waiting in Queue
                                        </Typography>
                                    </Box>
                                </CardContent>
                            </Card>
                        </Box>
                        <Box sx={{ flex: 1 }}>
                            <Card elevation={2} sx={{ borderRadius: 3, bgcolor: 'rgba(255, 255, 255, 0.9)' }}>
                                <CardContent sx={{ display: 'flex', alignItems: 'center', py: 3 }}>
                                    <Box sx={{ p: 2, borderRadius: '50%', bgcolor: 'warning.light', mr: 3, color: 'warning.dark' }}>
                                        <AccessTimeIcon sx={{ fontSize: 40 }} />
                                    </Box>
                                    <Box>
                                        <Typography variant="h3" fontWeight="800" color="text.primary">
                                            ~{estimatedWaitTime}<span style={{ fontSize: '1.5rem' }}>m</span>
                                        </Typography>
                                        <Typography variant="subtitle1" color="text.secondary" fontWeight="600">
                                            Est. Wait Time
                                        </Typography>
                                    </Box>
                                </CardContent>
                            </Card>
                        </Box>
                    </Box>

                    {/* Waiting List */}
                    <Card elevation={4} sx={{ flex: 1, borderRadius: 4, bgcolor: 'rgba(255, 255, 255, 0.85)', backdropFilter: 'blur(10px)', overflow: 'hidden' }}>
                        <CardContent sx={{ height: '100%', display: 'flex', flexDirection: 'column', p: 0 }}>
                            <Box sx={{ p: 3, bgcolor: 'rgba(255,255,255,0.5)', borderBottom: '1px solid rgba(0,0,0,0.05)' }}>
                                <Typography variant="h5" fontWeight="bold">Up Next</Typography>
                            </Box>

                            <Box sx={{ flex: 1, overflowY: 'auto', p: 3 }}>
                                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2 }}>
                                    {waitingCustomers.length === 0 ? (
                                        <Box width="100%">
                                            <Box textAlign="center" py={8} sx={{ opacity: 0.5 }}>
                                                <Typography variant="h4" gutterBottom>Queue is Empty</Typography>
                                                <Typography variant="h6">We are ready to serve you!</Typography>
                                            </Box>
                                        </Box>
                                    ) : (
                                        waitingCustomers.map((customer, index) => (
                                            <Box key={customer.id} sx={{ width: { xs: '100%', sm: '48%', lg: '31%' } }}>
                                                <Paper
                                                    elevation={index < 3 ? 3 : 1}
                                                    sx={{
                                                        p: 2,
                                                        borderRadius: 3,
                                                        borderLeft: `6px solid ${index === 0 ? '#4ade80' : index < 3 ? primaryColor : '#ccc'}`,
                                                        bgcolor: 'white',
                                                        transition: 'transform 0.2s',
                                                        '&:hover': { transform: 'translateY(-2px)' }
                                                    }}
                                                >
                                                    <Stack direction="row" alignItems="center" justifyContent="space-between">
                                                        <Stack direction="row" alignItems="center" spacing={2}>
                                                            <Avatar sx={{ bgcolor: index < 3 ? 'primary.main' : 'grey.300', color: 'white', fontWeight: 'bold' }}>
                                                                {customer.position}
                                                            </Avatar>
                                                            <Box>
                                                                <Typography variant="h6" fontWeight="bold" noWrap sx={{ maxWidth: 140 }}>
                                                                    {customer.customer_name}
                                                                </Typography>
                                                                <Typography variant="caption" color="text.secondary">
                                                                    {new Date(customer.checked_in_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                                                </Typography>
                                                            </Box>
                                                        </Stack>
                                                        {index < 3 && (
                                                            <Chip
                                                                size="small"
                                                                label={index === 0 ? "NEXT" : "SOON"}
                                                                color={index === 0 ? "success" : "primary"}
                                                                variant={index === 0 ? "filled" : "outlined"}
                                                            />
                                                        )}
                                                    </Stack>
                                                </Paper>
                                            </Box>
                                        ))
                                    )}
                                </Box>
                            </Box>
                        </CardContent>
                    </Card>

                    {/* Footer */}
                    <Box sx={{ mt: 3, textAlign: 'center' }}>
                        <Paper sx={{ display: 'inline-block', px: 4, py: 1, borderRadius: 20, bgcolor: 'rgba(255,255,255,0.9)', boxShadow: 2 }}>
                            <Typography variant="h6" fontWeight="500">
                                📱 Join the queue at <Box component="span" sx={{ color: primaryColor, fontWeight: 'bold' }}>
                                    {shop.slug ? `${shop.slug}.zeroqwait.com` : `nowait.app/${shop.id}`}
                                </Box>
                            </Typography>
                        </Paper>
                    </Box>

                </Box>
            </Box>
        </Box>
    );
};

export default InShopDisplayPage;
