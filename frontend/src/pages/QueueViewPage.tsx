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
    Grid,
    Divider,
    Alert,
    CircularProgress,
    Paper,
} from '@mui/material';
import axios from 'axios';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import PeopleIcon from '@mui/icons-material/People';
import ExitToAppIcon from '@mui/icons-material/ExitToApp';


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
    const [shop, setShop] = useState<Shop | null>(null);
    const [queue, setQueue] = useState<Queue | null>(null);
    const [customerName, setCustomerName] = useState('');
    const [customerPhone, setCustomerPhone] = useState('');
    const [customerEmail, setCustomerEmail] = useState('');
    const [notes, setNotes] = useState('');
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
            const response = await axios.get(`/shops/${shopId}`);
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

    const handleJoinQueue = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setSuccess('');

        if (!customerName.trim()) {
            setError('Please enter your name');
            return;
        }

        try {
            const response = await axios.post(`/queues/shop/${shopId}/join`, {
                customer_name: customerName,
                customer_phone: customerPhone,
                customer_email: customerEmail,
                notes: notes,
            });

            setMyQueueItem(response.data);
            localStorage.setItem(`queue_item_${shopId}`, response.data.id.toString());
            setSuccess('Successfully joined the queue!');
            setCustomerName('');
            setCustomerPhone('');
            setCustomerEmail('');
            setNotes('');
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to join queue');
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
            <Paper sx={{ p: 4, mb: 4 }}>
                <Typography variant="h3" gutterBottom>
                    {shop.name}
                </Typography>
                <Typography variant="body1" color="textSecondary" gutterBottom>
                    {shop.description}
                </Typography>
                <Typography variant="body2" color="textSecondary">
                    {shop.address}, {shop.city}, {shop.state}
                </Typography>
                <Typography variant="body2" color="textSecondary">
                    Phone: {shop.phone}
                </Typography>
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

            <Grid container spacing={3}>
                {/* My Queue Status */}
                {myQueueItem ? (
                    <Grid xs={12} md={6}>
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
                                        <Grid container spacing={2}>
                                            <Grid xs={6}>
                                                <Box display="flex" alignItems="center">
                                                    <PeopleIcon sx={{ mr: 1 }} />
                                                    <Box>
                                                        <Typography variant="h6">{waitEstimate.people_ahead}</Typography>
                                                        <Typography variant="caption">People Ahead</Typography>
                                                    </Box>
                                                </Box>
                                            </Grid>
                                            <Grid xs={6}>
                                                <Box display="flex" alignItems="center">
                                                    <AccessTimeIcon sx={{ mr: 1 }} />
                                                    <Box>
                                                        <Typography variant="h6">
                                                            ~{waitEstimate.estimated_wait_minutes} min
                                                        </Typography>
                                                        <Typography variant="caption">Est. Wait Time</Typography>
                                                    </Box>
                                                </Box>
                                            </Grid>
                                        </Grid>
                                    </Box>
                                )}
                            </CardContent>
                        </Card>
                    </Grid>
                ) : (
                    <Grid xs={12} md={6}>
                        <Card>
                            <CardContent>
                                <Typography variant="h5" gutterBottom>
                                    Join Queue
                                </Typography>
                                <Divider sx={{ mb: 3 }} />
                                <Box component="form" onSubmit={handleJoinQueue}>
                                    <TextField
                                        fullWidth
                                        required
                                        label="Your Name"
                                        value={customerName}
                                        onChange={(e) => setCustomerName(e.target.value)}
                                        sx={{ mb: 2 }}
                                    />
                                    <TextField
                                        fullWidth
                                        label="Phone Number"
                                        value={customerPhone}
                                        onChange={(e) => setCustomerPhone(e.target.value)}
                                        sx={{ mb: 2 }}
                                    />
                                    <TextField
                                        fullWidth
                                        label="Email (optional)"
                                        type="email"
                                        value={customerEmail}
                                        onChange={(e) => setCustomerEmail(e.target.value)}
                                        sx={{ mb: 2 }}
                                    />
                                    <TextField
                                        fullWidth
                                        multiline
                                        rows={2}
                                        label="Notes (optional)"
                                        value={notes}
                                        onChange={(e) => setNotes(e.target.value)}
                                        sx={{ mb: 3 }}
                                    />
                                    <Button
                                        type="submit"
                                        variant="contained"
                                        color="primary"
                                        fullWidth
                                        size="large"
                                    >
                                        Join Queue
                                    </Button>
                                </Box>
                            </CardContent>
                        </Card>
                    </Grid>
                )}

                {/* Current Queue Status */}
                <Grid xs={12} md={6}>
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
                </Grid>
            </Grid>
        </Container>
    );
};

export default QueueViewPage;
