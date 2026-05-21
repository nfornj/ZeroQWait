import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
    Accordion,
    AccordionDetails,
    AccordionSummary,
    Alert,
    Avatar,
    Box,
    Button,
    Card,
    Chip,
    CircularProgress,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    Grid,
    IconButton,
    InputAdornment,
    MenuItem,
    Paper,
    Stack,
    Switch,
    TextField,
    Typography,
} from '@mui/material';
import { DataGrid, GridActionsCellItem, GridColDef } from '@mui/x-data-grid';
import AddIcon from '@mui/icons-material/Add';
import AutoAwesomeRoundedIcon from '@mui/icons-material/AutoAwesomeRounded';
import CheckCircleOutlineRoundedIcon from '@mui/icons-material/CheckCircleOutlineRounded';
import ChevronRightRoundedIcon from '@mui/icons-material/ChevronRightRounded';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import ExpandMoreRoundedIcon from '@mui/icons-material/ExpandMoreRounded';
import PaletteRoundedIcon from '@mui/icons-material/PaletteRounded';
import api from '../../../services/api';
import { ThemePreset, useThemeContext } from '../../../contexts/ThemeContext';

const settingsSerifFont = '"Iowan Old Style", "Baskerville", "Palatino Linotype", "Book Antiqua", Georgia, serif';
const settingsSansFont = '"Inter", "Segoe UI", "Roboto", "Helvetica Neue", Arial, sans-serif';
const settingsColors = {
    canvas: '#ffffff',
    text: '#141923',
    mutedText: '#6f737b',
    border: '#e7e6e2',
    divider: '#e9e8e4',
    green: '#315b44',
    greenDark: '#264a38',
    greenWash: '#edf3ef',
    lightSurface: '#f8f9f8',
    infoWash: '#eef5fb',
    danger: '#dc3f3b',
};

const sectionSpacing = {
    page: {
        maxWidth: 1220,
        px: { xs: 1.25, md: 1.8 },
        pt: { xs: 1.35, md: 1.8 },
    },
    cardPadding: { xs: 1.35, md: 1.7 },
    cardPaddingCompact: { xs: 1.15, md: 1.45 },
    stepBadge: { xs: 1.2, md: 1.45 },
    footer: { xs: { left: 10, right: 10, py: 0.95, px: 1.1 }, md: { left: 18, right: 18, py: 1, px: 1.7 } },
};

const typographyScale = {
    pageTitle: { xs: 22, md: 30 },
    sectionTitle: { xs: 18, md: 24 },
    sectionSubTitle: { xs: 13.5, md: 14.5 },
    cardTitle: 14,
    small: 12.75,
    xsBody: 11.75,
};

const surfaceCardSx = {
    borderRadius: '14px',
    border: `1px solid ${settingsColors.border}`,
    bgcolor: '#fff',
    boxShadow: '0 8px 18px rgba(24,30,28,0.03), 0 1px 4px rgba(24,30,28,0.02)',
};

const THEMES: { id: ThemePreset; name: string; primary: string; secondary: string }[] = [
    { id: 'default', name: 'Coral', primary: '#FF5A5F', secondary: '#00A699' },
    { id: 'ocean', name: 'Ocean', primary: '#0077B6', secondary: '#48CAE4' },
    { id: 'forest', name: 'Forest', primary: '#2D6A4F', secondary: '#D8F3DC' },
    { id: 'sunset', name: 'Sunset', primary: '#E07A5F', secondary: '#F2CC8F' },
    { id: 'midnight', name: 'Midnight', primary: '#7209B7', secondary: '#4361EE' },
    { id: 'corporate', name: 'Corporate', primary: '#2B2D42', secondary: '#8D99AE' },
];

type WizardStep = 'branding' | 'business' | 'experience' | 'availability';

const wizardSteps: { key: WizardStep; title: string; subtitle: string; icon?: React.ReactElement }[] = [
    { key: 'branding', title: 'Branding', subtitle: 'Logo, colors & identity', icon: <PaletteRoundedIcon sx={{ fontSize: 16 }} /> },
    { key: 'business', title: 'Business Info', subtitle: 'Shop details & contact' },
    { key: 'experience', title: 'Experience', subtitle: 'Preferences & environment' },
    { key: 'availability', title: 'Availability', subtitle: 'Schedule & closed days' },
];

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

interface ServiceFormState {
    id?: number;
    name: string;
    description: string;
    duration_minutes: number;
    cost: number;
}

interface BusinessHoursRow {
    day: string;
    open: boolean;
    start: string;
    end: string;
}

interface ExperienceState {
    bookingEnabled: boolean;
    requireConfirmation: boolean;
    allowRescheduling: boolean;
    allowCancellations: boolean;
    reminderPreference: string;
    reminderTime: string;
    followUp: boolean;
    waitingList: boolean;
    autoConfirm: boolean;
    bookingNotice: string;
}

interface ClosedDayDraft {
    name: string;
    date: string;
    notes: string;
    repeatAnnually: boolean;
}

const initialHours: BusinessHoursRow[] = [
    { day: 'Monday', open: true, start: '09:00', end: '19:00' },
    { day: 'Tuesday', open: true, start: '09:00', end: '19:00' },
    { day: 'Wednesday', open: true, start: '09:00', end: '19:00' },
    { day: 'Thursday', open: true, start: '09:00', end: '20:00' },
    { day: 'Friday', open: true, start: '09:00', end: '20:00' },
    { day: 'Saturday', open: true, start: '10:00', end: '18:00' },
    { day: 'Sunday', open: false, start: '10:00', end: '16:00' },
];

const initialExperience: ExperienceState = {
    bookingEnabled: true,
    requireConfirmation: true,
    allowRescheduling: true,
    allowCancellations: true,
    reminderPreference: 'Send email and SMS reminders',
    reminderTime: '24 hours before appointment',
    followUp: true,
    waitingList: true,
    autoConfirm: false,
    bookingNotice: '2 hours',
};

const emptyClosedDayDraft: ClosedDayDraft = {
    name: '',
    date: '',
    notes: '',
    repeatAnnually: true,
};

const formatDateLong = (value: string | Date) => {
    const date = value instanceof Date ? value : new Date(value);
    if (Number.isNaN(date.getTime())) return '';
    return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
};

const formatTime = (value: string) => {
    const [hour, minute] = value.split(':');
    const hh = Number(hour);
    const suffix = hh >= 12 ? 'PM' : 'AM';
    const normalized = hh % 12 || 12;
    return `${normalized}:${minute} ${suffix}`;
};

