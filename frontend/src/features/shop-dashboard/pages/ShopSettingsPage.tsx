import React, { useState, useEffect, useCallback } from 'react';
import {
    Typography,
    Paper,
    TextField,
    Button,
    Box,
    Alert,
    CircularProgress,
    Avatar,
    Card,
    Grid,
    CardContent,
    Tabs,
    Tab,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    InputAdornment,
    IconButton,
    List,
    ListItem,
    ListItemText,
    ListItemSecondaryAction,
    Divider,
    Stack,
    Chip
} from '@mui/material';
import Header from '../components/Header';
import TelegramIntegrationCard from '../components/TelegramIntegrationCard';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import EventBusyIcon from '@mui/icons-material/EventBusy';
import api from '../../../services/api';
import { useThemeContext, ThemePreset } from '../../../contexts/ThemeContext';
import { DataGrid, GridColDef, GridActionsCellItem } from '@mui/x-data-grid';

const THEMES: { id: ThemePreset; name: string; primary: string; secondary: string }[] = [
    { id: 'default', name: 'Coral (Default)', primary: '#FF5A5F', secondary: '#00A699' },
    { id: 'ocean', name: 'Ocean', primary: '#0077B6', secondary: '#48CAE4' },
    { id: 'forest', name: 'Forest', primary: '#2D6A4F', secondary: '#D8F3DC' },
    { id: 'sunset', name: 'Sunset', primary: '#E07A5F', secondary: '#F2CC8F' },
    { id: 'midnight', name: 'Midnight', primary: '#7209B7', secondary: '#4361EE' },
    { id: 'corporate', name: 'Corporate', primary: '#2B2D42', secondary: '#8D99AE' },
];

interface TabPanelProps {
    children?: React.ReactNode;
    index: number;
    value: number;
}

interface ShopAIEnvironmentResponse {
    shop_id: number;
    subscription_tier: string;
    environment_name: string;
    environment_summary: string;
    operating_mode: string;
    status_label: string;
    uses_default: boolean;
    can_customize: boolean;
    capabilities: string[];
    experience_notes: string[];
}

function CustomTabPanel(props: TabPanelProps) {
    const { children, value, index, ...other } = props;
    return (
        <div
            role="tabpanel"
            hidden={value !== index}
            id={`shop-setup-tabpanel-${index}`}
            {...other}
        >
            {value === index && <Box sx={{ p: 0, pt: 3 }}>{children}</Box>}
        </div>
    );
}

