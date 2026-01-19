import React, { useState, useEffect } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import {
    Box,
    Card,
    CardContent,
    Typography,
    TextField,
    Button,
    Avatar,
    CircularProgress,
    Alert,
    Chip,
    Stack,
    Divider
} from '@mui/material';
import {
    People as PeopleIcon,
    Schedule as ScheduleIcon,
    CheckCircle as CheckCircleIcon
} from '@mui/icons-material';
import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

interface Shop {
    id: number;
    name: string;
    logo_url?: string;
    average_service_time: number;
    primary_color?: string;
    queues?: Queue[];
}

interface Queue {
    id: number;
    queue_items: QueueItem[];
}

interface QueueItem {
    id: number;
    status: string;
    position: number;
}

const WidgetPage: React.FC = () => {
    const { shopId } = useParams<{ shopId: string }>();
    const [searchParams] = useSearchParams();
    
    // State
    const [shop, setShop] = useState<Shop | null>(null);
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState(false);
    const [queuePosition, setQueuePosition] = useState<number | null>(null);
    const [estimatedWait, setEstimatedWait] = useState<number | null>(null);
    
    // Form state
    const [customerName, setCustomerName] = useState('');
    const [customerPhone, setCustomerPhone] = useState('');
    
    // Get customization from URL params
    const primaryColor = searchParams.get('primary') 
        ? `#${searchParams.get('primary')}` 
        : undefined;
    const secondaryColor = searchParams.get('secondary')
        ? `#${searchParams.get('secondary')}`
        : '#ffffff';

    // Calculate queue statistics
    const getQueueStats = () => {
        if (!shop?.queues || shop.queues.length === 0) {
            return { waiting: 0, serving: 0, totalWait: 0 };
        }

        const allItems = shop.queues.flatMap(q => q.queue_items);
        const waiting = allItems.filter(item => item.status === 'waiting').length;
        const serving = allItems.filter(item => item.status === 'being_served').length;
        const totalWait = waiting * shop.average_service_time;

        return { waiting, serving, totalWait };
    };

    // Fetch shop data
    useEffect(() => {
        const fetchShop = async () => {
            try {
                setLoading(true);
                const response = await axios.get(`${API_BASE_URL}/api/shops/${shopId}`);
                setShop(response.data);
                setError(null);
            } catch (err: any) {
                setError(err.response?.data?.detail || 'Failed to load shop information');
            } finally {
                setLoading(false);
            }
        };

        if (shopId) {
            fetchShop();
        }
    }, [shopId]);

    // Handle form submission
    const handleJoinQueue = async (e: React.FormEvent) => {
        e.preventDefault();
        
        if (!customerName.trim() || !customerPhone.trim()) {
            setError('Please enter your name and phone number');
            return;
        }

        try {
            setSubmitting(true);
            setError(null);

            const response = await axios.post(
                `${API_BASE_URL}/api/queues/shop/${shopId}/join`,
                {
                    customer_name: customerName.trim(),
                    customer_phone: customerPhone.trim()
                }
            );

            const stats = getQueueStats();
            setQueuePosition(stats.waiting + stats.serving + 1);
            setEstimatedWait(stats.totalWait + shop!.average_service_time);
            setSuccess(true);
        } catch (err: any) {
            if (err.response?.status === 429) {
                setError('Queue is currently full. Please try again later.');
            } else {
                setError(err.response?.data?.detail || 'Failed to join queue. Please try again.');
            }
        } finally {
            setSubmitting(false);
        }
    };

    // Determine the primary color to use
    const brandColor = primaryColor || shop?.primary_color || '#1976d2';

    // Loading state
    if (loading) {
        return (
            <Box
                sx={{
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    minHeight: '100vh',
                    bgcolor: secondaryColor
                }}
            >
                <CircularProgress sx={{ color: brandColor }} />
            </Box>
        );
    }

    // Error state
    if (error && !shop) {
        return (
            <Box
                sx={{
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    minHeight: '100vh',
                    bgcolor: secondaryColor,
                    p: 2
                }}
            >
                <Alert severity="error">{error}</Alert>
            </Box>
        );
    }

    if (!shop) return null;

    const stats = getQueueStats();

    // Success state
    if (success) {
        return (
            <Box
                sx={{
                    minHeight: '100vh',
                    bgcolor: secondaryColor,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    p: 2
                }}
            >
                <Card sx={{ maxWidth: 500, width: '100%', textAlign: 'center' }}>
                    <CardContent sx={{ p: 4 }}>
                        <CheckCircleIcon sx={{ fontSize: 80, color: brandColor, mb: 2 }} />
                        <Typography variant="h4" gutterBottom fontWeight="bold">
                            You're in Line!
                        </Typography>
                        <Typography variant="h5" color="text.secondary" gutterBottom>
                            Position #{queuePosition}
                        </Typography>
                        <Divider sx={{ my: 3 }} />
                        <Typography variant="h6" gutterBottom>
                            Estimated Wait Time
                        </Typography>
                        <Typography variant="h3" sx={{ color: brandColor, fontWeight: 'bold' }}>
                            ~{estimatedWait} min
                        </Typography>
                        <Typography variant="body2" color="text.secondary" sx={{ mt: 3 }}>
                            Please arrive at {shop.name} when your turn is near.
                            We'll serve you as soon as possible!
                        </Typography>
                    </CardContent>
                </Card>
            </Box>
        );
    }

    // Main widget view
    return (
        <Box
            sx={{
                minHeight: '100vh',
                bgcolor: secondaryColor,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                p: 2
            }}
        >
            <Card sx={{ maxWidth: 500, width: '100%' }}>
                {/* Shop Header */}
                <Box
                    sx={{
                        bgcolor: brandColor,
                        color: 'white',
                        p: 3,
                        textAlign: 'center'
                    }}
                >
                    {shop.logo_url && (
                        <Avatar
                            src={shop.logo_url}
                            sx={{
                                width: 80,
                                height: 80,
                                margin: '0 auto 16px',
                                border: '3px solid white'
                            }}
                        />
                    )}
                    <Typography variant="h5" fontWeight="bold" gutterBottom>
                        {shop.name}
                    </Typography>
                    <Typography variant="body2" sx={{ opacity: 0.9 }}>
                        Join the Queue
                    </Typography>
                </Box>

                <CardContent sx={{ p: 3 }}>
                    {/* Queue Statistics */}
                    <Stack direction="row" spacing={2} sx={{ mb: 3 }}>
                        <Chip
                            icon={<PeopleIcon />}
                            label={`${stats.waiting + stats.serving} in queue`}
                            sx={{ flex: 1 }}
                        />
                        <Chip
                            icon={<ScheduleIcon />}
                            label={`~${stats.totalWait} min wait`}
                            sx={{ flex: 1 }}
                        />
                    </Stack>

                    {error && (
                        <Alert severity="error" sx={{ mb: 2 }}>
                            {error}
                        </Alert>
                    )}

                    {/* Join Form */}
                    <form onSubmit={handleJoinQueue}>
                        <TextField
                            fullWidth
                            label="Your Name"
                            value={customerName}
                            onChange={(e) => setCustomerName(e.target.value)}
                            required
                            disabled={submitting}
                            sx={{ mb: 2 }}
                        />
                        <TextField
                            fullWidth
                            label="Phone Number"
                            value={customerPhone}
                            onChange={(e) => setCustomerPhone(e.target.value)}
                            required
                            disabled={submitting}
                            type="tel"
                            placeholder="(555) 123-4567"
                            sx={{ mb: 3 }}
                        />
                        <Button
                            type="submit"
                            fullWidth
                            variant="contained"
                            size="large"
                            disabled={submitting}
                            sx={{
                                bgcolor: brandColor,
                                '&:hover': {
                                    bgcolor: brandColor,
                                    opacity: 0.9
                                },
                                py: 1.5,
                                fontSize: '1.1rem'
                            }}
                        >
                            {submitting ? (
                                <CircularProgress size={24} sx={{ color: 'white' }} />
                            ) : (
                                'Join Queue'
                            )}
                        </Button>
                    </form>

                    {/* Footer */}
                    <Typography
                        variant="caption"
                        color="text.secondary"
                        sx={{ display: 'block', textAlign: 'center', mt: 2 }}
                    >
                        Served by ZeroQwait
                    </Typography>
                </CardContent>
            </Card>
        </Box>
    );
};

export default WidgetPage;
