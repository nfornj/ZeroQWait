import {
  Bar,
  BarChart,
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

const chartData = [
  { month: "Jan", pageViews: 2234, downloads: 3098, conversions: 4051 },
  { month: "Feb", pageViews: 3872, downloads: 4215, conversions: 2275 },
  { month: "Mar", pageViews: 2998, downloads: 2384, conversions: 3129 },
  { month: "Apr", pageViews: 4125, downloads: 2101, conversions: 4693 },
  { month: "May", pageViews: 3357, downloads: 4752, conversions: 3904 },
  { month: "Jun", pageViews: 2789, downloads: 3593, conversions: 2038 },
  { month: "Jul", pageViews: 2998, downloads: 2384, conversions: 2275 },
];

const chartConfig = {
  pageViews: {
    label: "Page views",
    color: "var(--chart-1)",
  },
  downloads: {
    label: "Downloads",
    color: "var(--chart-2)",
  },
  conversions: {
    label: "Conversions",
    color: "var(--chart-3)",
  },
} satisfies ChartConfig;

export default function PageViewsBarChart() {
  return (
    <Card className="w-full">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium">Page views and downloads</CardTitle>
        <div className="flex items-center gap-2">
          <p className="text-2xl font-semibold tracking-tight">1.3M</p>
          <Badge variant="destructive">-8%</Badge>
        </div>
        <CardDescription>Page views and downloads for the last 6 months</CardDescription>
      </CardHeader>
      <CardContent>
        <ChartContainer config={chartConfig} className="h-[250px] w-full">
          <BarChart accessibilityLayer data={chartData} margin={{ left: 0, right: 8, top: 20, bottom: 0 }}>
            <CartesianGrid vertical={false} />
            <XAxis
              dataKey="month"
              tickLine={false}
              axisLine={false}
              tickMargin={8}
            />
            <YAxis width={48} tickLine={false} axisLine={false} />
            <ChartTooltip content={<ChartTooltipContent />} />
            <Bar dataKey="pageViews" stackId="total" fill="var(--color-pageViews)" radius={[8, 8, 0, 0]} />
            <Bar dataKey="downloads" stackId="total" fill="var(--color-downloads)" radius={[8, 8, 0, 0]} />
            <Bar dataKey="conversions" stackId="total" fill="var(--color-conversions)" radius={[8, 8, 0, 0]} />
          </BarChart>
        </ChartContainer>
      </CardContent>
    </Card>
  );
}