const ShopSettingsPage: React.FC = () => {
    // Shared State
    const { themePreset, setThemePreset } = useThemeContext();
    const presetTheme = THEMES.find((item) => item.id === themePreset) || THEMES[0];
    const [shop, setShop] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [tabValue, setTabValue] = useState(0);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);

    // General Settings State
    const [saving, setSaving] = useState(false);
    const [logoFile, setLogoFile] = useState<File | null>(null);
    const [logoPreview, setLogoPreview] = useState<string>('');
    const [formData, setFormData] = useState({
        name: '', description: '', phone: '', website: '',
        primary_color: presetTheme.primary, secondary_color: presetTheme.secondary, accent_color: '', background_color: '',
        logo_url: '', slug: '', dashboard_gradient: 'violet' as string
    });

    // Services State
    const [services, setServices] = useState<any[]>([]);
    const [serviceLoading, setServiceLoading] = useState(false);
    const [openServiceDialog, setOpenServiceDialog] = useState(false);
    const [serviceFormData, setServiceFormData] = useState({
        id: undefined as number | undefined,
        name: '', description: '', duration_minutes: 30, cost: 0.0
    });
    const [generateDataDialogOpen, setGenerateDataDialogOpen] = useState(false);
    const [deleteServiceConfirmId, setDeleteServiceConfirmId] = useState<number | null>(null);

    // AI Settings State
    const [llmLoading, setLlmLoading] = useState(false);
    const [llmError, setLlmError] = useState<string | null>(null);
    const [aiEnvironment, setAiEnvironment] = useState<ShopAIEnvironmentResponse | null>(null);

    // Close Days State
    const [closeDays, setCloseDays] = useState<any[]>([]);
    const [closeDaysLoading, setCloseDaysLoading] = useState(false);
    const [newCloseDate, setNewCloseDate] = useState('');
    const [newCloseReason, setNewCloseReason] = useState('');

    const fetchShop = useCallback(async () => {
        try {
            const response = await api.get(`/shops/my-shops`);

            if (response.data.length > 0) {
                const shopData = response.data[0];
                setShop(shopData);
                setFormData({
                    name: shopData.name,
                    description: shopData.description || '',
                    phone: shopData.phone,
                    website: shopData.website || '',
                    primary_color: shopData.primary_color || presetTheme.primary,
                    secondary_color: shopData.secondary_color || presetTheme.secondary,
                    accent_color: shopData.accent_color || '',
                    background_color: shopData.background_color || '',
                    logo_url: shopData.logo_url || '',
                    slug: shopData.slug || '',
                    dashboard_gradient: shopData.dashboard_gradient || 'violet'
                });
                if (shopData.logo_url) setLogoPreview(shopData.logo_url);

                // Fetch related data
                fetchServices(shopData.id);
                fetchCloseDays(shopData.id);
                fetchLLMSettings(shopData.id);
            }
            setLoading(false);
        } catch (err) {
            setError('Failed to load shop settings');
            setLoading(false);
        }
    }, [presetTheme.primary, presetTheme.secondary]);

    useEffect(() => {
        fetchShop();
    }, [fetchShop]);

    const fetchServices = async (shopId: number) => {
        try {
            setServiceLoading(true);
            const response = await api.get(`/shops/${shopId}/services`);
            setServices(response.data);
            setServiceLoading(false);
        } catch (err) {
            console.error("Failed to fetch services", err);
            setServiceLoading(false);
        }
    };

    const fetchCloseDays = async (shopId: number) => {
        try {
            setCloseDaysLoading(true);
            const response = await api.get(`/shops/${shopId}/close-days`);
            setCloseDays(response.data);
            setCloseDaysLoading(false);
        } catch (err) {
            console.error("Failed to fetch close days", err);
            setCloseDaysLoading(false);
        }
    };

    const fetchLLMSettings = async (shopId: number) => {
        try {
            setLlmLoading(true);
            setLlmError(null);
            const response = await api.get<ShopAIEnvironmentResponse>(`/shops/${shopId}/llm-settings`);
            setAiEnvironment(response.data);
        } catch (err: any) {
            setLlmError(err.response?.data?.detail || 'Failed to load AI settings');
        } finally {
            setLlmLoading(false);
        }
    };

    // --- General Settings Handlers ---

    const handleGeneralSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setSaving(true);
        setError(null);
        setSuccess(null);

        try {
            await api.put(`/shops/${shop.id}`, formData);

            if (logoFile) {
                const fd = new FormData();
                fd.append('file', logoFile);
                await api.put(`/shops/${shop.id}/logo`, fd);
            }
            setSuccess('Settings saved successfully');
            setTimeout(() => window.location.reload(), 1000); // Reload to apply themes globally
        } catch (err) {
            setError('Failed to save settings');
        } finally {
            setSaving(false);
        }
    };

    const handleGenerateData = async () => {
        setGenerateDataDialogOpen(true);
    };

    const confirmGenerateData = async () => {
        setGenerateDataDialogOpen(false);
        try {
            await api.post(`/shops/${shop.id}/generate-sample-data`, {});
            setSuccess('Sample data generated! Refreshing...');
            setTimeout(() => window.location.reload(), 1500);
        } catch (e) {
            setError('Failed to generate data');
        }
    };

    // --- Services Handlers ---

    const handleServiceSubmit = async () => {
        try {
            if (serviceFormData.id) {
                await api.put(`/shops/${shop.id}/services/${serviceFormData.id}`, serviceFormData);
            } else {
                await api.post(`/shops/${shop.id}/services`, serviceFormData);
            }
            setOpenServiceDialog(false);
            fetchServices(shop.id);
            setSuccess('Service saved');
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to save service');
        }
    };

    const deleteService = (id: number) => {
        setDeleteServiceConfirmId(id);
    };

    const confirmDeleteService = async () => {
        if (deleteServiceConfirmId === null) return;
        try {
            await api.delete(`/shops/${shop.id}/services/${deleteServiceConfirmId}`);
            setDeleteServiceConfirmId(null);
            fetchServices(shop.id);
        } catch (e) { setError('Failed to delete service'); }
    };

    // --- Close Days Handlers ---

    const addCloseDay = async () => {
        if (!newCloseDate) return;
        try {
            await api.post(`/shops/${shop.id}/close-days`, null, {
                params: { date_str: newCloseDate, reason: newCloseReason },
            });
            setNewCloseDate('');
            setNewCloseReason('');
            fetchCloseDays(shop.id);
            setSuccess('Close day added');
        } catch (e: any) {
            setError('Failed to add close day');
        }
    };

    const deleteCloseDay = async (id: number) => {
        try {
            await api.delete(`/shops/${shop.id}/close-days/${id}`);
            fetchCloseDays(shop.id);
        } catch (e) {
            setError('Failed to remove close day');
        }
    };

    if (loading) {
        return (
            <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
                <CircularProgress />
            </Box>
        );
    }
    if (!shop) return <Alert severity="warning">No shop found</Alert>;

    const serviceColumns: GridColDef[] = [
        { field: 'name', headerName: 'Name', flex: 1 },
        { field: 'cost', headerName: 'Cost', width: 100, valueFormatter: (v) => `$${Number(v).toFixed(2)}` },
        { field: 'duration_minutes', headerName: 'Duration', width: 100, valueFormatter: (v) => `${v} min` },
        {
            field: 'actions', type: 'actions', width: 100,
            getActions: (params) => [
                <GridActionsCellItem icon={<EditIcon />} label="Edit" onClick={() => {
                    setServiceFormData({
                        id: params.row.id,
                        name: params.row.name,
                        description: params.row.description,
                        duration_minutes: params.row.duration_minutes,
                        cost: params.row.cost
                    });
                    setOpenServiceDialog(true);
                }} />,
                <GridActionsCellItem icon={<DeleteIcon color="error" />} label="Delete" onClick={() => deleteService(params.row.id)} />
            ]
        }
    ];
    return (
        <Box sx={{ width: '100%', maxWidth: { sm: '100%', md: '1700px' } }}>
            <Box sx={{ width: '100%', mb: 2 }}>
                <Header />
            </Box>

            <Grid container spacing={2} sx={{ mb: 2 }}>
                <Grid size={{ xs: 12, md: 8 }}>
                    <Card variant="outlined" sx={{ borderRadius: 3 }}>
                        <CardContent>
                            <Typography variant="h5" sx={{ fontWeight: 700, mb: 0.5 }}>Shop Setup</Typography>
                            <Typography color="text.secondary">
                                Configure branding, services, and schedule settings for your owner workspace.
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>
                <Grid size={{ xs: 12, md: 4 }}>
                    <Card variant="outlined" sx={{ borderRadius: 3, height: '100%' }}>
                        <CardContent>
                            <Typography variant="body2" color="text.secondary">Current Shop</Typography>
                            <Typography variant="h6" sx={{ fontWeight: 700, mt: 0.5 }}>{shop.name}</Typography>
                        </CardContent>
                    </Card>
                </Grid>
            </Grid>

            {error && <Alert severity="error" onClose={() => setError(null)} sx={{ mb: 2 }}>{error}</Alert>}
            {success && <Alert severity="success" onClose={() => setSuccess(null)} sx={{ mb: 2 }}>{success}</Alert>}

            <Paper variant="outlined" sx={{ width: '100%', borderRadius: 3, overflow: 'hidden' }}>
                <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
                    <Tabs value={tabValue} onChange={(e, v) => setTabValue(v)}>
                        <Tab label="General Settings" />
                        <Tab label="AI Environment" />
                        <Tab label="Services" />
                        <Tab label="Schedule & Close Days" />
                        <Tab label="Integrations" />
                    </Tabs>
                </Box>

                {/* TAB 1: GENERAL SETTINGS */}
                <CustomTabPanel value={tabValue} index={0}>
                    <Box component="form" onSubmit={handleGeneralSubmit} p={3}>
                        <Box display="flex" flexWrap="wrap" gap={4}>
                            {/* THEME SECTION */}
                            <Box sx={{ flex: 1, minWidth: '300px' }}>
                                <Typography variant="h6" gutterBottom>Theme & Branding</Typography>
                                <Typography variant="body2" color="text.secondary" mb={2}>Select a preset.</Typography>
                                <Box display="flex" gap={1} mb={3} flexWrap="wrap">
                                    {THEMES.map((theme) => (
                                        <Card key={theme.id} sx={{
                                            border: themePreset === theme.id ? `2px solid ${theme.primary}` : 'none',
                                            transform: themePreset === theme.id ? 'scale(1.05)' : 'none',
                                            width: 80, cursor: 'pointer'
                                        }} onClick={() => {
                                            setThemePreset(theme.id);
                                            // Also update the form data so it saves to the backend
                                            setFormData(prev => ({
                                                ...prev,
                                                primary_color: theme.primary,
                                                secondary_color: theme.secondary
                                            }));
                                        }}>
                                            <Box height={40} bgcolor={theme.primary} />
                                            <Typography variant="caption" align="center" display="block">{theme.name}</Typography>
                                        </Card>
                                    ))}
                                </Box>

                                <TextField fullWidth label="Shop Name" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} sx={{ mb: 2 }} />
                                <TextField fullWidth multiline rows={2} label="Description" value={formData.description} onChange={(e) => setFormData({ ...formData, description: e.target.value })} sx={{ mb: 2 }} />

                                <Box display="flex" gap={2}>
                                    <TextField label="Phone" value={formData.phone} onChange={(e) => setFormData({ ...formData, phone: e.target.value })} fullWidth />
                                    <TextField label="Website" value={formData.website} onChange={(e) => setFormData({ ...formData, website: e.target.value })} fullWidth />
                                </Box>
                            </Box>

                            {/* LOGO Only - Removed Manual Colors */}
                            <Box sx={{ flex: 1, minWidth: '300px' }}>
                                <Typography variant="h6" gutterBottom>Logo</Typography>
                                <Paper variant="outlined" sx={{ p: 2, textAlign: 'center', mb: 3 }}>
                                    {logoPreview ? (
                                        <Avatar src={logoPreview} sx={{ width: 80, height: 80, mx: 'auto', mb: 1 }} />
                                    ) : <CloudUploadIcon sx={{ fontSize: 40, color: 'text.secondary' }} />}
                                    <Button component="label" size="small">
                                        Upload Logo <input type="file" hidden accept="image/*" onChange={(e) => {
                                            const f = e.target.files?.[0];
                                            if (f) { setLogoFile(f); setLogoPreview(URL.createObjectURL(f)); }
                                        }} />
                                    </Button>
                                </Paper>
                            </Box>
                        </Box>

                        <Box mt={3} display="flex" justifyContent="flex-end" gap={2}>
                            <Button variant="outlined" color="warning" onClick={handleGenerateData}>Generate Sample Data</Button>
                            <Button type="submit" variant="contained" disabled={saving}>{saving ? 'Saving...' : 'Save General Settings'}</Button>
                        </Box>
                    </Box>
                </CustomTabPanel>

                {/* TAB 2: AI ENVIRONMENT */}
                <CustomTabPanel value={tabValue} index={1}>
                    <Box p={3}>
                        <Grid container spacing={2}>
                            <Grid size={{ xs: 12, md: 8 }}>
                                <Card variant="outlined" sx={{ borderRadius: 3, mb: 2 }}>
                                    <CardContent>
                                        <Typography variant="h6" gutterBottom>AI Environment</Typography>
                                        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                                            Your shop runs inside a ZeroQwait-managed AI environment built for owner operations, approvals, and day-to-day assistance.
                                        </Typography>

                                        {llmError && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setLlmError(null)}>{llmError}</Alert>}

                                        {llmLoading ? (
                                            <Box display="flex" justifyContent="center" py={6}>
                                                <CircularProgress />
                                            </Box>
                                        ) : (
                                            aiEnvironment && (
                                                <Box display="flex" flexDirection="column" gap={3}>
                                                    <Box>
                                                        <Typography variant="h5" sx={{ fontWeight: 700, mb: 1 }}>
                                                            {aiEnvironment.environment_name}
                                                        </Typography>
                                                        <Typography variant="body1" color="text.secondary">
                                                            {aiEnvironment.environment_summary}
                                                        </Typography>
                                                    </Box>

                                                    <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                                                        <Chip size="small" label={aiEnvironment.status_label} color="primary" />
                                                        <Chip size="small" label={aiEnvironment.operating_mode} variant="outlined" />
                                                        <Chip size="small" label={`Plan: ${aiEnvironment.subscription_tier}`} variant="outlined" />
                                                    </Stack>

                                                    <Alert severity="info">
                                                        ZeroQwait manages the underlying AI stack automatically so your team can focus on running the business, not configuring models.
                                                    </Alert>

                                                    <Box>
                                                        <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1.5 }}>
                                                            What Your AI Team Handles
                                                        </Typography>
                                                        <Stack spacing={1.5}>
                                                            {aiEnvironment.capabilities.map((item) => (
                                                                <Box key={item} sx={{ p: 1.5, borderRadius: 2, border: '1px solid', borderColor: 'divider' }}>
                                                                    <Typography variant="body2">{item}</Typography>
                                                                </Box>
                                                            ))}
                                                        </Stack>
                                                    </Box>
                                                </Box>
                                            )
                                        )}
                                    </CardContent>
                                </Card>
                            </Grid>

                            <Grid size={{ xs: 12, md: 4 }}>
                                <Card variant="outlined" sx={{ borderRadius: 3, mb: 2 }}>
                                    <CardContent>
                                        <Typography variant="subtitle2" color="text.secondary">Environment Status</Typography>
                                        <Typography variant="h6" sx={{ fontWeight: 700, mt: 0.5 }}>
                                            {aiEnvironment?.uses_default ? 'Managed by ZeroQwait' : 'Managed with internal override'}
                                        </Typography>
                                        <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
                                            Technical model, provider, and infrastructure choices are handled centrally and are not exposed in owner settings.
                                        </Typography>
                                    </CardContent>
                                </Card>

                                <Card variant="outlined" sx={{ borderRadius: 3 }}>
                                    <CardContent>
                                        <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 700 }}>How ZeroQwait Runs It</Typography>
                                        <Stack spacing={1}>
                                            {(aiEnvironment?.experience_notes || []).map((note) => (
                                                <Box key={note} sx={{ p: 1.5, borderRadius: 2, border: '1px solid', borderColor: 'divider' }}>
                                                    <Typography variant="body2" color="text.secondary">
                                                        {note}
                                                    </Typography>
                                                </Box>
                                            ))}
                                        </Stack>
                                    </CardContent>
                                </Card>
                            </Grid>
                        </Grid>
                    </Box>
                </CustomTabPanel>

                {/* TAB 3: SERVICES */}
                <CustomTabPanel value={tabValue} index={2}>
                    <Box p={3}>
                        <Box display="flex" justifyContent="space-between" mb={2}>
                            <Typography variant="h6">Manage Services</Typography>
                            <Button startIcon={<AddIcon />} variant="contained" onClick={() => {
                                setServiceFormData({ id: undefined, name: '', description: '', duration_minutes: 30, cost: 0.0 });
                                setOpenServiceDialog(true);
                            }}>Add Service</Button>
                        </Box>
                        <Box height={400} width="100%">
                            <DataGrid rows={services} columns={serviceColumns} loading={serviceLoading} disableRowSelectionOnClick />
                        </Box>
                    </Box>
                </CustomTabPanel>

                {/* TAB 4: SCHEDULE */}
                <CustomTabPanel value={tabValue} index={3}>
                    <Box p={3}>
                        <Typography variant="h6" gutterBottom>Operating Schedule</Typography>
                        <Alert severity="info" sx={{ mb: 3 }}>
                            We're working on advanced weekly scheduling. For now, you can manage your shop's off-days below.
                        </Alert>

                        <Box display="flex" gap={4} flexWrap="wrap">
                            <Box sx={{ flex: 1, minWidth: '300px' }}>
                                <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 'bold' }}>Add Close Date</Typography>
                                <Card variant="outlined">
                                    <CardContent>
                                        <TextField
                                            type="date"
                                            fullWidth
                                            label="Select Date"
                                            InputLabelProps={{ shrink: true }}
                                            value={newCloseDate}
                                            onChange={(e) => setNewCloseDate(e.target.value)}
                                            sx={{ mb: 2 }}
                                        />
                                        <TextField
                                            fullWidth
                                            label="Reason (Optional)"
                                            placeholder="e.g. Public Holiday, Renovation"
                                            value={newCloseReason}
                                            onChange={(e) => setNewCloseReason(e.target.value)}
                                            sx={{ mb: 2 }}
                                        />
                                        <Button
                                            variant="contained"
                                            startIcon={<EventBusyIcon />}
                                            fullWidth
                                            onClick={addCloseDay}
                                            disabled={!newCloseDate}
                                        >
                                            Mark as Closed
                                        </Button>
                                    </CardContent>
                                </Card>
                            </Box>

                            <Box sx={{ flex: 1, minWidth: '300px' }}>
                                <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 'bold' }}>Upcoming Close Dates</Typography>
                                <Paper variant="outlined" sx={{ maxHeight: 300, overflow: 'auto' }}>
                                    {closeDaysLoading ? <CircularProgress sx={{ m: 2 }} /> : closeDays.length === 0 ? (
                                        <Box p={3} textAlign="center"><Typography color="text.secondary">No upcoming off-days.</Typography></Box>
                                    ) : (
                                        <List>
                                            {closeDays.map((day) => (
                                                <React.Fragment key={day.id}>
                                                    <ListItem>
                                                        <ListItemText
                                                            primary={new Date(day.date).toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
                                                            secondary={day.reason || 'No reason provided'}
                                                        />
                                                        <ListItemSecondaryAction>
                                                            <IconButton edge="end" color="error" onClick={() => deleteCloseDay(day.id)}>
                                                                <DeleteIcon />
                                                            </IconButton>
                                                        </ListItemSecondaryAction>
                                                    </ListItem>
                                                    <Divider />
                                                </React.Fragment>
                                            ))}
                                        </List>
                                    )}
                                </Paper>
                            </Box>
                        </Box>
                    </Box>
                </CustomTabPanel>

                {/* TAB 5: INTEGRATIONS */}
                <CustomTabPanel value={tabValue} index={4}>
                    <Box p={3}>
                        <Typography variant="h6" sx={{ fontWeight: 700, mb: 0.5 }}>Integrations</Typography>
                        <Typography variant="body2" color="text.secondary" mb={3}>
                            Connect external services to extend your AI team's reach.
                        </Typography>
                        <Box sx={{ maxWidth: 600 }}>
                            <TelegramIntegrationCard shopId={shop.id} />
                        </Box>
                    </Box>
                </CustomTabPanel>
            </Paper>

            {/* Service Dialog */}
            <Dialog open={openServiceDialog} onClose={() => setOpenServiceDialog(false)}>
                <DialogTitle>{serviceFormData.id ? 'Edit Service' : 'New Service'}</DialogTitle>
                <DialogContent>
                    <Box pt={1} display="flex" flexDirection="column" gap={2} minWidth={300}>
                        <TextField label="Name" fullWidth value={serviceFormData.name} onChange={(e) => setServiceFormData({ ...serviceFormData, name: e.target.value })} />
                        <TextField label="Cost" type="number" fullWidth value={serviceFormData.cost} onChange={(e) => setServiceFormData({ ...serviceFormData, cost: parseFloat(e.target.value) })} InputProps={{ startAdornment: <InputAdornment position="start">$</InputAdornment> }} />
                        <TextField label="Duration (min)" type="number" fullWidth value={serviceFormData.duration_minutes} onChange={(e) => setServiceFormData({ ...serviceFormData, duration_minutes: parseInt(e.target.value) })} />
                        <TextField label="Description" fullWidth multiline rows={2} value={serviceFormData.description} onChange={(e) => setServiceFormData({ ...serviceFormData, description: e.target.value })} />
                    </Box>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setOpenServiceDialog(false)}>Cancel</Button>
                    <Button variant="contained" onClick={handleServiceSubmit} disabled={!serviceFormData.name}>Save</Button>
                </DialogActions>
            </Dialog>

            {/* Generate Sample Data Confirmation */}
            <Dialog open={generateDataDialogOpen} onClose={() => setGenerateDataDialogOpen(false)}>
                <DialogTitle>Generate Sample Data</DialogTitle>
                <DialogContent>
                    <Typography>This will generate 30 days of sample data. Proceed?</Typography>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setGenerateDataDialogOpen(false)}>Cancel</Button>
                    <Button variant="contained" onClick={confirmGenerateData}>Generate</Button>
                </DialogActions>
            </Dialog>

            {/* Delete Service Confirmation */}
            <Dialog open={deleteServiceConfirmId !== null} onClose={() => setDeleteServiceConfirmId(null)}>
                <DialogTitle>Delete Service</DialogTitle>
                <DialogContent>
                    <Typography>Delete this service? This cannot be undone.</Typography>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setDeleteServiceConfirmId(null)}>Cancel</Button>
                    <Button variant="contained" color="error" onClick={confirmDeleteService}>Delete</Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
};

export default ShopSettingsPage;
