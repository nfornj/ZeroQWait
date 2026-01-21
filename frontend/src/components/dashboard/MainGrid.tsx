import React, { useEffect, useState } from 'react';
import Grid from '@mui/material/Grid';
import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import axios from 'axios';
import { useShop } from '../../contexts/ShopContext';
import Copyright from './Copyright';
import ChartUserByCountry from './ChartUserByCountry';
import StackedRevenueChart from './StackedRevenueChart';
import SessionsChart from './SessionsChart';
import PageViewsBarChart from './PageViewsBarChart';
import StatCard, { StatCardProps } from './StatCard';
import RecentVisitsDataGrid from './RecentVisitsDataGrid';
import TeamHierarchy from './TeamHierarchy';

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

  useEffect(() => {
    const fetchAnalytics = async () => {
      if (!shop) return;

      try {
        const token = localStorage.getItem('token');
        const headers = { Authorization: `Bearer ${token}` };

        const response = await axios.get(`/analytics/${shop.id}?days=30`, { headers });
        const data = response.data;

        const dailyCounts = data.daily_stats.map((d: any) => d.count);
        const dayLabels = data.daily_stats.map((d: any) => {
          const date = new Date(d.date);
          return `${date.getMonth() + 1}/${date.getDate()}`;
        });

        setDailyVisits(dailyCounts);
        setDates(dayLabels);

        setStats([
          {
            title: 'Total Visits',
            value: data.total_customers.toString(),
            interval: 'Last 30 days',
            trend: 'up',
            data: dailyCounts
          },
          {
            title: 'Avg Wait Time',
            value: `${data.avg_wait_minutes} min`,
            interval: 'Last 30 days',
            trend: data.avg_wait_minutes < 15 ? 'down' : 'neutral',
            data: dailyCounts.map(() => data.avg_wait_minutes)
          },
          {
            title: 'Avg Service Time',
            value: `${data.avg_service_minutes} min`,
            interval: 'Last 30 days',
            trend: 'neutral',
            data: dailyCounts.map(() => data.avg_service_minutes)
          },
          {
            title: 'Total Revenue',
            value: data.total_revenue !== undefined ? `$${data.total_revenue}` : '$0.00',
            interval: 'Last 30 days',
            trend: 'up',
            data: data.daily_stats.map((d: any) => d.revenue || 0)
          }
        ]);

      } catch (error) {
        console.error("Failed to fetch analytics:", error);
      }
    };

    fetchAnalytics();
  }, [shop]);

  return (
    <Box sx={{ width: '100%', maxWidth: { sm: '100%', md: '1700px' } }}>
      <Typography component="h2" variant="h6" sx={{ mb: 2 }}>
        Overview
      </Typography>
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
            <TeamHierarchy />
            <ChartUserByCountry />
          </Stack>
        </Grid>
      </Grid>
      <Copyright sx={{ my: 4 }} />
    </Box>
  );
}
