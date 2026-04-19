import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Box,
    Container,
    Grid,
    Paper,
    Typography,
    Card,
    CardContent,
    Divider,
    List,
    ListItem,
    ListItemText,
    ListItemAvatar,
    Avatar,
    Chip,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    CircularProgress,
    Alert,
    Tabs,
    Tab,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Button,
    TextField,
    Select,
    MenuItem,
    FormControl,
    InputLabel,
    IconButton,
    Tooltip,
} from '@mui/material';
import {
    Store as ShopIcon,
    People as PeopleIcon,
    CheckCircle as CheckIcon,
    TrendingUp as TrendingIcon,
    AccessTime as TimeIcon,
    Feedback as FeedbackIcon,
    Close as CloseIcon,
    OpenInNew as OpenInNewIcon,
} from '@mui/icons-material';
import axios from 'axios';
import { constructShopUrl } from '../../../utils/domainUtils';

interface DashboardStats {
    total_shops: number;
    active_shops: number;
    total_users: number;
    real_time: {
        active_customers: number;
        completed_today: number;
    };
}

interface ShopStatus {
    id: number;
    name: number;
    slug: string;
    is_active: boolean;
    waiting_count: number;
    last_activity: string | null;
}

interface FeedbackItem {
    id: number;
    ticket_id: string;
    session_id: string | null;
    name: string | null;
    email: string | null;
    description: string;
    page_context: string | null;
    screenshot_filename: string | null;
    status: 'open' | 'reviewed' | 'closed';
    admin_notes: string | null;
    submitted_at: string;
    updated_at: string;
}

const STATUS_COLORS: Record<string, 'warning' | 'info' | 'default' | 'error'> = {
    open: 'warning',
    reviewed: 'info',
    closed: 'default',
};