const ShopSettingsPage: React.FC = () => {
    const { themePreset, setThemePreset } = useThemeContext();
    const presetTheme = THEMES.find((item) => item.id === themePreset) || THEMES[0];
    const [shop, setShop] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [wizardStep, setWizardStep] = useState<WizardStep>('branding');
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);
    const [saving, setSaving] = useState(false);
    const [logoFile, setLogoFile] = useState<File | null>(null);
    const [logoPreview, setLogoPreview] = useState<string>('');
    const [isAdvancedOpen, setIsAdvancedOpen] = useState(false);
    const [availabilityPanel, setAvailabilityPanel] = useState<'overview' | 'add-closed-day'>('overview');

    const [formData, setFormData] = useState({
        name: '',
        description: '',
        phone: '',
        website: '',
        email: '',
        shop_type: 'Spa & Wellness',
        address: '',
        city: '',
        state: '',
        zip_code: '',
        country: 'United States',
        primary_color: presetTheme.primary,
        secondary_color: presetTheme.secondary,
        accent_color: '',
        background_color: '',
        logo_url: '',
        slug: '',
    });

    const [businessHoursDraft, setBusinessHoursDraft] = useState<BusinessHoursRow[]>(initialHours);
    const [experienceDraft, setExperienceDraft] = useState<ExperienceState>(initialExperience);
    const [closedDayDraft, setClosedDayDraft] = useState<ClosedDayDraft>(emptyClosedDayDraft);

    // Services
    const [services, setServices] = useState<any[]>([]);
    const [serviceLoading, setServiceLoading] = useState(false);
    const [openServiceDialog, setOpenServiceDialog] = useState(false);
    const [serviceFormData, setServiceFormData] = useState<ServiceFormState>({
        id: undefined,
        name: '',
        description: '',
        duration_minutes: 30,
        cost: 0.0,
    });
    const [deleteServiceConfirmId, setDeleteServiceConfirmId] = useState<number | null>(null);

    // AI
    const [llmLoading, setLlmLoading] = useState(false);
    const [llmError, setLlmError] = useState<string | null>(null);
    const [aiEnvironment, setAiEnvironment] = useState<ShopAIEnvironmentResponse | null>(null);

    // Utilities / close days
    const [generateDataDialogOpen, setGenerateDataDialogOpen] = useState(false);
    const [closeDays, setCloseDays] = useState<any[]>([]);
    const [closeDaysLoading, setCloseDaysLoading] = useState(false);

    const fetchServices = useCallback(async (shopId: number) => {
        try {
            setServiceLoading(true);
            const response = await api.get(`/shops/${shopId}/services`);
            setServices(Array.isArray(response.data) ? response.data : []);
        } catch (err) {
            console.error('Failed to fetch services', err);
        } finally {
            setServiceLoading(false);
        }
    }, []);

    const fetchCloseDays = useCallback(async (shopId: number) => {
        try {
            setCloseDaysLoading(true);
            const response = await api.get(`/shops/${shopId}/close-days`);
            setCloseDays(Array.isArray(response.data) ? response.data : []);
        } catch (err) {
            console.error('Failed to fetch close days', err);
        } finally {
            setCloseDaysLoading(false);
        }
    }, []);

    const fetchLLMSettings = useCallback(async (shopId: number) => {
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
    }, []);

    const fetchShop = useCallback(async () => {
        try {
            const response = await api.get('/shops/my-shops');
            if (response.data.length > 0) {
                const shopData = response.data[0];
                setShop(shopData);
                setFormData({
                    name: shopData.name || '',
                    description: shopData.description || '',
                    phone: shopData.phone || '',
                    website: shopData.website || '',
                    email: shopData.email || '',
                    shop_type: shopData.shop_type || 'Spa & Wellness',
                    address: shopData.address || '',
                    city: shopData.city || '',
                    state: shopData.state || '',
                    zip_code: shopData.zip_code || '',
                    country: shopData.country || 'United States',
                    primary_color: shopData.primary_color || presetTheme.primary,
                    secondary_color: shopData.secondary_color || presetTheme.secondary,
                    accent_color: shopData.accent_color || '',
                    background_color: shopData.background_color || '',
                    logo_url: shopData.logo_url || '',
                    slug: shopData.slug || '',
                });
                if (shopData.logo_url) setLogoPreview(shopData.logo_url);
                fetchServices(shopData.id);
                fetchCloseDays(shopData.id);
                fetchLLMSettings(shopData.id);
            }
        } catch (err) {
            setError('Failed to load shop settings');
        } finally {
            setLoading(false);
        }
    }, [fetchCloseDays, fetchLLMSettings, fetchServices, presetTheme.primary, presetTheme.secondary]);

    useEffect(() => {
        void fetchShop();
    }, [fetchShop]);

    const saveGeneralSettings = useCallback(async (stepAdvance = false) => {
        if (!shop) return false;
        setSaving(true);
        setError(null);
        setSuccess(null);
        try {
            const payload = {
                name: formData.name,
                description: formData.description,
                phone: formData.phone,
                website: formData.website,
                email: formData.email,
                shop_type: formData.shop_type,
                address: formData.address,
                city: formData.city,
                state: formData.state,
                zip_code: formData.zip_code,
                country: formData.country,
                primary_color: formData.primary_color,
                secondary_color: formData.secondary_color,
                accent_color: formData.accent_color,
                background_color: formData.background_color,
            };
            await api.put(`/shops/${shop.id}`, payload);
            if (logoFile) {
                const fd = new FormData();
                fd.append('file', logoFile);
                await api.put(`/shops/${shop.id}/logo`, fd);
                setLogoFile(null);
            }
            if (!stepAdvance) {
                setSuccess('Settings saved successfully');
            }
            return true;
        } catch {
            setError('Failed to save settings');
            return false;
        } finally {
            setSaving(false);
        }
    }, [formData, logoFile, shop]);

    const handleGenerateData = async () => {
        setGenerateDataDialogOpen(false);
        if (!shop) return;
        try {
            await api.post(`/shops/${shop.id}/generate-sample-data`, {});
            setSuccess('Sample data generated! Refreshing...');
            setTimeout(() => window.location.reload(), 1500);
        } catch {
            setError('Failed to generate data');
        }
    };

    const handleServiceSubmit = async () => {
        if (!shop) return;
        try {
            if (serviceFormData.id) {
                await api.put(`/shops/${shop.id}/services/${serviceFormData.id}`, serviceFormData);
            } else {
                await api.post(`/shops/${shop.id}/services`, serviceFormData);
            }
            setOpenServiceDialog(false);
            await fetchServices(shop.id);
            setSuccess('Service saved');
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to save service');
        }
    };

    const confirmDeleteService = async () => {
        if (!shop || deleteServiceConfirmId === null) return;
        try {
            await api.delete(`/shops/${shop.id}/services/${deleteServiceConfirmId}`);
            setDeleteServiceConfirmId(null);
            await fetchServices(shop.id);
            setSuccess('Service deleted');
        } catch {
            setError('Failed to delete service');
        }
    };

    const addClosedDay = async () => {
        if (!shop || !closedDayDraft.date) return;
        try {
            const reason = closedDayDraft.name.trim()
                ? closedDayDraft.name.trim()
                : closedDayDraft.notes.trim()
                    ? closedDayDraft.notes.trim()
                    : 'Closed Day';
            await api.post(`/shops/${shop.id}/close-days`, null, {
                params: { date_str: closedDayDraft.date, reason },
            });
            setClosedDayDraft(emptyClosedDayDraft);
            setAvailabilityPanel('overview');
            await fetchCloseDays(shop.id);
            setSuccess('Close day added');
        } catch {
            setError('Failed to add close day');
        }
    };

    const deleteCloseDay = async (id: number) => {
        if (!shop) return;
        try {
            await api.delete(`/shops/${shop.id}/close-days/${id}`);
            await fetchCloseDays(shop.id);
            setSuccess('Closed day removed');
        } catch {
            setError('Failed to remove close day');
        }
    };

    const selectedTheme = useMemo(
        () => THEMES.find((theme) => theme.primary === formData.primary_color) || THEMES.find((theme) => theme.id === themePreset) || THEMES[0],
        [formData.primary_color, themePreset]
    );

    const stepIndex = wizardSteps.findIndex((step) => step.key === wizardStep);

    const goToStep = (next: WizardStep) => {
        setWizardStep(next);
        if (next !== 'availability') setAvailabilityPanel('overview');
    };

    const onSaveAndContinue = async () => {
        const isPersistedStep = wizardStep === 'branding' || wizardStep === 'business';
        if (isPersistedStep) {
            const ok = await saveGeneralSettings(true);
            if (!ok) return;
            setSuccess('Step saved');
        }
        if (wizardStep === 'experience') {
            setSuccess('Experience preferences saved locally');
        }
        if (wizardStep === 'availability') {
            if (availabilityPanel === 'add-closed-day') {
                await addClosedDay();
                return;
            }
            setSuccess('Availability preferences saved locally');
            return;
        }
        const next = wizardSteps[stepIndex + 1];
        if (next) goToStep(next.key);
    };

    const onBack = () => {
        if (wizardStep === 'availability' && availabilityPanel === 'add-closed-day') {
            setAvailabilityPanel('overview');
            return;
        }
        const previous = wizardSteps[stepIndex - 1];
        if (previous) goToStep(previous.key);
    };

    const updateHourRow = (day: string, patch: Partial<BusinessHoursRow>) => {
        setBusinessHoursDraft((prev) => prev.map((row) => (row.day === day ? { ...row, ...patch } : row)));
    };

    if (loading) {
        return (
            <Box display="flex" justifyContent="center" alignItems="center" minHeight={400}>
                <CircularProgress />
            </Box>
        );
    }

    if (!shop) {
        return <Alert severity="warning">No shop found</Alert>;
    }

    const serviceColumns: GridColDef[] = [
        { field: 'name', headerName: 'Name', flex: 1 },
        { field: 'cost', headerName: 'Cost', width: 100, valueFormatter: (value: any) => `$${Number(value).toFixed(2)}` },
        { field: 'duration_minutes', headerName: 'Duration', width: 110, valueFormatter: (value: any) => `${value} min` },
        {
            field: 'actions',
            type: 'actions',
            width: 100,
            getActions: (params) => [
                <GridActionsCellItem
                    icon={<EditIcon />}
                    label="Edit"
                    onClick={() => {
                        setServiceFormData({
                            id: params.row.id,
                            name: params.row.name,
                            description: params.row.description,
                            duration_minutes: params.row.duration_minutes,
                            cost: params.row.cost,
                        });
                        setOpenServiceDialog(true);
                    }}
                />,
                <GridActionsCellItem
                    icon={<DeleteIcon color="error" />}
                    label="Delete"
                    onClick={() => setDeleteServiceConfirmId(params.row.id)}
                />,
            ],
        },
    ];

    return (
        <Box
            sx={{
                width: '100%',
                minHeight: 'calc(100vh - var(--navbar-h))',
                bgcolor: settingsColors.canvas,
                color: settingsColors.text,
                fontFamily: settingsSansFont,
                px: sectionSpacing.page.px,
                pt: sectionSpacing.page.pt,
                pb: { xs: 14, md: 11 },
                '& .MuiInputLabel-root': { fontSize: 13.5 },
                '& .MuiInputBase-root': { fontSize: 14, borderRadius: '10px' },
                '& .MuiFormHelperText-root': { fontSize: 11.75, mx: 0.2 },
                '& .MuiButton-root': { textTransform: 'none', fontSize: 14, minHeight: 36 },
                '& .MuiChip-root': { height: 26, fontSize: 12 },
            }}
        >
            <Box sx={{ maxWidth: sectionSpacing.page.maxWidth, mx: 'auto' }}>
                <Box sx={{ mb: { xs: 2.2, md: 2.7 } }}>
                    <Typography
                        component="h1"
                        sx={{
                            fontFamily: settingsSerifFont,
                            fontSize: typographyScale.pageTitle,
                            lineHeight: 1,
                            fontWeight: 500,
                            color: settingsColors.text,
                        }}
                    >
                        Customize your workspace
                    </Typography>
                    <Typography
                        sx={{
                            mt: 1.2,
                            color: settingsColors.mutedText,
                            fontSize: typographyScale.sectionSubTitle,
                            lineHeight: 1.45,
                        }}
                    >
                        Configure your shop settings, branding, and preferences.
                    </Typography>
                </Box>

                <Card variant="outlined" sx={{ ...surfaceCardSx, mb: 3 }}>
                    <Box
                        sx={{
                            display: 'grid',
                            gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, minmax(0, 1fr))', lg: 'repeat(4, minmax(0, 1fr))' },
                        }}
                    >
                        {wizardSteps.map((step, index) => {
                            const isActive = wizardStep === step.key;
                            const isComplete = stepIndex > index;
                            return (
                                <Box key={step.key} sx={{ position: 'relative', px: { xs: 1.65, md: 2.05 }, py: sectionSpacing.stepBadge }}>
                                    <Button
                                        onClick={() => goToStep(step.key)}
                                        sx={{
                                            p: 0,
                                            minWidth: 0,
                                            textAlign: 'left',
                                            width: '100%',
                                            justifyContent: 'flex-start',
                                            color: settingsColors.text,
                                            '&:hover': { bgcolor: 'transparent' },
                                        }}
                                    >
                                        <Stack direction="row" spacing={1.25} alignItems="center" sx={{ width: '100%' }}>
                                            <Box
                                                sx={{
                                                    width: 30,
                                                    height: 30,
                                                    borderRadius: '50%',
                                                    bgcolor: isActive || isComplete ? settingsColors.greenWash : '#f0f1f1',
                                                    color: isActive || isComplete ? settingsColors.green : '#717682',
                                                    border: `1px solid ${isActive ? '#bad0c0' : '#ececeb'}`,
                                                    display: 'grid',
                                                    placeItems: 'center',
                                                    fontWeight: 700,
                                                    fontSize: 16,
                                                    flex: '0 0 auto',
                                                }}
                                            >
                                                {step.icon || index + 1}
                                            </Box>
                                            <Box sx={{ minWidth: 0 }}>
                                                <Typography sx={{ fontSize: { xs: 14, md: 15 }, fontWeight: 700, color: settingsColors.text }}>
                                                    {step.title}
                                                </Typography>
                                                <Typography sx={{ fontSize: 12, color: settingsColors.mutedText }}>
                                                    {step.subtitle}
                                                </Typography>
                                            </Box>
                                        </Stack>
                                    </Button>
                                    {isActive && (
                                    <Box
                                        sx={{
                                            position: 'absolute',
                                            left: 12,
                                            right: 12,
                                            bottom: 0,
                                            height: 3,
                                            width: { xs: '56%', md: 64 },
                                            borderRadius: 8,
                                            bgcolor: settingsColors.green,
                                        }}
                                    />
                                    )}
                                </Box>
                            );
                        })}
                    </Box>
                </Card>

                {error && <Alert severity="error" onClose={() => setError(null)} sx={{ mb: 2.1 }}>{error}</Alert>}
                {success && <Alert severity="success" onClose={() => setSuccess(null)} sx={{ mb: 2.1 }}>{success}</Alert>}

                {wizardStep === 'branding' && (
                    <Grid container spacing={2.2}>
                        <Grid size={{ xs: 12, lg: 7.6 }}>
                            <Card variant="outlined" sx={{ ...surfaceCardSx, p: sectionSpacing.cardPadding, height: '100%' }}>
                                <Typography sx={{ fontFamily: settingsSerifFont, fontSize: typographyScale.sectionTitle, lineHeight: 1, fontWeight: 600 }}>
                                    Brand Identity
                                </Typography>
                                <Typography sx={{ mt: 1, color: settingsColors.mutedText, fontSize: typographyScale.sectionSubTitle, lineHeight: 1.45 }}>
                                    Set your logo and brand colors. These will be reflected across your workspace and booking pages.
                                </Typography>

                                <Grid container spacing={2} sx={{ mt: 0.6 }}>
                                    <Grid size={{ xs: 12, md: 4.1 }}>
                                        <Typography sx={{ mb: 0.8, fontSize: typographyScale.cardTitle, fontWeight: 700 }}>Logo</Typography>
                                        <Box
                                            sx={{
                                                border: `1px dashed ${settingsColors.border}`,
                                                borderRadius: '14px',
                                                p: 1.6,
                                                textAlign: 'center',
                                                bgcolor: settingsColors.lightSurface,
                                            }}
                                        >
                                            {logoPreview ? (
                                                <Avatar src={logoPreview} sx={{ width: 78, height: 78, mx: 'auto', mb: 1.1 }} />
                                            ) : (
                                                <CloudUploadIcon sx={{ fontSize: 40, color: '#89909a', mb: 1 }} />
                                            )}
                                            <Button
                                                component="label"
                                                size="small"
                                                sx={{ color: `${settingsColors.text} !important`, fontWeight: 700 }}
                                            >
                                                Upload your logo
                                                <input
                                                    type="file"
                                                    hidden
                                                    accept="image/*"
                                                    onChange={(event) => {
                                                        const file = event.target.files?.[0];
                                                        if (file) {
                                                            setLogoFile(file);
                                                            setLogoPreview(URL.createObjectURL(file));
                                                        }
                                                    }}
                                                />
                                            </Button>
                                            <Typography sx={{ mt: 0.6, color: settingsColors.mutedText, fontSize: typographyScale.xsBody }}>
                                                PNG, JPG or SVG. Max 2MB
                                            </Typography>
                                        </Box>
                                    </Grid>

                                    <Grid size={{ xs: 12, md: 7.9 }}>
                                        <Typography sx={{ mb: 0.8, fontSize: typographyScale.cardTitle, fontWeight: 700 }}>Choose your brand colors</Typography>
                                        <Typography sx={{ color: settingsColors.mutedText, fontSize: 15 }}>
                                            Select a theme color that represents your brand.
                                        </Typography>
                                        <Stack direction="row" spacing={1.1} flexWrap="wrap" useFlexGap sx={{ mt: 1.8 }}>
                                            {THEMES.map((theme) => {
                                                const selected = selectedTheme.id === theme.id;
                                                return (
                                                    <Box
                                                        key={theme.id}
                                                        component="button"
                                                        onClick={() => {
                                                            setThemePreset(theme.id);
                                                            setFormData((prev) => ({
                                                                ...prev,
                                                                primary_color: theme.primary,
                                                                secondary_color: theme.secondary,
                                                            }));
                                                        }}
                                                        sx={{
                                                            width: 84,
                                                            border: selected ? `2px solid ${theme.primary}` : `1px solid ${settingsColors.border}`,
                                                            borderRadius: '11px',
                                                            bgcolor: '#fff',
                                                            p: 0.55,
                                                            cursor: 'pointer',
                                                            font: 'inherit',
                                                        }}
                                                    >
                                                        <Box sx={{ height: 48, borderRadius: '8px', bgcolor: theme.primary }} />
                                                        <Typography sx={{ mt: 0.7, fontSize: 13, fontWeight: selected ? 700 : 600, color: settingsColors.text }}>
                                                            {theme.name}
                                                        </Typography>
                                                    </Box>
                                                );
                                            })}
                                        </Stack>
                                    </Grid>
                                </Grid>

                                <Card
                                    variant="outlined"
                                    sx={{
                                        mt: 1.8,
                                        borderRadius: '12px',
                                        border: `1px solid ${settingsColors.border}`,
                                        overflow: 'hidden',
                                    }}
                                >
                                    <Box sx={{ p: 1.35, borderBottom: `1px solid ${settingsColors.border}` }}>
                                        <Typography sx={{ fontSize: 14, fontWeight: 700 }}>Live Preview</Typography>
                                    </Box>
                                    <Box
                                        sx={{
                                            px: 1.4,
                                            py: 1.55,
                                            background: `linear-gradient(110deg, ${selectedTheme.secondary || '#f4f5f6'} 0%, #ffffff 55%, #f2f3ef 100%)`,
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: 1.35,
                                        }}
                                    >
                                        <Avatar
                                            src={logoPreview || undefined}
                                            sx={{
                                                width: 68,
                                                height: 68,
                                                bgcolor: selectedTheme.primary,
                                                color: '#fff',
                                                fontSize: 24,
                                            }}
                                        >
                                            {(!logoPreview && formData.name) ? formData.name.charAt(0).toUpperCase() : null}
                                        </Avatar>
                                        <Box>
                                            <Typography sx={{ fontFamily: settingsSerifFont, fontSize: 20, lineHeight: 1, color: '#17335a' }}>
                                                {formData.name || 'Your Shop'}
                                            </Typography>
                                            <Typography sx={{ mt: 0.35, fontSize: 17, lineHeight: 1.05, color: '#1f2a43' }}>
                                                {formData.shop_type || 'Business'}
                                            </Typography>
                                            <Typography sx={{ mt: 0.45, fontSize: 13.5, color: '#2f3955' }}>
                                                Relax. Restore. Rebalance.
                                            </Typography>
                                        </Box>
                                    </Box>
                                </Card>

                                <Alert
                                    icon={<AutoAwesomeRoundedIcon />}
                                    severity="info"
                                    sx={{
                                        mt: 1.8,
                                        borderRadius: '11px',
                                        bgcolor: settingsColors.infoWash,
                                        border: `1px solid #d9e6f3`,
                                    }}
                                >
                                    Tip: A strong brand helps build trust and makes your shop memorable.
                                </Alert>
                            </Card>
                        </Grid>

                        <Grid size={{ xs: 12, lg: 4.4 }}>
                            <Card variant="outlined" sx={{ ...surfaceCardSx, p: sectionSpacing.cardPadding, height: '100%' }}>
                                <Typography sx={{ fontFamily: settingsSerifFont, fontSize: typographyScale.sectionTitle, lineHeight: 1, fontWeight: 600 }}>
                                    Business Details
                                </Typography>
                                <Typography sx={{ mt: 1, color: settingsColors.mutedText, fontSize: typographyScale.sectionSubTitle }}>
                                    Basic information about your shop.
                                </Typography>
                                <Stack spacing={1.6} sx={{ mt: 1.8 }}>
                                    <TextField
                                        label="Shop Name"
                                        value={formData.name}
                                        onChange={(event) => setFormData((prev) => ({ ...prev, name: event.target.value }))}
                                        fullWidth
                                    />
                                    <TextField
                                        label="Description"
                                        value={formData.description}
                                        onChange={(event) => setFormData((prev) => ({ ...prev, description: event.target.value }))}
                                        fullWidth
                                        multiline
                                        rows={3}
                                        helperText={`${formData.description.length}/200`}
                                    />
                                    <Grid container spacing={1.25}>
                                        <Grid size={{ xs: 12, md: 6 }}>
                                            <TextField
                                                label="Phone"
                                                value={formData.phone}
                                                onChange={(event) => setFormData((prev) => ({ ...prev, phone: event.target.value }))}
                                                fullWidth
                                            />
                                        </Grid>
                                        <Grid size={{ xs: 12, md: 6 }}>
                                            <TextField
                                                label="Website"
                                                value={formData.website}
                                                onChange={(event) => setFormData((prev) => ({ ...prev, website: event.target.value }))}
                                                fullWidth
                                            />
                                        </Grid>
                                    </Grid>

                                    <Card
                                        variant="outlined"
                                        sx={{
                                            p: 1.7,
                                            borderRadius: '13px',
                                            borderColor: '#dbe8e1',
                                            bgcolor: '#f5fbf7',
                                        }}
                                    >
                                        <Stack direction="row" spacing={1.5} alignItems="flex-start">
                                            <Avatar
                                                sx={{
                                                    bgcolor: settingsColors.greenWash,
                                                    color: settingsColors.green,
                                                    width: 34,
                                                    height: 34,
                                                }}
                                            >
                                                <AutoAwesomeRoundedIcon sx={{ fontSize: 20 }} />
                                            </Avatar>
                                            <Box>
                                            <Typography sx={{ fontSize: typographyScale.cardTitle, fontWeight: 700, color: settingsColors.green }}>
                                                Need help writing?
                                            </Typography>
                                            <Typography sx={{ mt: 0.35, color: settingsColors.mutedText, fontSize: typographyScale.small }}>
                                                Generate a description with AI based on your services.
                                            </Typography>
                                            <Button
                                                onClick={() => setGenerateDataDialogOpen(true)}
                                                sx={{
                                                    mt: 1.1,
                                                    borderRadius: '11px',
                                                    border: '1px solid #bdd7c8',
                                                    color: `${settingsColors.green} !important`,
                                                        fontWeight: 700,
                                                    }}
                                                >
                                                    Generate with AI
                                                </Button>
                                            </Box>
                                        </Stack>
                                    </Card>
                                </Stack>
                            </Card>
                        </Grid>
                    </Grid>
                )}

                {wizardStep === 'business' && (
                    <Grid container spacing={2.2}>
                        <Grid size={{ xs: 12, lg: 8.4 }}>
                            <Card variant="outlined" sx={{ ...surfaceCardSx, p: sectionSpacing.cardPadding, height: '100%' }}>
                                <Typography sx={{ fontFamily: settingsSerifFont, fontSize: typographyScale.sectionTitle, lineHeight: 1, fontWeight: 600 }}>
                                    Business Information
                                </Typography>
                                <Typography sx={{ mt: 1, color: settingsColors.mutedText, fontSize: typographyScale.sectionSubTitle }}>
                                    Provide key details about your business so clients can connect with you.
                                </Typography>

                                <Grid container spacing={1.8} sx={{ mt: 1.2 }}>
                                    <Grid size={{ xs: 12, md: 6 }}>
                                        <TextField
                                            label="Shop Name"
                                            value={formData.name}
                                            onChange={(event) => setFormData((prev) => ({ ...prev, name: event.target.value }))}
                                            fullWidth
                                        />
                                    </Grid>
                                    <Grid size={{ xs: 12, md: 6 }}>
                                        <TextField
                                            label="Phone"
                                            value={formData.phone}
                                            onChange={(event) => setFormData((prev) => ({ ...prev, phone: event.target.value }))}
                                            fullWidth
                                        />
                                    </Grid>
                                    <Grid size={{ xs: 12, md: 6 }}>
                                        <TextField
                                            label="Tagline (Optional)"
                                            value="Relax. Restore. Rebalance."
                                            fullWidth
                                            disabled
                                        />
                                    </Grid>
                                    <Grid size={{ xs: 12, md: 6 }}>
                                        <TextField
                                            label="Email"
                                            value={formData.email}
                                            onChange={(event) => setFormData((prev) => ({ ...prev, email: event.target.value }))}
                                            fullWidth
                                        />
                                    </Grid>
                                    <Grid size={{ xs: 12, md: 6 }}>
                                        <TextField
                                            label="Business Type"
                                            value={formData.shop_type}
                                            onChange={(event) => setFormData((prev) => ({ ...prev, shop_type: event.target.value }))}
                                            fullWidth
                                        />
                                    </Grid>
                                    <Grid size={{ xs: 12, md: 6 }}>
                                        <TextField
                                            label="Website"
                                            value={formData.website}
                                            onChange={(event) => setFormData((prev) => ({ ...prev, website: event.target.value }))}
                                            fullWidth
                                        />
                                    </Grid>
                                    <Grid size={{ xs: 12, md: 6 }}>
                                        <TextField label="Tax ID / Business Number (Optional)" value="" disabled fullWidth />
                                    </Grid>
                                    <Grid size={{ xs: 12, md: 6 }}>
                                        <TextField label="Instagram (Optional)" value="" disabled fullWidth />
                                    </Grid>
                                    <Grid size={{ xs: 12 }}>
                                        <TextField
                                            label="Address"
                                            value={formData.address}
                                            onChange={(event) => setFormData((prev) => ({ ...prev, address: event.target.value }))}
                                            fullWidth
                                        />
                                    </Grid>
                                    <Grid size={{ xs: 12, md: 4 }}>
                                        <TextField
                                            label="City"
                                            value={formData.city}
                                            onChange={(event) => setFormData((prev) => ({ ...prev, city: event.target.value }))}
                                            fullWidth
                                        />
                                    </Grid>
                                    <Grid size={{ xs: 12, md: 4 }}>
                                        <TextField
                                            label="State"
                                            value={formData.state}
                                            onChange={(event) => setFormData((prev) => ({ ...prev, state: event.target.value }))}
                                            fullWidth
                                        />
                                    </Grid>
                                    <Grid size={{ xs: 12, md: 4 }}>
                                        <TextField
                                            label="ZIP / Postal Code"
                                            value={formData.zip_code}
                                            onChange={(event) => setFormData((prev) => ({ ...prev, zip_code: event.target.value }))}
                                            fullWidth
                                        />
                                    </Grid>
                                    <Grid size={{ xs: 12 }}>
                                        <TextField
                                            select
                                            label="Timezone"
                                            value="(GMT-05:00) Eastern Time (US & Canada)"
                                            fullWidth
                                            disabled
                                        >
                                            <MenuItem value="(GMT-05:00) Eastern Time (US & Canada)">
                                                (GMT-05:00) Eastern Time (US & Canada)
                                            </MenuItem>
                                        </TextField>
                                    </Grid>
                                </Grid>
                            </Card>
                        </Grid>

                        <Grid size={{ xs: 12, lg: 3.6 }}>
                            <Card variant="outlined" sx={{ ...surfaceCardSx, p: sectionSpacing.cardPaddingCompact }}>
                                <Typography sx={{ fontSize: 16, fontWeight: 700 }}>Your Business Preview</Typography>
                                <Card variant="outlined" sx={{ mt: 1.2, borderRadius: '11px', overflow: 'hidden' }}>
                                    <Box
                                        sx={{
                                            height: 84,
                                            background: `linear-gradient(120deg, ${selectedTheme.secondary || '#e8edf2'} 0%, #fff 40%, #e4ebdf 100%)`,
                                        }}
                                    />
                                    <Box sx={{ p: 1.15 }}>
                                        <Typography sx={{ fontFamily: settingsSerifFont, fontSize: 18, lineHeight: 1 }}>
                                            {formData.name || 'Your Shop'}
                                        </Typography>
                                        <Typography sx={{ mt: 0.45, color: settingsColors.mutedText, fontSize: typographyScale.small }}>
                                            {formData.description || 'Add a short description for your business.'}
                                        </Typography>
                                        <Stack spacing={0.2} sx={{ mt: 0.8, color: '#4e5561' }}>
                                            <Typography sx={{ fontSize: typographyScale.small }}>{formData.phone || 'Phone not set'}</Typography>
                                            <Typography sx={{ fontSize: typographyScale.small }}>{formData.email || 'Email not set'}</Typography>
                                            <Typography sx={{ fontSize: typographyScale.small }}>{formData.website || 'Website not set'}</Typography>
                                            <Typography sx={{ fontSize: typographyScale.small }}>
                                                {[formData.address, formData.city, formData.state, formData.zip_code].filter(Boolean).join(', ') || 'Address not set'}
                                            </Typography>
                                        </Stack>
                                        <Button
                                            fullWidth
                                            sx={{
                                                mt: 1,
                                                borderRadius: '10px',
                                                border: '1px solid #cad9d0',
                                                color: `${settingsColors.green} !important`,
                                                fontWeight: 700,
                                            }}
                                        >
                                            Edit Branding
                                        </Button>
                                    </Box>
                                </Card>
                            </Card>
                        </Grid>
                    </Grid>
                )}

                {wizardStep === 'experience' && (
                    <Grid container spacing={2.2}>
                        <Grid size={{ xs: 12, lg: 8.4 }}>
                            <Card variant="outlined" sx={{ ...surfaceCardSx, p: sectionSpacing.cardPadding }}>
                                <Typography sx={{ fontFamily: settingsSerifFont, fontSize: typographyScale.sectionTitle, lineHeight: 1, fontWeight: 600 }}>
                                    Client Experience
                                </Typography>
                                <Typography sx={{ mt: 1, color: settingsColors.mutedText, fontSize: typographyScale.sectionSubTitle }}>
                                    Set preferences that shape how your clients book and interact with your shop.
                                </Typography>

                                <Grid container spacing={2} sx={{ mt: 0.6 }}>
                                    <Grid size={{ xs: 12, md: 6 }}>
                                        <Stack spacing={1.7}>
                                            {[
                                                ['Booking Enabled', 'Allow clients to book appointments online', 'bookingEnabled'],
                                                ['Require Confirmation', 'Ask for confirmation before booking', 'requireConfirmation'],
                                                ['Allow Rescheduling', 'Let clients reschedule their appointments', 'allowRescheduling'],
                                                ['Allow Cancellations', 'Let clients cancel appointments', 'allowCancellations'],
                                            ].map(([title, detail, key]) => (
                                                <Box key={key} sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                                    <Box>
                                                        <Typography sx={{ fontSize: 15, fontWeight: 700 }}>{title}</Typography>
                                                        <Typography sx={{ color: settingsColors.mutedText, fontSize: 13.5 }}>{detail}</Typography>
                                                    </Box>
                                                    <Switch
                                                        checked={experienceDraft[key as keyof ExperienceState] as boolean}
                                                        onChange={(event) =>
                                                            setExperienceDraft((prev) => ({ ...prev, [key]: event.target.checked }))
                                                        }
                                                    />
                                                </Box>
                                            ))}
                                            <TextField
                                                select
                                                label="Booking Notice"
                                                value={experienceDraft.bookingNotice}
                                                onChange={(event) =>
                                                    setExperienceDraft((prev) => ({ ...prev, bookingNotice: event.target.value }))
                                                }
                                                fullWidth
                                            >
                                                <MenuItem value="1 hour">1 hour</MenuItem>
                                                <MenuItem value="2 hours">2 hours</MenuItem>
                                                <MenuItem value="4 hours">4 hours</MenuItem>
                                                <MenuItem value="24 hours">24 hours</MenuItem>
                                            </TextField>
                                        </Stack>
                                    </Grid>

                                    <Grid size={{ xs: 12, md: 6 }}>
                                        <Stack spacing={1.7}>
                                            <TextField
                                                select
                                                label="Reminder Preferences"
                                                value={experienceDraft.reminderPreference}
                                                onChange={(event) =>
                                                    setExperienceDraft((prev) => ({ ...prev, reminderPreference: event.target.value }))
                                                }
                                            >
                                                <MenuItem value="Send email reminders">Send email reminders</MenuItem>
                                                <MenuItem value="Send email and SMS reminders">Send email and SMS reminders</MenuItem>
                                                <MenuItem value="No reminders">No reminders</MenuItem>
                                            </TextField>
                                            <TextField
                                                select
                                                label="Reminder Time"
                                                value={experienceDraft.reminderTime}
                                                onChange={(event) =>
                                                    setExperienceDraft((prev) => ({ ...prev, reminderTime: event.target.value }))
                                                }
                                            >
                                                <MenuItem value="1 hour before appointment">1 hour before appointment</MenuItem>
                                                <MenuItem value="24 hours before appointment">24 hours before appointment</MenuItem>
                                                <MenuItem value="48 hours before appointment">48 hours before appointment</MenuItem>
                                            </TextField>

                                            {[
                                                ['Follow Up', 'Send thank you message after visit', 'followUp'],
                                                ['Waiting List', 'Allow clients to join waiting list', 'waitingList'],
                                                ['Auto Confirm Appointments', 'Automatically confirm new bookings', 'autoConfirm'],
                                            ].map(([title, detail, key]) => (
                                                <Box key={key} sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                                    <Box>
                                                        <Typography sx={{ fontSize: 15, fontWeight: 700 }}>{title}</Typography>
                                                        <Typography sx={{ color: settingsColors.mutedText, fontSize: 13.5 }}>{detail}</Typography>
                                                    </Box>
                                                    <Switch
                                                        checked={experienceDraft[key as keyof ExperienceState] as boolean}
                                                        onChange={(event) =>
                                                            setExperienceDraft((prev) => ({ ...prev, [key]: event.target.checked }))
                                                        }
                                                    />
                                                </Box>
                                            ))}
                                        </Stack>
                                    </Grid>
                                </Grid>
                            </Card>
                        </Grid>

                        <Grid size={{ xs: 12, lg: 3.6 }}>
                            <Card variant="outlined" sx={{ ...surfaceCardSx, p: sectionSpacing.cardPaddingCompact, height: '100%' }}>
                                <Typography sx={{ fontFamily: settingsSerifFont, fontSize: 20, lineHeight: 1, fontWeight: 600 }}>
                                    Preview
                                </Typography>
                                <Card
                                    variant="outlined"
                                    sx={{
                                        mt: 1.15,
                                        borderRadius: '18px',
                                        border: `1px solid ${settingsColors.border}`,
                                        p: 1.25,
                                        bgcolor: '#fbfbfb',
                                    }}
                                >
                                    <Typography sx={{ textAlign: 'center', fontSize: 13.5, fontWeight: 700 }}>
                                        Book Your Appointment
                                    </Typography>
                                    <Stack spacing={0.7} sx={{ mt: 0.95 }}>
                                        {['Choose Service', 'Select Provider', 'Pick Date & Time', 'Your Details', 'Confirmation'].map((item) => (
                                            <Stack key={item} direction="row" spacing={1} alignItems="center">
                                                <CheckCircleOutlineRoundedIcon sx={{ color: '#8ec2a0', fontSize: 18 }} />
                                                <Typography sx={{ color: settingsColors.mutedText, fontSize: 12.75 }}>{item}</Typography>
                                            </Stack>
                                        ))}
                                    </Stack>
                                    <Button
                                        fullWidth
                                        variant="contained"
                                        sx={{
                                            mt: 1.2,
                                            borderRadius: '10px',
                                            bgcolor: `${settingsColors.green} !important`,
                                            color: '#fff !important',
                                            fontWeight: 700,
                                            '&:hover': { bgcolor: `${settingsColors.greenDark} !important` },
                                        }}
                                    >
                                        Book Now
                                    </Button>
                                </Card>
                            </Card>
                        </Grid>
                    </Grid>
                )}

                {wizardStep === 'availability' && (
                    <Grid container spacing={2.2}>
                        {availabilityPanel === 'overview' && (
                            <>
                                <Grid size={{ xs: 12, lg: 6.8 }}>
                                <Card variant="outlined" sx={{ ...surfaceCardSx, p: sectionSpacing.cardPadding }}>
                                    <Typography sx={{ fontFamily: settingsSerifFont, fontSize: typographyScale.sectionTitle, lineHeight: 1, fontWeight: 600 }}>
                                        Business Hours
                                    </Typography>
                                    <Stack spacing={1.1} sx={{ mt: 1.5 }}>
                                        {businessHoursDraft.map((row) => (
                                            <Stack
                                                    key={row.day}
                                                    direction={{ xs: 'column', md: 'row' }}
                                                    spacing={1}
                                                    alignItems={{ xs: 'stretch', md: 'center' }}
                                                >
                                                    <Typography sx={{ minWidth: 90, fontWeight: 700 }}>{row.day}</Typography>
                                                    <TextField
                                                        select
                                                        size="small"
                                                        value={row.start}
                                                        onChange={(event) => updateHourRow(row.day, { start: event.target.value })}
                                                        disabled={!row.open}
                                                        sx={{ minWidth: 126 }}
                                                    >
                                                        {['08:00', '09:00', '10:00', '11:00'].map((time) => (
                                                            <MenuItem key={time} value={time}>{formatTime(time)}</MenuItem>
                                                        ))}
                                                    </TextField>
                                                    <Typography sx={{ color: settingsColors.mutedText, display: { xs: 'none', md: 'block' } }}>-</Typography>
                                                    <TextField
                                                        select
                                                        size="small"
                                                        value={row.end}
                                                        onChange={(event) => updateHourRow(row.day, { end: event.target.value })}
                                                        disabled={!row.open}
                                                        sx={{ minWidth: 126 }}
                                                    >
                                                        {['16:00', '17:00', '18:00', '19:00', '20:00'].map((time) => (
                                                            <MenuItem key={time} value={time}>{formatTime(time)}</MenuItem>
                                                        ))}
                                                    </TextField>
                                                    <Switch
                                                        checked={row.open}
                                                        onChange={(event) => updateHourRow(row.day, { open: event.target.checked })}
                                                    />
                                                </Stack>
                                            ))}
                                        </Stack>
                                    </Card>
                                </Grid>

                                <Grid size={{ xs: 12, lg: 5.2 }}>
                                    <Card variant="outlined" sx={{ ...surfaceCardSx, p: sectionSpacing.cardPadding }}>
                                        <Typography sx={{ fontFamily: settingsSerifFont, fontSize: typographyScale.sectionTitle, lineHeight: 1, fontWeight: 600 }}>
                                            Closed Days & Holidays
                                        </Typography>
                                        <Stack spacing={0.9} sx={{ mt: 1.5 }}>
                                            {closeDaysLoading && <CircularProgress size={20} />}
                                            {!closeDaysLoading && closeDays.length === 0 && (
                                                <Typography sx={{ color: settingsColors.mutedText }}>No upcoming closed days.</Typography>
                                            )}
                                            {!closeDaysLoading && closeDays.map((day) => (
                                                <Paper
                                                    key={day.id}
                                                    variant="outlined"
                                                    sx={{
                                                        p: 1,
                                                        borderRadius: '11px',
                                                        borderColor: settingsColors.border,
                                                        display: 'flex',
                                                        justifyContent: 'space-between',
                                                        alignItems: 'center',
                                                    }}
                                                >
                                                    <Typography sx={{ fontWeight: 600 }}>{day.reason || 'Closed Day'}</Typography>
                                                    <Stack direction="row" spacing={0.8} alignItems="center">
                                                        <Typography sx={{ color: settingsColors.mutedText }}>{formatDateLong(day.date)}</Typography>
                                                        <IconButton size="small" onClick={() => deleteCloseDay(day.id)}>
                                                            <DeleteIcon sx={{ fontSize: 18 }} />
                                                        </IconButton>
                                                    </Stack>
                                                </Paper>
                                            ))}
                                        </Stack>
                                        <Button
                                            fullWidth
                                            onClick={() => setAvailabilityPanel('add-closed-day')}
                                            startIcon={<AddIcon />}
                                            sx={{
                                                mt: 1.3,
                                                borderRadius: '10px',
                                                border: '1px solid #d5ddd8',
                                                color: `${settingsColors.green} !important`,
                                                fontWeight: 700,
                                            }}
                                        >
                                            Add Closed Day
                                        </Button>
                                    </Card>
                                </Grid>
                            </>
                        )}

                        {availabilityPanel === 'add-closed-day' && (
                            <>
                                <Grid size={{ xs: 12, lg: 7.3 }}>
                                    <Card variant="outlined" sx={{ ...surfaceCardSx, p: sectionSpacing.cardPadding }}>
                                        <Button
                                            startIcon={<ChevronRightRoundedIcon sx={{ transform: 'rotate(180deg)' }} />}
                                            onClick={() => setAvailabilityPanel('overview')}
                                            sx={{ p: 0, minWidth: 0, mb: 1, color: `${settingsColors.mutedText} !important` }}
                                        >
                                            Back to Availability
                                        </Button>
                                        <Typography sx={{ fontFamily: settingsSerifFont, fontSize: typographyScale.sectionTitle, lineHeight: 1, fontWeight: 600 }}>
                                            Add Closed Day
                                        </Typography>
                                        <Typography sx={{ mt: 1, color: settingsColors.mutedText, fontSize: typographyScale.sectionSubTitle }}>
                                            Mark a day when your business will be closed.
                                        </Typography>
                                        <Stack spacing={1.6} sx={{ mt: 1.7 }}>
                                            <TextField
                                                label="Name"
                                                value={closedDayDraft.name}
                                                onChange={(event) =>
                                                    setClosedDayDraft((prev) => ({ ...prev, name: event.target.value }))
                                                }
                                                fullWidth
                                            />
                                            <TextField
                                                type="date"
                                                label="Date"
                                                value={closedDayDraft.date}
                                                onChange={(event) =>
                                                    setClosedDayDraft((prev) => ({ ...prev, date: event.target.value }))
                                                }
                                                fullWidth
                                                InputLabelProps={{ shrink: true }}
                                            />
                                            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                                <Box>
                                                    <Typography sx={{ fontWeight: 700 }}>Repeat every year</Typography>
                                                    <Typography sx={{ color: settingsColors.mutedText, fontSize: 13.5 }}>
                                                        This closed day will be added every year on this date.
                                                    </Typography>
                                                </Box>
                                                <Switch
                                                    checked={closedDayDraft.repeatAnnually}
                                                    onChange={(event) =>
                                                        setClosedDayDraft((prev) => ({ ...prev, repeatAnnually: event.target.checked }))
                                                    }
                                                />
                                            </Box>
                                            <TextField
                                                label="Notes (Optional)"
                                                value={closedDayDraft.notes}
                                                onChange={(event) =>
                                                    setClosedDayDraft((prev) => ({ ...prev, notes: event.target.value.slice(0, 100) }))
                                                }
                                                helperText={`${closedDayDraft.notes.length}/100`}
                                                fullWidth
                                                multiline
                                                rows={3}
                                            />
                                        </Stack>
                                    </Card>
                                </Grid>

                                <Grid size={{ xs: 12, lg: 4.7 }}>
                                    <Card variant="outlined" sx={{ ...surfaceCardSx, p: sectionSpacing.cardPadding }}>
                                        <Typography sx={{ fontFamily: settingsSerifFont, fontSize: { xs: 26, md: 32 }, lineHeight: 1, fontWeight: 600 }}>
                                            Upcoming Closed Days
                                        </Typography>
                                        <Stack spacing={0.9} sx={{ mt: 1.4 }}>
                                            {closeDays.map((day) => (
                                                <Paper
                                                    key={day.id}
                                                    variant="outlined"
                                                    sx={{
                                                        p: 1,
                                                        borderRadius: '10px',
                                                        borderColor: settingsColors.border,
                                                        display: 'flex',
                                                        justifyContent: 'space-between',
                                                        alignItems: 'center',
                                                    }}
                                                >
                                                    <Typography sx={{ fontWeight: 600 }}>{day.reason || 'Closed Day'}</Typography>
                                                    <Stack direction="row" spacing={0.8} alignItems="center">
                                                        <Typography sx={{ color: settingsColors.mutedText }}>{formatDateLong(day.date)}</Typography>
                                                        <IconButton size="small" onClick={() => deleteCloseDay(day.id)}>
                                                            <DeleteIcon sx={{ fontSize: 18 }} />
                                                        </IconButton>
                                                    </Stack>
                                                </Paper>
                                            ))}
                                        </Stack>
                                    </Card>
                                </Grid>
                            </>
                        )}
                    </Grid>
                )}

                <Accordion
                    expanded={isAdvancedOpen}
                    onChange={(_, expanded) => setIsAdvancedOpen(expanded)}
                    sx={{ ...surfaceCardSx, mt: 2.2, '&::before': { display: 'none' } }}
                >
                    <AccordionSummary expandIcon={<ExpandMoreRoundedIcon />}>
                        <Typography sx={{ fontSize: 16, fontWeight: 700 }}>Advanced Tools</Typography>
                    </AccordionSummary>
                    <AccordionDetails>
                        <Grid container spacing={2}>
                            <Grid size={{ xs: 12, lg: 6.2 }}>
                                <Card variant="outlined" sx={{ ...surfaceCardSx, p: sectionSpacing.cardPaddingCompact }}>
                                    <Typography sx={{ fontFamily: settingsSerifFont, fontSize: 28, lineHeight: 1, fontWeight: 600 }}>
                                        AI Environment
                                    </Typography>
                                    {llmError && <Alert severity="error" sx={{ mt: 1.2 }} onClose={() => setLlmError(null)}>{llmError}</Alert>}
                                    {llmLoading ? (
                                        <Box display="flex" justifyContent="center" py={4}>
                                            <CircularProgress />
                                        </Box>
                                    ) : (
                                        <Stack spacing={1.2} sx={{ mt: 1.3 }}>
                                            <Typography sx={{ color: settingsColors.mutedText }}>
                                                {aiEnvironment?.environment_summary || 'No AI environment data available.'}
                                            </Typography>
                                            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                                                {aiEnvironment?.status_label && <Chip size="small" label={aiEnvironment.status_label} />}
                                                {aiEnvironment?.operating_mode && <Chip size="small" label={aiEnvironment.operating_mode} variant="outlined" />}
                                                {aiEnvironment?.subscription_tier && <Chip size="small" label={`Plan: ${aiEnvironment.subscription_tier}`} variant="outlined" />}
                                            </Stack>
                                            {(aiEnvironment?.capabilities || []).map((item) => (
                                                <Paper key={item} variant="outlined" sx={{ p: 0.95, borderRadius: '10px' }}>
                                                    <Typography sx={{ fontSize: 13.5 }}>{item}</Typography>
                                                </Paper>
                                            ))}
                                        </Stack>
                                    )}
                                </Card>
                            </Grid>

                            <Grid size={{ xs: 12, lg: 5.8 }}>
                                <Card variant="outlined" sx={{ ...surfaceCardSx, p: sectionSpacing.cardPaddingCompact }}>
                                    <Stack direction="row" justifyContent="space-between" alignItems="center">
                                        <Typography sx={{ fontFamily: settingsSerifFont, fontSize: 28, lineHeight: 1, fontWeight: 600 }}>
                                            Services
                                        </Typography>
                                        <Button
                                            startIcon={<AddIcon />}
                                            variant="contained"
                                            onClick={() => {
                                                setServiceFormData({
                                                    id: undefined,
                                                    name: '',
                                                    description: '',
                                                    duration_minutes: 30,
                                                    cost: 0.0,
                                                });
                                                setOpenServiceDialog(true);
                                            }}
                                            sx={{
                                                bgcolor: `${settingsColors.green} !important`,
                                                color: '#fff !important',
                                                '&:hover': { bgcolor: `${settingsColors.greenDark} !important` },
                                            }}
                                        >
                                            Add Service
                                        </Button>
                                    </Stack>
                                    <Box sx={{ mt: 1.15, height: 280 }}>
                                        <DataGrid
                                            rows={services}
                                            columns={serviceColumns}
                                            loading={serviceLoading}
                                            disableRowSelectionOnClick
                                            sx={{
                                                borderRadius: '12px',
                                                borderColor: settingsColors.border,
                                                '& .MuiDataGrid-columnHeaders': { backgroundColor: '#fafafa' },
                                            }}
                                        />
                                    </Box>
                                </Card>
                            </Grid>

                            <Grid size={{ xs: 12 }}>
                                <Card variant="outlined" sx={{ ...surfaceCardSx, p: sectionSpacing.cardPaddingCompact }}>
                                    <Typography sx={{ fontFamily: settingsSerifFont, fontSize: 25, lineHeight: 1, fontWeight: 600 }}>
                                        Utilities
                                    </Typography>
                                    <Typography sx={{ mt: 0.8, color: settingsColors.mutedText, fontSize: 13.5 }}>
                                        Generate sample data for demos and onboarding.
                                    </Typography>
                                    <Button
                                        sx={{
                                            mt: 1.1,
                                            borderRadius: '11px',
                                            bgcolor: `${settingsColors.green} !important`,
                                            color: '#fff !important',
                                            '&:hover': { bgcolor: `${settingsColors.greenDark} !important` },
                                        }}
                                        variant="contained"
                                        onClick={() => setGenerateDataDialogOpen(true)}
                                    >
                                        Generate Sample Data
                                    </Button>
                                </Card>
                            </Grid>
                        </Grid>
                    </AccordionDetails>
                </Accordion>
            </Box>

            <Paper
                variant="outlined"
                sx={{
                    position: { xs: 'static', md: 'fixed' },
                    left: { xs: 'auto', md: sectionSpacing.footer.md.left },
                    right: { xs: 'auto', md: sectionSpacing.footer.md.right },
                    bottom: { xs: 'auto', md: 10 },
                    mt: { xs: 2.2, md: 0 },
                    borderRadius: { xs: '12px', md: '14px' },
                    border: `1px solid ${settingsColors.border}`,
                    boxShadow: '0 11px 24px rgba(20,26,24,0.08)',
                    bgcolor: '#fff',
                    px: { xs: sectionSpacing.footer.xs.px, md: sectionSpacing.footer.md.px },
                    py: { xs: sectionSpacing.footer.xs.py, md: sectionSpacing.footer.md.py },
                    zIndex: 1200,
                    display: 'block',
                }}
            >
                <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" alignItems={{ xs: 'stretch', sm: 'center' }} gap={1.2}>
                    <Stack direction="row" alignItems="center" spacing={0.9}>
                        <CheckCircleOutlineRoundedIcon sx={{ color: '#8ec2a0' }} />
                        <Typography sx={{ color: settingsColors.mutedText, fontWeight: 600, fontSize: 13 }}>
                            {saving ? 'Saving changes...' : 'All changes saved'}
                        </Typography>
                    </Stack>
                    <Stack direction={{ xs: 'column', sm: 'row' }} spacing={0.9}>
                        <Button
                            onClick={onBack}
                            variant="outlined"
                            disabled={stepIndex === 0 && availabilityPanel !== 'add-closed-day'}
                            sx={{
                                borderRadius: '9px',
                                borderColor: '#d8dcd9',
                                color: `${settingsColors.text} !important`,
                                fontWeight: 700,
                                px: 1.5,
                                width: { xs: '100%', sm: 'auto' },
                            }}
                        >
                            Back
                        </Button>
                        <Button
                            onClick={onSaveAndContinue}
                            variant="contained"
                            disabled={saving}
                            sx={{
                                borderRadius: '9px',
                                bgcolor: `${settingsColors.green} !important`,
                                color: '#fff !important',
                                fontWeight: 700,
                                px: 1.8,
                                width: { xs: '100%', sm: 'auto' },
                                '&:hover': { bgcolor: `${settingsColors.greenDark} !important` },
                            }}
                        >
                            {wizardStep === 'availability' ? (availabilityPanel === 'add-closed-day' ? 'Save & Continue' : 'Save Changes') : 'Save & Continue'}
                        </Button>
                    </Stack>
                </Stack>
            </Paper>

            <Dialog open={openServiceDialog} onClose={() => setOpenServiceDialog(false)}>
                <DialogTitle>{serviceFormData.id ? 'Edit Service' : 'New Service'}</DialogTitle>
                <DialogContent>
                    <Box pt={1} display="flex" flexDirection="column" gap={2} minWidth={300}>
                        <TextField
                            label="Name"
                            fullWidth
                            value={serviceFormData.name}
                            onChange={(event) => setServiceFormData((prev) => ({ ...prev, name: event.target.value }))}
                        />
                        <TextField
                            label="Cost"
                            type="number"
                            fullWidth
                            value={serviceFormData.cost}
                            onChange={(event) => setServiceFormData((prev) => ({ ...prev, cost: parseFloat(event.target.value) }))}
                            InputProps={{ startAdornment: <InputAdornment position="start">$</InputAdornment> }}
                        />
                        <TextField
                            label="Duration (min)"
                            type="number"
                            fullWidth
                            value={serviceFormData.duration_minutes}
                            onChange={(event) => setServiceFormData((prev) => ({ ...prev, duration_minutes: parseInt(event.target.value, 10) }))}
                        />
                        <TextField
                            label="Description"
                            fullWidth
                            multiline
                            rows={2}
                            value={serviceFormData.description}
                            onChange={(event) => setServiceFormData((prev) => ({ ...prev, description: event.target.value }))}
                        />
                    </Box>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setOpenServiceDialog(false)}>Cancel</Button>
                    <Button variant="contained" onClick={handleServiceSubmit} disabled={!serviceFormData.name}>
                        Save
                    </Button>
                </DialogActions>
            </Dialog>

            <Dialog open={generateDataDialogOpen} onClose={() => setGenerateDataDialogOpen(false)}>
                <DialogTitle>Generate Sample Data</DialogTitle>
                <DialogContent>
                    <Typography>This will generate 30 days of sample data. Proceed?</Typography>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setGenerateDataDialogOpen(false)}>Cancel</Button>
                    <Button variant="contained" onClick={handleGenerateData}>Generate</Button>
                </DialogActions>
            </Dialog>

            <Dialog open={deleteServiceConfirmId !== null} onClose={() => setDeleteServiceConfirmId(null)}>
                <DialogTitle>Delete Service</DialogTitle>
                <DialogContent>
                    <Typography>Delete this service? This cannot be undone.</Typography>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setDeleteServiceConfirmId(null)}>Cancel</Button>
                    <Button variant="contained" color="error" onClick={confirmDeleteService}>
                        Delete
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
};

export default ShopSettingsPage;
