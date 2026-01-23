import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import {
    Container,
    Box,
    Typography,
    Card,
    CardContent,
    TextField,
    Button,
    List,
    ListItem,
    ListItemText,
    Chip,
    Divider,
    Alert,
    CircularProgress,
    Paper,
    Grid,
} from '@mui/material';
import axios from 'axios';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import PeopleIcon from '@mui/icons-material/People';
import ExitToAppIcon from '@mui/icons-material/ExitToApp';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { useNavigate } from 'react-router-dom';
import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';
import Select from '@mui/material/Select';
import MenuItem from '@mui/material/MenuItem';


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
    slug?: string;
    ai_agent_name?: string;
    primary_color?: string;
}

interface QueueItem {
    id: number;
    customer_name: string;
    position: number;
    status: string;
    checked_in_at: string;
}

interface Queue {
    id: number;
    shop_id: number;
    queue_items: QueueItem[];
}

interface WaitEstimate {
    position: number;
    people_ahead: number;
    estimated_wait_minutes: number;
    status: string;
}

const QueueViewPage: React.FC = () => {
    const { shopId } = useParams<{ shopId: string }>();
    const navigate = useNavigate();
    const [shop, setShop] = useState<Shop | null>(null);
    const [queue, setQueue] = useState<Queue | null>(null);
    const [myQueueItem, setMyQueueItem] = useState<QueueItem | null>(null);
    const [waitEstimate, setWaitEstimate] = useState<WaitEstimate | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');

    useEffect(() => {
        if (shopId) {
            fetchShop();
        }
    }, [shopId]);

    useEffect(() => {
        if (shop) {
            fetchQueue();
            const interval = setInterval(fetchQueue, 5000); // Refresh every 5 seconds
            return () => clearInterval(interval);
        }
    }, [shop]);

    useEffect(() => {
        if (myQueueItem) {
            fetchWaitEstimate();
            const interval = setInterval(fetchWaitEstimate, 10000); // Update estimate every 10 seconds
            return () => clearInterval(interval);
        }
    }, [myQueueItem]);

    const fetchShop = async () => {
        try {
            const isSlug = isNaN(Number(shopId));
            const endpoint = isSlug ? `/shops/s/${shopId}` : `/shops/${shopId}`;
            const response = await axios.get(endpoint);
            setShop(response.data);
            setLoading(false);
        } catch (err) {
            setError('Failed to load shop details');
            setLoading(false);
        }
    };

    const fetchQueue = async () => {
        if (!shop) return;
        try {
            const response = await axios.get(`/queues/shop/${shop.id}/active`);
            setQueue(response.data);

            // Check if user has an active queue item using the numeric ID primarily
            const savedItemId = localStorage.getItem(`queue_item_${shop.id}`) || localStorage.getItem(`queue_item_${shopId}`);

            if (savedItemId) {
                const item = response.data.queue_items.find(
                    (i: QueueItem) => i.id === parseInt(savedItemId)
                );

                if (item) {
                    if (item.status === 'completed' || item.status === 'cancelled') {
                        // Definitely done - clear it
                        localStorage.removeItem(`queue_item_${shop.id}`);
                        localStorage.removeItem(`queue_item_${shopId}`);
                        setMyQueueItem(null);
                    } else {
                        // Still active
                        setMyQueueItem(item);
                        localStorage.setItem(`queue_item_${shop.id}`, savedItemId);
                    }
                } else {
                    // Item not found in the currently fetched queue list. 
                    // DO NOT clear it yet - it might just be the wrong queue object or transient sync issues.
                    // Instead, use the estimate endpoint as a definitive "exists" check
                    try {
                        const checkRes = await axios.get(`/queues/items/${savedItemId}/estimate`);
                        if (checkRes.data && (checkRes.data.status !== 'completed' && checkRes.data.status !== 'cancelled')) {
                            // Item exists and is active!
                            setMyQueueItem({
                                id: parseInt(savedItemId),
                                status: checkRes.data.status,
                                position: checkRes.data.position,
                                customer_name: "You" // Fallback name
                            } as any);
                        }
                    } catch (e) {
                        // If the specific check fails with 404, THEN we clear it
                        // console.error("Item verified as gone:", e);
                    }
                }
            }
        } catch (err) {
            // Silently fail - retry on next interval
        }
    };

    const fetchWaitEstimate = async () => {
        if (!myQueueItem) return;

        try {
            const response = await axios.get(
                `/queues/items/${myQueueItem.id}/estimate`
            );
            setWaitEstimate(response.data);
        } catch (err) {
            // Silently fail - retry on next interval
        }
    };

    const handleLeaveQueue = async () => {
        if (!myQueueItem) return;
        if (!window.confirm('Are you sure you want to leave the queue?')) return;

        try {
            await axios.delete(`/queues/items/${myQueueItem.id}/leave`);
            setSuccess('You have left the queue');
            localStorage.removeItem(`queue_item_${shopId}`);
            setMyQueueItem(null);
            setWaitEstimate(null);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to leave queue');
        }
    };

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'waiting':
                return 'warning';
            case 'being_served':
                return 'success';
            case 'completed':
                return 'default';
            default:
                return 'default';
        }
    };

    const waitingCustomers = queue?.queue_items.filter(
        (item) => item.status === 'waiting'
    ) || [];

    if (loading) {
        return (
            <Box display="flex" justifyContent="center" alignItems="center" minHeight="80vh">
                <CircularProgress />
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

    return (
        <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
            <Paper sx={{ p: 4, mb: 4, position: 'relative' }}>
                <Button
                    startIcon={<ArrowBackIcon />}
                    onClick={() => navigate(`/s/${shop.slug || shop.id}`)}
                    sx={{ mb: 2 }}
                >
                    Back to Shop
                </Button>
                <Typography variant="h3" fontWeight="bold" gutterBottom>
                    {shop.name}
                </Typography>
                <Typography variant="body1" color="textSecondary" sx={{ mb: 2 }}>
                    {shop.address}, {shop.city}, {shop.state}
                </Typography>

                {/* AI Concierge Switcher */}
                <Box
                    sx={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 2,
                        p: 2,
                        bgcolor: 'primary.main',
                        color: 'white',
                        borderRadius: 2,
                        cursor: 'pointer',
                        '&:hover': { bgcolor: 'primary.dark' }
                    }}
                    onClick={() => navigate(`/shop-ai/${shopId}`)}
                >
                    <SmartToyIcon />
                    <Box>
                        <Typography variant="subtitle1" fontWeight="bold">Switch to AI Assistant</Typography>
                        <Typography variant="body2" sx={{ opacity: 0.9 }}>Talk to {shop.ai_agent_name || shop.name} about your spot in line.</Typography>
                    </Box>
                </Box>
            </Paper>

            {error && (
                <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
                    {error}
                </Alert>
            )}
            {success && (
                <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess('')}>
                    {success}
                </Alert>
            )}

            <Box display="flex" flexWrap="wrap" gap={3}>
                {/* My Queue Status or Redirection */}
                {myQueueItem ? (
                    <Box sx={{ flex: 1, minWidth: '300px' }}>
                        <Card variant="outlined" sx={{
                            borderRadius: 4,
                            border: '1px solid #e0e0e0',
                            overflow: 'hidden',
                            boxShadow: '0 4px 25px rgba(0,0,0,0.05)'
                        }}>
                            <Box sx={{
                                bgcolor: shop?.primary_color || 'primary.main',
                                color: 'white',
                                p: 3,
                                textAlign: 'center'
                            }}>
                                <Typography variant="h6" sx={{ opacity: 0.9 }}>Your Current Wait</Typography>
                                <Typography variant="h1" sx={{ fontWeight: 800, my: 1 }}>
                                    #{myQueueItem.position}
                                </Typography>
                                <Chip
                                    label={myQueueItem.status.replace('_', ' ').toUpperCase()}
                                    sx={{
                                        bgcolor: 'rgba(255,255,255,0.2)',
                                        color: 'white',
                                        fontWeight: 'bold',
                                        px: 2
                                    }}
                                />
                            </Box>

                            <CardContent sx={{ p: 4 }}>
                                <Grid container spacing={3}>
                                    <Grid size={{ xs: 6 }}>
                                        <Box sx={{ textAlign: 'center', p: 2, bgcolor: '#f8faff', borderRadius: 3 }}>
                                            <PeopleIcon color="primary" sx={{ fontSize: 32, mb: 1 }} />
                                            <Typography variant="h4" fontWeight="bold">
                                                {waitEstimate?.people_ahead ?? '...'}
                                            </Typography>
                                            <Typography variant="caption" color="textSecondary">People Ahead</Typography>
                                        </Box>
                                    </Grid>
                                    <Grid size={{ xs: 6 }}>
                                        <Box sx={{ textAlign: 'center', p: 2, bgcolor: '#fff8f8', borderRadius: 3 }}>
                                            <AccessTimeIcon color="error" sx={{ fontSize: 32, mb: 1 }} />
                                            <Typography variant="h4" fontWeight="bold">
                                                ~{waitEstimate?.estimated_wait_minutes ?? '...'}
                                            </Typography>
                                            <Typography variant="caption" color="textSecondary">Min Remaining</Typography>
                                        </Box>
                                    </Grid>
                                </Grid>

                                <Divider sx={{ my: 4 }} />

                                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                                    <Button
                                        fullWidth
                                        variant="contained"
                                        size="large"
                                        startIcon={<SmartToyIcon />}
                                        onClick={() => navigate(`/shop-ai/${shopId}`)}
                                        sx={{
                                            borderRadius: 3,
                                            py: 1.5,
                                            background: 'linear-gradient(45deg, #2196F3, #21CBF3)',
                                            boxShadow: '0 3px 15px rgba(33, 203, 243, .3)',
                                        }}
                                    >
                                        Add Someone Else (AI Support)
                                    </Button>

                                    <Button
                                        fullWidth
                                        variant="outlined"
                                        color="error"
                                        startIcon={<ExitToAppIcon />}
                                        onClick={handleLeaveQueue}
                                        sx={{ borderRadius: 3, py: 1.5 }}
                                    >
                                        Exit the Queue
                                    </Button>
                                </Box>
                            </CardContent>
                        </Card>
                    </Box>
                ) : (
                    <Box sx={{ flex: 1, minWidth: '300px' }}>
                        <Card variant="outlined" sx={{ bgcolor: '#f8f9fa', border: '1px dashed #ccc' }}>
                            <CardContent sx={{ textAlign: 'center', py: 6 }}>
                                <Typography variant="h6" gutterBottom color="textSecondary">
                                    You are not currently in the queue
                                </Typography>
                                <Typography variant="body2" color="textSecondary" sx={{ mb: 3 }}>
                                    To join the line, please head back to the shop's main page.
                                </Typography>
                                <Button
                                    variant="contained"
                                    onClick={() => navigate(`/s/${shop.slug || shop.id}`)}
                                    startIcon={<ArrowBackIcon />}
                                >
                                    Go to Enrollment Form
                                </Button>
                            </CardContent>
                        </Card>
                    </Box>
                )}

                {/* Current Queue Status */}
                <Box sx={{ flex: 1, minWidth: '250px' }}>
                    <Card>
                        <CardContent>
                            <Typography variant="h5" gutterBottom>
                                Current Queue
                            </Typography>
                            <Divider sx={{ mb: 2 }} />
                            <Box display="flex" alignItems="center" mb={2}>
                                <PeopleIcon sx={{ mr: 1 }} />
                                <Typography variant="h6">
                                    {waitingCustomers.length} people waiting
                                </Typography>
                            </Box>
                            {waitingCustomers.length === 0 ? (
                                <Typography color="textSecondary">Queue is empty - join now!</Typography>
                            ) : (
                                <List>
                                    {waitingCustomers.slice(0, 5).map((item) => (
                                        <ListItem
                                            key={item.id}
                                            sx={{
                                                bgcolor: 'action.hover',
                                                mb: 1,
                                            }}
                                        >
                                            <Box sx={{ mr: 2, fontWeight: 'bold' }}>#{item.position}</Box>
                                            <ListItemText
                                                primary={item.customer_name}
                                                secondary={new Date(item.checked_in_at).toLocaleTimeString()}
                                            />
                                        </ListItem>
                                    ))}
                                    {waitingCustomers.length > 5 && (
                                        <Typography variant="body2" color="textSecondary" sx={{ mt: 1 }}>
                                            ... and {waitingCustomers.length - 5} more
                                        </Typography>
                                    )}
                                </List>
                            )}
                        </CardContent>
                    </Card>
                </Box>
            </Box>
        </Container>
    );
};

export default QueueViewPage;