const MasterDashboardPage: React.FC = () => {
    const navigate = useNavigate();
    const [activeTab, setActiveTab] = useState(0);

    // ---- Overview state ----
    const [stats, setStats] = useState<DashboardStats | null>(null);
    const [shops, setShops] = useState<ShopStatus[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

    // ---- Feedback state ----
    const [feedbacks, setFeedbacks] = useState<FeedbackItem[]>([]);
    const [feedbackLoading, setFeedbackLoading] = useState(false);
    const [feedbackError, setFeedbackError] = useState<string | null>(null);
    const [selectedFeedback, setSelectedFeedback] = useState<FeedbackItem | null>(null);
    const [detailOpen, setDetailOpen] = useState(false);
    const [editStatus, setEditStatus] = useState<string>('open');
    const [editNotes, setEditNotes] = useState<string>('');
    const [saving, setSaving] = useState(false);

    const authHeaders = () => ({
        Authorization: `Bearer ${localStorage.getItem('token')}`,
    });

    const fetchData = async () => {
        try {
            const [statsRes, shopsRes] = await Promise.all([
                axios.get('/admin/dashboard-stats', { headers: authHeaders() }),
                axios.get('/admin/shops-status', { headers: authHeaders() }),
            ]);
            setStats(statsRes.data);
            setShops(shopsRes.data);
            setError(null);
            setLastUpdated(new Date());
        } catch (err: any) {
            if (loading) {
                setError(err.response?.data?.detail || 'Failed to fetch dashboard data');
            }
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const fetchFeedbacks = useCallback(async () => {
        setFeedbackLoading(true);
        try {
            const res = await axios.get('/api/chat-feedback/', { headers: authHeaders() });
            setFeedbacks(res.data);
            setFeedbackError(null);
        } catch (err: any) {
            setFeedbackError(err.response?.data?.detail || 'Failed to load feedback');
        } finally {
            setFeedbackLoading(false);
        }
    }, []);

    useEffect(() => {
        let isMounted = true;
        const poll = async () => {
            if (!isMounted) return;
            await fetchData();
            if (isMounted) setTimeout(poll, 2000);
        };
        poll();
        return () => { isMounted = false; };
    }, []);

    useEffect(() => {
        if (activeTab === 1) fetchFeedbacks();
    }, [activeTab, fetchFeedbacks]);

    const openDetail = (fb: FeedbackItem) => {
        setSelectedFeedback(fb);
        setEditStatus(fb.status);
        setEditNotes(fb.admin_notes ?? '');
        setDetailOpen(true);
    };

    const saveDetail = async () => {
        if (!selectedFeedback) return;
        setSaving(true);
        try {
            await axios.patch(
                `/api/chat-feedback/${selectedFeedback.ticket_id}`,
                { status: editStatus, admin_notes: editNotes },
                { headers: authHeaders() },
            );
            setDetailOpen(false);
            fetchFeedbacks();
        } catch (err: any) {
            alert(err.response?.data?.detail || 'Save failed');
        } finally {
            setSaving(false);
        }
    };

    if (loading && !stats) return <Box sx={{ display: 'flex', justifyContent: 'center', mt: 10 }}><CircularProgress /></Box>;

    return (
        <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
            {/* Header */}
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                <Box>
                    <Typography variant="h4" sx={{ fontWeight: 'bold', color: 'primary.main', display: 'flex', alignItems: 'center', gap: 2 }}>
                        Corporate Master Dashboard
                        <Chip
                            label="LIVE"
                            color="success"
                            size="small"
                            sx={{
                                fontWeight: 'bold',
                                animation: 'pulse 1.5s infinite',
                                '@keyframes pulse': { '0%': { opacity: 1 }, '50%': { opacity: 0.5 }, '100%': { opacity: 1 } },
                            }}
                        />
                    </Typography>
                    <Typography variant="subtitle1" color="text.secondary">
                        Real-time platform overview and shop performance
                    </Typography>
                </Box>
                {lastUpdated && (
                    <Typography variant="caption" color="text.secondary">
                        Last updated: {lastUpdated.toLocaleTimeString()}
                    </Typography>
                )}
            </Box>

            {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

            {/* Tabs */}
            <Tabs
                value={activeTab}
                onChange={(_, v) => setActiveTab(v)}
                sx={{ mb: 3, borderBottom: '1px solid', borderColor: 'divider' }}
            >
                <Tab label="Overview" />
                <Tab label="Feedback" icon={feedbacks.filter(f => f.status === 'open').length > 0 ?
                    <Chip label={feedbacks.filter(f => f.status === 'open').length} size="small" color="warning" sx={{ ml: 0.5 }} /> : undefined}
                    iconPosition="end"
                />
            </Tabs>

            {/* ====== TAB 0: OVERVIEW ====== */}
            {activeTab === 0 && (
                <>
                    {/* Top Metrics */}
                    <Grid container spacing={3} sx={{ mb: 4 }}>
                        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                            <MetricCard title="Total Shops" value={stats?.total_shops || 0} icon={<ShopIcon color="primary" />} />
                        </Grid>
                        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                            <MetricCard title="Active Customers" value={stats?.real_time.active_customers || 0} icon={<PeopleIcon color="secondary" />} />
                        </Grid>
                        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                            <MetricCard title="Completed Today" value={stats?.real_time.completed_today || 0} icon={<CheckIcon sx={{ color: '#4caf50' }} />} />
                        </Grid>
                        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                            <MetricCard title="Platform Load" value={`${stats?.active_shops || 0} Active`} icon={<TrendingIcon color="info" />} />
                        </Grid>
                    </Grid>

                    {/* Live Shop Status */}
                    <Typography variant="h5" gutterBottom sx={{ mt: 4, mb: 2 }}>Live Shop Feed</Typography>
                    <TableContainer component={Paper} elevation={0} sx={{ border: '1px solid #e0e0e0', borderRadius: 2 }}>
                        <Table>
                            <TableHead sx={{ bgcolor: 'grey.50' }}>
                                <TableRow>
                                    <TableCell sx={{ fontWeight: 'bold' }}>Shop Name</TableCell>
                                    <TableCell sx={{ fontWeight: 'bold' }}>Status</TableCell>
                                    <TableCell sx={{ fontWeight: 'bold' }}>Waiting</TableCell>
                                    <TableCell sx={{ fontWeight: 'bold' }}>Last Activity</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {shops.map((shop) => (
                                    <TableRow
                                        key={shop.id}
                                        hover
                                        onClick={() => { window.location.href = constructShopUrl(shop.slug); }}
                                        sx={{ cursor: 'pointer' }}
                                    >
                                        <TableCell>
                                            <Box sx={{ display: 'flex', alignItems: 'center' }}>
                                                <Typography variant="body1" sx={{ fontWeight: 500 }}>{shop.name}</Typography>
                                                <Typography variant="caption" sx={{ ml: 1, color: 'text.secondary' }}>@{shop.slug}</Typography>
                                            </Box>
                                        </TableCell>
                                        <TableCell>
                                            <Chip label={shop.is_active ? 'Online' : 'Offline'} size="small" color={shop.is_active ? 'success' : 'default'} variant="outlined" />
                                        </TableCell>
                                        <TableCell>
                                            <Box sx={{ display: 'flex', alignItems: 'center' }}>
                                                <Typography variant="body1" sx={{ mr: 1, fontWeight: 600 }}>{shop.waiting_count}</Typography>
                                                <Typography variant="caption" color="text.secondary">customers</Typography>
                                            </Box>
                                        </TableCell>
                                        <TableCell>
                                            <Typography variant="body2" color="text.secondary">
                                                {shop.last_activity ? new Date(shop.last_activity).toLocaleTimeString() : 'No recent activity'}
                                            </Typography>
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </TableContainer>
                </>
            )}

            {/* ====== TAB 1: FEEDBACK ====== */}
            {activeTab === 1 && (
                <>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                        <Typography variant="h5">User Feedback</Typography>
                        <Button size="small" variant="outlined" onClick={fetchFeedbacks} disabled={feedbackLoading}>
                            Refresh
                        </Button>
                    </Box>

                    {feedbackError && <Alert severity="error" sx={{ mb: 2 }}>{feedbackError}</Alert>}

                    {feedbackLoading && feedbacks.length === 0 ? (
                        <Box sx={{ display: 'flex', justifyContent: 'center', mt: 6 }}><CircularProgress /></Box>
                    ) : feedbacks.length === 0 ? (
                        <Alert severity="info">No feedback submissions yet.</Alert>
                    ) : (
                        <TableContainer component={Paper} elevation={0} sx={{ border: '1px solid #e0e0e0', borderRadius: 2 }}>
                            <Table size="small">
                                <TableHead sx={{ bgcolor: 'grey.50' }}>
                                    <TableRow>
                                        <TableCell sx={{ fontWeight: 'bold' }}>Ticket ID</TableCell>
                                        <TableCell sx={{ fontWeight: 'bold' }}>Name</TableCell>
                                        <TableCell sx={{ fontWeight: 'bold' }}>Description</TableCell>
                                        <TableCell sx={{ fontWeight: 'bold' }}>Status</TableCell>
                                        <TableCell sx={{ fontWeight: 'bold' }}>Date</TableCell>
                                        <TableCell sx={{ fontWeight: 'bold' }}>Screenshot</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {feedbacks.map((fb) => (
                                        <TableRow
                                            key={fb.id}
                                            hover
                                            onClick={() => openDetail(fb)}
                                            sx={{ cursor: 'pointer' }}
                                        >
                                            <TableCell>
                                                <Typography variant="caption" sx={{ fontFamily: 'monospace', fontWeight: 700 }}>
                                                    {fb.ticket_id}
                                                </Typography>
                                            </TableCell>
                                            <TableCell>
                                                <Typography variant="body2">{fb.name || <em>anonymous</em>}</Typography>
                                                {fb.email && <Typography variant="caption" color="text.secondary">{fb.email}</Typography>}
                                            </TableCell>
                                            <TableCell sx={{ maxWidth: 260 }}>
                                                <Typography variant="body2" noWrap title={fb.description}>
                                                    {fb.description}
                                                </Typography>
                                            </TableCell>
                                            <TableCell>
                                                <Chip
                                                    label={fb.status}
                                                    size="small"
                                                    color={STATUS_COLORS[fb.status] ?? 'default'}
                                                    variant="outlined"
                                                />
                                            </TableCell>
                                            <TableCell>
                                                <Typography variant="caption" color="text.secondary">
                                                    {new Date(fb.submitted_at).toLocaleDateString()}
                                                </Typography>
                                            </TableCell>
                                            <TableCell>
                                                {fb.screenshot_filename ? (
                                                    <Chip label="Yes" size="small" color="info" variant="outlined" />
                                                ) : (
                                                    <Typography variant="caption" color="text.disabled">—</Typography>
                                                )}
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </TableContainer>
                    )}

                    {/* Feedback detail dialog */}
                    <Dialog open={detailOpen} onClose={() => setDetailOpen(false)} maxWidth="sm" fullWidth>
                        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', pb: 0 }}>
                            <Box>
                                <Typography variant="h6">Feedback Detail</Typography>
                                <Typography variant="caption" sx={{ fontFamily: 'monospace', color: 'text.secondary' }}>
                                    {selectedFeedback?.ticket_id}
                                </Typography>
                            </Box>
                            <IconButton onClick={() => setDetailOpen(false)} size="small">
                                <CloseIcon />
                            </IconButton>
                        </DialogTitle>
                        <DialogContent dividers>
                            {selectedFeedback && (
                                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                                    <Box>
                                        <Typography variant="overline" color="text.secondary">Submitted by</Typography>
                                        <Typography variant="body2">
                                            {selectedFeedback.name || 'Anonymous'}
                                            {selectedFeedback.email ? ` · ${selectedFeedback.email}` : ''}
                                        </Typography>
                                        <Typography variant="caption" color="text.disabled">
                                            {new Date(selectedFeedback.submitted_at).toLocaleString()}
                                        </Typography>
                                    </Box>
                                    <Box>
                                        <Typography variant="overline" color="text.secondary">Description</Typography>
                                        <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                                            {selectedFeedback.description}
                                        </Typography>
                                    </Box>
                                    {selectedFeedback.screenshot_filename && (
                                        <Box>
                                            <Typography variant="overline" color="text.secondary">Screenshot</Typography>
                                            <Box
                                                component="img"
                                                src={`/api/chat-feedback/screenshot/${selectedFeedback.screenshot_filename}`}
                                                alt="Feedback screenshot"
                                                sx={{
                                                    display: 'block',
                                                    maxWidth: '100%',
                                                    maxHeight: 300,
                                                    objectFit: 'contain',
                                                    borderRadius: 1,
                                                    border: '1px solid #e0e0e0',
                                                    mt: 0.5,
                                                }}
                                            />
                                        </Box>
                                    )}
                                    <FormControl size="small" fullWidth>
                                        <InputLabel>Status</InputLabel>
                                        <Select
                                            value={editStatus}
                                            label="Status"
                                            onChange={(e) => setEditStatus(e.target.value)}
                                        >
                                            <MenuItem value="open">Open</MenuItem>
                                            <MenuItem value="reviewed">Reviewed</MenuItem>
                                            <MenuItem value="closed">Closed</MenuItem>
                                        </Select>
                                    </FormControl>
                                    <TextField
                                        label="Admin notes"
                                        multiline
                                        minRows={2}
                                        maxRows={6}
                                        fullWidth
                                        size="small"
                                        value={editNotes}
                                        onChange={(e) => setEditNotes(e.target.value)}
                                        placeholder="Internal notes (not visible to user)"
                                    />
                                </Box>
                            )}
                        </DialogContent>
                        <DialogActions>
                            <Button onClick={() => setDetailOpen(false)} color="inherit">Cancel</Button>
                            <Button onClick={saveDetail} variant="contained" disabled={saving}>
                                {saving ? <CircularProgress size={16} sx={{ mr: 1 }} /> : null}
                                Save
                            </Button>
                        </DialogActions>
                    </Dialog>
                </>
            )}
        </Container>
    );
};

const MetricCard: React.FC<{ title: string; value: string | number; icon: React.ReactNode }> = ({ title, value, icon }) => (
    <Card elevation={0} sx={{ border: '1px solid #e0e0e0', borderRadius: 2 }}>
        <CardContent sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Box>
                <Typography color="text.secondary" variant="overline" display="block">
                    {title}
                </Typography>
                <Typography variant="h4" sx={{ fontWeight: 'bold' }}>
                    {value}
                </Typography>
            </Box>
            <Avatar sx={{ bgcolor: 'grey.100', width: 56, height: 56 }}>
                {icon}
            </Avatar>
        </CardContent>
    </Card>
);

export default MasterDashboardPage;
