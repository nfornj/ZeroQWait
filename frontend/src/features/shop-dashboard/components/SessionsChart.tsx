import {
  Area,
  AreaChart,
  CartesianGrid,
  XAxis,
  YAxis,
} from "recharts";

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  ChartConfig,
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart";

export type SessionsChartProps = {
  seriesData?: number[];
  xLabels?: string[];
};

const chartConfig = {
  visits: {
    label: "Visits",
    color: "var(--chart-1)",
  },
} satisfies ChartConfig;

export default function SessionsChart({ seriesData = [], xLabels = [] }: SessionsChartProps) {
  const chartData = xLabels.map((label, index) => ({
    date: label,
    visits: seriesData[index] ?? 0,
  }));
  const totalVisits = seriesData.reduce((a, b) => a + b, 0);

  return (
    <Card className="h-full w-full rounded-2xl border-border bg-card shadow-none">
      <CardHeader className="p-5 pb-2">
        <CardTitle className="text-base font-bold text-foreground">Daily visits</CardTitle>
        <div className="flex items-center gap-2">
          <p className="text-3xl font-bold tracking-tight text-foreground">{totalVisits.toLocaleString()}</p>
          <Badge variant="secondary" className="rounded-full bg-muted px-2.5 py-1 text-xs font-semibold text-foreground">
            Last 30 Days
          </Badge>
        </div>
        <CardDescription className="text-sm">Number of users per day visited</CardDescription>
      </CardHeader>
      <CardContent className="p-5 pt-2">
        <ChartContainer config={chartConfig} className="h-[280px] w-full">
          <AreaChart accessibilityLayer data={chartData} margin={{ left: 0, right: 12, top: 20, bottom: 20 }}>
            <defs>
              <linearGradient id="visitsGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--color-visits)" stopOpacity={0.45} />
                <stop offset="95%" stopColor="var(--color-visits)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid vertical={false} />
            <XAxis
              dataKey="date"
              tickLine={false}
              axisLine={false}
              tickMargin={8}
              interval={4}
            />
            <YAxis width={48} tickLine={false} axisLine={false} />
            <ChartTooltip content={<ChartTooltipContent />} />
            <Area
              dataKey="visits"
              type="linear"
              stroke="var(--color-visits)"
              fill="url(#visitsGradient)"
              strokeWidth={2}
            />
          </AreaChart>
        </ChartContainer>
      </CardContent>
    </Card>
  );
}
