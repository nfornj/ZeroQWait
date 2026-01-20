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
    CardContent
} from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import axios from 'axios';
import { useThemeContext, ThemePreset } from '../contexts/ThemeContext';

const THEMES: { id: ThemePreset; name: string; primary: string; secondary: string }[] = [
    { id: 'default', name: 'Coral (Default)', primary: '#FF5A5F', secondary: '#00A699' },
    { id: 'ocean', name: 'Ocean', primary: '#0077B6', secondary: '#48CAE4' },
    { id: 'forest', name: 'Forest', primary: '#2D6A4F', secondary: '#D8F3DC' },
    { id: 'sunset', name: 'Sunset', primary: '#E07A5F', secondary: '#F2CC8F' },
    { id: 'midnight', name: 'Midnight', primary: '#7209B7', secondary: '#4361EE' },
    { id: 'corporate', name: 'Corporate', primary: '#2B2D42', secondary: '#8D99AE' },
];

const ShopSettingsPage: React.FC = () => {
    const { themePreset, setThemePreset, setDashboardGradient } = useThemeContext();
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');
    const [shop, setShop] = useState<any>(null);
    const [logoFile, setLogoFile] = useState<File | null>(null);
    const [logoPreview, setLogoPreview] = useState<string>('');
    const [formData, setFormData] = useState({
        name: '',
        description: '',
        phone: '',
        website: '',
        primary_color: '#1976d2',
        secondary_color: '',
        accent_color: '',
        background_color: '',
        logo_url: '',
        slug: '',
        dashboard_gradient: 'violet' as string
    });

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
            }
            setLoading(false);
        } catch (err) {
            setError('Failed to load shop settings');
            setLoading(false);
        }
    };

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setFormData({
            ...formData,
            [e.target.name]: e.target.value
        });
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setSaving(true);
        setError('');
        setSuccess('');

        try {
            const token = localStorage.getItem('token');
            // Ensure dashboard_gradient is included in the payload
            await axios.put(`/shops/${shop.id}`, formData, {
                headers: { Authorization: `Bearer ${token}` }
            });

            // Upload logo to DB if selected
            if (logoFile) {
                const fd = new FormData();
                fd.append('file', logoFile);
                await axios.put(`/shops/${shop.id}/logo`, fd, {
                    headers: { Authorization: `Bearer ${token}` }
                });
            }
            setSuccess('Settings saved successfully');

            // Reload shop data to reflect changes
            await fetchShop();

            // Trigger a page reload after a short delay
            setTimeout(() => {
                window.location.reload();
            }, 1000);
        } catch (err) {
            setError('Failed to save settings');
        } finally {
            setSaving(false);
        }
    };

    const handleThemeSelect = (preset: ThemePreset) => {
        setThemePreset(preset);
        // Note: We're not saving this to the backend currently, it's a local preference
        // managed by ThemeContext (localStorage)
    };

    if (loading) return <CircularProgress />;

    if (!shop) return <Alert severity="warning">No shop found</Alert>;

    return (
        <Container maxWidth="md">
            <Typography variant="h4" gutterBottom sx={{ fontWeight: 'bold' }}>
                Shop Settings
            </Typography>

            {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
            {success && <Alert severity="success" sx={{ mb: 2 }}>{success}</Alert>}

            <Paper sx={{ p: 4 }}>
                <Box component="form" onSubmit={handleSubmit}>
                    <Box display="flex" flexWrap="wrap" gap={4}>
                        {/* PERSONALIZATION SECTION */}
                        <Box sx={{ flex: 1, minWidth: '250px' }}>
                            <Typography variant="h6" gutterBottom sx={{ fontWeight: 600 }}>
                                Dashboard Theme
                            </Typography>
                            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                                Personalize your dashboard experience. This affects your view and the public shop colors.
                            </Typography>

                            <Box display="flex" flexWrap="wrap" gap={2}>
                                {THEMES.map((theme) => (
                                    <Box sx={{ flex: 1, minWidth: '250px' }} key={theme.id}>
                                        <Card
                                            elevation={themePreset === theme.id ? 4 : 1}
                                            sx={{
                                                border: themePreset === theme.id ? `2px solid ${theme.primary}` : '2px solid transparent',
                                                transition: 'all 0.2s',
                                                transform: themePreset === theme.id ? 'scale(1.05)' : 'scale(1)'
                                            }}
                                        >
                                            <CardActionArea onClick={() => handleThemeSelect(theme.id)}>
                                                <Box sx={{ height: 60, bgcolor: theme.primary, position: 'relative' }}>
                                                    <Box sx={{
                                                        position: 'absolute',
                                                        bottom: 0,
                                                        right: 0,
                                                        width: '50%',
                                                        height: '100%',
                                                        bgcolor: theme.secondary,
                                                        clipPath: 'polygon(100% 0, 0% 100%, 100% 100%)'
                                                    }} />
                                                    {themePreset === theme.id && (
                                                        <Box sx={{
                                                            position: 'absolute',
                                                            top: '50%',
                                                            left: '50%',
                                                            transform: 'translate(-50%, -50%)',
                                                            bgcolor: 'white',
                                                            borderRadius: '50%',
                                                            p: 0.5,
                                                            display: 'flex'
                                                        }}>
                                                            <CheckCircleIcon color="primary" fontSize="small" />
                                                        </Box>
                                                    )}
                                                </Box>
                                                <CardContent sx={{ p: 1, textAlign: 'center', '&:last-child': { pb: 1 } }}>
                                                    <Typography variant="caption" sx={{ fontWeight: 600, display: 'block' }}>
                                                        {theme.name}
                                                    </Typography>
                                                </CardContent>
                                            </CardActionArea>
                                        </Card>
                                    </Box>
                                ))}
                            </Box>
                        </Box>

                        <Box sx={{ flex: 1, minWidth: '250px' }}>
                            <Typography variant="h6" gutterBottom sx={{ fontWeight: 600 }}>
                                Background Gradient
                            </Typography>
                            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                                Choose the background style for your dashboard and public pages.
                            </Typography>
                            <Box display="flex" flexWrap="wrap" gap={2}>
                                {['violet', 'ocean', 'sunset', 'minimal'].map((gradient) => (
                                    <Box sx={{ flex: 1, minWidth: '100px' }} key={gradient}>
                                        <Card
                                            elevation={formData.dashboard_gradient === gradient ? 4 : 1}
                                            sx={{
                                                border: formData.dashboard_gradient === gradient ? '2px solid #1976d2' : '2px solid transparent',
                                                cursor: 'pointer'
                                            }}
                                            onClick={() => {
                                                setFormData({ ...formData, dashboard_gradient: gradient });
                                                setDashboardGradient(gradient as any);
                                            }}
                                        >
                                            <Box sx={{
                                                height: 50,
                                                background: gradient === 'minimal' ? '#f5f5f5' : (gradient === 'violet' ? 'linear-gradient(to right, #e0c3fc, #8ec5fc)' : (gradient === 'ocean' ? 'linear-gradient(to right, #4facfe, #00f2fe)' : 'linear-gradient(to right, #fa709a, #fee140)'))
                                            }} />
                                            <CardContent sx={{ p: 1, textAlign: 'center', '&:last-child': { pb: 1 } }}>
                                                <Typography variant="caption" sx={{ textTransform: 'capitalize' }}>{gradient}</Typography>
                                            </CardContent>
                                        </Card>
                                    </Box>
                                ))}
                            </Box>
                        </Box>

                        <Box sx={{ flex: 1, minWidth: '250px' }}><Typography variant="h6" sx={{ fontWeight: 600 }}>Shop Identity</Typography></Box>

                        <Box sx={{ flex: 1, minWidth: '250px' }}>
                            <TextField
                                fullWidth
                                label="Shop Name"
                                name="name"
                                value={formData.name}
                                onChange={handleChange}
                                variant="outlined"
                                sx={{ mb: 3 }}
                            />

                            <TextField
                                fullWidth
                                label="Logo URL"
                                name="logo_url"
                                value={formData.logo_url}
                                onChange={handleChange}
                                helperText="Or paste a direct link to your logo image"
                                size="small"
                            />
                        </Box>

                        <Box sx={{ flex: 1, minWidth: '250px' }}>
                            <Paper
                                variant="outlined"
                                sx={{
                                    p: 3,
                                    textAlign: 'center',
                                    borderStyle: 'dashed',
                                    borderColor: 'divider',
                                    bgcolor: 'background.default',
                                    display: 'flex',
                                    flexDirection: 'column',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    minHeight: 200
                                }}
                            >
                                {logoPreview ? (
                                    <Box sx={{ mb: 2, position: 'relative' }}>
                                        <Avatar
                                            src={logoPreview}
                                            sx={{ width: 100, height: 100, boxShadow: 2, mb: 1 }}
                                        />
                                        <Button
                                            size="small"
                                            color="error"
                                            onClick={() => {
                                                setLogoFile(null);
                                                setLogoPreview('');
                                                setFormData({ ...formData, logo_url: '' });
                                            }}
                                        >
                                            Remove
                                        </Button>
                                    </Box>
                                ) : (
                                    <Box sx={{ mb: 2, opacity: 0.5 }}>
                                        <CloudUploadIcon sx={{ fontSize: 48, mb: 1 }} />
                                        <Typography variant="body2">No logo uploaded</Typography>
                                    </Box>
                                )}

                                <Button
                                    variant="contained"
                                    component="label"
                                    size="small"
                                >
                                    Choose File
                                    <input
                                        type="file"
                                        accept="image/*"
                                        hidden
                                        onChange={(e) => {
                                            const f = e.target.files?.[0] || null;
                                            setLogoFile(f || null);
                                            if (f) setLogoPreview(URL.createObjectURL(f));
                                        }}
                                    />
                                </Button>
                                <Typography variant="caption" display="block" sx={{ mt: 1, color: 'text.secondary' }}>
                                    Recommended size: 200x200px
                                </Typography>
                            </Paper>
                        </Box>

                        <Box sx={{ flex: 1, minWidth: '250px' }}>
                            <Typography variant="h6" gutterBottom sx={{ mt: 2, fontWeight: 600 }}>
                                Customer View Branding
                            </Typography>
                            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                                Customize your brand colors. These colors will be used on the public queue page and widget.
                            </Typography>
                        </Box>

                        <Box sx={{ flex: 1, minWidth: '250px' }}>
                            <TextField
                                fullWidth
                                label="Primary Color"
                                name="primary_color"
                                type="color"
                                value={formData.primary_color}
                                onChange={handleChange}
                                helperText="Main buttons, headers"
                            />
                        </Box>

                        <Box sx={{ flex: 1, minWidth: '250px' }}>
                            <TextField
                                fullWidth
                                label="Secondary Color"
                                name="secondary_color"
                                type="color"
                                value={formData.secondary_color || '#f5f5f5'}
                                onChange={handleChange}
                                helperText="Backgrounds"
                            />
                        </Box>

                        <Box sx={{ flex: 1, minWidth: '250px' }}>
                            <TextField
                                fullWidth
                                label="Accent Color"
                                name="accent_color"
                                type="color"
                                value={formData.accent_color || '#ff5722'}
                                onChange={handleChange}
                                helperText="Highlights"
                            />
                        </Box>

                        <Box sx={{ flex: 1, minWidth: '250px' }}>
                            <TextField
                                fullWidth
                                label="Queue Card Color"
                                name="background_color"
                                type="color"
                                value={formData.background_color || '#fff3e0'}
                                onChange={handleChange}
                                helperText="Color for waiting queue cards"
                            />
                        </Box>

                        <Box sx={{ flex: 1, minWidth: '250px' }}>
                            <Typography variant="h6" gutterBottom sx={{ mt: 2, fontWeight: 600 }}>
                                Contact Information
                            </Typography>
                        </Box>

                        <Box sx={{ flex: 1, minWidth: '250px' }}>
                            <TextField
                                fullWidth
                                multiline
                                rows={3}
                                label="Description"
                                name="description"
                                value={formData.description}
                                onChange={handleChange}
                            />
                        </Box>

                        <Box sx={{ flex: 1, minWidth: '250px' }}>
                            <TextField
                                fullWidth
                                label="Phone"
                                name="phone"
                                value={formData.phone}
                                onChange={handleChange}
                            />
                        </Box>

                        <Box sx={{ flex: 1, minWidth: '250px' }}>
                            <TextField
                                fullWidth
                                label="Website"
                                name="website"
                                value={formData.website}
                                onChange={handleChange}
                            />
                        </Box>

                        <Box sx={{ mt: 2 }}>
                            <Button
                                type="submit"
                                variant="contained"
                                size="large"
                                disabled={saving}
                                sx={{ px: 4, py: 1.5 }}
                            >
                                {saving ? 'Saving...' : 'Save Settings'}
                            </Button>
                        </Box>
                    </Box>
                </Box>
            </Paper>
        </Container>
    );
};

export default ShopSettingsPage;
