import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
    Container,
    Typography,
    Box,
    Card,
    CardContent,
    Button,
    Chip,
    Avatar,
    CircularProgress,
    Alert,
    TextField,
    Grid,
    Divider,
    List,
    ListItem,
    ListItemText,
    FormControl,
    InputLabel,
    Select,
    MenuItem,
    Paper
} from '@mui/material';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import PeopleIcon from '@mui/icons-material/People';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import axios from 'axios';


const PublicShopPage: React.FC = () => {
    const { slug } = useParams<{ slug: string }>();
    const navigate = useNavigate();
    const [shop, setShop] = useState<any>(null);
    const [queues, setQueues] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    useEffect(() => {
        fetchShopAndQueues();
    }, [slug]);

    const fetchShopAndQueues = async () => {
        try {
            const response = await axios.get(`/shops/s/${slug}`);
            setShop(response.data);

            // Redirect if already in queue
            const savedItemId = localStorage.getItem(`queue_item_${response.data.id}`);
            if (savedItemId) {
                navigate(`/queue/${response.data.id}`);
                return;
            }

            if (response.data.queues) {
                setQueues(response.data.queues.filter((q: any) => q.is_active));
            } else {
                setQueues([]);
            }

            // Fetch services for the shop
            const servicesRes = await axios.get(`/shops/${response.data.id}/services`);
            setServices(servicesRes.data.filter((s: any) => s.is_active));

            setLoading(false);
        } catch (err) {
            setError('Shop not found');
            setLoading(false);
        }
    };

    const [services, setServices] = useState<any[]>([]);
    const [customerName, setCustomerName] = useState('');
    const [customerPhone, setCustomerPhone] = useState('');
    const [customerEmail, setCustomerEmail] = useState('');
    const [notes, setNotes] = useState('');
    const [selectedServiceId, setSelectedServiceId] = useState<number | ''>('');
    const [joinLoading, setJoinLoading] = useState(false);
    const [joinError, setJoinError] = useState('');

    const handleJoinQueue = async (e: React.FormEvent) => {
        e.preventDefault();
        setJoinError('');
        setJoinLoading(true);

        if (!customerName.trim()) {
            setJoinError('Please enter your name');
            setJoinLoading(false);
            return;
        }

        try {
            const response = await axios.post(`/queues/shop/${shop.id}/join`, {
                customer_name: customerName,
                customer_phone: customerPhone,
                customer_email: customerEmail,
                notes: notes,
                service_id: selectedServiceId || undefined,
            });

            localStorage.setItem(`queue_item_${shop.id}`, response.data.id.toString());
            navigate(`/queue/${shop.id}`);
        } catch (err: any) {
            setJoinError(err.response?.data?.detail || 'Failed to join queue');
            setJoinLoading(false);
        }
    };

    if (loading) return (
        <Box display="flex" justifyContent="center" alignItems="center" minHeight="80vh">
            <CircularProgress />
        </Box>
    );

    if (error || !shop) return (
        <Container maxWidth="md" sx={{ mt: 8 }}>
            <Alert severity="error">Shop not found</Alert>
        </Container>
    );

    return (
        <Box sx={{ bgcolor: '#ffffff', minHeight: '100vh', pb: 8 }}>
            {/* Minimal Header with branding */}
            <Paper elevation={0} sx={{ borderBottom: '1px solid #eee', py: 2, mb: 4 }}>
                <Container maxWidth="lg">
                    <Box display="flex" justifyContent="space-between" alignItems="center">
                        <Typography variant="h4" fontWeight="bold" color="primary" sx={{ cursor: 'pointer' }} onClick={() => navigate('/')}>
                            ZeroQWait
                        </Typography>
                        <Box display="flex" gap={2}>
                            <Button variant="text" size="small">SEARCH</Button>
                            <Button variant="text" size="small">PRICING</Button>
                            <Button variant="text" size="small">LOG IN</Button>
                            <Button variant="contained" color="error" size="small" sx={{ borderRadius: 2 }}>SIGN UP</Button>
                        </Box>
                    </Box>
                </Container>
            </Paper>

            <Container maxWidth="lg">
                {/* Shop Info Card */}
                <Card variant="outlined" sx={{ mb: 4, borderRadius: 2, p: 1 }}>
                    <CardContent>
                        <Box display="flex" alignItems="center" gap={3}>
                            {shop.logo_url && (
                                <Avatar
                                    src={shop.logo_url}
                                    sx={{ width: 80, height: 80, borderRadius: 1, border: '1px solid #eee' }}
                                />
                            )}
                            <Box>
                                <Typography variant="h3" fontWeight="bold" gutterBottom>
                                    {shop.name}
                                </Typography>
                                <Typography variant="body2" color="text.secondary">
                                    {shop.address}, {shop.city}, {shop.state}
                                </Typography>
                                <Typography variant="body2" color="text.secondary">
                                    Phone: {shop.phone}
                                </Typography>
                            </Box>
                        </Box>
                    </CardContent>
                </Card>

                {/* AI Concierge Call-to-action */}
                <Box
                    sx={{
                        mb: 4,
                        p: 3,
                        borderRadius: 3,
                        background: `linear-gradient(90deg, ${shop.primary_color || '#1976d2'}, #000)`,
                        color: 'white',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        boxShadow: '0 4px 20px rgba(0,0,0,0.1)'
                    }}
                >
                    <Box>
                        <Typography variant="h5" fontWeight="bold">Try our Intelligent Concierge</Typography>
                        <Typography variant="body1" sx={{ opacity: 0.8 }}>Talk to Boomboo to join the queue or check wait times instantly.</Typography>
                    </Box>
                    <Button
                        variant="contained"
                        startIcon={<SmartToyIcon />}
                        onClick={() => navigate(`/shop-ai/${shop.id}`)}
                        sx={{
                            bgcolor: 'white',
                            color: 'black',
                            fontWeight: 'bold',
                            borderRadius: 10,
                            px: 4,
                            '&:hover': { bgcolor: '#eee' }
                        }}
                    >
                        START CHAT
                    </Button>
                </Box>

                <Grid container spacing={4}>
                    {/* Left Side: Join Queue Form */}
                    <Grid size={{ xs: 12, md: 7 }}>
                        <Card variant="outlined" sx={{ borderRadius: 2 }}>
                            <CardContent sx={{ p: 4 }}>
                                <Typography variant="h5" fontWeight="bold" gutterBottom>
                                    Join Queue
                                </Typography>
                                <Divider sx={{ mb: 3 }} />

                                {joinError && <Alert severity="error" sx={{ mb: 2 }}>{joinError}</Alert>}

                                <Box component="form" onSubmit={handleJoinQueue}>
                                    <TextField
                                        fullWidth
                                        required
                                        label="Your Name *"
                                        value={customerName}
                                        onChange={(e) => setCustomerName(e.target.value)}
                                        sx={{ mb: 2 }}
                                    />
                                    <TextField
                                        fullWidth
                                        label="Phone Number"
                                        value={customerPhone}
                                        onChange={(e) => setCustomerPhone(e.target.value)}
                                        sx={{ mb: 2 }}
                                    />
                                    <TextField
                                        fullWidth
                                        label="Email (optional)"
                                        type="email"
                                        value={customerEmail}
                                        onChange={(e) => setCustomerEmail(e.target.value)}
                                        sx={{ mb: 2 }}
                                    />
                                    <TextField
                                        fullWidth
                                        multiline
                                        rows={3}
                                        label="Notes (optional)"
                                        value={notes}
                                        onChange={(e) => setNotes(e.target.value)}
                                        sx={{ mb: 2 }}
                                    />

                                    <FormControl fullWidth sx={{ mb: 3 }}>
                                        <InputLabel id="service-select-label">Service (Optional)</InputLabel>
                                        <Select
                                            labelId="service-select-label"
                                            value={selectedServiceId}
                                            label="Service (Optional)"
                                            onChange={(e) => setSelectedServiceId(e.target.value as number)}
                                        >
                                            <MenuItem value=""><em>None</em></MenuItem>
                                            {services.map((service) => (
                                                <MenuItem key={service.id} value={service.id}>
                                                    {service.name} - ${service.cost} ({service.duration_minutes} min)
                                                </MenuItem>
                                            ))}
                                        </Select>
                                    </FormControl>

                                    <Button
                                        type="submit"
                                        variant="contained"
                                        fullWidth
                                        size="large"
                                        disabled={joinLoading}
                                        sx={{
                                            py: 1.5,
                                            fontSize: '1.1rem',
                                            fontWeight: 'bold',
                                            borderRadius: 1,
                                            boxShadow: 'none'
                                        }}
                                    >
                                        {joinLoading ? <CircularProgress size={24} /> : 'JOIN QUEUE'}
                                    </Button>
                                </Box>
                            </CardContent>
                        </Card>
                    </Grid>

                    {/* Right Side: Current Queue Status */}
                    <Grid size={{ xs: 12, md: 5 }}>
                        <Card variant="outlined" sx={{ borderRadius: 2 }}>
                            <CardContent sx={{ p: 4 }}>
                                <Typography variant="h5" fontWeight="bold" gutterBottom>
                                    Current Queue
                                </Typography>
                                <Divider sx={{ mb: 2 }} />

                                {queues.length > 0 && queues[0].queue_items ? (
                                    <>
                                        <Box display="flex" alignItems="center" mb={3}>
                                            <PeopleIcon sx={{ mr: 1, color: 'text.secondary' }} />
                                            <Typography variant="h6">
                                                {queues[0].queue_items.filter((i: any) => i.status === 'waiting').length} people waiting
                                            </Typography>
                                        </Box>

                                        <List disablePadding>
                                            {queues[0].queue_items.filter((i: any) => i.status === 'waiting').slice(0, 5).map((item: any, idx: number) => (
                                                <ListItem
                                                    key={item.id}
                                                    sx={{
                                                        bgcolor: '#f8f9fa',
                                                        mb: 1,
                                                        borderRadius: 1,
                                                        borderLeft: idx === 0 ? `4px solid ${shop.primary_color || '#1976d2'}` : 'none'
                                                    }}
                                                >
                                                    <Box sx={{ mr: 2, fontWeight: 'bold', color: 'text.secondary' }}>#{idx + 1}</Box>
                                                    <ListItemText
                                                        primary={item.customer_name}
                                                        secondary={new Date(item.checked_in_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                                    />
                                                </ListItem>
                                            ))}
                                            {queues[0].queue_items.filter((i: any) => i.status === 'waiting').length > 5 && (
                                                <Typography variant="body2" color="text.secondary" textAlign="center" mt={2}>
                                                    ... and more
                                                </Typography>
                                            )}
                                        </List>
                                    </>
                                ) : (
                                    <Box textAlign="center" py={4}>
                                        <Typography color="text.secondary">Queue is empty. Join now!</Typography>
                                    </Box>
                                )}
                            </CardContent>
                        </Card>

                        {/* Additional Info Box */}
                        <Box sx={{ mt: 3, p: 2, bgcolor: '#f0f4f8', borderRadius: 2 }}>
                            <Typography variant="subtitle2" fontWeight="bold" display="flex" alignItems="center" gap={1}>
                                <AccessTimeIcon fontSize="small" /> Estimated Wait Time
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                                Each service takes about {shop.average_service_time} minutes on average.
                            </Typography>
                        </Box>
                    </Grid>
                </Grid>
            </Container>
        </Box>
    );
};

export default PublicShopPage;
