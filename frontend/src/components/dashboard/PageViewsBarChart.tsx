import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import Typography from '@mui/material/Typography';
import Stack from '@mui/material/Stack';
import { BarChart } from '@mui/x-charts/BarChart';
import { useTheme } from '@mui/material/styles';

export default function PageViewsBarChart() {
    const theme = useTheme();

    // Safe palette access (some themes might not have 'vars', fallback to standard palette)
    const primaryMain = theme.palette.primary.main;
    const primaryDark = theme.palette.primary.dark;
    const primaryLight = theme.palette.primary.light;

    const colorPalette = [primaryDark, primaryMain, primaryLight];

    return (
        <Card variant="outlined" sx={{ width: '100%' }}>
            <CardContent>
                <Typography component="h2" variant="subtitle2" gutterBottom>
                    Service Volume
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
                            1.3k
                        </Typography>
                        <Chip size="small" color="error" label="-8%" />
                    </Stack>
                    <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                        Services completed for the last 6 months
                    </Typography>
                </Stack>
                <BarChart
                    borderRadius={8}
                    colors={colorPalette}
                    xAxis={[
                        {
                            scaleType: 'band',
                            categoryGapRatio: 0.5,
                            data: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul'],
                        },
                    ]}
                    series={[
                        {
                            id: 'haircuts',
                            label: 'Haircuts',
                            data: [2234, 3872, 2998, 4125, 3357, 2789, 2998],
                            stack: 'A',
                        },
                        {
                            id: 'shaves',
                            label: 'Shaves',
                            data: [3098, 4215, 2384, 2101, 4752, 3593, 2384],
                            stack: 'A',
                        },
                        {
                            id: 'coloring',
                            label: 'Coloring',
                            data: [4051, 2275, 3129, 4693, 3904, 2038, 2275],
                            stack: 'A',
                        },
                    ]}
                    height={250}
                    margin={{ left: 50, right: 0, top: 20, bottom: 20 }}
                    grid={{ horizontal: true }}
                    slotProps={{
                        legend: {
                            hidden: true,
                        },
                    }}
                />
            </CardContent>
        </Card>
    );
}
