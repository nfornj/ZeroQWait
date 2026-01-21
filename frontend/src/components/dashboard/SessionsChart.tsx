import { useTheme } from '@mui/material/styles';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import Typography from '@mui/material/Typography';
import Stack from '@mui/material/Stack';
import { LineChart } from '@mui/x-charts/LineChart';

function AreaGradient({ color, id }: { color: string; id: string }) {
  return (
    <defs>
      <linearGradient id={id} x1="50%" y1="0%" x2="50%" y2="100%">
        <stop offset="0%" stopColor={color} stopOpacity={0.5} />
        <stop offset="100%" stopColor={color} stopOpacity={0} />
      </linearGradient>
    </defs>
  );
}

export type SessionsChartProps = {
  seriesData?: number[];
  xLabels?: string[];
};

export default function SessionsChart({ seriesData = [], xLabels = [] }: SessionsChartProps) {
  const theme = useTheme();

  // Use passed data or fallback to empty
  const data = xLabels.length > 0 ? xLabels : [];
  const visits = seriesData.length > 0 ? seriesData : [];

  // Calculate total visits
  const totalVisits = visits.reduce((a, b) => a + b, 0);

  const colorPalette = [
    theme.palette.primary.main,
  ];

  return (
    <Card variant="outlined" sx={{ width: '100%' }}>
      <CardContent>
        <Typography component="h2" variant="subtitle2" gutterBottom>
          Daily Visits
        </Typography>
        <Stack sx={{ justifyContent: 'space-between' }}>
          <Stack
            direction="row"
            sx={{
              alignContent: { xs: 'center', sm: 'flex-start' },
              alignItems: 'center',
              gap: 1,
            }}
          >
            <Typography variant="h4" component="p">
              {totalVisits.toLocaleString()}
            </Typography>
            <Chip size="small" color="success" label="Last 30 Days" />
          </Stack>
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>
            Number of users per day visited
          </Typography>
        </Stack>
        <LineChart
          colors={colorPalette}
          xAxis={[
            {
              scaleType: 'point',
              data,
              tickInterval: (index, i) => (i + 1) % 5 === 0,
            },
          ]}
          series={[
            {
              id: 'visits',
              label: 'Visits',
              showMark: false,
              curve: 'linear',
              stack: 'total',
              area: true,
              stackOrder: 'ascending',
              data: visits,
            },
          ]}
          height={250}
          margin={{ left: 50, right: 20, top: 20, bottom: 20 }}
          grid={{ horizontal: true }}
          sx={{
            '& .MuiAreaElement-series-visits': {
              fill: "url('#visits')",
            },
          }}
        >
          <AreaGradient color={theme.palette.primary.main} id="visits" />
        </LineChart>
      </CardContent>
    </Card>
  );
}
