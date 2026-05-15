import { Cell, Label, Pie, PieChart } from "recharts";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  ChartConfig,
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart";
import { Progress } from "@/components/ui/progress";

import {
  BrazilFlag,
  GlobeFlag,
  IndiaFlag,
  UsaFlag,
} from "./CustomIcons";

const countries = [
  {
    name: "India",
    value: 50,
    metric: 50000,
    flag: <IndiaFlag />,
    color: "var(--chart-1)",
  },
  {
    name: "USA",
    value: 35,
    metric: 35000,
    flag: <UsaFlag />,
    color: "var(--chart-2)",
  },
  {
    name: "Brazil",
    value: 10,
    metric: 10000,
    flag: <BrazilFlag />,
    color: "var(--chart-3)",
  },
  {
    name: "Other",
    value: 5,
    metric: 5000,
    flag: <GlobeFlag />,
    color: "var(--chart-4)",
  },
];

const chartConfig = countries.reduce<ChartConfig>((config, country) => {
  config[country.name] = {
    label: country.name,
    color: country.color,
  };
  return config;
}, {});

export default function ChartUserByCountry() {
  return (
    <Card className="flex h-full flex-col gap-2 rounded-2xl border-border bg-card shadow-none">
      <CardHeader className="p-5 pb-2">
        <CardTitle className="text-base font-bold text-foreground">Users by country</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4 p-5 pt-0">
        <ChartContainer config={chartConfig} className="mx-auto aspect-square h-[220px]">
          <PieChart accessibilityLayer>
            <ChartTooltip content={<ChartTooltipContent nameKey="name" hideLabel />} />
            <Pie
              data={countries}
              dataKey="metric"
              nameKey="name"
              innerRadius={72}
              outerRadius={100}
              paddingAngle={1}
            >
              {countries.map((country) => (
                <Cell key={country.name} fill={country.color} />
              ))}
              <Label
                content={({ viewBox }) => {
                  if (!viewBox || !("cx" in viewBox) || !("cy" in viewBox)) return null;

                  return (
                    <text x={viewBox.cx} y={viewBox.cy} textAnchor="middle" dominantBaseline="middle">
                      <tspan x={viewBox.cx} y={(viewBox.cy || 0) - 8} className="fill-foreground text-xl font-semibold">
                        98.5K
                      </tspan>
                      <tspan x={viewBox.cx} y={(viewBox.cy || 0) + 16} className="fill-muted-foreground text-xs">
                        Total
                      </tspan>
                    </text>
                  );
                }}
              />
            </Pie>
          </PieChart>
        </ChartContainer>

        <div className="flex flex-col gap-4">
          {countries.map((country) => (
            <div key={country.name} className="flex items-center gap-3">
              {country.flag}
              <div className="flex min-w-0 flex-1 flex-col gap-2">
                <div className="flex items-center justify-between gap-2 text-sm">
                  <span className="font-medium">{country.name}</span>
                  <span className="text-muted-foreground">{country.value}%</span>
                </div>
                <Progress value={country.value} className="h-2" />
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
