import React, { useState, useEffect } from 'react';
import {
    Box,
    Container,
    Grid,
    Paper,
    Typography,
    Card,
    CardContent,
    Divider,
    List,
    ListItem,
    ListItemText,
    ListItemAvatar,
    Avatar,
    Chip,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    CircularProgress,
    Alert
} from '@mui/material';
import {
    Store as ShopIcon,
    People as PeopleIcon,
    CheckCircle as CheckIcon,
    TrendingUp as TrendingIcon,
    AccessTime as TimeIcon
} from '@mui/icons-material';
import axios from 'axios';

interface DashboardStats {
    total_shops: number;
    active_shops: number;
    total_users: number;
    real_time: {
        active_customers: number;
        completed_today: number;
    };
}

interface ShopStatus {
    id: number;
    name: number;
    slug: string;
    is_active: boolean;
    waiting_count: number;
    last_activity: string | null;
}

const MasterDashboardPage: React.FC = () => {
    const [stats, setStats] = useState<DashboardStats | null>(null);
    const [shops, setShops] = useState<ShopStatus[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

    const fetchData = async () => {
        try {
            const token = localStorage.getItem('token');
            const headers = { Authorization: `Bearer ${token}` };

            const [statsRes, shopsRes] = await Promise.all([
                axios.get('/admin/dashboard-stats', { headers }),
                axios.get('/admin/shops-status', { headers })
            ]);

            setStats(statsRes.data);
            setShops(shopsRes.data);
            setError(null);
            setLastUpdated(new Date());
        } catch (err: any) {
            // Only set error on initial load or if persistent failure
            if (loading) {
                setError(err.response?.data?.detail || 'Failed to fetch dashboard data');
            }
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        let isMounted = true;

        const poll = async () => {
            if (!isMounted) return;
            await fetchData();
            if (isMounted) {
                setTimeout(poll, 2000); // Poll every 2 seconds
            }
        };

        poll();

        return () => {
            isMounted = false;
        };
    }, []);

    if (loading && !stats) return <Box sx={{ display: 'flex', justifyContent: 'center', mt: 10 }}><CircularProgress /></Box>;

    return (
        <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
            <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 3 }}>
                <Box>
                    <Typography variant="h4" sx={{ fontWeight: 'bold', color: 'primary.main', display: 'flex', alignItems: 'center', gap: 2 }}>
                        Corporate Master Dashboard
                        <Chip
                            label="LIVE"
                            color="success"
                            size="small"
                            sx={{
                                fontWeight: 'bold',
                                animation: 'pulse 1.5s infinite',
                                '@keyframes pulse': {
                                    '0%': { opacity: 1 },
                                    '50%': { opacity: 0.5 },
                                    '100%': { opacity: 1 }
                                }
                            }}
                        />
                    </Typography>
                    <Typography variant="subtitle1" color="text.secondary">
                        Real-time platform overview and shop performance
                    </Typography>
                </Box>
                {lastUpdated && (
                    <Typography variant="caption" color="text.secondary">
                        Last updated: {lastUpdated.toLocaleTimeString()}
                    </Typography>
                )}
            </Box>

            {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

            {/* Top Metrics */}
            <Grid container spacing={3} sx={{ mb: 4 }}>
                <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                    <MetricCard title="Total Shops" value={stats?.total_shops || 0} icon={<ShopIcon color="primary" />} />
                </Grid>
                <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                    <MetricCard title="Active Customers" value={stats?.real_time.active_customers || 0} icon={<PeopleIcon color="secondary" />} />
                </Grid>
                <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                    <MetricCard title="Completed Today" value={stats?.real_time.completed_today || 0} icon={<CheckIcon sx={{ color: '#4caf50' }} />} />
                </Grid>
                <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                    <MetricCard title="Platform Load" value={`${stats?.active_shops || 0} Active`} icon={<TrendingIcon color="info" />} />
                </Grid>
            </Grid>

            {/* Live Shop Status */}
            <Typography variant="h5" gutterBottom sx={{ mt: 4, mb: 2 }}>
                Live Shop Feed
            </Typography>
            <TableContainer component={Paper} elevation={0} sx={{ border: '1px solid #e0e0e0', borderRadius: 2 }}>
                <Table>
                    <TableHead sx={{ bgcolor: 'grey.50' }}>
                        <TableRow>
                            <TableCell sx={{ fontWeight: 'bold' }}>Shop Name</TableCell>
                            <TableCell sx={{ fontWeight: 'bold' }}>Status</TableCell>
                            <TableCell sx={{ fontWeight: 'bold' }}>Waiting</TableCell>
                            <TableCell sx={{ fontWeight: 'bold' }}>Last Activity</TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {shops.map((shop) => (
                            <TableRow key={shop.id} hover>
                                <TableCell>
                                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                                        <Typography variant="body1" sx={{ fontWeight: 500 }}>{shop.name}</Typography>
                                        <Typography variant="caption" sx={{ ml: 1, color: 'text.secondary' }}>@{shop.slug}</Typography>
                                    </Box>
                                </TableCell>
                                <TableCell>
                                    <Chip
                                        label={shop.is_active ? "Online" : "Offline"}
                                        size="small"
                                        color={shop.is_active ? "success" : "default"}
                                        variant="outlined"
                                    />
                                </TableCell>
                                <TableCell>
                                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                                        <Typography variant="body1" sx={{ mr: 1, fontWeight: 600 }}>{shop.waiting_count}</Typography>
                                        <Typography variant="caption" color="text.secondary">customers</Typography>
                                    </Box>
                                </TableCell>
                                <TableCell>
                                    <Typography variant="body2" color="text.secondary">
                                        {shop.last_activity ? new Date(shop.last_activity).toLocaleTimeString() : 'No recent activity'}
                                    </Typography>
                                </TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            </TableContainer>
        </Container>
    );
};

const MetricCard: React.FC<{ title: string; value: string | number; icon: React.ReactNode }> = ({ title, value, icon }) => (
    <Card elevation={0} sx={{ border: '1px solid #e0e0e0', borderRadius: 2 }}>
        <CardContent sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Box>
                <Typography color="text.secondary" variant="overline" display="block">
                    {title}
                </Typography>
                <Typography variant="h4" sx={{ fontWeight: 'bold' }}>
                    {value}
                </Typography>
            </Box>
            <Avatar sx={{ bgcolor: 'grey.100', width: 56, height: 56 }}>
                {icon}
            </Avatar>
        </CardContent>
    </Card>
);

export default MasterDashboardPage;
