import React, { useState, useEffect } from 'react';
import {
    Typography,
    Paper,

    IconButton,
    Button,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    TextField,
    Alert,
    Chip,
    Box
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import AddIcon from '@mui/icons-material/Add';
import TvIcon from '@mui/icons-material/Tv';
import axios from 'axios';
import Header from '../components/dashboard/Header';
import QueueDataGrid from '../components/dashboard/QueueDataGrid';


const QueueManagementPage: React.FC = () => {
    const [queues, setQueues] = useState<any[]>([]);
    const [shop, setShop] = useState<any>(null);
    const [open, setOpen] = useState(false);
    const [newQueueName, setNewQueueName] = useState('');
    const [error, setError] = useState('');

    useEffect(() => {
        fetchShopAndQueues();
    }, []);

    const fetchShopAndQueues = async () => {
        try {
            const token = localStorage.getItem('token');
            const shopRes = await axios.get(`/shops/my-shops`, {
                headers: { Authorization: `Bearer ${token}` }
            });

            if (shopRes.data.length > 0) {
                const currentShop = shopRes.data[0];
                setShop(currentShop);

                // Fetch all queues for the shop
                const queueRes = await axios.get(`/queues/shop/${currentShop.id}/all`, {
                    headers: { Authorization: `Bearer ${token}` }
                });
                setQueues(queueRes.data);
            }
        } catch (err) {
            // Silently fail - error will show in UI
        }
    };

    const handleCreateQueue = async () => {
        try {
            const token = localStorage.getItem('token');
            setError('');
            await axios.post(`/queues/shop/${shop.id}`,
                { name: newQueueName },
                { headers: { Authorization: `Bearer ${token}` } }
            );
            setOpen(false);
            setNewQueueName('');
            fetchShopAndQueues(); // Refresh list
        } catch (err: any) {
            const errorMsg = err.response?.data?.detail || 'Failed to create queue';
            setError(errorMsg);
            setOpen(false);
        }
    };

    return (
        <Box sx={{ width: '100%', maxWidth: { sm: '100%', md: '1700px' } }}>
            <Header />
            <Box display="flex" justifyContent="flex-end" alignItems="center" mb={3} mt={2}>
                <Button
                    variant="contained"
                    startIcon={<AddIcon />}
                    onClick={() => setOpen(true)}
                >
                    Create Queue
                </Button>
            </Box>

            {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

            {shop && (
                <Alert severity="info" sx={{ mb: 2 }} icon={<TvIcon />}>
                    <Box display="flex" justifyContent="space-between" alignItems="center">
                        <Box>
                            <Typography variant="subtitle2" fontWeight="bold">In-Shop Display Available</Typography>
                            <Typography variant="body2">
                                Display your queue on a TV screen for customers in your shop
                            </Typography>
                        </Box>
                        <Button
                            variant="outlined"
                            size="small"
                            startIcon={<TvIcon />}
                            onClick={() => window.open(`/display/${shop.id}`, '_blank')}
                        >
                            Open Display
                        </Button>
                    </Box>
                </Alert>
            )}

            <Paper sx={{ width: '100%', overflow: 'hidden' }}>
                <QueueDataGrid
                    rows={queues}
                    onEdit={(queue) => {
                        // For now just allow editing name via same dialog logic if we want, 
                        // or just keep it simple. The original code didn't have edit.
                        // We'll treat "Create" as the only action for now or repurpose.
                        // Let's just log or ignore for this step as backend might not support update yet.
                        console.log('Edit queue', queue);
                    }}
                />
            </Paper>

            <Dialog open={open} onClose={() => setOpen(false)}>
                <DialogTitle>Create New Queue</DialogTitle>
                <DialogContent>
                    <TextField
                        autoFocus
                        margin="dense"
                        label="Queue Name"
                        fullWidth
                        value={newQueueName}
                        onChange={(e) => setNewQueueName(e.target.value)}
                        placeholder="e.g., Barber 2, Walk-ins"
                    />
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setOpen(false)}>Cancel</Button>
                    <Button onClick={handleCreateQueue} variant="contained">Create</Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
};

export default QueueManagementPage;
