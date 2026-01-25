import React, { useEffect, useState } from 'react';
import { Box, Typography, Grid, Paper, CircularProgress, Stack, useTheme } from '@mui/material';
import Header from '../components/dashboard/Header';
import StatCard from '../components/dashboard/StatCard';
import { LineChart } from '@mui/x-charts/LineChart';
import { BarChart } from '@mui/x-charts/BarChart';
import { PieChart } from '@mui/x-charts/PieChart';
import axios from 'axios';
import { useShop } from '../contexts/ShopContext';

export default function ShopAnalyticsPage() {
    const { shop } = useShop();
    const theme = useTheme();
    const [loading, setLoading] = useState(true);
    const [analytics, setAnalytics] = useState<any>(null);
    const [peakHours, setPeakHours] = useState<any>(null);
    const [serviceStats, setServiceStats] = useState<any[]>([]);

    useEffect(() => {
        const fetchData = async () => {
            if (!shop?.id) return;
            try {
                const token = localStorage.getItem('token');
                const headers = { Authorization: `Bearer ${token}` };

                const [analyticsRes, peakRes, servicesRes] = await Promise.all([
                    axios.get(`/api/analytics/${shop.id}?days=30`, { headers }),
                    axios.get(`/api/analytics/peak-hours/${shop.id}?days=30`, { headers }),
                    axios.get(`/api/analytics/services/${shop.id}?days=30`, { headers })
                ]);

                setAnalytics(analyticsRes.data);
                setPeakHours(peakRes.data);
                setServiceStats(servicesRes.data);
            } catch (error) {
                console.error("Error fetching analytics:", error);
            } finally {
                setLoading(false);
            }
        };

        fetchData();
    }, [shop]);

    if (loading) {
        return (
            <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
                <CircularProgress />
            </Box>
        );
    }

    if (!shop) return null;

    // Prepare chart data
    const dates = analytics?.daily_stats?.map((d: any) => d.date) || [];
    const visits = analytics?.daily_stats?.map((d: any) => d.count) || [];

    // Peak hours data (0-23)
    const hours = Array.from({ length: 24 }, (_, i) => i);
    const peakData = hours.map(h => peakHours?.hourly_distribution?.[h.toString()] || 0);

    return (
        <Box sx={{ width: '100%', maxWidth: { sm: '100%', md: '1700px' } }}>
            <Header />

            <Box sx={{ mt: 3, mb: 3 }}>
                <Typography variant="h4" gutterBottom>Analytics Dashboard</Typography>
                <Typography variant="body1" color="text.secondary">
                    Performance metrics for the last 30 days
                </Typography>
            </Box>

            <Grid container spacing={3} mb={4}>
                <Grid item xs={12} sm={6} md={3}>
                    <StatCard
                        title="Total Customers"
                        value={analytics?.total_customers?.toString() || "0"}
                        trend="neutral"
                    />
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                    <StatCard
                        title="Avg Wait Time"
                        value={`${analytics?.avg_wait_minutes || 0} min`}
                        trend={analytics?.avg_wait_minutes < 15 ? "up" : "down"}
                    />
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                    <StatCard
                        title="Avg Service Time"
                        value={`${analytics?.avg_service_minutes || 0} min`}
                        trend="neutral"
                    />
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                    <StatCard
                        title="Busiest Hour"
                        value={peakHours?.peak_hour ? `${peakHours.peak_hour}:00` : "N/A"}
                        trend="neutral"
                    />
                </Grid>
            </Grid>

            <Grid container spacing={3}>
                {/* Visits Over Time */}
                <Grid item xs={12} lg={8}>
                    <Paper sx={{ p: 3, height: '100%' }}>
                        <Typography variant="h6" gutterBottom>Daily Visits</Typography>
                        <Box sx={{ height: 300, width: '100%' }}>
                            <LineChart
                                xAxis={[{ data: dates, scaleType: 'band' }]}
                                series={[{ data: visits, area: true, color: theme.palette.primary.main }]}
                                height={300}
                            />
                        </Box>
                    </Paper>
                </Grid>

                {/* Service Popularity */}
                <Grid item xs={12} lg={4}>
                    <Paper sx={{ p: 3, height: '100%' }}>
                        <Typography variant="h6" gutterBottom>Service Preferences</Typography>
                        <Box sx={{ height: 300, width: '100%' }}>
                            <PieChart
                                series={[
                                    {
                                        data: serviceStats.map((item, index) => ({
                                            id: index,
                                            value: item.value,
                                            label: item.name
                                        })),
                                        highlightScope: { faded: 'global', highlighted: 'item' },
                                        faded: { innerRadius: 30, additionalRadius: -30 },
                                    }
                                ]}
                                height={300}
                                slotProps={{
                                    legend: { hidden: true } // Hide legend if too many items
                                }}
                            />
                        </Box>
                    </Paper>
                </Grid>

                {/* Peak Hours */}
                <Grid item xs={12}>
                    <Paper sx={{ p: 3 }}>
                        <Typography variant="h6" gutterBottom>Peak Hours Distribution</Typography>
                        <Box sx={{ height: 300, width: '100%' }}>
                            <BarChart
                                xAxis={[{ scaleType: 'band', data: hours.map(h => `${h}:00`) }]}
                                series={[{ data: peakData, color: theme.palette.secondary.main }]}
                                height={300}
                            />
                        </Box>
                    </Paper>
                </Grid>
            </Grid>
        </Box>
    );
}
