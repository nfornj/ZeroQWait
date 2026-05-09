import { Area, AreaChart } from "recharts";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  ChartConfig,
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart";

export type StatCardProps = {
  title: string;
  value: string;
  interval: string;
  trend: "up" | "down" | "neutral";
  data: number[];
};

const trendValues = { up: "+25%", down: "-25%", neutral: "+5%" };

const chartConfig = {
  value: {
    label: "Value",
    color: "var(--chart-1)",
  },
} satisfies ChartConfig;

export default function StatCard({
  title,
  value,
  interval,
  trend,
  data,
}: StatCardProps) {
  const chartData = data.map((item, index) => ({ index: String(index + 1), value: item }));

  return (
    <Card className="h-full flex-grow glass">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <div className="flex items-center justify-between gap-3">
          <p className="text-2xl font-semibold tracking-tight">{value}</p>
          <Badge
            variant={trend === "down" ? "destructive" : trend === "neutral" ? "secondary" : "default"}
          >
            {trendValues[trend]}
          </Badge>
        </div>
        <p className="text-xs text-muted-foreground">{interval}</p>
        <ChartContainer config={chartConfig} className="h-[50px] w-full">
          <AreaChart accessibilityLayer data={chartData} margin={{ left: 0, right: 0, top: 6, bottom: 0 }}>
            <defs>
              <linearGradient id={`area-gradient-${title.replace(/\W/g, "-")}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--color-value)" stopOpacity={0.35} />
                <stop offset="95%" stopColor="var(--color-value)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <ChartTooltip content={<ChartTooltipContent hideLabel />} />
            <Area
              dataKey="value"
              type="monotone"
              stroke="var(--color-value)"
              fill={`url(#area-gradient-${title.replace(/\W/g, "-")})`}
              strokeWidth={2}
            />
          </AreaChart>
        </ChartContainer>
      </CardContent>
    </Card>
  );
}
