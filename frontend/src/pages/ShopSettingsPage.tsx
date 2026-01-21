import React, { useState, useEffect } from 'react';
import {
    Container,
    Typography,
    Paper,
    TextField,
    Button,
    Box,
    Alert,
    CircularProgress,
    Avatar,
    Card,
    CardActionArea,
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
    Divider
} from '@mui/material';
import Header from '../components/dashboard/Header';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import EventBusyIcon from '@mui/icons-material/EventBusy';
import axios from 'axios';
import { useThemeContext, ThemePreset } from '../contexts/ThemeContext';
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
    const { themePreset, setThemePreset, setDashboardGradient } = useThemeContext();
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
        primary_color: '#1976d2', secondary_color: '', accent_color: '', background_color: '',
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

    // Close Days State
    const [closeDays, setCloseDays] = useState<any[]>([]);
    const [closeDaysLoading, setCloseDaysLoading] = useState(false);
    const [newCloseDate, setNewCloseDate] = useState('');
    const [newCloseReason, setNewCloseReason] = useState('');

    useEffect(() => {
        fetchShop();
    }, []);

    const fetchShop = async () => {
        try {
            const token = localStorage.getItem('token');
            const response = await axios.get(`/shops/my-shops`, {
                headers: { Authorization: `Bearer ${token}` }
            });

            if (response.data.length > 0) {
                const shopData = response.data[0];
                setShop(shopData);
                setFormData({
                    name: shopData.name,
                    description: shopData.description || '',
                    phone: shopData.phone,
                    website: shopData.website || '',
                    primary_color: shopData.primary_color || '#1976d2',
                    secondary_color: shopData.secondary_color || '',
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
            }
            setLoading(false);
        } catch (err) {
            setError('Failed to load shop settings');
            setLoading(false);
        }
    };

    const fetchServices = async (shopId: number) => {
        try {
            setServiceLoading(true);
            const token = localStorage.getItem('token');
            const response = await axios.get(`/shops/${shopId}/services`, {
                headers: { Authorization: `Bearer ${token}` }
            });
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
            const token = localStorage.getItem('token');
            const response = await axios.get(`/shops/${shopId}/close-days`, {
                headers: { Authorization: `Bearer ${token}` }
            });
            setCloseDays(response.data);
            setCloseDaysLoading(false);
        } catch (err) {
            console.error("Failed to fetch close days", err);
            setCloseDaysLoading(false);
        }
    };

    // --- General Settings Handlers ---

    const handleGeneralSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setSaving(true);
        setError(null);
        setSuccess(null);

        try {
            const token = localStorage.getItem('token');
            await axios.put(`/shops/${shop.id}`, formData, {
                headers: { Authorization: `Bearer ${token}` }
            });

            if (logoFile) {
                const fd = new FormData();
                fd.append('file', logoFile);
                await axios.put(`/shops/${shop.id}/logo`, fd, {
                    headers: { Authorization: `Bearer ${token}` }
                });
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
        if (!window.confirm('This will generate 30 days of sample data. Proceed?')) return;
        try {
            const token = localStorage.getItem('token');
            await axios.post(`/shops/${shop.id}/generate-sample-data`, {}, {
                headers: { Authorization: `Bearer ${token}` }
            });
            setSuccess('Sample data generated! Refreshing...');
            setTimeout(() => window.location.reload(), 1500);
        } catch (e) {
            setError('Failed to generate data');
        }
    };

    // --- Services Handlers ---

    const handleServiceSubmit = async () => {
        try {
            const token = localStorage.getItem('token');
            const headers = { Authorization: `Bearer ${token}` };
            if (serviceFormData.id) {
                await axios.put(`/shops/${shop.id}/services/${serviceFormData.id}`, serviceFormData, { headers });
            } else {
                await axios.post(`/shops/${shop.id}/services`, serviceFormData, { headers });
            }
            setOpenServiceDialog(false);
            fetchServices(shop.id);
            setSuccess('Service saved');
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to save service');
        }
    };

    const deleteService = async (id: number) => {
        if (!window.confirm("Delete this service?")) return;
        try {
            const token = localStorage.getItem('token');
            await axios.delete(`/shops/${shop.id}/services/${id}`, {
                headers: { Authorization: `Bearer ${token}` }
            });
            fetchServices(shop.id);
        } catch (e) { setError('Failed to delete service'); }
    }

    // --- Close Days Handlers ---

    const addCloseDay = async () => {
        if (!newCloseDate) return;
        try {
            const token = localStorage.getItem('token');
            await axios.post(`/shops/${shop.id}/close-days`, null, {
                params: { date_str: newCloseDate, reason: newCloseReason },
                headers: { Authorization: `Bearer ${token}` }
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
            const token = localStorage.getItem('token');
            await axios.delete(`/shops/${shop.id}/close-days/${id}`, {
                headers: { Authorization: `Bearer ${token}` }
            });
            fetchCloseDays(shop.id);
        } catch (e) {
            setError('Failed to remove close day');
        }
    };

    if (loading) return <CircularProgress />;
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
        <Container maxWidth="lg">
            <Box sx={{ width: '100%', mb: 4 }}>
                <Header />
            </Box>

            <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                <Typography variant="h4" sx={{ fontWeight: 'bold' }}>Shop Setup</Typography>
            </Box>

            {error && <Alert severity="error" onClose={() => setError(null)} sx={{ mb: 2 }}>{error}</Alert>}
            {success && <Alert severity="success" onClose={() => setSuccess(null)} sx={{ mb: 2 }}>{success}</Alert>}

            <Paper sx={{ width: '100%' }}>
                <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
                    <Tabs value={tabValue} onChange={(e, v) => setTabValue(v)}>
                        <Tab label="General Settings" />
                        <Tab label="Services" />
                        <Tab label="Schedule & Close Days" />
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
                                        }} onClick={() => setThemePreset(theme.id)}>
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

                {/* TAB 2: SERVICES */}
                <CustomTabPanel value={tabValue} index={1}>
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

                {/* TAB 3: SCHEDULE */}
                <CustomTabPanel value={tabValue} index={2}>
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
        </Container>
    );
};

export default ShopSettingsPage;
