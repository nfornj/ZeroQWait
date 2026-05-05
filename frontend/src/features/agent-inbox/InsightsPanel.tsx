import React, { useCallback } from "react";
import { BarChart2, Download, AlertTriangle } from "lucide-react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  Tooltip,
} from "recharts";
import { Button } from "../../components/ui/button";
import { useOwnerBrand } from "../../hooks/useOwnerBrand";
import { resolveAgentChart } from "./types";
import type { InsightItem, AgentChart, AgentFile, ResolvedAgentChart } from "./types";

interface InsightsPanelProps {
  items: InsightItem[];
}

const downloadFile = (file: AgentFile) => {
  const link = document.createElement("a");
  if (file.content.startsWith("http://") || file.content.startsWith("https://")) {
    link.href = file.content;
  } else {
    link.href = `data:${file.mimeType};base64,${file.content}`;
  }
  link.download = file.filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
};

const FALLBACK_COLORS = ["#0284c7", "#0f766e", "#ca8a04"];

const buildChartPalette = (chart: ResolvedAgentChart, accent: string) => {
  const explicit = Array.isArray(chart.colors)
    ? chart.colors.filter((v) => typeof v === "string" && v.trim())
    : [];
  return explicit.length > 0 ? explicit : [accent, ...FALLBACK_COLORS];
};

