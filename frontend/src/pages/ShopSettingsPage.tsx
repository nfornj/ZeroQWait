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
    Avatar
} from '@mui/material';
import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

const ShopSettingsPage: React.FC = () => {
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
            const response = await axios.get(`${API_URL}/shops/my-shops`, {
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
            await axios.put(`${API_URL}/shops/${shop.id}`, formData, {
                headers: { Authorization: `Bearer ${token}` }
            });

            // Upload logo to DB if selected
            if (logoFile) {
                const fd = new FormData();
                fd.append('file', logoFile);
                await axios.put(`${API_URL}/shops/${shop.id}/logo`, fd, {
                    headers: { Authorization: `Bearer ${token}` }
                });
            }
            setSuccess('Settings saved successfully');
            
            // Reload shop data to reflect changes
            await fetchShop();
            
            // Trigger a page reload after a short delay to update all components
            setTimeout(() => {
                window.location.reload();
            }, 1000);
        } catch (err) {
            setError('Failed to save settings');
        } finally {
            setSaving(false);
        }
    };

    if (loading) return <CircularProgress />;

    if (!shop) return <Alert severity="warning">No shop found</Alert>;

    return (
        <Container maxWidth="md">
            <Typography variant="h4" gutterBottom>
                Shop Settings
            </Typography>

            {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
            {success && <Alert severity="success" sx={{ mb: 2 }}>{success}</Alert>}

            <Paper sx={{ p: 3 }}>
                <Box component="form" onSubmit={handleSubmit}>
                    <Grid container spacing={3}>
                        <Grid item xs={12}>
                            <Typography variant="h6" gutterBottom>
                                Branding
                            </Typography>
                        </Grid>

                        <Grid item xs={12} sm={6}>
                            <TextField
                                fullWidth
                                label="Shop Name"
                                name="name"
                                value={formData.name}
                                onChange={handleChange}
                            />
                        </Grid>

                        <Grid item xs={12} sm={6}>
                            <TextField
                                fullWidth
                                label="Primary Color"
                                name="primary_color"
                                type="color"
                                value={formData.primary_color}
                                onChange={handleChange}
                                helperText="Click to pick a brand color"
                            />
                        </Grid>

                        <Grid item xs={12} sm={6}>
                            <TextField
                                fullWidth
                                label="Secondary Color"
                                name="secondary_color"
                                type="color"
                                value={formData.secondary_color}
                                onChange={handleChange}
                            />
                        </Grid>

                        <Grid item xs={12} sm={6}>
                            <TextField
                                fullWidth
                                label="Accent Color"
                                name="accent_color"
                                type="color"
                                value={formData.accent_color}
                                onChange={handleChange}
                            />
                        </Grid>

                        <Grid item xs={12} sm={6}>
                            <TextField
                                fullWidth
                                label="Background Color"
                                name="background_color"
                                type="color"
                                value={formData.background_color}
                                onChange={handleChange}
                            />
                        </Grid>

                        <Grid item xs={12} sm={6}>
                            <TextField
                                fullWidth
                                label="Logo URL (optional)"
                                name="logo_url"
                                value={formData.logo_url}
                                onChange={handleChange}
                                helperText="Optional: external logo URL"
                            />
                        </Grid>

                        <Grid item xs={12} sm={6}>
                            <Button variant="outlined" component="label" fullWidth>
                                {logoFile ? 'Change Logo (DB)' : 'Upload Logo (DB)'}
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
                            {logoPreview && (
                                <Box sx={{ mt: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
                                    <Avatar src={logoPreview} sx={{ width: 48, height: 48 }} />
                                    <Typography variant="caption" color="text.secondary">Preview</Typography>
                                </Box>
                            )}
                        </Grid>

                        <Grid item xs={12}>
                            <Typography variant="h6" gutterBottom sx={{ mt: 2 }}>
                                General Information
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

                        <Grid item xs={12}>
                            <Button
                                type="submit"
                                variant="contained"
                                size="large"
                                disabled={saving}
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
