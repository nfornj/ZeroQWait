import React, { useState, useEffect } from 'react';
import { Card, CardContent, Typography, Box, CircularProgress } from '@mui/material';
import { BarChart } from '@mui/x-charts/BarChart';
import axios from 'axios';
import { useShop } from '../../../contexts/ShopContext';

import { useTheme, alpha } from '@mui/material/styles';

export default function StackedRevenueChart() {
    const { shop } = useShop();
    const theme = useTheme();
    const [loading, setLoading] = useState(true);
    const [chartData, setChartData] = useState<any[]>([]);
    const [serviceKeys, setServiceKeys] = useState<string[]>([]);

    useEffect(() => {
        const fetchData = async () => {
            if (!shop) return;
            try {
                const token = localStorage.getItem('token');
                const response = await axios.get(`/analytics/revenue/monthly-by-service/${shop.id}`, {
                    headers: { Authorization: `Bearer ${token}` }
                });

                const data = response.data;
                if (data.length > 0) {
                    const keys = new Set<string>();
                    data.forEach((item: any) => {
                        Object.keys(item).forEach(k => {
                            if (k !== 'month') keys.add(k);
                        });
                    });
                    setServiceKeys(Array.from(keys));
                    setChartData(data);
                }
                setLoading(false);
            } catch (error) {
                console.error("Failed to fetch revenue data", error);
                setLoading(false);
            }
        };

        fetchData();
    }, [shop]);

    if (loading) {
        return (
            <Card variant="outlined" sx={{ width: '100%', height: '100%', display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 300 }}>
                <CircularProgress />
            </Card>
        );
    }

    if (chartData.length === 0) {
        return (
            <Card variant="outlined" sx={{ width: '100%', height: '100%' }}>
                <CardContent>
                    <Typography variant="h6" gutterBottom>Monthly Revenue by Service</Typography>
                    <Box height={250} display="flex" alignItems="center" justifyContent="center">
                        <Typography color="text.secondary">No revenue data available</Typography>
                    </Box>
                </CardContent>
            </Card>
        )
    }

    // Generate colors based on theme
    const getSeriesColor = (index: number) => {
        // We'll alternate between primary and secondary shades, or just use primary with opacity
        // Strategy: Use primary.main, primary.dark, primary.light, secondary.main, secondary.light...
        // Or simpler: just alpha shades of primary if we want "shades of theme"
        const opacity = 1 - (index * 0.15) % 1; // 1, 0.85, 0.7...
        // Ensure minimum opacity
        const finalOpacity = Math.max(opacity, 0.2);

        // Let's create a palette array strategy
        const candidates = [
            theme.palette.primary.main,
            theme.palette.primary.dark,
            theme.palette.primary.light,
            theme.palette.secondary.main,
            theme.palette.secondary.light,
            alpha(theme.palette.primary.main, 0.5),
            alpha(theme.palette.secondary.main, 0.5),
        ];

        return candidates[index % candidates.length];
    };

    return (
        <Card variant="outlined" sx={{ width: '100%', height: '100%' }}>
            <CardContent>
                <Typography component="h2" variant="subtitle2" gutterBottom>
                    Monthly Revenue by Service
                </Typography>
                <Box sx={{ width: '100%', height: 280 }}>
                    <BarChart
                        dataset={chartData}
                        xAxis={[{ scaleType: 'band', dataKey: 'month' }]}
                        series={serviceKeys.map((key, index) => ({
                            dataKey: key,
                            label: key,
                            stack: 'total',
                            color: getSeriesColor(index)
                        }))}
                        slotProps={{
                            legend: {
                                direction: 'row',
                                position: { vertical: 'bottom', horizontal: 'center' },
                                padding: 0,
                            },
                        }}
                        margin={{ left: 50, right: 10, top: 20, bottom: 50 }}
                        grid={{ horizontal: true }}
                        borderRadius={4}
                    />
                </Box>
            </CardContent>
        </Card>
    );
}
