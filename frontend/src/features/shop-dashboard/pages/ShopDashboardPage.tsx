import React from 'react';
import Stack from '@mui/material/Stack';
import Alert from '@mui/material/Alert';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Button from '@mui/material/Button';
import Typography from '@mui/material/Typography';
import Grid from '@mui/material/Grid';
import Chip from '@mui/material/Chip';
import AutoAwesomeRoundedIcon from '@mui/icons-material/AutoAwesomeRounded';
import OpenInNewRoundedIcon from '@mui/icons-material/OpenInNewRounded';
import { Link as RouterLink } from 'react-router-dom';
import Header from '../components/Header';
import MainGrid from '../components/MainGrid';

const ShopDashboardPage: React.FC = () => {
    return (
        <Stack spacing={2} sx={{ width: '100%', pb: 4, px: 3 }}>
            <Header />

            <Grid container spacing={2}>
                <Grid size={{ xs: 12, md: 8 }}>
                    <Card variant="outlined" sx={{ borderRadius: 3 }}>
                        <CardContent>
                            <Stack direction={{ xs: 'column', md: 'row' }} justifyContent="space-between" spacing={1.5}>
                                <Stack>
                                    <Typography variant="h5" sx={{ mb: 0.5 }}>
                                        Operations Dashboard
                                    </Typography>
                                    <Typography color="text.secondary">
                                        Live business metrics, queue trends, and performance widgets are active.
                                    </Typography>
                                </Stack>
                                <Stack direction="row" spacing={1} alignItems="center">
                                    <Chip icon={<AutoAwesomeRoundedIcon />} label="MUI Widgets" color="primary" variant="outlined" />
                                    <Button
                                        component={RouterLink}
                                        to="/dashboard"
                                        variant="contained"
                                        endIcon={<OpenInNewRoundedIcon />}
                                    >
                                        Open Live Dashboard
                                    </Button>
                                </Stack>
                            </Stack>
                        </CardContent>
                    </Card>
                </Grid>

                <Grid size={{ xs: 12, md: 4 }}>
                    <Alert severity="info" sx={{ borderRadius: 3, height: '100%' }}>
                        Tip: Use the live dashboard for today view, operations summaries, and agent orchestration. This page remains the historical analytics workspace.
                    </Alert>
                </Grid>
            </Grid>

            <MainGrid />
        </Stack>
    );
};

export default ShopDashboardPage;
