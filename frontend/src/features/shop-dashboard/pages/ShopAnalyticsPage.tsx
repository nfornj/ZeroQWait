import React, { useEffect, useState } from 'react';
import { Box, Typography, Grid, Paper, CircularProgress, Stack, useTheme, Divider } from '@mui/material';
import Header from '../components/Header';
import StatCard from '../components/StatCard';
import { LineChart } from '@mui/x-charts/LineChart';
import { BarChart } from '@mui/x-charts/BarChart';
import { PieChart } from '@mui/x-charts/PieChart';
import api from '../../../services/api';
import { useShop } from '../../../contexts/ShopContext';

interface DailyStat {
    date: string;
    count: number;
}

interface AnalyticsData {
    total_customers: number;
    avg_wait_minutes: number;
    avg_service_minutes: number;
    daily_stats: DailyStat[];
}

interface PeakHoursData {
    peak_hour: number | null;
    hourly_distribution: Record<string, number>;
}

interface ServiceStat {
    name: string;
    value: number;
}

export default function ShopAnalyticsPage() {
    const { shop } = useShop();
    const theme = useTheme();
    const [loading, setLoading] = useState(true);
    const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
    const [peakHours, setPeakHours] = useState<PeakHoursData | null>(null);
    const [serviceStats, setServiceStats] = useState<ServiceStat[]>([]);
    const [payrollExpense, setPayrollExpense] = useState<any>(null);

    useEffect(() => {
        const fetchData = async () => {
            if (!shop?.id) return;
            try {
                const [analyticsRes, peakRes, servicesRes] = await Promise.all([
                    api.get(`/analytics/${shop.id}?days=30`),
                    api.get(`/analytics/peak-hours/${shop.id}?days=30`),
                    api.get(`/analytics/services/${shop.id}?days=30`)
                ]);

                setAnalytics(analyticsRes.data);
                setPeakHours(peakRes.data);
                setServiceStats(servicesRes.data);

                // Payroll expense (non-blocking — may 404 if no approved payslips yet)
                try {
                    const payrollRes = await api.get(`/payroll/shop/${shop.id}/expense-summary?months=3`);
                    setPayrollExpense(payrollRes.data);
                } catch {
                    // No payroll data yet — ignore
                }
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
    const visitTrendData = visits.length > 0 ? visits : [0];

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
                <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                    <StatCard
                        title="Total Customers"
                        value={analytics?.total_customers?.toString() || "0"}
                        interval="Last 30 days"
                        trend="neutral"
                        data={visitTrendData}
                    />
                </Grid>
                <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                    <StatCard
                        title="Avg Wait Time"
                        value={`${analytics?.avg_wait_minutes || 0} min`}
                        interval="Target under 15 min"
                        trend={(analytics?.avg_wait_minutes ?? 0) < 15 ? "up" : "down"}
                        data={visitTrendData}
                    />
                </Grid>
                <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                    <StatCard
                        title="Avg Service Time"
                        value={`${analytics?.avg_service_minutes || 0} min`}
                        interval="Rolling average"
                        trend="neutral"
                        data={visitTrendData}
                    />
                </Grid>
                <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                    <StatCard
                        title="Busiest Hour"
                        value={peakHours?.peak_hour ? `${peakHours.peak_hour}:00` : "N/A"}
                        interval="Peak traffic window"
                        trend="neutral"
                        data={peakData.length > 0 ? peakData : [0]}
                    />
                </Grid>
            </Grid>

            <Grid container spacing={3}>
                {/* Visits Over Time */}
                <Grid size={{ xs: 12, lg: 8 }}>
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
                <Grid size={{ xs: 12, lg: 4 }}>
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
                                        highlightScope: { fade: 'global', highlight: 'item' },
                                        faded: { innerRadius: 30, additionalRadius: -30 },
                                    }
                                ]}
                                height={300}
                                hideLegend
                            />
                        </Box>
                    </Paper>
                </Grid>

                {/* Peak Hours */}
                <Grid size={{ xs: 12 }}>
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

                {/* Payroll Expenses */}
                {payrollExpense && (
                    <Grid size={{ xs: 12 }}>
                        <Paper sx={{ p: 3 }}>
                            <Typography variant="h6" gutterBottom>Payroll Expenses (Last 3 Months)</Typography>
                            <Divider sx={{ mb: 2 }} />
                            <Grid container spacing={3} mb={3}>
                                <Grid size={{ xs: 12, sm: 4 }}>
                                    <StatCard
                                        title="Total Gross Pay"
                                        value={`$${parseFloat(payrollExpense.summary?.total_gross_pay || 0).toLocaleString('en-CA', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
                                        interval={`${payrollExpense.summary?.payslip_count || 0} payslips`}
                                        trend="neutral"
                                        data={[parseFloat(payrollExpense.summary?.total_gross_pay || 0)]}
                                    />
                                </Grid>
                                <Grid size={{ xs: 12, sm: 4 }}>
                                    <StatCard
                                        title="Net Pay Out"
                                        value={`$${parseFloat(payrollExpense.summary?.total_net_pay || 0).toLocaleString('en-CA', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
                                        interval="Employee take-home"
                                        trend="neutral"
                                        data={[parseFloat(payrollExpense.summary?.total_net_pay || 0)]}
                                    />
                                </Grid>
                                <Grid size={{ xs: 12, sm: 4 }}>
                                    <StatCard
                                        title="Employer Obligations"
                                        value={`$${parseFloat(payrollExpense.summary?.total_cra_remittance || 0).toLocaleString('en-CA', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
                                        interval="CPP + EI + Income Tax"
                                        trend="neutral"
                                        data={[parseFloat(payrollExpense.summary?.total_cra_remittance || 0)]}
                                    />
                                </Grid>
                            </Grid>
                            {payrollExpense.monthly_breakdown?.length > 0 && (
                                <Box sx={{ height: 280, width: '100%' }}>
                                    <BarChart
                                        xAxis={[{
                                            scaleType: 'band',
                                            data: payrollExpense.monthly_breakdown.map((r: any) => r.month)
                                        }]}
                                        series={[
                                            {
                                                data: payrollExpense.monthly_breakdown.map((r: any) => parseFloat(r.gross || 0)),
                                                label: 'Gross Pay',
                                                color: theme.palette.primary.main
                                            },
                                            {
                                                data: payrollExpense.monthly_breakdown.map((r: any) => parseFloat(r.net || 0)),
                                                label: 'Net Pay',
                                                color: theme.palette.success.main
                                            },
                                            {
                                                data: payrollExpense.monthly_breakdown.map((r: any) => parseFloat(r.employer_obligations || 0)),
                                                label: 'Employer Obligations',
                                                color: theme.palette.warning.main
                                            }
                                        ]}
                                        height={280}
                                    />
                                </Box>
                            )}
                        </Paper>
                    </Grid>
                )}
            </Grid>
        </Box>
    );
}
