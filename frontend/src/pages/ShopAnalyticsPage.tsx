import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
    Container,
    Grid,
    Paper,
    Typography,
    Box,
    Card,
    CardContent,
    CircularProgress,
    Alert,
    Button,
    Divider
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import PeopleIcon from '@mui/icons-material/People';
import axios from 'axios';


interface DailyStat {
    date: string;
    count: number;
}

interface AnalyticsData {
    period_days: number;
    total_customers: number;
    avg_wait_minutes: number;
    avg_service_minutes: number;
    daily_stats: DailyStat[];
}

const ShopAnalyticsPage: React.FC = () => {
    const navigate = useNavigate();
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [data, setData] = useState<AnalyticsData | null>(null);
    const [shopId, setShopId] = useState<number | null>(null);

    useEffect(() => {
        const fetchAnalytics = async () => {
            try {
                const token = localStorage.getItem('token');
                if (!token) {
                    navigate('/login');
                    return;
                }

                // First, get the user's shops to find the shop ID
                const shopsResponse = await axios.get(`/shops/my-shops`, {
                    headers: { Authorization: `Bearer ${token}` }
                });

                if (shopsResponse.data.length === 0) {
                    setError('No shops found');
                    setLoading(false);
                    return;
                }

                const firstShopId = shopsResponse.data[0].id;
                setShopId(firstShopId);

                // Fetch analytics for the shop
                const response = await axios.get(`/analytics/${firstShopId}`, {
                    headers: { Authorization: `Bearer ${token}` }
                });

                setData(response.data);
            } catch (err: any) {
                setError('Failed to load analytics data');
            } finally {
                setLoading(false);
            }
        };

        fetchAnalytics();
    }, [navigate]);

    if (loading) {
        return (
            <Box display="flex" justifyContent="center" alignItems="center" minHeight="80vh">
                <CircularProgress />
            </Box>
        );
    }

    if (error) {
        return (
            <Container maxWidth="lg" sx={{ mt: 4 }}>
                <Alert severity="error">{error}</Alert>
                <Button startIcon={<ArrowBackIcon />} onClick={() => navigate(-1)} sx={{ mt: 2 }}>
                    Back to Dashboard
                </Button>
            </Container>
        );
    }

    if (!data) return null;

    // Find max value for chart scaling
    const maxCount = Math.max(...data.daily_stats.map(d => d.count), 1);

    return (
        <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
            <Box display="flex" alignItems="center" mb={4}>
                <Button startIcon={<ArrowBackIcon />} onClick={() => navigate(-1)} sx={{ mr: 2 }}>
                    Back
                </Button>
                <Typography variant="h4" component="h1">
                    Shop Analytics
                </Typography>
            </Box>

            {/* Summary Cards */}
            <Grid container spacing={3} mb={4}>
                <Grid item xs={12} md={4}>
                    <Card elevation={2}>
                        <CardContent>
                            <Box display="flex" alignItems="center" mb={1}>
                                <PeopleIcon color="primary" sx={{ mr: 1 }} />
                                <Typography variant="h6" color="textSecondary">
                                    Total Customers
                                </Typography>
                            </Box>
                            <Typography variant="h3">{data.total_customers}</Typography>
                            <Typography variant="body2" color="textSecondary">
                                Last 30 days
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>

                <Grid item xs={12} md={4}>
                    <Card elevation={2}>
                        <CardContent>
                            <Box display="flex" alignItems="center" mb={1}>
                                <AccessTimeIcon color="secondary" sx={{ mr: 1 }} />
                                <Typography variant="h6" color="textSecondary">
                                    Avg Wait Time
                                </Typography>
                            </Box>
                            <Typography variant="h3">{data.avg_wait_minutes}m</Typography>
                            <Typography variant="body2" color="textSecondary">
                                Check-in to Service
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>

                <Grid item xs={12} md={4}>
                    <Card elevation={2}>
                        <CardContent>
                            <Box display="flex" alignItems="center" mb={1}>
                                <TrendingUpIcon color="success" sx={{ mr: 1 }} />
                                <Typography variant="h6" color="textSecondary">
                                    Avg Service Time
                                </Typography>
                            </Box>
                            <Typography variant="h3">{data.avg_service_minutes}m</Typography>
                            <Typography variant="body2" color="textSecondary">
                                Service Duration
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>
            </Grid>

            {/* Daily Stats Chart */}
            <Paper elevation={2} sx={{ p: 3 }}>
                <Typography variant="h6" gutterBottom>
                    Customers Per Day (Last 30 Days)
                </Typography>
                <Divider sx={{ mb: 3 }} />

                <Box
                    sx={{
                        display: 'flex',
                        alignItems: 'flex-end',
                        height: 300,
                        gap: 1,
                        overflowX: 'auto',
                        pb: 2
                    }}
                >
                    {data.daily_stats.map((stat) => (
                        <Box
                            key={stat.date}
                            sx={{
                                display: 'flex',
                                flexDirection: 'column',
                                alignItems: 'center',
                                flex: 1,
                                minWidth: 30
                            }}
                        >
                            <Box
                                sx={{
                                    width: '100%',
                                    bgcolor: '#2196f3',
                                    borderRadius: '4px 4px 0 0',
                                    transition: 'height 0.3s',
                                    height: `${(stat.count / maxCount) * 100}%`,
                                    minHeight: stat.count > 0 ? 4 : 0,
                                    position: 'relative',
                                    '&:hover': {
                                        bgcolor: '#1976d2',
                                        '& .tooltip': {
                                            opacity: 1
                                        }
                                    }
                                }}
                            >
                                {/* Tooltip */}
                                <Box
                                    className="tooltip"
                                    sx={{
                                        position: 'absolute',
                                        top: -30,
                                        left: '50%',
                                        transform: 'translateX(-50%)',
                                        bgcolor: 'rgba(0,0,0,0.8)',
                                        color: 'white',
                                        padding: '4px 8px',
                                        fontSize: '0.75rem',
                                        opacity: 0,
                                        transition: 'opacity 0.2s',
                                        whiteSpace: 'nowrap',
                                        pointerEvents: 'none',
                                        zIndex: 1
                                    }}
                                >
                                    {stat.count}
                                </Box>
                            </Box>
                            <Typography variant="caption" sx={{ fontSize: '0.65rem', transform: 'rotate(-45deg)', transformOrigin: 'top left', mt: 2 }}>
                                {new Date(stat.date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                            </Typography>
                        </Box>
                    ))}
                </Box>
            </Paper>
        </Container>
    );
};

export default ShopAnalyticsPage;
