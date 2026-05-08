import React, { useEffect, useState } from 'react';
import Grid from '@mui/material/Grid';
import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { FormControl, Select, MenuItem, TextField } from '@mui/material';
import api from '../../../services/api';
import { useShop } from '../../../contexts/ShopContext';
import Copyright from './Copyright';
import ChartUserByCountry from './ChartUserByCountry';
import StackedRevenueChart from './StackedRevenueChart';
import SessionsChart from './SessionsChart';
import PageViewsBarChart from './PageViewsBarChart';
import StatCard, { StatCardProps } from './StatCard';
import RecentVisitsDataGrid from './RecentVisitsDataGrid';
import TeamHierarchy from './TeamHierarchy';
import InventorySummaryWidget from './InventorySummaryWidget';

const defaultStats: StatCardProps[] = [
  { title: 'Total Visits', value: '-', interval: 'Last 30 days', trend: 'neutral', data: [] },
  { title: 'Avg Wait Time', value: '-', interval: 'Last 30 days', trend: 'neutral', data: [] },
  { title: 'Avg Service Time', value: '-', interval: 'Last 30 days', trend: 'neutral', data: [] },
  { title: 'Total Revenue', value: '-', interval: 'Last 30 days', trend: 'neutral', data: [] },
];

export default function MainGrid() {
  const { shop } = useShop();
  const [stats, setStats] = useState<StatCardProps[]>(defaultStats);
  const [dailyVisits, setDailyVisits] = useState<number[]>([]);
  const [dates, setDates] = useState<string[]>([]);

  // Date Range State
  const [period, setPeriod] = useState<string>('30'); // 30, 60, 365, custom
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');

  useEffect(() => {
    const fetchAnalytics = async () => {
      if (!shop) return;

      try {
        let url = `/analytics/${shop.id}?`;
        if (period !== 'custom') {
          url += `days=${period}`;
        } else {
          url += `start_date=${startDate}&end_date=${endDate}`;
        }

        const response = await api.get(url);
        const data = response.data;

        const dailyCounts = data.daily_stats.map((d: any) => d.count);
        const dayLabels = data.daily_stats.map((d: any) => {
          const date = new Date(d.date);
          return `${date.getMonth() + 1}/${date.getDate()}`;
        });

        setDailyVisits(dailyCounts);
        setDates(dayLabels);

        // Helper to format trend
        const getTrend = (val: number) => val > 0 ? 'up' : val < 0 ? 'down' : 'neutral';
        const getTrendValue = (val: number) => val !== 0 ? `${val > 0 ? '+' : ''}${val}%` : '';

        const intervalLabel = period === 'custom'
          ? `${startDate} - ${endDate}`
          : `Last ${period} days`;

        setStats([
          {
            title: 'Total Visits',
            value: data.total_customers.toString(),
            interval: intervalLabel,
            trend: getTrend(data.trends?.visits || 0),
            data: dailyCounts
          },
          {
            title: 'Avg Wait Time',
            value: `${data.avg_wait_minutes} min`,
            interval: intervalLabel,
            trend: getTrend(-(data.trends?.wait || 0)),
            data: dailyCounts.map(() => data.avg_wait_minutes)
          },
          {
            title: 'Avg Service Time',
            value: `${data.avg_service_minutes} min`,
            interval: intervalLabel,
            trend: 'neutral',
            data: dailyCounts.map(() => data.avg_service_minutes)
          },
          {
            title: 'Total Revenue',
            value: data.total_revenue !== undefined ? `$${data.total_revenue}` : '$0.00',
            interval: intervalLabel,
            trend: getTrend(data.trends?.revenue || 0),
            data: data.daily_stats.map((d: any) => d.revenue || 0)
          }
        ]);

      } catch (error) {
        console.error("Failed to fetch analytics:", error);
      }
    };

    if (period !== 'custom' || (startDate && endDate)) {
      fetchAnalytics();
    }
  }, [shop, period, startDate, endDate]);

  return (
    <Box sx={{ width: '100%', maxWidth: { sm: '100%', md: '1700px' } }}>
      {/* Title */}
      <Typography component="h2" variant="h6" sx={{ mb: 2 }}>
        Overview
      </Typography>

      {/* Controls - separate section */}
      <Box display="flex" justifyContent="flex-end" mb={4} sx={{ marginTop: 2 }}>
        <Stack direction="row" spacing={2} alignItems="center">
          <FormControl size="small">
            <Select
              value={period}
              onChange={(e) => setPeriod(e.target.value)}
              sx={{ minWidth: 150, bgcolor: 'var(--owner-glass-bg)', backdropFilter: 'blur(18px)', borderRadius: 2, boxShadow: 'var(--owner-glass-shadow)', '& .MuiOutlinedInput-notchedOutline': { borderColor: 'var(--owner-glass-border)' } }}
            >
              <MenuItem value="30">Last 30 Days</MenuItem>
              <MenuItem value="60">Last 60 Days</MenuItem>
              <MenuItem value="365">Last Year</MenuItem>
              <MenuItem value="custom">Custom Range</MenuItem>
            </Select>
          </FormControl>

          {period === 'custom' && (
            <>
              <TextField
                type="date"
                size="small"
                label="Start"
                InputLabelProps={{ shrink: true }}
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                sx={{ '& .MuiOutlinedInput-root': { bgcolor: 'var(--owner-glass-bg)', backdropFilter: 'blur(18px)', boxShadow: 'var(--owner-glass-shadow)', '& fieldset': { borderColor: 'var(--owner-glass-border)' } } }}
              />
              <TextField
                type="date"
                size="small"
                label="End"
                InputLabelProps={{ shrink: true }}
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                sx={{ '& .MuiOutlinedInput-root': { bgcolor: 'var(--owner-glass-bg)', backdropFilter: 'blur(18px)', boxShadow: 'var(--owner-glass-shadow)', '& fieldset': { borderColor: 'var(--owner-glass-border)' } } }}
              />
            </>
          )}
        </Stack>
      </Box>

      <Grid
        container
        spacing={2}
        columns={12}
        sx={{ mb: (theme) => theme.spacing(2) }}
      >
        {stats.map((card, index) => (
          <Grid key={index} size={{ xs: 12, sm: 6, lg: 3 }}>
            <StatCard {...card} />
          </Grid>
        ))}

        <Grid size={{ xs: 12, md: 6 }}>
          <SessionsChart seriesData={dailyVisits} xLabels={dates} />
        </Grid>
        <Grid size={{ xs: 12, md: 6 }}>
          <StackedRevenueChart />
        </Grid>
      </Grid>

      <Typography component="h2" variant="h6" sx={{ mb: 2 }}>
        Recent Visits
      </Typography>
      <Grid container spacing={2} columns={12}>
        <Grid size={{ xs: 12, lg: 9 }}>
          <RecentVisitsDataGrid />
        </Grid>
        <Grid size={{ xs: 12, lg: 3 }}>
          <Stack gap={2} direction={{ xs: 'column', sm: 'row', lg: 'column' }}>
            <InventorySummaryWidget />
            <TeamHierarchy />
            <ChartUserByCountry />
          </Stack>
        </Grid>
      </Grid>
      <Copyright sx={{ my: 4 }} />
    </Box>
  );
}
