import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Container,
    Box,
    Typography,
    Button,
    Card,
    CardContent,
    Alert,
    CircularProgress,
    Avatar,
    Chip,
    List,
    ListItem,
    ListItemText,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    TextField,
    Paper
} from '@mui/material';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import ExitToAppIcon from '@mui/icons-material/ExitToApp';
import PersonAddIcon from '@mui/icons-material/PersonAdd';
import PhotoCameraIcon from '@mui/icons-material/PhotoCamera';
import DeleteIcon from '@mui/icons-material/Delete';
import SkipNextIcon from '@mui/icons-material/SkipNext';
import IconButton from '@mui/material/IconButton';
import axios from 'axios';
import { useAuth } from '../contexts/AuthContext';
import ProfilePhotoUploader from '../components/ProfilePhotoUploader';


interface Shop {
    id: number;
    name: string;
}

interface QueueItem {
    id: number;
    customer_name: string;
    position: number;
    status: string;
    checked_in_at: string;
}

interface Shift {
    id: number;
    shop_id: number;
    clock_in: string;
    clock_out: string | null;
}

const EmployeeQueuePage: React.FC = () => {
    const [shops, setShops] = useState<Shop[]>([]);
    const [selectedShop, setSelectedShop] = useState<Shop | null>(null);
    const [currentShift, setCurrentShift] = useState<Shift | null>(null);
    const [queue, setQueue] = useState<QueueItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);
    const [photoDialogOpen, setPhotoDialogOpen] = useState(false);
    const [photoUrl, setPhotoUrl] = useState('');
    const [removeDialogOpen, setRemoveDialogOpen] = useState(false);
    const [selectedCustomer, setSelectedCustomer] = useState<QueueItem | null>(null);
    const [removeReason, setRemoveReason] = useState('');
    const { user } = useAuth();
    const navigate = useNavigate();

    useEffect(() => {
        fetchInitialData();
    }, []);

    useEffect(() => {
        if (selectedShop) {
            const interval = setInterval(fetchQueue, 5000);
            return () => clearInterval(interval);
        }
    }, [selectedShop]);

    const fetchInitialData = async () => {
        try {
            setLoading(true);
            const token = localStorage.getItem('token');
            
            // Fetch shops
            const shopsResponse = await axios.get(`/employees/my-shops`, {
                headers: { Authorization: `Bearer ${token}` }
            });
            setShops(shopsResponse.data);

            // Fetch current shift
            const shiftResponse = await axios.get(`/current-shift`, {
                headers: { Authorization: `Bearer ${token}` }
            });
            
            if (shiftResponse.data) {
                setCurrentShift(shiftResponse.data);
                const currentShop = shopsResponse.data.find((s: Shop) => s.id === shiftResponse.data.shop_id);
                if (currentShop) {
                    setSelectedShop(currentShop);
                    await fetchQueue(currentShop.id);
                }
            }
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to load data');
        } finally {
            setLoading(false);
        }
    };

    const fetchQueue = async (shopId?: number) => {
        const id = shopId || selectedShop?.id;
        if (!id) return;

        try {
            const token = localStorage.getItem('token');
            const response = await axios.get(`/queues/shop/${id}/active`, {
                headers: { Authorization: `Bearer ${token}` }
            });
            setQueue(response.data.queue_items || []);
        } catch (err) {
            // Silently fail - retry on next interval
        }
    };

    const handleClockIn = async (shopId: number) => {
        try {
            setError(null);
            const token = localStorage.getItem('token');
            await axios.post(`/clock-in/${shopId}`, {}, {
                headers: { Authorization: `Bearer ${token}` }
            });
            setSuccess('Clocked in successfully!');
            await fetchInitialData();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to clock in');
        }
    };

    const handleClockOut = async () => {
        try {
            setError(null);
            const token = localStorage.getItem('token');
            await axios.post(`/clock-out`, {}, {
                headers: { Authorization: `Bearer ${token}` }
            });
            setSuccess('Clocked out successfully!');
            setCurrentShift(null);
            setSelectedShop(null);
            setQueue([]);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to clock out');
        }
    };

    const handleCallNext = async () => {
        if (!selectedShop) return;

        try {
            setError(null);
            const token = localStorage.getItem('token');
            const response = await axios.get(`/queues/shop/${selectedShop.id}/active`, {
                headers: { Authorization: `Bearer ${token}` }
            });
            
            const queueId = response.data.id;
            
            await axios.post(`/queues/${queueId}/call-next`, {}, {
                headers: { Authorization: `Bearer ${token}` }
            });
            
            setSuccess('Called next customer!');
            fetchQueue();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to call next customer');
        }
    };

    const handleRemoveCustomer = async () => {
        if (!selectedCustomer || !removeReason.trim()) return;

        try {
            setError(null);
            const token = localStorage.getItem('token');
            await axios.delete(`/queues/items/${selectedCustomer.id}`, {
                headers: { Authorization: `Bearer ${token}` },
                params: { reason: removeReason }
            });
            setSuccess('Customer removed from queue');
            setRemoveDialogOpen(false);
            setSelectedCustomer(null);
            setRemoveReason('');
            fetchQueue();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to remove customer');
        }
    };

    const handleServeSpecific = async (customer: QueueItem) => {
        if (!window.confirm(`Serve ${customer.customer_name} now (skip the queue)?`)) return;

        try {
            setError(null);
            const token = localStorage.getItem('token');
            await axios.post(`/queues/items/${customer.id}/serve`, {}, {
                headers: { Authorization: `Bearer ${token}` }
            });
            setSuccess(`Now serving ${customer.customer_name}`);
            await fetchQueue(); // Wait for queue to refresh
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to serve customer');
        }
    };

    const handleUploadPhoto = async (photoDataUrl: string) => {
        try {
            const token = localStorage.getItem('token');
            await axios.post(`/upload-profile-photo`, 
                { photo_url: photoDataUrl },
                {
                    headers: { 
                        Authorization: `Bearer ${token}`,
                        'Content-Type': 'application/json'
                    },
                    params: { photo_url: photoDataUrl }
                }
            );
            setSuccess('Profile photo updated!');
        } catch (err: any) {
            throw new Error(err.response?.data?.detail || 'Failed to upload photo');
        }
    };

    const waitingCustomers = queue.filter(item => item.status === 'waiting');
    const servingCustomer = queue.find(item => item.status === 'being_served');

    if (loading) {
        return (
            <Box display="flex" justifyContent="center" alignItems="center" minHeight="80vh">
                <CircularProgress />
            </Box>
        );
    }

    return (
        <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
                <Box>
                    <Typography variant="h4" sx={{ fontWeight: 600, mb: 1 }}>
                        Welcome, {user?.username}!
                    </Typography>
                    <Typography variant="body1" color="text.secondary">
                        {currentShift ? `Working at ${selectedShop?.name}` : 'Select a shop to clock in'}
                    </Typography>
                </Box>
                <Button
                    variant="outlined"
                    startIcon={<PhotoCameraIcon />}
                    onClick={() => setPhotoDialogOpen(true)}
                >
                    Update Photo
                </Button>
            </Box>

            {error && <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>{error}</Alert>}
            {success && <Alert severity="success" sx={{ mb: 3 }} onClose={() => setSuccess(null)}>{success}</Alert>}

            {!currentShift ? (
                <Box display="flex" flexWrap="wrap" gap={3}>
                    {shops.map((shop) => (
                        <Box xs={12} md={6} key={shop.id}>
                            <Card>
                                <CardContent>
                                    <Typography variant="h6" sx={{ mb: 2 }}>
                                        {shop.name}
                                    </Typography>
                                    <Button
                                        fullWidth
                                        variant="contained"
                                        startIcon={<AccessTimeIcon />}
                                        onClick={() => handleClockIn(shop.id)}
                                    >
                                        Clock In
                                    </Button>
                                </CardContent>
                            </Card>
                        </Box>
                    ))}
                </Box>
            ) : (
                <Box>
                    <Paper sx={{ p: 3, mb: 3 }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <Box>
                                <Typography variant="h6">Current Shift</Typography>
                                <Typography variant="body2" color="text.secondary">
                                    Clocked in at {new Date(currentShift.clock_in).toLocaleTimeString()}
                                </Typography>
                            </Box>
                            <Button
                                variant="outlined"
                                color="error"
                                startIcon={<ExitToAppIcon />}
                                onClick={handleClockOut}
                            >
                                Clock Out
                            </Button>
                        </Box>
                    </Paper>

                    <Box display="flex" flexWrap="wrap" gap={3}>
                        <Box xs={12} md={6}>
                            <Card>
                                <CardContent>
                                    <Typography variant="h6" sx={{ mb: 2 }}>
                                        Now Serving
                                    </Typography>
                                    {servingCustomer ? (
                                        <Box sx={{ textAlign: 'center', py: 4 }}>
                                            <Typography variant="h2" sx={{ fontWeight: 700, mb: 2 }}>
                                                #{servingCustomer.position}
                                            </Typography>
                                            <Typography variant="h5">
                                                {servingCustomer.customer_name}
                                            </Typography>
                                        </Box>
                                    ) : (
                                        <Typography color="text.secondary" sx={{ textAlign: 'center', py: 4 }}>
                                            No customer being served
                                        </Typography>
                                    )}
                                    <Button
                                        fullWidth
                                        variant="contained"
                                        size="large"
                                        startIcon={<PersonAddIcon />}
                                        onClick={handleCallNext}
                                        disabled={waitingCustomers.length === 0}
                                    >
                                        Call Next Customer
                                    </Button>
                                </CardContent>
                            </Card>
                        </Box>

                        <Box xs={12} md={6}>
                            <Card>
                                <CardContent>
                                    <Typography variant="h6" sx={{ mb: 2 }}>
                                        Waiting Queue ({waitingCustomers.length})
                                    </Typography>
                                    {waitingCustomers.length === 0 ? (
                                        <Typography color="text.secondary" sx={{ textAlign: 'center', py: 4 }}>
                                            No customers waiting
                                        </Typography>
                                    ) : (
                                        <List>
                                            {waitingCustomers.slice(0, 10).map((item) => (
                                                <ListItem 
                                                    key={item.id} 
                                                    sx={{ borderBottom: '1px solid #eee' }}
                                                    secondaryAction={
                                                        <Box>
                                                            <IconButton 
                                                                edge="end" 
                                                                aria-label="serve"
                                                                onClick={() => handleServeSpecific(item)}
                                                                sx={{ mr: 1 }}
                                                                color="primary"
                                                                title="Serve this customer now"
                                                            >
                                                                <SkipNextIcon />
                                                            </IconButton>
                                                            <IconButton 
                                                                edge="end" 
                                                                aria-label="remove"
                                                                onClick={() => {
                                                                    setSelectedCustomer(item);
                                                                    setRemoveDialogOpen(true);
                                                                }}
                                                                color="error"
                                                                title="Remove from queue"
                                                            >
                                                                <DeleteIcon />
                                                            </IconButton>
                                                        </Box>
                                                    }
                                                >
                                                    <Chip label={`#${item.position}`} sx={{ mr: 2 }} />
                                                    <ListItemText
                                                        primary={item.customer_name}
                                                        secondary={new Date(item.checked_in_at).toLocaleTimeString()}
                                                    />
                                                </ListItem>
                                            ))}
                                        </List>
                                    )}
                                </CardContent>
                            </Card>
                        </Box>
                    </Box>
                </Box>
            )}

            {/* Photo Upload Dialog */}
            <ProfilePhotoUploader
                open={photoDialogOpen}
                onClose={() => setPhotoDialogOpen(false)}
                onUpload={handleUploadPhoto}
            />

            {/* Remove Customer Dialog */}
            <Dialog open={removeDialogOpen} onClose={() => setRemoveDialogOpen(false)}>
                <DialogTitle>Remove Customer from Queue</DialogTitle>
                <DialogContent>
                    <Typography variant="body1" sx={{ mb: 2 }}>
                        Why are you removing <strong>{selectedCustomer?.customer_name}</strong>?
                    </Typography>
                    <TextField
                        fullWidth
                        multiline
                        rows={3}
                        label="Reason for removal"
                        value={removeReason}
                        onChange={(e) => setRemoveReason(e.target.value)}
                        placeholder="e.g., Did not appear when called, Left the premises, etc."
                        sx={{ mt: 2 }}
                    />
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => {
                        setRemoveDialogOpen(false);
                        setSelectedCustomer(null);
                        setRemoveReason('');
                    }}>Cancel</Button>
                    <Button 
                        onClick={handleRemoveCustomer} 
                        variant="contained" 
                        color="error"
                        disabled={!removeReason.trim()}
                    >
                        Remove
                    </Button>
                </DialogActions>
            </Dialog>
        </Container>
    );
};

export default EmployeeQueuePage;
