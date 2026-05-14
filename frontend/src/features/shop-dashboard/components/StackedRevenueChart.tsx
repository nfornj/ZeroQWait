import React, { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  XAxis,
  YAxis,
} from "recharts";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  ChartConfig,
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart";
import { Skeleton } from "@/components/ui/skeleton";
import api from "../../../services/api";
import { useShop } from "../../../contexts/ShopContext";

export default function StackedRevenueChart() {
  const { shop } = useShop();
  const [loading, setLoading] = useState(true);
  const [chartData, setChartData] = useState<Record<string, number | string>[]>([]);
  const [serviceKeys, setServiceKeys] = useState<string[]>([]);

  useEffect(() => {
    const fetchData = async () => {
      if (!shop) return;

      try {
        const response = await api.get(`/analytics/revenue/monthly-by-service/${shop.id}`);
        const data = response.data;

        if (data.length > 0) {
          const keys = new Set<string>();
          data.forEach((item: Record<string, unknown>) => {
            Object.keys(item).forEach((key) => {
              if (key !== "month") keys.add(key);
            });
          });

          setServiceKeys(Array.from(keys));
          setChartData(data);
        }
      } catch (error) {
        console.error("Failed to fetch revenue data", error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [shop]);

  const chartConfig = useMemo<ChartConfig>(() => {
    return serviceKeys.reduce<ChartConfig>((config, key, index) => {
      config[key] = {
        label: key,
        color: `var(--chart-${(index % 5) + 1})`,
      };
      return config;
    }, {});
  }, [serviceKeys]);

  if (loading) {
    return (
      <Card className="flex min-h-[330px] w-full items-center justify-center rounded-2xl border-border bg-card shadow-none">
        <Skeleton className="h-[240px] w-[92%]" />
      </Card>
    );
  }

  if (chartData.length === 0) {
    return (
      <Card className="h-full w-full rounded-2xl border-border bg-card shadow-none">
        <CardHeader className="p-5">
          <CardTitle className="text-base font-bold text-foreground">Monthly revenue by service</CardTitle>
        </CardHeader>
        <CardContent className="flex h-[280px] items-center justify-center p-5 pt-0 text-sm text-muted-foreground">
          No revenue data available
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="h-full w-full rounded-2xl border-border bg-card shadow-none">
      <CardHeader className="p-5 pb-2">
        <CardTitle className="text-base font-bold text-foreground">Monthly revenue by service</CardTitle>
      </CardHeader>
      <CardContent className="p-5 pt-2">
        <ChartContainer config={chartConfig} className="h-[300px] w-full">
          <BarChart accessibilityLayer data={chartData} margin={{ left: 0, right: 10, top: 20, bottom: 8 }}>
            <CartesianGrid vertical={false} />
            <XAxis dataKey="month" tickLine={false} axisLine={false} tickMargin={8} />
            <YAxis width={50} tickLine={false} axisLine={false} />
            <ChartTooltip content={<ChartTooltipContent />} />
            <ChartLegend content={<ChartLegendContent />} />
            {serviceKeys.map((key, index) => (
              <Bar
                key={key}
                dataKey={key}
                stackId="revenue"
                fill={`var(--chart-${(index % 5) + 1})`}
                radius={[4, 4, 0, 0]}
              />
            ))}
          </BarChart>
        </ChartContainer>
      </CardContent>
    </Card>
  );
}
