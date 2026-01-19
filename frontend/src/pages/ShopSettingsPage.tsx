import React, { useState, useEffect } from 'react';
import {
    Container,
    Typography,
    Paper,
    Grid,
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
    const { themePreset, setThemePreset } = useThemeContext();
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
        slug: ''
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
                    slug: shopData.slug || ''
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

            // Trigger a page reload after a short delay to update all components
            // We removed the full reload here because the theme updates instantly via Context
            // But if shop data (logo etc) changed, other components might need to know. 
            // For now, let's keep it but make it optional or smoother if possible.
            // Actually, for theme change we don't need reload. For shop data we might.
            // Keeping it simple:
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
                    <Grid container spacing={4}>
                        {/* PERSONALIZATION SECTION */}
                        <Grid item xs={12}>
                            <Typography variant="h6" gutterBottom sx={{ fontWeight: 600 }}>
                                Dashboard Theme
                            </Typography>
                            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                                Personalize your dashboard experience. This only affects your view.
                            </Typography>

                            <Grid container spacing={2}>
                                {THEMES.map((theme) => (
                                    <Grid item xs={6} sm={4} md={2} key={theme.id}>
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
                                    </Grid>
                                ))}
                            </Grid>
                        </Grid>


                        <Grid item xs={12}><Typography variant="h6" sx={{ fontWeight: 600 }}>Shop Identity</Typography></Grid>

                        <Grid item xs={12} md={6}>
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
                        </Grid>

                        <Grid item xs={12} md={6}>
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
                        </Grid>

                        <Grid item xs={12}>
                            <Typography variant="h6" gutterBottom sx={{ mt: 2, fontWeight: 600 }}>
                                Customer View Branding
                            </Typography>
                            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                                Customize your brand colors. These colors will be used on the public queue page and widget.
                            </Typography>
                        </Grid>

                        <Grid item xs={12} sm={6}>
                            <TextField
                                fullWidth
                                label="Primary Color"
                                name="primary_color"
                                type="color"
                                value={formData.primary_color}
                                onChange={handleChange}
                                helperText="Main buttons, headers"
                            />
                        </Grid>

                        <Grid item xs={12} sm={6}>
                            <TextField
                                fullWidth
                                label="Secondary Color"
                                name="secondary_color"
                                type="color"
                                value={formData.secondary_color || '#f5f5f5'}
                                onChange={handleChange}
                                helperText="Backgrounds"
                            />
                        </Grid>

                        <Grid item xs={12} sm={6}>
                            <TextField
                                fullWidth
                                label="Accent Color"
                                name="accent_color"
                                type="color"
                                value={formData.accent_color || '#ff5722'}
                                onChange={handleChange}
                                helperText="Highlights"
                            />
                        </Grid>

                        <Grid item xs={12} sm={6}>
                            <TextField
                                fullWidth
                                label="Queue Card Color"
                                name="background_color"
                                type="color"
                                value={formData.background_color || '#fff3e0'}
                                onChange={handleChange}
                                helperText="Color for waiting queue cards"
                            />
                        </Grid>

                        <Grid item xs={12}>
                            <Typography variant="h6" gutterBottom sx={{ mt: 2, fontWeight: 600 }}>
                                Contact Information
                            </Typography>
                        </Grid>

                        <Grid item xs={12}>
                            <TextField
                                fullWidth
                                multiline
                                rows={3}
                                label="Description"
                                name="description"
                                value={formData.description}
                                onChange={handleChange}
                            />
                        </Grid>

                        <Grid item xs={12} sm={6}>
                            <TextField
                                fullWidth
                                label="Phone"
                                name="phone"
                                value={formData.phone}
                                onChange={handleChange}
                            />
                        </Grid>

                        <Grid item xs={12} sm={6}>
                            <TextField
                                fullWidth
                                label="Website"
                                name="website"
                                value={formData.website}
                                onChange={handleChange}
                            />
                        </Grid>

                        <Grid item xs={12} sx={{ mt: 2 }}>
                            <Button
                                type="submit"
                                variant="contained"
                                size="large"
                                disabled={saving}
                                sx={{ px: 4, py: 1.5 }}
                            >
                                {saving ? 'Saving...' : 'Save Settings'}
                            </Button>
                        </Grid>
                    </Grid>
                </Box>
            </Paper>
        </Container>
    );
};

export default ShopSettingsPage;
