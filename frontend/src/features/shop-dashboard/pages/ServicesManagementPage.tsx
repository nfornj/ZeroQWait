import React, { useState, useEffect } from 'react';
import api from '../../../services/api';
import {
    Box,
    Typography,
    Button,
    Paper,
    Card,
    CardContent,
    Grid,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    TextField,
    IconButton,
    Alert,
    CircularProgress,
    InputAdornment
} from '@mui/material';
import { DataGrid, GridColDef, GridActionsCellItem, GridToolbar } from '@mui/x-data-grid';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import Header from '../components/Header';
import { useShop } from '../../../contexts/ShopContext';

interface ShopService {
    id: number;
    shop_id: number;
    name: string;
    description: string;
    duration_minutes: number;
    cost: number;
    currency: string;
    is_active: boolean;
}

const ServicesManagementPage: React.FC = () => {
    const { shop } = useShop();
    const [services, setServices] = useState<ShopService[]>([]);
    const [loading, setLoading] = useState(true);
    const [openDialog, setOpenDialog] = useState(false);
    const [formData, setFormData] = useState({
        id: undefined as number | undefined,
        name: '',
        description: '',
        duration_minutes: 30,
        cost: 0.0
    });
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);
    const [submitting, setSubmitting] = useState(false);
    const [deleteConfirmId, setDeleteConfirmId] = useState<number | null>(null);

    useEffect(() => {
        if (shop) {
            fetchServices();
        }
    }, [shop]);

    const fetchServices = async () => {
        if (!shop) return;
        try {
            const response = await api.get(`/shops/${shop.id}/services`);
            setServices(response.data);
            setLoading(false);
        } catch (err: any) {
            setError('Failed to load services');
            setLoading(false);
        }
    };

    const handleOpenDialog = (service?: ShopService) => {
        if (service) {
            setFormData({
                id: service.id,
                name: service.name,
                description: service.description || '',
                duration_minutes: service.duration_minutes,
                cost: service.cost
            });
        } else {
            setFormData({
                id: undefined,
                name: '',
                description: '',
                duration_minutes: 30,
                cost: 0.0
            });
        }
        setError(null);
        setOpenDialog(true);
    };

    const handleSubmit = async () => {
        if (!shop) return;
        setSubmitting(true);
        setError(null);

        try {
            if (formData.id) {
                // Update
                await api.put(`/shops/${shop.id}/services/${formData.id}`, formData);
                setSuccess('Service updated successfully');
            } else {
                // Create
                await api.post(`/shops/${shop.id}/services`, formData);
                setSuccess('Service created successfully');
            }

            setOpenDialog(false);
            fetchServices();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to save service');
        } finally {
            setSubmitting(false);
        }
    };

    const handleDelete = (id: number) => {
        setDeleteConfirmId(id);
    };

    const confirmDelete = async () => {
        if (!shop || deleteConfirmId === null) return;
        try {
            await api.delete(`/shops/${shop.id}/services/${deleteConfirmId}`);
            setSuccess('Service deleted successfully');
            setDeleteConfirmId(null);
            fetchServices();
        } catch (err: any) {
            setError('Failed to delete service');
            setDeleteConfirmId(null);
        }
    };

    const columns: GridColDef[] = [
        { field: 'name', headerName: 'Service Name', flex: 1, minWidth: 150 },
        {
            field: 'cost',
            headerName: 'Cost',
            width: 100,
            valueFormatter: (value) => `$${Number(value).toFixed(2)}`
        },
        {
            field: 'duration_minutes',
            headerName: 'Duration',
            width: 100,
            valueFormatter: (value) => `${value} min`
        },
        { field: 'description', headerName: 'Description', flex: 2, minWidth: 200 },
        {
            field: 'actions',
            type: 'actions',
            headerName: 'Actions',
            width: 100,
            getActions: (params) => [
                <GridActionsCellItem
                    icon={<EditIcon />}
                    label="Edit"
                    onClick={() => handleOpenDialog(params.row)}
                />,
                <GridActionsCellItem
                    icon={<DeleteIcon color="error" />}
                    label="Delete"
                    onClick={() => handleDelete(params.row.id)}
                />,
            ],
        },
    ];

    return (
        <Box sx={{ width: '100%', maxWidth: { sm: '100%', md: '1700px' } }}>
            <Header />

            <Grid container spacing={2} sx={{ mb: 2 }}>
                <Grid size={{ xs: 12, md: 8 }}>
                    <Card variant="outlined" sx={{ borderRadius: 3 }}>
                        <CardContent>
                            <Box display="flex" justifyContent="space-between" alignItems={{ xs: 'flex-start', md: 'center' }} flexDirection={{ xs: 'column', md: 'row' }} gap={2}>
                                <Box>
                                    <Typography variant="h5" sx={{ mb: 0.5, fontWeight: 700 }}>Service Catalog</Typography>
                                    <Typography color="text.secondary">
                                        Curate your menu with pricing, duration, and descriptions for customers.
                                    </Typography>
                                </Box>
                                <Button
                                    variant="contained"
                                    startIcon={<AddIcon />}
                                    onClick={() => handleOpenDialog()}
                                >
                                    Add Service
                                </Button>
                            </Box>
                        </CardContent>
                    </Card>
                </Grid>
                <Grid size={{ xs: 12, md: 4 }}>
                    <Card variant="outlined" sx={{ borderRadius: 3, height: '100%' }}>
                        <CardContent>
                            <Typography variant="body2" color="text.secondary">Published Services</Typography>
                            <Typography variant="h4" sx={{ fontWeight: 700, mt: 0.5 }}>{services.length}</Typography>
                        </CardContent>
                    </Card>
                </Grid>
            </Grid>

            {error && <Alert severity="error" onClose={() => setError(null)} sx={{ mb: 2 }}>{error}</Alert>}
            {success && <Alert severity="success" onClose={() => setSuccess(null)} sx={{ mb: 2 }}>{success}</Alert>}

            <Paper variant="outlined" sx={{ width: '100%', overflow: 'hidden', borderRadius: 3 }}>
                <DataGrid
                    rows={services}
                    columns={columns}
                    autoHeight
                    slots={{ toolbar: GridToolbar }}
                    slotProps={{ toolbar: { showQuickFilter: true, quickFilterProps: { debounceMs: 250 } } }}
                    pageSizeOptions={[10, 25]}
                    initialState={{
                        pagination: { paginationModel: { pageSize: 10 } },
                    }}
                    loading={loading}
                    disableRowSelectionOnClick
                    sx={{
                        border: 0,
                        '& .MuiDataGrid-columnHeaders': {
                            bgcolor: 'background.default',
                            borderBottom: '1px solid',
                            borderColor: 'divider',
                        },
                        '& .MuiDataGrid-toolbarContainer': {
                            p: 1,
                            borderBottom: '1px solid',
                            borderColor: 'divider',
                        },
                    }}
                />
            </Paper>

            <Dialog open={openDialog} onClose={() => setOpenDialog(false)} maxWidth="sm" fullWidth>
                <DialogTitle>{formData.id ? 'Edit Service' : 'Add New Service'}</DialogTitle>
                <DialogContent>
                    <Box sx={{ pt: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
                        <TextField
                            label="Service Name"
                            value={formData.name}
                            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                            fullWidth
                            required
                        />
                        <TextField
                            label="Price"
                            type="number"
                            value={formData.cost}
                            onChange={(e) => setFormData({ ...formData, cost: parseFloat(e.target.value) })}
                            fullWidth
                            required
                            InputProps={{
                                startAdornment: <InputAdornment position="start">$</InputAdornment>,
                            }}
                        />
                        <TextField
                            label="Duration (minutes)"
                            type="number"
                            value={formData.duration_minutes}
                            onChange={(e) => setFormData({ ...formData, duration_minutes: parseInt(e.target.value) })}
                            fullWidth
                            required
                            InputProps={{
                                endAdornment: <InputAdornment position="end">min</InputAdornment>,
                            }}
                        />
                        <TextField
                            label="Description"
                            value={formData.description}
                            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                            fullWidth
                            multiline
                            rows={3}
                        />
                    </Box>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setOpenDialog(false)}>Cancel</Button>
                    <Button
                        onClick={handleSubmit}
                        variant="contained"
                        disabled={submitting || !formData.name || formData.cost < 0}
                    >
                        {submitting ? 'Saving...' : 'Save'}
                    </Button>
                </DialogActions>
            </Dialog>

            {/* Delete Service Confirmation Dialog */}
            <Dialog open={deleteConfirmId !== null} onClose={() => setDeleteConfirmId(null)}>
                <DialogTitle>Delete Service</DialogTitle>
                <DialogContent>
                    <Typography>Are you sure you want to delete this service? This cannot be undone.</Typography>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setDeleteConfirmId(null)}>Cancel</Button>
                    <Button variant="contained" color="error" onClick={confirmDelete}>Delete</Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
};

export default ServicesManagementPage;
