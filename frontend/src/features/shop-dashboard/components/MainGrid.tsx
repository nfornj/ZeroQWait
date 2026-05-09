import React, { useEffect, useState } from "react";

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
    <div className="w-full max-w-[1700px]">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="text-xl font-semibold tracking-tight">Overview</h2>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <Select value={period} onValueChange={setPeriod}>
            <SelectTrigger className="w-full glass sm:w-[170px]">
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
                className="glass sm:w-[160px]"
              />
              <Input
                type="date"
                aria-label="End date"
                value={endDate}
                onChange={(event) => setEndDate(event.target.value)}
                className="glass sm:w-[160px]"
              />
            </>
          )}
        </div>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((card) => (
          <StatCard key={card.title} {...card} />
        ))}
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <SessionsChart seriesData={dailyVisits} xLabels={dates} />
        <StackedRevenueChart />
      </div>

      <h2 className="mt-8 text-xl font-semibold tracking-tight">Recent Visits</h2>
      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-12">
        <div className="lg:col-span-9">
          <RecentVisitsDataGrid />
        </div>
        <div className="flex flex-col gap-4 lg:col-span-3">
          <TeamHierarchy />
          <ChartUserByCountry />
        </div>
      </div>
      <Copyright className="my-8" />
    </div>
  );
}
