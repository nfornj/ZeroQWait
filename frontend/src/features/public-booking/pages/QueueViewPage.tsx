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
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import PeopleIcon from '@mui/icons-material/People';
import ExitToAppIcon from '@mui/icons-material/ExitToApp';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { useNavigate } from 'react-router-dom';
import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';
import Select from '@mui/material/Select';
import { useAuth } from '../../../contexts/AuthContext';
import { constructShopUrl } from '../../../utils/domainUtils';


const StyledHeader = styled(Box)(({ theme }) => ({
    position: 'sticky',
    top: 20,
    zIndex: 1100,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '12px 24px',
    borderRadius: '16px',
    backdropFilter: 'blur(12px)',
    backgroundColor: alpha(theme.palette.background.default, 0.7),
    border: `1px solid ${theme.palette.divider}`,
    boxShadow: '0 8px 32px rgba(0,0,0,0.08)',
    marginBottom: theme.spacing(4),
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

    return (
        <>
        <Container maxWidth="lg" sx={{ pt: 2, pb: 8 }}>
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
                    alignItems: 'center',
                    justifyContent: 'space-between',
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

            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {/* My Queue Status Card */}
                {myQueueItem ? (
                    <Box sx={{ flex: 1, minWidth: '100%', mb: 2 }}>
                        <Card elevation={0} sx={{
                            borderRadius: 6,
                            background: `linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%)`,
                            color: 'white',
                            position: 'relative',
                            overflow: 'hidden',
                            boxShadow: '0 24px 48px rgba(0,0,0,0.15)',
                            p: { xs: 4, md: 8 }
                        }}>
                            {/* Abstract brand pattern background */}
                            <Box sx={{
                                position: 'absolute',
                                top: -50,
                                right: -50,
                                width: 250,
                                height: 250,
                                borderRadius: '50%',
                                background: alpha('#FF5A5F', 0.1),
                                filter: 'blur(60px)'
                            }} />

                            <Grid container spacing={6} alignItems="center">
                                <Grid size={{ xs: 12, md: 7 }}>
                                    <Box sx={{ textAlign: { xs: 'center', md: 'left' } }}>
                                        <Typography variant="overline" sx={{ letterSpacing: 3, opacity: 0.6, mb: 2, display: 'block' }}>
                                            LIVE STATUS
                                        </Typography>
                                        <Typography variant="h1" sx={{ fontWeight: 900, mb: 1, fontSize: { xs: '5rem', md: '10rem' }, lineHeight: 0.9 }}>
                                            {myQueueItem.position}
                                            <Typography component="span" variant="h3" sx={{ verticalAlign: 'top', ml: 1, fontWeight: 800 }}>
                                                {myQueueItem.position === 1 ? 'st' : myQueueItem.position === 2 ? 'nd' : myQueueItem.position === 3 ? 'rd' : 'th'}
                                            </Typography>
                                        </Typography>
                                        <Typography variant="h4" sx={{ fontWeight: 700, mb: 4, letterSpacing: '-0.01em' }}>
                                            in the queue
                                        </Typography>

                                        <Stack direction="row" spacing={2} sx={{ justifyContent: { xs: 'center', md: 'flex-start' } }}>
                                            <Box sx={{ bgcolor: 'rgba(255,255,255,0.08)', px: 3, py: 1.5, borderRadius: 3 }}>
                                                <Typography variant="caption" sx={{ display: 'block', opacity: 0.5, mb: 0.5 }}>ESTIMATED WAIT</Typography>
                                                <Typography variant="h6" fontWeight="800">~{waitEstimate?.estimated_wait_minutes ?? '...'} MINS</Typography>
                                            </Box>
                                            <Box sx={{ bgcolor: 'rgba(255,255,255,0.08)', px: 3, py: 1.5, borderRadius: 3 }}>
                                                <Typography variant="caption" sx={{ display: 'block', opacity: 0.5, mb: 0.5 }}>PEOPLE AHEAD</Typography>
                                                <Typography variant="h6" fontWeight="800">{waitEstimate?.people_ahead ?? '...'}</Typography>
                                            </Box>
                                        </Stack>
                                    </Box>
                                </Grid>
                                <Grid size={{ xs: 12, md: 5 }}>
                                    <Stack spacing={2}>
                                        <Button
                                            fullWidth
                                            variant="contained"
                                            size="large"
                                            onClick={() => navigate(`/shop-ai/${shopId}`)}
                                            sx={{
                                                borderRadius: 4,
                                                py: 2.5,
                                                fontSize: '1.1rem',
                                                fontWeight: 'bold',
                                                bgcolor: 'white',
                                                color: 'black',
                                                '&:hover': { bgcolor: '#f0f0f0' }
                                            }}
                                        >
                                            Add More People (AI)
                                        </Button>
                                        <Button
                                            fullWidth
                                            variant="text"
                                            onClick={handleLeaveQueue}
                                            sx={{ color: '#ff4d4f', fontWeight: 600 }}
                                        >
                                            Cancel Registration
                                        </Button>
                                    </Stack>
                                </Grid>
                            </Grid>
                        </Card>
                    </Box>
                ) : (
                    <Box sx={{ flex: 1, minWidth: '100%', mb: 4 }}>
                        <Paper
                            variant="outlined"
                            sx={{
                                p: 8,
                                borderRadius: 6,
                                textAlign: 'center',
                                border: '2px dashed',
                                borderColor: 'divider',
                                bgcolor: alpha('#000', 0.01)
                            }}
                        >
                            <Typography variant="h5" fontWeight="800" gutterBottom>
                                Not Enrolled
                            </Typography>
                            <Typography color="textSecondary" sx={{ mb: 4 }}>
                                You are not currently in this shop's queue.
                            </Typography>
                            <Button
                                variant="contained"
                                onClick={() => window.location.href = constructShopUrl(shop.slug || `shop-${shop.id}`)}
                                startIcon={<ArrowBackIcon />}
                                sx={{ borderRadius: 3, px: 4, py: 1.5, fontWeight: 'bold' }}
                            >
                                Go to Shop Page
                            </Button>
                        </Paper>
                    </Box>
                )}

                {/* Privacy Queue Table */}
                <Box sx={{ flex: 1, minWidth: '100%' }}>
                    <Typography variant="h5" fontWeight="800" sx={{ mb: 3, px: 1 }}>
                        Active Queue
                    </Typography>

                    <Paper elevation={0} sx={{
                        borderRadius: 5,
                        border: '1px solid',
                        borderColor: 'divider',
                        overflow: 'hidden'
                    }}>
                        <Box sx={{ overflowX: 'auto' }}>
                            <Box sx={{ minWidth: 600 }}>
                                {/* Header */}
                                <Grid container sx={{ px: 3, py: 2, bgcolor: 'action.hover', borderBottom: '1px solid', borderColor: 'divider' }}>
                                    <Grid size={{ xs: 2 }}><Typography variant="caption" fontWeight="800" color="textSecondary">POSITION</Typography></Grid>
                                    <Grid size={{ xs: 6 }}><Typography variant="caption" fontWeight="800" color="textSecondary">CUSTOMER</Typography></Grid>
                                    <Grid size={{ xs: 2 }}><Typography variant="caption" fontWeight="800" color="textSecondary">CHECK-IN</Typography></Grid>
                                    <Grid size={{ xs: 2 }}><Typography variant="caption" fontWeight="800" color="textSecondary">STATUS</Typography></Grid>
                                </Grid>

                                {waitingCustomers.length === 0 ? (
                                    <Box sx={{ p: 6, textAlign: 'center' }}>
                                        <Typography color="textSecondary">No one in the queue yet.</Typography>
                                    </Box>
                                ) : (
                                    waitingCustomers.slice(0, 15).map((item, index) => {
                                        const isMe = myQueueItem?.id === item.id;
                                        return (
                                            <Grid
                                                container
                                                key={item.id}
                                                alignItems="center"
                                                sx={{
                                                    px: 3,
                                                    py: 2.5,
                                                    borderBottom: index === waitingCustomers.length - 1 ? 'none' : '1px solid',
                                                    borderColor: 'divider',
                                                    background: isMe ? alpha('#FF5A5F', 0.05) : 'transparent',
                                                    position: 'relative'
                                                }}
                                            >
                                                <Grid size={{ xs: 2 }}>
                                                    <Typography variant="h6" fontWeight="900">#{item.position}</Typography>
                                                </Grid>
                                                <Grid size={{ xs: 6 }}>
                                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                                                        <Avatar sx={{
                                                            bgcolor: isMe ? 'primary.main' : 'grey.300',
                                                            width: 32,
                                                            height: 32,
                                                            fontSize: '0.8rem',
                                                            fontWeight: 'bold'
                                                        }}>
                                                            {isMe ? item.customer_name[0] : '?'}
                                                        </Avatar>

                                                        {isMe ? (
                                                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                                                <Typography fontWeight="800">{item.customer_name}</Typography>
                                                                <Chip label="YOU" size="small" color="primary" />
                                                            </Box>
                                                        ) : (
                                                            <BlurryName>{item.customer_name}</BlurryName>
                                                        )}
                                                    </Box>
                                                </Grid>
                                                <Grid size={{ xs: 2 }}>
                                                    <Typography variant="body2" color="textSecondary">
                                                        {new Date(item.checked_in_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                                    </Typography>
                                                </Grid>
                                                <Grid size={{ xs: 2 }}>
                                                    {item.status === 'being_served' ? (
                                                        <Chip label="SERVING" size="small" color="success" />
                                                    ) : (
                                                        <Chip label="WAITING" size="small" variant="outlined" color="warning" />
                                                    )}
                                                </Grid>
                                            </Grid>
                                        );
                                    })
                                )}
                            </Box>
                        </Box>
                    </Paper>
                </Box>
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
