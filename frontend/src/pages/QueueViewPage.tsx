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
            fetchQueue();
            const interval = setInterval(fetchQueue, 5000); // Refresh every 5 seconds
            return () => clearInterval(interval);
        }
    }, [shopId]);

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
        try {
            const response = await axios.get(`/queues/shop/${shopId}/active`);
            setQueue(response.data);

            // Check if user has an active queue item
            const savedItemId = localStorage.getItem(`queue_item_${shopId}`);
            if (savedItemId) {
                const item = response.data.queue_items.find(
                    (i: QueueItem) => i.id === parseInt(savedItemId)
                );
                if (item && item.status !== 'completed' && item.status !== 'cancelled') {
                    setMyQueueItem(item);
                } else {
                    localStorage.removeItem(`queue_item_${shopId}`);
                    setMyQueueItem(null);
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
                {/* My Queue Status */}
                {myQueueItem ? (
                    <Box sx={{ flex: 1, minWidth: '250px' }}>
                        <Card sx={{ bgcolor: 'primary.light', color: 'white' }}>
                            <CardContent>
                                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                                    <Typography variant="h5">
                                        Your Position
                                    </Typography>
                                    <Button
                                        variant="outlined"
                                        size="small"
                                        startIcon={<ExitToAppIcon />}
                                        onClick={handleLeaveQueue}
                                        sx={{
                                            color: 'white',
                                            borderColor: 'white',
                                            '&:hover': {
                                                borderColor: 'white',
                                                bgcolor: 'rgba(255,255,255,0.1)'
                                            }
                                        }}
                                    >
                                        Leave Queue
                                    </Button>
                                </Box>
                                <Divider sx={{ my: 2, bgcolor: 'white' }} />
                                <Box textAlign="center" py={3}>
                                    <Typography variant="h1" sx={{ fontWeight: 'bold' }}>
                                        #{myQueueItem.position}
                                    </Typography>
                                    <Chip
                                        label={myQueueItem.status.replace('_', ' ').toUpperCase()}
                                        color={getStatusColor(myQueueItem.status) as any}
                                        sx={{ mt: 2 }}
                                    />
                                </Box>
                                {waitEstimate && (
                                    <Box mt={3}>
                                        <Box display="flex" flexWrap="wrap" gap={2}>
                                            <Box sx={{ flex: 1, minWidth: '250px' }}>
                                                <Box display="flex" alignItems="center">
                                                    <PeopleIcon sx={{ mr: 1 }} />
                                                    <Box>
                                                        <Typography variant="h6">{waitEstimate.people_ahead}</Typography>
                                                        <Typography variant="caption">People Ahead</Typography>
                                                    </Box>
                                                </Box>
                                            </Box>
                                            <Box sx={{ flex: 1, minWidth: '250px' }}>
                                                <Box display="flex" alignItems="center">
                                                    <AccessTimeIcon sx={{ mr: 1 }} />
                                                    <Box>
                                                        <Typography variant="h6">
                                                            ~{waitEstimate.estimated_wait_minutes} min
                                                        </Typography>
                                                        <Typography variant="caption">Est. Wait Time</Typography>
                                                    </Box>
                                                </Box>
                                            </Box>
                                        </Box>
                                    </Box>
                                )}
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
