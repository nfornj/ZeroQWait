import React, { useCallback } from "react";
import {
  alpha,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Divider,
  Stack,
  Typography,
  useTheme,
} from "@mui/material";
import BarChartRoundedIcon from "@mui/icons-material/BarChartRounded";
import FileDownloadRoundedIcon from "@mui/icons-material/FileDownloadRounded";
import WarningAmberRoundedIcon from "@mui/icons-material/WarningAmberRounded";
import { BarChart } from "@mui/x-charts/BarChart";
import { LineChart } from "@mui/x-charts/LineChart";
import { PieChart } from "@mui/x-charts/PieChart";
import { SparkLineChart } from "@mui/x-charts/SparkLineChart";
import type { InsightItem, AgentChart, AgentFile } from "./types";
import { useShop } from "../../contexts/ShopContext";

interface InsightsPanelProps {
  items: InsightItem[];
}

/** Trigger a browser download from a base64 string or URL. */
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

const MiniChart: React.FC<{ chart: AgentChart; accent: string }> = ({ chart, accent }) => {
  const labels = chart.data.map((d) => d.label);
  const values = chart.data.map((d) => d.value);

  if (chart.chartType === "sparkline") {
    return (
      <SparkLineChart
        data={values}
        height={48}
        curve="natural"
        area
        color={accent}
      />
    );
  }

  if (chart.chartType === "pie") {
    return (
      <PieChart
        series={[{ data: chart.data.map((d, i) => ({ id: i, value: d.value, label: d.label })) }]}
        height={120}
      />
    );
  }

  if (chart.chartType === "line") {
    return (
      <LineChart
        xAxis={[{ data: labels, scaleType: "band" }]}
        series={[{ data: values, color: accent }]}
        height={120}
        margin={{ top: 8, right: 8, bottom: 24, left: 36 }}
      />
    );
  }

  // Default: bar
  return (
    <BarChart
      xAxis={[{ data: labels, scaleType: "band" }]}
      series={[{ data: values, color: accent }]}
      height={120}
      margin={{ top: 8, right: 8, bottom: 24, left: 36 }}
    />
  );
};

const InsightsPanel: React.FC<InsightsPanelProps> = ({ items }) => {
  const muiTheme = useTheme();
  const { shop } = useShop();
  const brandPrimary = shop?.primary_color || muiTheme.palette.primary.main;
  const cardBg =
    muiTheme.palette.mode === "dark"
      ? "rgba(255, 255, 255, 0.05)"
      : alpha("#ffffff", 0.68);
  const cardBorder =
    muiTheme.palette.mode === "dark"
      ? alpha(brandPrimary, 0.24)
      : alpha(brandPrimary, 0.16);

  const handleDownload = useCallback((file: AgentFile) => {
    downloadFile(file);
  }, []);

  return (
    <Card
      variant="outlined"
      sx={{
        borderRadius: 3,
        borderColor: cardBorder,
        bgcolor: cardBg,
        backdropFilter: "blur(20px)",
      }}
    >
      <CardContent sx={{ py: 1.5 }}>
        <Stack spacing={1}>
          <Stack direction="row" justifyContent="space-between" alignItems="center">
            <Typography variant="h6">Insights</Typography>
            {items.length > 0 && (
              <Chip
                size="small"
                label={items.length}
                sx={{
                  bgcolor: alpha(brandPrimary, 0.14),
                  color: brandPrimary,
                  border: `1px solid ${alpha(brandPrimary, 0.22)}`,
                  fontWeight: 700,
                }}
              />
            )}
          </Stack>

          <Divider sx={{ borderColor: alpha(brandPrimary, 0.12) }} />

          {items.length === 0 && (
            <Stack alignItems="center" spacing={0.5} py={2}>
              <BarChartRoundedIcon sx={{ fontSize: 28, color: alpha(brandPrimary, 0.3) }} />
              <Typography variant="body2" color="text.secondary" textAlign="center">
                Ask financial or analytics questions to see charts and insights here.
              </Typography>
            </Stack>
          )}

          <Stack spacing={1.5} sx={{ maxHeight: 400, overflowY: "auto" }}>
            {items.map((item) => (
              <Box
                key={item.id}
                sx={{
                  p: 1.5,
                  borderRadius: 2,
                  border: `1px solid ${muiTheme.palette.divider}`,
                  bgcolor:
                    muiTheme.palette.mode === "dark"
                      ? "rgba(255,255,255,0.02)"
                      : "rgba(255,255,255,0.6)",
                }}
              >
                {item.type === "chart" && item.chart && (
                  <>
                    <Stack direction="row" spacing={0.75} alignItems="center" mb={0.5}>
                      <BarChartRoundedIcon sx={{ fontSize: 16, color: brandPrimary }} />
                      <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                        {item.chart.title}
                      </Typography>
                    </Stack>
                    <MiniChart chart={item.chart} accent={brandPrimary} />
                  </>
                )}

                {item.type === "summary" && item.summary && (
                  <Stack spacing={1}>
                    <Stack direction="row" spacing={0.75} alignItems="center">
                      <WarningAmberRoundedIcon sx={{ fontSize: 16, color: brandPrimary }} />
                      <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                        {item.summary.title}
                      </Typography>
                    </Stack>
                    <Typography variant="body2" color="text.secondary">
                      {item.summary.body}
                    </Typography>
                    {!!item.summary.chips?.length && (
                      <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap>
                        {item.summary.chips.map((chip) => (
                          <Chip
                            key={`${item.id}_${chip}`}
                            size="small"
                            label={chip}
                            sx={{
                              bgcolor: alpha(brandPrimary, 0.1),
                              color: brandPrimary,
                              border: `1px solid ${alpha(brandPrimary, 0.18)}`,
                            }}
                          />
                        ))}
                      </Stack>
                    )}
                  </Stack>
                )}

                {item.type === "file" && item.file && (
                  <Stack direction="row" spacing={1} alignItems="center" justifyContent="space-between">
                    <Stack direction="row" spacing={0.75} alignItems="center" sx={{ minWidth: 0 }}>
                      <FileDownloadRoundedIcon sx={{ fontSize: 16, color: brandPrimary }} />
                      <Typography
                        variant="body2"
                        sx={{ fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
                      >
                        {item.file.filename}
                      </Typography>
                    </Stack>
                    <Button
                      size="small"
                      variant="outlined"
                      onClick={() => handleDownload(item.file!)}
                      sx={{ textTransform: "none", fontWeight: 600, flexShrink: 0 }}
                    >
                      Download
                    </Button>
                  </Stack>
                )}

                <Typography variant="caption" sx={{ opacity: 0.6, mt: 0.5, display: "block" }}>
                  {new Date(item.timestamp).toLocaleTimeString()}
                </Typography>
              </Box>
            ))}
          </Stack>
        </Stack>
      </CardContent>
    </Card>
  );
};

export default InsightsPanel;
