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
    Alert
} from '@mui/material';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import PeopleIcon from '@mui/icons-material/People';
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
            // We need an endpoint to fetch by slug. 
            // Current API only supports ID. We need to update backend or search by slug.
            // For now, let's assume we added a /shops/slug/:slug endpoint.
            // If not, we might fail. I should check backend.
            // Wait, I didn't add fetch by slug endpoint. I added the field but not the lookup.
            // I need to add `GET /shops/s/{slug}` to backend.

            const response = await axios.get(`/shops/s/${slug}`);
            setShop(response.data);
            if (response.data.queues) {
                setQueues(response.data.queues.filter((q: any) => q.is_active));
            } else {
                setQueues([]);
            }
            setLoading(false);
        } catch (err) {
            setError('Shop not found');
            setLoading(false);
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
        <Box sx={{ bgcolor: 'background.default', minHeight: '100vh', pb: 8 }}>
            {/* Hero Section with Branding */}
            <Box
                sx={{
                    bgcolor: shop.primary_color || '#1976d2',
                    color: 'white',
                    py: 4, // Reduced from 8
                    mb: 4,
                    textAlign: 'center'
                }}
            >
                <Container maxWidth="md">
                    {shop.logo_url && (
                        <Avatar
                            src={shop.logo_url}
                            sx={{ width: 80, height: 80, mx: 'auto', mb: 2, border: '3px solid white' }} // Reduced size
                        />
                    )}
                    <Typography variant="h3" fontWeight="bold" gutterBottom> {/* Reduced from h2 */}
                        {shop.name}
                    </Typography>
                    <Typography variant="h6" sx={{ opacity: 0.9 }}> {/* Reduced from h5 */}
                        {shop.address}, {shop.city}
                    </Typography>
                </Container>
            </Box>

            <Container maxWidth="md">
                <Typography variant="h4" gutterBottom sx={{ mb: 3 }}>
                    Join a Queue
                </Typography>

                <Box display="flex" flexWrap="wrap" gap={3}>
                    {queues.map((queue) => (
                        <Box xs={12} md={6} key={queue.id}>
                            <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
                                <CardContent sx={{ flexGrow: 1 }}>
                                    <Typography variant="h5" gutterBottom>
                                        {queue.name || "Main Queue"}
                                    </Typography>

                                    <Box display="flex" alignItems="center" mb={1}>
                                        <PeopleIcon sx={{ mr: 1, color: 'text.secondary' }} />
                                        <Typography color="text.secondary">
                                            {queue.queue_items?.filter((i: any) => i.status === 'waiting').length || 0} waiting
                                        </Typography>
                                    </Box>

                                    <Box display="flex" alignItems="center" mb={3}>
                                        <AccessTimeIcon sx={{ mr: 1, color: 'text.secondary' }} />
                                        <Typography color="text.secondary">
                                            ~{shop.average_service_time} min wait
                                        </Typography>
                                    </Box>

                                    <Button
                                        variant="contained"
                                        fullWidth
                                        size="large"
                                        sx={{ bgcolor: shop.primary_color }}
                                        onClick={() => navigate(`/queue/${shop.id}`)}
                                    >
                                        Join Queue
                                    </Button>
                                </CardContent>
                            </Card>
                        </Box>
                    ))}
                </Box>

                <Box mt={6}>
                    <Typography variant="h5" gutterBottom>
                        About Us
                    </Typography>
                    <Card>
                        <CardContent>
                            <Typography variant="body1">
                                {shop.description || "No description available."}
                            </Typography>
                            <Box mt={2}>
                                <Typography variant="body2" color="text.secondary">
                                    <strong>Phone:</strong> {shop.phone}
                                </Typography>
                                {shop.website && (
                                    <Typography variant="body2" color="text.secondary">
                                        <strong>Website:</strong> <a href={shop.website} target="_blank" rel="noopener noreferrer">{shop.website}</a>
                                    </Typography>
                                )}
                            </Box>
                        </CardContent>
                    </Card>
                </Box>
            </Container>
        </Box>
    );
};

export default PublicShopPage;
