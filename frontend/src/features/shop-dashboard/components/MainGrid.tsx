import React, { useEffect, useState } from "react";
import { CalendarRange, SlidersHorizontal } from "lucide-react";

import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import api from "../../../services/api";
import { useShop } from "../../../contexts/ShopContext";
import Copyright from "./Copyright";
import ChartUserByCountry from "./ChartUserByCountry";
import StackedRevenueChart from "./StackedRevenueChart";
import SessionsChart from "./SessionsChart";
import StatCard, { StatCardProps } from "./StatCard";
import RecentVisitsDataGrid from "./RecentVisitsDataGrid";
import TeamHierarchy from "./TeamHierarchy";

const defaultStats: StatCardProps[] = [
  { title: "Total Visits", value: "-", interval: "Last 30 days", trend: "neutral", data: [] },
  { title: "Avg Wait Time", value: "-", interval: "Last 30 days", trend: "neutral", data: [] },
  { title: "Avg Service Time", value: "-", interval: "Last 30 days", trend: "neutral", data: [] },
  { title: "Total Revenue", value: "-", interval: "Last 30 days", trend: "neutral", data: [] },
];

export default function MainGrid() {
  const { shop } = useShop();
  const [stats, setStats] = useState<StatCardProps[]>(defaultStats);
  const [dailyVisits, setDailyVisits] = useState<number[]>([]);
  const [dates, setDates] = useState<string[]>([]);
  const [period, setPeriod] = useState<string>("30");
  const [startDate, setStartDate] = useState<string>("");
  const [endDate, setEndDate] = useState<string>("");

  useEffect(() => {
    const fetchAnalytics = async () => {
      if (!shop) return;

      try {
        let url = `/analytics/${shop.id}?`;
        if (period !== "custom") {
          url += `days=${period}`;
        } else {
          url += `start_date=${startDate}&end_date=${endDate}`;
        }

        const response = await api.get(url);
        const data = response.data;
        const dailyCounts = data.daily_stats.map((entry: any) => entry.count);
        const dayLabels = data.daily_stats.map((entry: any) => {
          const date = new Date(entry.date);
          return `${date.getMonth() + 1}/${date.getDate()}`;
        });

        setDailyVisits(dailyCounts);
        setDates(dayLabels);

        const getTrend = (val: number): StatCardProps["trend"] => (val > 0 ? "up" : val < 0 ? "down" : "neutral");
        const intervalLabel = period === "custom" ? `${startDate} - ${endDate}` : `Last ${period} days`;

        setStats([
          {
            title: "Total Visits",
            value: data.total_customers.toString(),
            interval: intervalLabel,
            trend: getTrend(data.trends?.visits || 0),
            data: dailyCounts,
          },
          {
            title: "Avg Wait Time",
            value: `${data.avg_wait_minutes} min`,
            interval: intervalLabel,
            trend: getTrend(-(data.trends?.wait || 0)),
            data: dailyCounts.map(() => data.avg_wait_minutes),
          },
          {
            title: "Avg Service Time",
            value: `${data.avg_service_minutes} min`,
            interval: intervalLabel,
            trend: "neutral",
            data: dailyCounts.map(() => data.avg_service_minutes),
          },
          {
            title: "Total Revenue",
            value: data.total_revenue !== undefined ? `$${data.total_revenue}` : "$0.00",
            interval: intervalLabel,
            trend: getTrend(data.trends?.revenue || 0),
            data: data.daily_stats.map((entry: any) => entry.revenue || 0),
          },
        ]);
      } catch (error) {
        console.error("Failed to fetch analytics:", error);
      }
    };

    if (period !== "custom" || (startDate && endDate)) {
      fetchAnalytics();
    }
  }, [shop, period, startDate, endDate]);

  return (
    <div className="w-full">
      <section id="overview-metrics" className="mt-8 scroll-mt-24">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="text-xl font-bold tracking-tight text-foreground">Performance snapshot</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Top-line metrics for the selected analytics window.
            </p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <Select value={period} onValueChange={setPeriod}>
              <SelectTrigger className="h-10 w-full rounded-xl border-border bg-card shadow-none sm:w-[170px]">
                <CalendarRange className="mr-2 h-4 w-4 text-muted-foreground" />
                <SelectValue placeholder="Select period" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="30">Last 30 Days</SelectItem>
                  <SelectItem value="60">Last 60 Days</SelectItem>
                  <SelectItem value="365">Last Year</SelectItem>
                  <SelectItem value="custom">Custom Range</SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>

            {period === "custom" && (
              <>
                <Input
                  type="date"
                  aria-label="Start date"
                  value={startDate}
                  onChange={(event) => setStartDate(event.target.value)}
                  className="h-10 rounded-xl border-border bg-card shadow-none sm:w-[160px]"
                />
                <Input
                  type="date"
                  aria-label="End date"
                  value={endDate}
                  onChange={(event) => setEndDate(event.target.value)}
                  className="h-10 rounded-xl border-border bg-card shadow-none sm:w-[160px]"
                />
              </>
            )}
          </div>
        </div>

        <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {stats.map((card) => (
            <StatCard key={card.title} {...card} />
          ))}
        </div>
      </section>

      <section id="overview-trends" className="mt-6 scroll-mt-24">
        <div className="mb-4 flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-full border border-border bg-card text-muted-foreground">
            <SlidersHorizontal className="h-4 w-4" />
          </span>
          <div>
            <h2 className="text-xl font-bold tracking-tight text-foreground">Trend workspace</h2>
            <p className="text-sm text-muted-foreground">Daily traffic and revenue composition over time.</p>
          </div>
        </div>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <SessionsChart seriesData={dailyVisits} xLabels={dates} />
          <StackedRevenueChart />
        </div>
      </section>

      <section id="recent-visits" className="mt-8 scroll-mt-24">
        <div className="mb-4">
          <h2 className="text-xl font-bold tracking-tight text-foreground">Recent visits</h2>
          <p className="mt-1 text-sm text-muted-foreground">Completed customer visits and service history.</p>
        </div>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
          <div className="lg:col-span-9">
            <RecentVisitsDataGrid />
          </div>
          <div id="team-context" className="flex scroll-mt-24 flex-col gap-4 lg:col-span-3">
            <TeamHierarchy />
            <ChartUserByCountry />
          </div>
        </div>
      </section>
      <Copyright className="my-10 text-xs text-muted-foreground" />
    </div>
  );
}