const MiniChart: React.FC<{ chart: AgentChart; accent: string }> = ({ chart, accent }) => {
  const resolvedChart = resolveAgentChart(chart);
  if (!resolvedChart) return null;

  const palette = buildChartPalette(resolvedChart, accent);
  const primaryColor = palette[0] ?? accent;

  if (resolvedChart.chartType === "sparkline") {
    const sparkData = resolvedChart.data.map((point) => {
      const key = resolvedChart.series[0]?.key;
      const val = key ? point[key] : 0;
      return { value: typeof val === "number" ? val : Number(val ?? 0) };
    });
    return (
      <ResponsiveContainer width="100%" height={48}>
        <LineChart data={sparkData}>
          <Line type="monotone" dataKey="value" stroke={primaryColor} dot={false} strokeWidth={2} />
        </LineChart>
      </ResponsiveContainer>
    );
  }

  if (resolvedChart.chartType === "pie") {
    const key = resolvedChart.series[0]?.key;
    const pieData = resolvedChart.data.map((point, i) => ({
      name: String(point[resolvedChart.xKey] ?? i),
      value: key ? (typeof point[key] === "number" ? point[key] as number : Number(point[key] ?? 0)) : 0,
    }));
    return (
      <ResponsiveContainer width="100%" height={120}>
        <PieChart>
          <Pie data={pieData} dataKey="value" nameKey="name" innerRadius={24} outerRadius={48}>
            {pieData.map((_, i) => (
              <Cell key={i} fill={palette[i % palette.length]} />
            ))}
          </Pie>
          {resolvedChart.showLegend && <Tooltip />}
        </PieChart>
      </ResponsiveContainer>
    );
  }

  if (resolvedChart.chartType === "line") {
    return (
      <ResponsiveContainer width="100%" height={120}>
        <LineChart data={resolvedChart.data} margin={{ top: 8, right: 8, bottom: 16, left: 24 }}>
          <XAxis dataKey={resolvedChart.xKey} tick={{ fontSize: 10 }} />
          {resolvedChart.showGrid && <YAxis tick={{ fontSize: 10 }} />}
          {resolvedChart.series.map((s, i) => (
            <Line
              key={s.key}
              type="monotone"
              dataKey={s.key}
              stroke={s.color || palette[i % palette.length]}
              dot={false}
              strokeWidth={2}
              name={s.label}
            />
          ))}
          {resolvedChart.showLegend && <Tooltip />}
        </LineChart>
      </ResponsiveContainer>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={120}>
      <BarChart data={resolvedChart.data} margin={{ top: 8, right: 8, bottom: 16, left: 24 }}>
        <XAxis dataKey={resolvedChart.xKey} tick={{ fontSize: 10 }} />
        {resolvedChart.showGrid && <YAxis tick={{ fontSize: 10 }} />}
        {resolvedChart.series.map((s, i) => (
          <Bar
            key={s.key}
            dataKey={s.key}
            fill={s.color || palette[i % palette.length]}
            name={s.label}
            radius={[3, 3, 0, 0]}
          />
        ))}
        {resolvedChart.showLegend && <Tooltip />}
      </BarChart>
    </ResponsiveContainer>
  );
};

const InsightsPanel: React.FC<InsightsPanelProps> = ({ items }) => {
  const brand = useOwnerBrand();

  const handleDownload = useCallback((file: AgentFile) => {
    downloadFile(file);
  }, []);

  return (
    <div
      className="rounded-2xl border backdrop-blur-xl"
      style={{
        borderColor: brand.glass.border,
        backgroundColor: brand.glass.bg,
      }}
    >
      <div className="px-4 py-3">
        {/* Header */}
        <div className="flex items-center justify-between mb-2">
          <p className="text-base font-semibold">Insights</p>
          {items.length > 0 && (
            <span
              className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-bold border"
              style={{
                backgroundColor: `${brand.primary}24`,
                color: brand.primary,
                borderColor: `${brand.primary}38`,
              }}
            >
              {items.length}
            </span>
          )}
        </div>

        <hr className="mb-3" style={{ borderColor: `${brand.primary}1f` }} />

        {items.length === 0 && (
          <div className="flex flex-col items-center gap-1.5 py-4">
            <BarChart2 className="h-7 w-7 opacity-30" style={{ color: brand.primary }} />
            <p className="text-sm text-muted-foreground text-center">
              Ask financial or analytics questions to see charts and insights here.
            </p>
          </div>
        )}

        <div className="flex flex-col gap-3 max-h-96 overflow-y-auto">
          {items.map((item) => (
            <div
              key={item.id}
              className="rounded-xl border p-3"
              style={{
                borderColor: "hsl(var(--border))",
                backgroundColor: "rgba(255,255,255,0.02)",
              }}
            >
              {item.type === "chart" && item.chart && (
                <>
                  <div className="flex items-center gap-2 mb-1.5">
                    <BarChart2 className="h-4 w-4 flex-shrink-0" style={{ color: brand.primary }} />
                    <div>
                      <p className="text-sm font-semibold">{item.chart.title}</p>
                      {item.chart.description && (
                        <p className="text-xs text-muted-foreground">{item.chart.description}</p>
                      )}
                    </div>
                  </div>
                  <MiniChart chart={item.chart} accent={brand.primary} />
                </>
              )}

              {item.type === "summary" && item.summary && (
                <div className="flex flex-col gap-2">
                  <div className="flex items-center gap-2">
                    <AlertTriangle className="h-4 w-4 flex-shrink-0" style={{ color: brand.primary }} />
                    <p className="text-sm font-semibold">{item.summary.title}</p>
                  </div>
                  <p className="text-sm text-muted-foreground">{item.summary.body}</p>
                  {!!item.summary.chips?.length && (
                    <div className="flex flex-wrap gap-1.5">
                      {item.summary.chips.map((chip) => (
                        <span
                          key={`${item.id}_${chip}`}
                          className="inline-flex items-center rounded-full px-2 py-0.5 text-xs border"
                          style={{
                            backgroundColor: `${brand.primary}1a`,
                            color: brand.primary,
                            borderColor: `${brand.primary}2e`,
                          }}
                        >
                          {chip}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {item.type === "file" && item.file && (
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <Download className="h-4 w-4 flex-shrink-0" style={{ color: brand.primary }} />
                    <p className="text-sm font-semibold truncate">{item.file.filename}</p>
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleDownload(item.file!)}
                    className="flex-shrink-0 h-7 text-xs font-semibold"
                  >
                    Download
                  </Button>
                </div>
              )}

              <p className="text-xs text-muted-foreground/60 mt-1.5 block">
                {new Date(item.timestamp).toLocaleTimeString()}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default InsightsPanel;
