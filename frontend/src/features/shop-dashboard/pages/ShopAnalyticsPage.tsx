import React, { useEffect, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  XAxis,
  YAxis,
} from "recharts";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  ChartConfig,
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart";
import { Skeleton } from "@/components/ui/skeleton";
import Header from "../components/Header";
import StatCard from "../components/StatCard";
import api from "../../../services/api";
import { useShop } from "../../../contexts/ShopContext";

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

const visitsConfig = {
  visits: { label: "Visits", color: "var(--chart-1)" },
} satisfies ChartConfig;

const peakConfig = {
  customers: { label: "Customers", color: "var(--chart-2)" },
} satisfies ChartConfig;

export default function ShopAnalyticsPage() {
  const { shop } = useShop();
  const [loading, setLoading] = useState(true);
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [peakHours, setPeakHours] = useState<PeakHoursData | null>(null);
  const [serviceStats, setServiceStats] = useState<ServiceStat[]>([]);

  useEffect(() => {
    const fetchData = async () => {
      if (!shop?.id) return;

      try {
        const [analyticsRes, peakRes, servicesRes] = await Promise.all([
          api.get(`/analytics/${shop.id}?days=30`),
          api.get(`/analytics/peak-hours/${shop.id}?days=30`),
          api.get(`/analytics/services/${shop.id}?days=30`),
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
      <div className="flex min-h-[400px] items-center justify-center">
        <Skeleton className="h-40 w-full max-w-3xl" />
      </div>
    );
  }

  if (!shop) return null;

  const visitChartData = analytics?.daily_stats?.map((entry) => ({
    date: entry.date,
    visits: entry.count,
  })) || [];
  const visits = visitChartData.map((entry) => entry.visits);
  const hours = Array.from({ length: 24 }, (_, hour) => hour);
  const peakChartData = hours.map((hour) => ({
    hour: `${hour}:00`,
    customers: peakHours?.hourly_distribution?.[hour.toString()] || 0,
  }));
  const peakData = peakChartData.map((entry) => entry.customers);
  const visitTrendData = visits.length > 0 ? visits : [0];

  const serviceConfig = serviceStats.reduce<ChartConfig>((config, item, index) => {
    config[item.name] = { label: item.name, color: `var(--chart-${(index % 5) + 1})` };
    return config;
  }, {});

  return (
    <div className="w-full max-w-[1700px]">
      <Header />

      <div className="mb-6 mt-4">
        <h1 className="text-3xl font-semibold tracking-tight">Analytics Dashboard</h1>
        <p className="mt-1 text-sm text-muted-foreground">Performance metrics for the last 30 days</p>
      </div>

      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          title="Total Customers"
          value={analytics?.total_customers?.toString() || "0"}
          interval="Last 30 days"
          trend="neutral"
          data={visitTrendData}
        />
        <StatCard
          title="Avg Wait Time"
          value={`${analytics?.avg_wait_minutes || 0} min`}
          interval="Target under 15 min"
          trend={(analytics?.avg_wait_minutes ?? 0) < 15 ? "up" : "down"}
          data={visitTrendData}
        />
        <StatCard
          title="Avg Service Time"
          value={`${analytics?.avg_service_minutes || 0} min`}
          interval="Rolling average"
          trend="neutral"
          data={visitTrendData}
        />
        <StatCard
          title="Busiest Hour"
          value={peakHours?.peak_hour ? `${peakHours.peak_hour}:00` : "N/A"}
          interval="Peak traffic window"
          trend="neutral"
          data={peakData.length > 0 ? peakData : [0]}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        <Card className="xl:col-span-8">
          <CardHeader>
            <CardTitle>Daily Visits</CardTitle>
          </CardHeader>
          <CardContent>
            <ChartContainer config={visitsConfig} className="h-[300px] w-full">
              <AreaChart accessibilityLayer data={visitChartData}>
                <defs>
                  <linearGradient id="analyticsVisits" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="var(--color-visits)" stopOpacity={0.45} />
                    <stop offset="95%" stopColor="var(--color-visits)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="date" tickLine={false} axisLine={false} tickMargin={8} />
                <YAxis width={48} tickLine={false} axisLine={false} />
                <ChartTooltip content={<ChartTooltipContent />} />
                <Area dataKey="visits" stroke="var(--color-visits)" fill="url(#analyticsVisits)" strokeWidth={2} />
              </AreaChart>
            </ChartContainer>
          </CardContent>
        </Card>

        <Card className="xl:col-span-4">
          <CardHeader>
            <CardTitle>Service Preferences</CardTitle>
          </CardHeader>
          <CardContent>
            <ChartContainer config={serviceConfig} className="h-[300px] w-full">
              <PieChart accessibilityLayer>
                <ChartTooltip content={<ChartTooltipContent nameKey="name" hideLabel />} />
                <Pie data={serviceStats} dataKey="value" nameKey="name" innerRadius={52} outerRadius={96}>
                  {serviceStats.map((item, index) => (
                    <Cell key={item.name} fill={`var(--chart-${(index % 5) + 1})`} />
                  ))}
                </Pie>
              </PieChart>
            </ChartContainer>
          </CardContent>
        </Card>

        <Card className="xl:col-span-12">
          <CardHeader>
            <CardTitle>Peak Hours Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <ChartContainer config={peakConfig} className="h-[300px] w-full">
              <BarChart accessibilityLayer data={peakChartData}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="hour" tickLine={false} axisLine={false} tickMargin={8} />
                <YAxis width={48} tickLine={false} axisLine={false} />
                <ChartTooltip content={<ChartTooltipContent />} />
                <Bar dataKey="customers" fill="var(--color-customers)" radius={4} />
              </BarChart>
            </ChartContainer>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
