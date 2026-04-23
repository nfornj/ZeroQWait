import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import {
    Container,
    Box,
    Typography,
    Button,
    Chip,
    Divider,
    Alert,
    CircularProgress,
    Paper,
    Grid,
    alpha,
    styled,
    Stack,
    Avatar,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
} from '@mui/material';
import axios from 'axios';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../../contexts/AuthContext';
import { constructShopUrl } from '../../../utils/domainUtils';


const StyledHeader = styled(Box)(({ theme }) => ({
    position: 'sticky',
    top: 12,
    zIndex: 1100,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    flexWrap: 'wrap',
    gap: theme.spacing(1.5),
    padding: theme.spacing(1.5, 2),
    borderRadius: '16px',
    backdropFilter: 'blur(12px)',
    backgroundColor: alpha(theme.palette.background.paper, 0.82),
    border: `1px solid ${theme.palette.divider}`,
    boxShadow: '0 8px 32px rgba(0,0,0,0.08)',
    marginBottom: theme.spacing(3),
    [theme.breakpoints.up('md')]: {
        top: 20,
        padding: theme.spacing(1.75, 3),
    },
    [theme.breakpoints.down('sm')]: {
        alignItems: 'flex-start',
    },
}));

const BlurryName = styled(Typography)(({ theme }) => ({
    filter: 'blur(5px)',
    userSelect: 'none',
    opacity: 0.6,
    transition: 'filter 0.3s ease',
}));


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
    const { user, isAuthenticated } = useAuth();
    const [shop, setShop] = useState<Shop | null>(null);
    const [queue, setQueue] = useState<Queue | null>(null);
    const [myQueueItem, setMyQueueItem] = useState<QueueItem | null>(null);
    const [waitEstimate, setWaitEstimate] = useState<WaitEstimate | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');
    const [leaveQueueDialogOpen, setLeaveQueueDialogOpen] = useState(false);

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

    const handleLeaveQueue = () => {
        if (!myQueueItem) return;
        setLeaveQueueDialogOpen(true);
    };

    const confirmLeaveQueue = async () => {
        if (!myQueueItem) return;
        setLeaveQueueDialogOpen(false);
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

    const queueCount = waitingCustomers.length;
    const averageServiceTime = Math.max(shop.average_service_time || 0, 15);
    const fallbackEtaMinutes = myQueueItem
        ? Math.max((myQueueItem.position - 1) * averageServiceTime, 0)
        : queueCount * averageServiceTime;
    const liveEtaMinutes = waitEstimate?.estimated_wait_minutes ?? fallbackEtaMinutes;

    return (
        <>
        <Container maxWidth="xl" sx={{ pt: { xs: 2, md: 3 }, pb: { xs: 5, md: 8 } }}>
            {/* V4 Glassmorphism Header */}
            <StyledHeader>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                    <Typography variant="h6" fontWeight="800" sx={{ color: 'primary.main', letterSpacing: '-0.02em' }}>
                        ZeroQwait
                    </Typography>
                    <Divider orientation="vertical" flexItem sx={{ height: 24, my: 'auto' }} />
                    <Typography variant="subtitle1" fontWeight="600" sx={{ color: 'text.primary' }}>
                        {shop.name}
                    </Typography>
                </Box>
                {isAuthenticated && (user?.role === 'shop_owner' || user?.role === 'employee' || user?.role === 'manager') && (
                    <Button
                        startIcon={<ArrowBackIcon />}
                        onClick={() => window.location.href = constructShopUrl(shop.slug || `shop-${shop.id}`)}
                        variant="text"
                        size="small"
                        sx={{ color: 'text.secondary', fontWeight: 600 }}
                    >
                        Back to Shop
                    </Button>
                )}
            </StyledHeader>

            {/* AI Concierge Banner (Subtle) */}
            <Paper
                elevation={0}
                sx={{
                    p: 2,
                    mb: 6,
                    borderRadius: 4,
                    border: '1px solid',
                    borderColor: 'primary.light',
                    bgcolor: alpha('#FF5A5F', 0.03),
                    display: 'flex',
                    flexDirection: { xs: 'column', sm: 'row' },
                    alignItems: { xs: 'flex-start', sm: 'center' },
                    justifyContent: 'space-between',
                    gap: 1.5,
                    cursor: 'pointer',
                    '&:hover': { bgcolor: alpha('#FF5A5F', 0.08) }
                }}
                onClick={() => navigate(`/shop-ai/${shopId}`)}
            >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                    <SmartToyIcon color="primary" sx={{ fontSize: 28 }} />
                    <Box>
                        <Typography variant="subtitle2" fontWeight="800" color="primary">Talk to our AI Concierge</Typography>
                        <Typography variant="caption" color="textSecondary">Questions about your wait? Tap to chat with {shop.ai_agent_name || shop.name}.</Typography>
                    </Box>
                </Box>
                <ArrowBackIcon color="primary" sx={{ transform: 'rotate(180deg)' }} />
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

            <Box sx={{ display: 'flex', flexDirection: 'column', gap: { xs: 2.5, md: 3 } }}>
                <Grid container spacing={{ xs: 2, md: 3 }}>
                    <Grid size={{ xs: 12, md: 7 }}>
                        <Paper
                            elevation={0}
                            sx={{
                                position: 'relative',
                                overflow: 'hidden',
                                minHeight: '100%',
                                p: { xs: 3, md: 4 },
                                borderRadius: 6,
                                color: 'common.white',
                                border: '1px solid',
                                borderColor: alpha('#ffffff', 0.14),
                                background: 'linear-gradient(145deg, #0f172a 0%, #17324d 48%, #1d5d86 100%)',
                                boxShadow: '0 24px 60px rgba(12, 30, 56, 0.18)',
                            }}
                        >
                            <Box
                                sx={{
                                    position: 'absolute',
                                    inset: 'auto -80px -120px auto',
                                    width: 260,
                                    height: 260,
                                    borderRadius: '50%',
                                    background: alpha('#7dd3fc', 0.18),
                                    filter: 'blur(30px)',
                                }}
                            />
                            <Stack spacing={3} sx={{ position: 'relative', zIndex: 1 }}>
                                <Stack
                                    direction={{ xs: 'column', sm: 'row' }}
                                    spacing={1.5}
                                    justifyContent="space-between"
                                    alignItems={{ xs: 'flex-start', sm: 'flex-start' }}
                                >
                                    <Box>
                                        <Typography variant="overline" sx={{ letterSpacing: 2.2, opacity: 0.72 }}>
                                            LIVE QUEUE BOARD
                                        </Typography>
                                        <Typography variant="h3" sx={{ fontWeight: 800, letterSpacing: '-0.03em', mt: 0.5 }}>
                                            {shop.name}
                                        </Typography>
                                        <Typography sx={{ opacity: 0.72, mt: 0.5 }}>
                                            {shop.city} • {shop.shop_type}
                                        </Typography>
                                    </Box>
                                    <Chip
                                        label={`${queueCount} waiting now`}
                                        sx={{
                                            bgcolor: alpha('#ffffff', 0.12),
                                            color: 'common.white',
                                            fontWeight: 700,
                                            borderRadius: 999,
                                            border: `1px solid ${alpha('#ffffff', 0.16)}`,
                                        }}
                                    />
                                </Stack>

                                <Stack direction="row" flexWrap="wrap" gap={1.25}>
                                    <Chip
                                        label={`ETA ${liveEtaMinutes} min`}
                                        sx={{
                                            bgcolor: '#f59e0b',
                                            color: '#111827',
                                            fontWeight: 800,
                                            px: 0.75,
                                        }}
                                    />
                                    <Chip
                                        label={`Avg service ${averageServiceTime} min`}
                                        sx={{ bgcolor: alpha('#ffffff', 0.12), color: 'common.white' }}
                                    />
                                    <Chip
                                        label="Refreshes every 5 seconds"
                                        sx={{ bgcolor: alpha('#ffffff', 0.12), color: 'common.white' }}
                                    />
                                </Stack>

                                {myQueueItem ? (
                                    <Grid container spacing={2.5} alignItems="flex-end">
                                        <Grid size={{ xs: 12, sm: 5 }}>
                                            <Typography variant="overline" sx={{ letterSpacing: 2, opacity: 0.72 }}>
                                                YOUR POSITION
                                            </Typography>
                                            <Typography variant="h1" sx={{ fontWeight: 900, lineHeight: 0.9, fontSize: { xs: '4.25rem', md: '5.75rem' } }}>
                                                {myQueueItem.position}
                                            </Typography>
                                        </Grid>
                                        <Grid size={{ xs: 12, sm: 7 }}>
                                            <Stack spacing={1.5}>
                                                <Typography variant="h5" sx={{ fontWeight: 700, letterSpacing: '-0.02em' }}>
                                                    You&apos;re checked in and moving through the line.
                                                </Typography>
                                                <Typography sx={{ opacity: 0.8, maxWidth: 440 }}>
                                                    We&apos;ll keep this board current while the queue moves. Use the AI concierge if you need to update details or add another guest.
                                                </Typography>
                                                <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
                                                    <Button
                                                        variant="contained"
                                                        onClick={() => navigate(`/shop-ai/${shopId}`)}
                                                        sx={{
                                                            borderRadius: 999,
                                                            px: 3,
                                                            py: 1.3,
                                                            fontWeight: 700,
                                                            bgcolor: 'common.white',
                                                            color: '#102033',
                                                            '&:hover': { bgcolor: alpha('#ffffff', 0.92) },
                                                        }}
                                                    >
                                                        Open AI Concierge
                                                    </Button>
                                                    <Button
                                                        variant="text"
                                                        onClick={handleLeaveQueue}
                                                        sx={{ color: alpha('#ffffff', 0.88), fontWeight: 700 }}
                                                    >
                                                        Leave queue
                                                    </Button>
                                                </Stack>
                                            </Stack>
                                        </Grid>
                                    </Grid>
                                ) : (
                                    <Stack spacing={2}>
                                        <Typography variant="h4" sx={{ fontWeight: 750, letterSpacing: '-0.03em', maxWidth: 520 }}>
                                            Track the line first, then join when you&apos;re ready.
                                        </Typography>
                                        <Typography sx={{ opacity: 0.8, maxWidth: 520 }}>
                                            The live board gives you the queue depth instantly. When you want to jump in, the AI concierge can collect details and confirm your place in one flow.
                                        </Typography>
                                        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
                                            <Button
                                                variant="contained"
                                                onClick={() => navigate(`/shop-ai/${shopId}`)}
                                                sx={{
                                                    borderRadius: 999,
                                                    px: 3,
                                                    py: 1.3,
                                                    fontWeight: 700,
                                                    bgcolor: 'common.white',
                                                    color: '#102033',
                                                    '&:hover': { bgcolor: alpha('#ffffff', 0.92) },
                                                }}
                                            >
                                                Join with AI Concierge
                                            </Button>
                                            <Button
                                                variant="outlined"
                                                onClick={() => window.location.href = constructShopUrl(shop.slug || `shop-${shop.id}`)}
                                                startIcon={<ArrowBackIcon />}
                                                sx={{
                                                    borderRadius: 999,
                                                    px: 3,
                                                    py: 1.3,
                                                    color: 'common.white',
                                                    borderColor: alpha('#ffffff', 0.32),
                                                }}
                                            >
                                                Back to Shop Page
                                            </Button>
                                        </Stack>
                                    </Stack>
                                )}
                            </Stack>
                        </Paper>
                    </Grid>

                    <Grid size={{ xs: 12, md: 5 }}>
                        <Stack spacing={{ xs: 2, md: 3 }} sx={{ height: '100%' }}>
                            <Paper
                                elevation={0}
                                sx={{
                                    p: { xs: 2.5, md: 3 },
                                    borderRadius: 6,
                                    border: '1px solid',
                                    borderColor: 'divider',
                                    background: 'linear-gradient(180deg, rgba(255,255,255,0.95) 0%, rgba(248,250,252,0.92) 100%)',
                                }}
                            >
                                <Stack spacing={2}>
                                    <Box>
                                        <Typography variant="overline" sx={{ letterSpacing: 2, color: 'text.secondary' }}>
                                            RECEPTION DESK
                                        </Typography>
                                        <Typography variant="h5" sx={{ fontWeight: 800, letterSpacing: '-0.02em', mt: 0.5 }}>
                                            Need help before you join?
                                        </Typography>
                                        <Typography color="text.secondary" sx={{ mt: 1 }}>
                                            Start with the AI receptionist for services, wait times, bookings, or queue check-in.
                                        </Typography>
                                    </Box>

                                    <Stack direction="row" flexWrap="wrap" gap={1}>
                                        {['Show Services', 'Book Appointment', 'Check Wait Time', 'Join Queue'].map((label) => (
                                            <Chip
                                                key={label}
                                                label={label}
                                                variant="outlined"
                                                sx={{ borderRadius: 999, px: 0.5 }}
                                            />
                                        ))}
                                    </Stack>

                                    <Button
                                        fullWidth
                                        variant="contained"
                                        startIcon={<SmartToyIcon />}
                                        onClick={() => navigate(`/shop-ai/${shopId}`)}
                                        sx={{ borderRadius: 999, py: 1.35, fontWeight: 700 }}
                                    >
                                        Open AI Concierge
                                    </Button>
                                    <Button
                                        fullWidth
                                        variant="text"
                                        onClick={() => window.location.href = constructShopUrl(shop.slug || `shop-${shop.id}`)}
                                        sx={{ fontWeight: 700 }}
                                    >
                                        Visit full shop page
                                    </Button>
                                </Stack>
                            </Paper>

                            <Paper
                                elevation={0}
                                sx={{
                                    p: { xs: 2.5, md: 3 },
                                    borderRadius: 6,
                                    border: '1px solid',
                                    borderColor: 'divider',
                                }}
                            >
                                <Stack spacing={1.5}>
                                    <Typography variant="overline" sx={{ letterSpacing: 2, color: 'text.secondary' }}>
                                        VISIT DETAILS
                                    </Typography>
                                    <Typography variant="body1" sx={{ fontWeight: 700 }}>
                                        {shop.address}
                                    </Typography>
                                    <Typography color="text.secondary">
                                        {shop.city}, {shop.state}
                                    </Typography>
                                    <Divider />
                                    <Typography color="text.secondary">
                                        Phone: {shop.phone}
                                    </Typography>
                                    <Typography color="text.secondary">
                                        Average service window: {averageServiceTime} minutes
                                    </Typography>
                                    <Typography color="text.secondary">
                                        Customer names remain blurred until it&apos;s your turn, so the board stays useful without exposing full queue details.
                                    </Typography>
                                </Stack>
                            </Paper>
                        </Stack>
                    </Grid>
                </Grid>

                <Paper
                    elevation={0}
                    sx={{
                        p: { xs: 2, md: 3 },
                        borderRadius: 6,
                        border: '1px solid',
                        borderColor: 'divider',
                    }}
                >
                    <Stack spacing={2.5}>
                        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} justifyContent="space-between" alignItems={{ xs: 'flex-start', sm: 'center' }}>
                            <Box>
                                <Typography variant="h5" sx={{ fontWeight: 800, letterSpacing: '-0.02em' }}>
                                    Active Queue
                                </Typography>
                                <Typography color="text.secondary" sx={{ mt: 0.5 }}>
                                    The board refreshes continuously so you can gauge the line before you head over.
                                </Typography>
                            </Box>
                            {myQueueItem && <Chip label={`You are #${myQueueItem.position}`} color="primary" />}
                        </Stack>

                        {waitingCustomers.length === 0 ? (
                            <Box sx={{ py: 6, textAlign: 'center', borderRadius: 4, bgcolor: alpha('#0f172a', 0.02) }}>
                                <Typography color="text.secondary">No one is waiting right now.</Typography>
                            </Box>
                        ) : (
                            <Stack spacing={1.25}>
                                {waitingCustomers.slice(0, 15).map((item) => {
                                    const isMe = myQueueItem?.id === item.id;
                                    return (
                                        <Box
                                            key={item.id}
                                            sx={{
                                                p: { xs: 2, sm: 2.25 },
                                                borderRadius: 4,
                                                border: '1px solid',
                                                borderColor: isMe ? alpha('#1976d2', 0.2) : 'divider',
                                                bgcolor: isMe ? alpha('#1976d2', 0.06) : alpha('#0f172a', 0.015),
                                                display: 'grid',
                                                gridTemplateColumns: { xs: '1fr', sm: '72px minmax(0,1fr) auto auto' },
                                                gap: { xs: 1.25, sm: 1.5 },
                                                alignItems: 'center',
                                            }}
                                        >
                                            <Typography variant="h6" sx={{ fontWeight: 900, letterSpacing: '-0.03em' }}>
                                                #{item.position}
                                            </Typography>

                                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, minWidth: 0 }}>
                                                <Avatar
                                                    sx={{
                                                        bgcolor: isMe ? 'primary.main' : 'grey.300',
                                                        width: 34,
                                                        height: 34,
                                                        fontSize: '0.82rem',
                                                        fontWeight: 'bold',
                                                    }}
                                                >
                                                    {isMe ? item.customer_name[0] : '?'}
                                                </Avatar>
                                                <Box sx={{ minWidth: 0 }}>
                                                    {isMe ? (
                                                        <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
                                                            <Typography fontWeight="800">{item.customer_name}</Typography>
                                                            <Chip label="YOU" size="small" color="primary" />
                                                        </Stack>
                                                    ) : (
                                                        <BlurryName>{item.customer_name}</BlurryName>
                                                    )}
                                                </Box>
                                            </Box>

                                            <Typography variant="body2" color="text.secondary">
                                                {new Date(item.checked_in_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                            </Typography>

                                            <Chip
                                                label={item.status === 'being_served' ? 'SERVING' : 'WAITING'}
                                                size="small"
                                                color={getStatusColor(item.status)}
                                                variant={item.status === 'being_served' ? 'filled' : 'outlined'}
                                            />
                                        </Box>
                                    );
                                })}
                            </Stack>
                        )}
                    </Stack>
                </Paper>
            </Box>
        </Container>

        <Dialog open={leaveQueueDialogOpen} onClose={() => setLeaveQueueDialogOpen(false)}>
            <DialogTitle>Leave Queue</DialogTitle>
            <DialogContent>
                <Typography>Are you sure you want to leave the queue? You will lose your position.</Typography>
            </DialogContent>
            <DialogActions>
                <Button onClick={() => setLeaveQueueDialogOpen(false)}>Cancel</Button>
                <Button variant="contained" color="error" onClick={confirmLeaveQueue}>Leave Queue</Button>
            </DialogActions>
        </Dialog>
        </>
    );
};

export default QueueViewPage;
