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
        (item) => item.status === 'waiting' || item.status === 'being_served'
    ).sort((a, b) => (a.position || 0) - (b.position || 0)) || [];

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
            {/* Main Header / Hero Section */}
            <Box sx={{ mb: 6, textAlign: 'center' }}>
                <Button
                    startIcon={<ArrowBackIcon />}
                    onClick={() => navigate(`/s/${shop.slug || shop.id}`)}
                    sx={{ mb: 3 }}
                >
                    Back to Shop
                </Button>
                <Typography variant="h2" fontWeight="800" gutterBottom sx={{ color: '#1a1a1a', letterSpacing: '-0.02em' }}>
                    {shop.name}
                </Typography>
                <Typography variant="h6" color="textSecondary">
                    {shop.address}, {shop.city}
                </Typography>
            </Box>

            {/* AI Concierge Banner */}
            <Paper
                elevation={0}
                sx={{
                    p: 2.5,
                    mb: 4,
                    borderRadius: 4,
                    background: 'linear-gradient(90deg, #2196F3 0%, #21CBF3 100%)',
                    color: 'white',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    cursor: 'pointer',
                    '&:hover': { transform: 'translateY(-2px)', transition: '0.2s' }
                }}
                onClick={() => navigate(`/shop-ai/${shopId}`)}
            >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                    <SmartToyIcon sx={{ fontSize: 32 }} />
                    <Box>
                        <Typography variant="h6" fontWeight="bold">Switch to AI Assistant</Typography>
                        <Typography variant="body2">Talk to {shop.ai_agent_name || shop.name} about your spot in line.</Typography>
                    </Box>
                </Box>
                <ArrowBackIcon sx={{ transform: 'rotate(180deg)' }} />
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
                    <Box sx={{ flex: 1, minWidth: '100%', mb: 4 }}>
                        <Card variant="outlined" sx={{
                            borderRadius: 6,
                            border: 'none',
                            bgcolor: '#1a1a1a',
                            color: 'white',
                            overflow: 'hidden',
                            boxShadow: '0 20px 40px rgba(0,0,0,0.2)',
                            p: { xs: 4, md: 6 }
                        }}>
                            <Grid container spacing={4} alignItems="center">
                                <Grid size={{ xs: 12, md: 7 }}>
                                    <Box sx={{ textAlign: { xs: 'center', md: 'left' } }}>
                                        <Typography variant="h5" sx={{ opacity: 0.6, mb: 1, fontWeight: 500 }}>
                                            YOU ARE
                                        </Typography>
                                        <Typography variant="h1" sx={{ fontWeight: 900, mb: 2, fontSize: { xs: '5rem', md: '8rem' }, lineHeight: 1 }}>
                                            {myQueueItem.position}
                                            <Typography component="span" variant="h3" sx={{ verticalAlign: 'top', ml: 1, opacity: 0.8 }}>
                                                {myQueueItem.position === 1 ? 'st' : myQueueItem.position === 2 ? 'nd' : myQueueItem.position === 3 ? 'rd' : 'th'}
                                            </Typography>
                                        </Typography>
                                        <Typography variant="h4" sx={{ fontWeight: 600, mb: 3 }}>
                                            in the queue
                                        </Typography>
                                        <Typography variant="h5" sx={{ fontWeight: 500, bgcolor: 'rgba(255,255,255,0.1)', p: 2, borderRadius: 3, display: 'inline-block' }}>
                                            Estimated Wait: <strong>~{waitEstimate?.estimated_wait_minutes ?? '...'} mins</strong>
                                        </Typography>
                                    </Box>
                                </Grid>
                                <Grid size={{ xs: 12, md: 5 }}>
                                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
                                        <Button
                                            fullWidth
                                            variant="contained"
                                            size="large"
                                            startIcon={<SmartToyIcon />}
                                            onClick={() => navigate(`/shop-ai/${shopId}`)}
                                            sx={{
                                                borderRadius: 4,
                                                py: 2.5,
                                                fontSize: '1.1rem',
                                                fontWeight: 'bold',
                                                background: 'white',
                                                color: '#1a1a1a',
                                                '&:hover': { background: '#f5f5f5' }
                                            }}
                                        >
                                            Add Someone Else (AI)
                                        </Button>

                                        <Button
                                            fullWidth
                                            variant="text"
                                            onClick={handleLeaveQueue}
                                            sx={{ color: '#ff4d4f', fontSize: '1rem' }}
                                        >
                                            Exit the Queue
                                        </Button>
                                    </Box>
                                </Grid>
                            </Grid>
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
                                    {waitingCustomers.slice(0, 10).map((item) => {
                                        const isMe = myQueueItem?.id === item.id;
                                        return (
                                            <ListItem
                                                key={item.id}
                                                sx={{
                                                    bgcolor: isMe ? 'primary.light' : 'action.hover',
                                                    color: isMe ? 'white' : 'inherit',
                                                    borderRadius: 2,
                                                    mb: 1,
                                                    border: isMe ? 'none' : '1px solid #eee'
                                                }}
                                            >
                                                <Box sx={{ mr: 2, fontWeight: '900', fontSize: '1.2rem' }}>#{item.position}</Box>
                                                <ListItemText
                                                    primary={
                                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                                            <Typography fontWeight={isMe ? "800" : "500"}>
                                                                {item.customer_name}
                                                            </Typography>
                                                            {isMe && <Chip label="YOU" size="small" sx={{ bgcolor: 'white', color: 'primary.main', fontWeight: 'bold', height: 20 }} />}
                                                        </Box>
                                                    }
                                                    secondary={
                                                        <Typography variant="caption" sx={{ color: isMe ? 'white' : 'textSecondary', opacity: isMe ? 0.8 : 1 }}>
                                                            {new Date(item.checked_in_at).toLocaleTimeString()}
                                                        </Typography>
                                                    }
                                                />
                                                {item.status === 'being_served' && (
                                                    <Chip label="SERVING" size="small" color="success" />
                                                )}
                                            </ListItem>
                                        );
                                    })}

                                    {/* Show "Your Spot" if you are deep in the queue (>10) */}
                                    {myQueueItem && myQueueItem.position > 10 && (
                                        <>
                                            <Box sx={{ textAlign: 'center', py: 1, opacity: 0.5 }}>•••</Box>
                                            <ListItem
                                                sx={{
                                                    bgcolor: 'primary.main',
                                                    color: 'white',
                                                    borderRadius: 2,
                                                    mb: 1,
                                                    boxShadow: '0 4px 12px rgba(0,0,0,0.1)'
                                                }}
                                            >
                                                <Box sx={{ mr: 2, fontWeight: '900', fontSize: '1.2rem' }}>#{myQueueItem.position}</Box>
                                                <ListItemText
                                                    primary={<Typography fontWeight="800">You (Your Spot)</Typography>}
                                                    secondary={<Typography variant="caption" sx={{ color: 'white', opacity: 0.8 }}>Deep in line</Typography>}
                                                />
                                                <Chip label="YOU" size="small" sx={{ bgcolor: 'white', color: 'primary.main', fontWeight: 'bold' }} />
                                            </ListItem>
                                        </>
                                    )}

                                    {waitingCustomers.length > 10 && (!myQueueItem || myQueueItem.position <= 10) && (
                                        <Typography variant="body2" color="textSecondary" sx={{ mt: 1, textAlign: 'center' }}>
                                            ... and {waitingCustomers.length - 10} more waiting
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
