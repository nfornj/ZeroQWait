import React, { useState, useEffect, useCallback } from 'react';
import {
    Palette, Building2, Sparkles, CalendarDays,
    Upload, Check, Lightbulb, CircleCheck, Trash2,
    CalendarOff, Plus, Globe, Phone, Mail, AtSign,
    MessageCircle, MapPin, ChevronLeft,
} from 'lucide-react';
import api from '../../../services/api';
import { GradientPreset, gradientPresets, useThemeContext } from '../../../contexts/ThemeContext';
import { useShop } from '../../../contexts/ShopContext';
import { THEME_PRESETS, themePresetFromColors } from '../../../theme/presets';
import { Button } from '../../../components/ui/button';
import { Input } from '../../../components/ui/input';
import { Textarea } from '../../../components/ui/textarea';
import { Badge } from '../../../components/ui/badge';
import { Switch } from '../../../components/ui/switch';
import {
    Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../../../components/ui/select';
import {
    Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle,
} from '../../../components/ui/dialog';
import { cn } from '../../../lib/utils';

// ─── Constants ────────────────────────────────────────────────────────────────

const THEMES = THEME_PRESETS;

const GRADIENT_OPTIONS: { id: GradientPreset; name: string }[] = [
    { id: 'violet', name: 'Violet' },
    { id: 'ocean', name: 'Ocean' },
    { id: 'sunset', name: 'Sunset' },
    { id: 'minimal', name: 'Minimal' },
];

const STEPS = [
    { id: 'branding', icon: Palette, label: 'Branding', sub: 'Logo, colors & identity' },
    { id: 'business', icon: Building2, label: 'Business Info', sub: 'Shop details & contact' },
    { id: 'experience', icon: Sparkles, label: 'Experience', sub: 'Preferences & environment' },
    { id: 'availability', icon: CalendarDays, label: 'Availability', sub: 'Schedule & closed days' },
];

const BUSINESS_TYPES = [
    'Barber Shop', 'Hair Salon', 'Nail Salon', 'Spa & Wellness',
    'Medical Clinic', 'Dental Clinic', 'Auto Shop', 'Tattoo Studio',
    'Pet Grooming', 'Photography Studio', 'Other',
];

const TIMEZONES = [
    'America/New_York', 'America/Chicago', 'America/Denver', 'America/Los_Angeles',
    'America/Toronto', 'America/Vancouver', 'Europe/London', 'Europe/Paris',
    'Asia/Dubai', 'Pacific/Auckland',
];

const DAYS_OF_WEEK = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

const DESCRIPTION_MAX = 200;

const isGradientPreset = (value: unknown): value is GradientPreset =>
    GRADIENT_OPTIONS.some((option) => option.id === value);

interface ShopAIEnvironmentResponse {
    shop_id: number; subscription_tier: string; environment_name: string;
    environment_summary: string; operating_mode: string; status_label: string;
    uses_default: boolean; can_customize: boolean;
    capabilities: string[]; experience_notes: string[];
}

interface BusinessHour { day: string; isOpen: boolean; openTime: string; closeTime: string; }

type BookingPrefs = {
    bookingEnabled: boolean;
    requireConfirmation: boolean;
    allowRescheduling: boolean;
    allowCancellations: boolean;
    bookingNotice: string;
    reminderPreferences: string;
    reminderTime: string;
    followUp: boolean;
    waitingList: boolean;
    autoConfirm: boolean;
};

// ─── Sub-components ───────────────────────────────────────────────────────────

function FieldLabel({ children }: { children: React.ReactNode }) {
    return <p className="mb-1.5 text-sm font-medium text-[#374151]">{children}</p>;
}

// ─── Main Component ───────────────────────────────────────────────────────────

const ShopSettingsPage: React.FC = () => {
    const { themePreset, setThemePreset, dashboardGradient, setDashboardGradient } = useThemeContext();
    const { refreshOwnedShops } = useShop();
    const presetTheme = THEMES.find((t) => t.id === themePreset) || THEMES[0];

    const [shop, setShop] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [activeStep, setActiveStep] = useState('branding');
    const [saved, setSaved] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Branding
    const [logoFile, setLogoFile] = useState<File | null>(null);
    const [logoPreview, setLogoPreview] = useState('');
    const [formData, setFormData] = useState({
        name: '', description: '', phone: '', website: '',
        primary_color: presetTheme.primary, secondary_color: presetTheme.secondary,
        accent_color: '', background_color: '', logo_url: '', slug: '',
        dashboard_gradient: 'violet' as string,
        tagline: '', shop_type: '', tax_id: '',
        address: '', timezone: 'America/New_York',
        email: '', instagram: '', whatsapp: '',
    });

    // Services (kept for dialogs)
    const [services, setServices] = useState<any[]>([]);
    const [openServiceDialog, setOpenServiceDialog] = useState(false);
    const [serviceFormData, setServiceFormData] = useState({
        id: undefined as number | undefined,
        name: '', description: '', duration_minutes: 30, cost: 0.0,
    });
    const [generateDataDialogOpen, setGenerateDataDialogOpen] = useState(false);
    const [deleteServiceConfirmId, setDeleteServiceConfirmId] = useState<number | null>(null);

    // AI environment (kept for fetch)
    const [aiEnvironment, setAiEnvironment] = useState<ShopAIEnvironmentResponse | null>(null);

    // Booking preferences (Step 3)
    const [bookingPrefs, setBookingPrefs] = useState<BookingPrefs>({
        bookingEnabled: true,
        requireConfirmation: false,
        allowRescheduling: true,
        allowCancellations: true,
        bookingNotice: '24',
        reminderPreferences: 'email',
        reminderTime: '24',
        followUp: false,
        waitingList: false,
        autoConfirm: false,
    });

    // Business hours (Step 4)
    const [businessHours, setBusinessHours] = useState<BusinessHour[]>(
        DAYS_OF_WEEK.map((day) => ({
            day, isOpen: day !== 'Sunday', openTime: '09:00', closeTime: '18:00',
        })),
    );

    // Close days (Step 4)
    const [closeDays, setCloseDays] = useState<any[]>([]);
    const [closeDaysLoading, setCloseDaysLoading] = useState(false);
    const [addClosedDayView, setAddClosedDayView] = useState(false);
    const [closedDayName, setClosedDayName] = useState('');
    const [closedDayDate, setClosedDayDate] = useState('');
    const [closedDayRepeat, setClosedDayRepeat] = useState(false);
    const [closedDayNotes, setClosedDayNotes] = useState('');

    // ── Data fetching ────────────────────────────────────────────────────────

    const applyShopPayload = useCallback((s: any) => {
        setShop(s);
        setFormData({
            name: s.name ?? '', description: s.description ?? '',
            phone: s.phone ?? '', website: s.website ?? '',
            primary_color: s.primary_color || presetTheme.primary,
            secondary_color: s.secondary_color || presetTheme.secondary,
            accent_color: s.accent_color ?? '', background_color: s.background_color ?? '',
            logo_url: s.logo_url ?? '', slug: s.slug ?? '',
            dashboard_gradient: isGradientPreset(s.dashboard_gradient) ? s.dashboard_gradient : 'violet',
            tagline: s.tagline ?? '', shop_type: s.shop_type ?? '',
            tax_id: s.tax_id ?? '', address: s.address ?? '',
            timezone: s.timezone ?? 'America/New_York',
            email: s.email ?? '', instagram: s.instagram ?? '', whatsapp: s.whatsapp ?? '',
        });

        const persistedPreset = themePresetFromColors(s.primary_color, s.secondary_color);
        if (persistedPreset) setThemePreset(persistedPreset);
        setDashboardGradient(isGradientPreset(s.dashboard_gradient) ? s.dashboard_gradient : 'violet');
        if (s.logo_url) setLogoPreview(s.logo_url);
    }, [presetTheme.primary, presetTheme.secondary, setDashboardGradient, setThemePreset]);

    const fetchBusinessHours = async (shopId: number) => {
        try {
            const r = await api.get<BusinessHour[]>(`/shops/${shopId}/business-hours`);
            setBusinessHours(r.data);
        } catch {
            setError('Failed to load business hours');
        }
    };

    const fetchBookingSettings = async (shopId: number) => {
        try {
            const r = await api.get<BookingPrefs>(`/shops/${shopId}/booking-settings`);
            setBookingPrefs(r.data);
        } catch {
            setError('Failed to load booking preferences');
        }
    };

    const fetchShop = useCallback(async () => {
        try {
            const res = await api.get('/shops/my-shops');
            if (res.data.length > 0) {
                const s = res.data[0];
                applyShopPayload(s);
                fetchServices(s.id);
                fetchCloseDays(s.id);
                fetchLLMSettings(s.id);
                fetchBusinessHours(s.id);
                fetchBookingSettings(s.id);
            }
            setLoading(false);
        } catch { setError('Failed to load shop settings'); setLoading(false); }
    }, [applyShopPayload]);

    useEffect(() => { fetchShop(); }, [fetchShop]);

    const fetchServices = async (shopId: number) => {
        try { const r = await api.get(`/shops/${shopId}/services`); setServices(r.data); }
        catch { /* silent */ }
    };

    const fetchCloseDays = async (shopId: number) => {
        setCloseDaysLoading(true);
        try { const r = await api.get(`/shops/${shopId}/close-days`); setCloseDays(r.data); }
        catch { /* silent */ } finally { setCloseDaysLoading(false); }
    };

    const fetchLLMSettings = async (shopId: number) => {
        try { const r = await api.get<ShopAIEnvironmentResponse>(`/shops/${shopId}/llm-settings`); setAiEnvironment(r.data); }
        catch { /* silent */ }
    };

    // ── Handlers ─────────────────────────────────────────────────────────────

    const markUnsaved = () => setSaved(false);

    const updateField = (key: string, val: string) => {
        setFormData((p) => ({ ...p, [key]: val }));
        markUnsaved();
    };

    const updateBookingPref = (key: keyof BookingPrefs, val: boolean | string) => {
        setBookingPrefs((p) => ({ ...p, [key]: val }));
        markUnsaved();
    };

    const handleSave = async (skipReload = false) => {
        if (!shop) return;
        setSaving(true);
        setError(null);
        try {
            await api.put(`/shops/${shop.id}`, formData);
            await api.put(`/shops/${shop.id}/booking-settings`, bookingPrefs);
            await api.put(`/shops/${shop.id}/business-hours`, businessHours);
            if (logoFile) {
                const fd = new FormData();
                fd.append('file', logoFile);
                await api.put(`/shops/${shop.id}/logo`, fd);
            }
            const shopsRes = await api.get('/shops/my-shops');
            const refreshed = Array.isArray(shopsRes.data)
                ? shopsRes.data.find((item: any) => item.id === shop.id) || shopsRes.data[0]
                : null;
            if (refreshed) applyShopPayload(refreshed);
            await Promise.all([
                fetchBusinessHours(shop.id),
                fetchBookingSettings(shop.id),
                fetchCloseDays(shop.id),
                refreshOwnedShops(),
            ]);
            setSaved(true);
        } catch { setError('Failed to save settings'); }
        finally { setSaving(false); }
    };

    const confirmGenerateData = async () => {
        setGenerateDataDialogOpen(false);
        try {
            await api.post(`/shops/${shop.id}/generate-sample-data`, {});
            setSaved(false);
            setTimeout(() => window.location.reload(), 1500);
        } catch { setError('Failed to generate data'); }
    };

    const handleServiceSubmit = async () => {
        try {
            if (serviceFormData.id) {
                await api.put(`/shops/${shop.id}/services/${serviceFormData.id}`, serviceFormData);
            } else {
                await api.post(`/shops/${shop.id}/services`, serviceFormData);
            }
            setOpenServiceDialog(false);
            fetchServices(shop.id);
        } catch (e: any) { setError(e.response?.data?.detail || 'Failed to save service'); }
    };

    const confirmDeleteService = async () => {
        if (deleteServiceConfirmId === null) return;
        try {
            await api.delete(`/shops/${shop.id}/services/${deleteServiceConfirmId}`);
            setDeleteServiceConfirmId(null);
            fetchServices(shop.id);
        } catch { setError('Failed to delete service'); }
    };

    const addClosedDayFromForm = async () => {
        if (!closedDayDate) return;
        try {
            await api.post(`/shops/${shop.id}/close-days`, {
                date: closedDayDate,
                name: closedDayName || undefined,
                reason: closedDayName || closedDayNotes || undefined,
                notes: closedDayNotes || undefined,
                repeatYearly: closedDayRepeat,
            });
            setClosedDayDate('');
            setClosedDayName('');
            setClosedDayRepeat(false);
            setClosedDayNotes('');
            setAddClosedDayView(false);
            fetchCloseDays(shop.id);
        } catch { setError('Failed to add close day'); }
    };

    const deleteCloseDay = async (id: number) => {
        try { await api.delete(`/shops/${shop.id}/close-days/${id}`); fetchCloseDays(shop.id); }
        catch { setError('Failed to remove close day'); }
    };

    // ── Step navigation ───────────────────────────────────────────────────────

    const stepIds = STEPS.map((s) => s.id);
    const currentStepIndex = stepIds.indexOf(activeStep);
    const isFirstStep = currentStepIndex === 0;
    const isLastStep = currentStepIndex === stepIds.length - 1;

    const goBack = () => {
        if (activeStep === 'availability' && addClosedDayView) {
            setAddClosedDayView(false);
        } else if (!isFirstStep) {
            setActiveStep(stepIds[currentStepIndex - 1]);
        }
    };

    const goNext = async () => {
        await handleSave(true);
        if (!isLastStep) setActiveStep(stepIds[currentStepIndex + 1]);
    };

    // ── Loading / empty states ────────────────────────────────────────────────

    if (loading) {
        return (
            <div className="flex min-h-[400px] items-center justify-center">
                <div className="h-8 w-8 animate-spin rounded-full border-2 border-border border-t-primary" />
            </div>
        );
    }
    if (!shop) {
        return <p className="text-sm text-muted-foreground">No shop found.</p>;
    }

    const activeTheme = THEMES.find((t) => t.id === themePreset) || THEMES[0];

    // ── Render ────────────────────────────────────────────────────────────────
    return (
        <div
            className="flex min-h-full flex-col pb-24 bg-[#f9fafb]"
            style={{
                // Force light-mode design tokens + forest-green primary for the settings page
                '--background': '210 20% 98%',
                '--foreground': '222 47% 11%',
                '--card': '0 0% 100%',
                '--card-foreground': '222 47% 11%',
                '--popover': '0 0% 100%',
                '--popover-foreground': '222 47% 11%',
                '--muted': '210 40% 96%',
                '--muted-foreground': '215 16% 47%',
                '--border': '214 32% 91%',
                '--input': '214 32% 91%',
                '--primary': '154 40% 30%',         /* #2D6A4F dark forest green */
                '--primary-foreground': '0 0% 100%', /* white text on green */
                '--ring': '154 40% 30%',
            } as React.CSSProperties}
        >
            {/* ── Page title ── */}
            <div className="mb-6">
                <h1 className="text-3xl font-bold tracking-tight text-foreground">
                    Customize your workspace
                </h1>
                <p className="mt-1 text-sm text-muted-foreground">
                    Configure your shop settings, branding, and preferences.
                </p>
            </div>

            {error && (
                <div className="mb-4 flex items-center justify-between rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-2.5 text-sm text-red-400">
                    {error}
                    <button type="button" onClick={() => setError(null)} className="ml-4 text-xs hover:opacity-70">Dismiss</button>
                </div>
            )}

            {/* ── Step navigator ── */}
            <div className="mb-6 rounded-2xl border border-border bg-card p-1.5">
                <div className="grid grid-cols-4">
                    {STEPS.map((step, idx) => {
                        const isActive = step.id === activeStep;
                        const isDone = idx < currentStepIndex;
                        const Icon = step.icon;
                        return (
                            <button
                                key={step.id}
                                type="button"
                                onClick={() => setActiveStep(step.id)}
                                className={cn(
                                    'relative flex items-center gap-3 rounded-xl px-4 py-3.5 text-left transition-all',
                                    isActive ? 'bg-background shadow-sm' : 'hover:bg-muted/40',
                                )}
                            >
                                <div
                                    className={cn(
                                        'flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full text-sm font-semibold transition-colors',
                                        isActive
                                            ? 'bg-primary text-primary-foreground'
                                            : isDone
                                            ? 'bg-emerald-500/15 text-emerald-600'
                                            : 'border border-border bg-background text-muted-foreground',
                                    )}
                                >
                                    {isDone ? <CircleCheck className="h-4 w-4" /> : isActive ? <Icon className="h-4 w-4" /> : idx + 1}
                                </div>
                                <div className="min-w-0">
                                    <p className={cn(
                                        'truncate text-sm font-semibold',
                                        isActive ? 'text-foreground' : 'text-muted-foreground',
                                    )}>
                                        {step.label}
                                    </p>
                                    <p className="truncate text-xs text-muted-foreground">{step.sub}</p>
                                </div>
                                {isActive && (
                                    <span className="absolute bottom-0 left-4 right-4 h-0.5 rounded-full bg-primary" />
                                )}
                            </button>
                        );
                    })}
                </div>
            </div>

            {/* ══════════════════════════════════════════════════════════════
                STEP 1 — BRANDING
            ══════════════════════════════════════════════════════════════ */}
            {activeStep === 'branding' && (
                <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
                    {/* Left: Brand Identity */}
                    <div className="lg:col-span-3">
                        <div className="rounded-2xl border border-border bg-card p-6">
                            <h2 className="text-lg font-bold text-foreground">Brand Identity</h2>
                            <p className="mt-0.5 text-sm text-muted-foreground">
                                Set your logo and brand colors. These appear across your workspace and booking pages.
                            </p>

                            <div className="mt-6 grid grid-cols-1 gap-8 sm:grid-cols-2">
                                {/* Logo upload */}
                                <div>
                                    <FieldLabel>Logo</FieldLabel>
                                    <label
                                        className={cn(
                                            'flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-border bg-background p-8 transition-colors',
                                            'hover:border-primary hover:bg-muted/20',
                                        )}
                                    >
                                        {logoPreview ? (
                                            <img src={logoPreview} alt="Logo" className="h-16 w-16 rounded-xl object-cover" />
                                        ) : (
                                            <>
                                                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-muted">
                                                    <Upload className="h-5 w-5 text-muted-foreground" />
                                                </div>
                                                <span className="text-sm font-medium text-foreground">Upload your logo</span>
                                                <span className="text-xs text-muted-foreground">PNG, JPG or SVG · Max 2MB</span>
                                            </>
                                        )}
                                        <input
                                            type="file"
                                            accept="image/*"
                                            className="hidden"
                                            onChange={(e) => {
                                                const f = e.target.files?.[0];
                                                if (f) { setLogoFile(f); setLogoPreview(URL.createObjectURL(f)); markUnsaved(); }
                                            }}
                                        />
                                    </label>
                                </div>

                                {/* Color swatches */}
                                <div>
                                    <FieldLabel>Brand Colors</FieldLabel>
                                    <p className="mb-3 text-xs text-muted-foreground">Choose a theme that represents your brand.</p>
                                    <div className="flex flex-wrap gap-3">
                                        {THEMES.map((theme) => {
                                            const isSelected = themePreset === theme.id;
                                            return (
                                                <button
                                                    key={theme.id}
                                                    type="button"
                                                    onClick={() => {
                                                        setThemePreset(theme.id);
                                                        setFormData((p) => ({
                                                            ...p,
                                                            primary_color: theme.primary,
                                                            secondary_color: theme.secondary,
                                                        }));
                                                        markUnsaved();
                                                    }}
                                                    className="flex flex-col items-center gap-1.5"
                                                >
                                                    <div
                                                        className={cn(
                                                            'relative h-12 w-12 rounded-xl transition-all',
                                                            isSelected
                                                                ? 'ring-2 ring-offset-2 ring-foreground scale-105'
                                                                : 'hover:scale-105',
                                                        )}
                                                        style={{ backgroundColor: theme.primary }}
                                                    >
                                                        {isSelected && (
                                                            <div className="absolute inset-0 flex items-center justify-center rounded-xl bg-black/20">
                                                                <Check className="h-5 w-5 text-white drop-shadow" />
                                                            </div>
                                                        )}
                                                    </div>
                                                    <span className={cn(
                                                        'text-[11px]',
                                                        isSelected ? 'font-semibold text-foreground' : 'text-muted-foreground',
                                                    )}>
                                                        {theme.name}
                                                    </span>
                                                </button>
                                            );
                                        })}
                                    </div>
                                </div>
                            </div>

                            <div className="mt-6">
                                <FieldLabel>Dashboard Background</FieldLabel>
                                <p className="mb-3 text-xs text-muted-foreground">Choose the background your workspace and display pages use.</p>
                                <div className="flex flex-wrap gap-3">
                                    {GRADIENT_OPTIONS.map((preset) => {
                                        const selectedGradient = isGradientPreset(formData.dashboard_gradient)
                                            ? formData.dashboard_gradient
                                            : dashboardGradient;
                                        const isSelected = selectedGradient === preset.id;
                                        const preview = gradientPresets[preset.id].light === 'none'
                                            ? '#f9fafb'
                                            : gradientPresets[preset.id].light;

                                        return (
                                            <button
                                                key={preset.id}
                                                type="button"
                                                onClick={() => {
                                                    setDashboardGradient(preset.id);
                                                    setFormData((p) => ({ ...p, dashboard_gradient: preset.id }));
                                                    markUnsaved();
                                                }}
                                                className="flex flex-col items-center gap-1.5"
                                            >
                                                <div
                                                    className={cn(
                                                        'relative h-12 w-20 rounded-xl border border-border transition-all',
                                                        isSelected ? 'ring-2 ring-offset-2 ring-foreground scale-105' : 'hover:scale-105',
                                                    )}
                                                    style={{ background: preview }}
                                                >
                                                    {isSelected && (
                                                        <div className="absolute inset-0 flex items-center justify-center rounded-xl bg-black/15">
                                                            <Check className="h-5 w-5 text-white drop-shadow" />
                                                        </div>
                                                    )}
                                                </div>
                                                <span className={cn(
                                                    'text-[11px]',
                                                    isSelected ? 'font-semibold text-foreground' : 'text-muted-foreground',
                                                )}>
                                                    {preset.name}
                                                </span>
                                            </button>
                                        );
                                    })}
                                </div>
                            </div>

                            {/* Live Preview */}
                            <div className="mt-6">
                                <FieldLabel>Live Preview</FieldLabel>
                                <div
                                    className="overflow-hidden rounded-xl border border-border bg-gradient-to-br from-background to-muted/40 p-5"
                                    style={{ borderLeftColor: activeTheme.primary, borderLeftWidth: 3 }}
                                >
                                    <div className="flex items-center gap-4">
                                        {logoPreview ? (
                                            <img src={logoPreview} alt="Logo" className="h-14 w-14 flex-shrink-0 rounded-xl object-cover" />
                                        ) : (
                                            <div
                                                className="flex h-14 w-14 flex-shrink-0 items-center justify-center rounded-xl"
                                                style={{ backgroundColor: activeTheme.primary }}
                                            >
                                                <span className="text-xl font-bold text-white">
                                                    {formData.name.charAt(0) || 'S'}
                                                </span>
                                            </div>
                                        )}
                                        <div className="flex-1 min-w-0">
                                            <p className="text-base font-bold text-foreground truncate">
                                                {formData.name || shop.name}
                                            </p>
                                            {(formData.description || formData.tagline) && (
                                                <p className="mt-0.5 text-sm text-muted-foreground line-clamp-1">
                                                    {formData.tagline || formData.description}
                                                </p>
                                            )}
                                            {formData.shop_type && (
                                                <Badge variant="outline" className="mt-1.5 text-xs">{formData.shop_type}</Badge>
                                            )}
                                        </div>
                                        <div
                                            className="ml-auto h-3 w-3 flex-shrink-0 rounded-full"
                                            style={{ backgroundColor: activeTheme.primary }}
                                        />
                                    </div>
                                </div>
                            </div>

                            <div className="mt-4 flex items-start gap-2.5 rounded-xl bg-muted/40 px-4 py-3">
                                <Lightbulb className="mt-0.5 h-4 w-4 flex-shrink-0 text-amber-500" />
                                <p className="text-sm text-muted-foreground">
                                    Tip: A strong brand helps build trust and makes your shop memorable.
                                </p>
                            </div>
                        </div>
                    </div>

                    {/* Right: Business Details (quick fields) */}
                    <div className="lg:col-span-2">
                        <div className="rounded-2xl border border-border bg-card p-6">
                            <h2 className="text-lg font-bold text-foreground">Quick Details</h2>
                            <p className="mt-0.5 text-sm text-muted-foreground">Basic information about your shop.</p>

                            <div className="mt-5 flex flex-col gap-4">
                                <div>
                                    <FieldLabel>Shop Name</FieldLabel>
                                    <Input
                                        value={formData.name}
                                        onChange={(e) => updateField('name', e.target.value)}
                                        className="border-border bg-background"
                                        placeholder="Your shop name"
                                    />
                                </div>

                                <div>
                                    <FieldLabel>Tagline</FieldLabel>
                                    <Input
                                        value={formData.tagline}
                                        onChange={(e) => updateField('tagline', e.target.value)}
                                        className="border-border bg-background"
                                        placeholder="A short, memorable phrase"
                                    />
                                </div>

                                <div>
                                    <FieldLabel>Description</FieldLabel>
                                    <Textarea
                                        rows={3}
                                        maxLength={DESCRIPTION_MAX}
                                        value={formData.description}
                                        onChange={(e) => updateField('description', e.target.value)}
                                        className="resize-none border-border bg-background"
                                        placeholder="Describe your shop and services..."
                                    />
                                    <div className="mt-1 flex justify-end">
                                        <span className="text-xs text-muted-foreground">
                                            {formData.description.length}/{DESCRIPTION_MAX}
                                        </span>
                                    </div>
                                </div>
                            </div>

                            <div className="mt-5 rounded-xl border border-border bg-muted/30 p-4">
                                <div className="flex items-start gap-3">
                                    <Sparkles className="mt-0.5 h-5 w-5 flex-shrink-0 text-primary" />
                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm font-semibold text-foreground">Need help writing?</p>
                                        <p className="mt-0.5 text-xs text-muted-foreground">
                                            Generate a description with AI based on your services.
                                        </p>
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            className="mt-3 border-border text-foreground"
                                            onClick={() => setGenerateDataDialogOpen(true)}
                                        >
                                            Generate with AI
                                        </Button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* ══════════════════════════════════════════════════════════════
                STEP 2 — BUSINESS INFO
            ══════════════════════════════════════════════════════════════ */}
            {activeStep === 'business' && (
                <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
                    {/* Left: Full business form */}
                    <div className="lg:col-span-3 rounded-2xl border border-border bg-card p-6">
                        <h2 className="text-lg font-bold text-foreground">Business Information</h2>
                        <p className="mt-0.5 mb-6 text-sm text-muted-foreground">
                            This information appears on your public profile and booking page.
                        </p>

                        <div className="flex flex-col gap-5">
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <FieldLabel>Shop Name</FieldLabel>
                                    <Input value={formData.name} onChange={(e) => updateField('name', e.target.value)} placeholder="Your shop name" className="border-border bg-background" />
                                </div>
                                <div>
                                    <FieldLabel>Tagline</FieldLabel>
                                    <Input value={formData.tagline} onChange={(e) => updateField('tagline', e.target.value)} placeholder="A short phrase..." className="border-border bg-background" />
                                </div>
                            </div>

                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <FieldLabel>Business Type</FieldLabel>
                                    <Select value={formData.shop_type || ''} onValueChange={(v) => updateField('shop_type', v)}>
                                        <SelectTrigger className="border-border bg-background">
                                            <SelectValue placeholder="Select type..." />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {BUSINESS_TYPES.map((t) => (
                                                <SelectItem key={t} value={t}>{t}</SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                                <div>
                                    <FieldLabel>Tax ID</FieldLabel>
                                    <Input value={formData.tax_id} onChange={(e) => updateField('tax_id', e.target.value)} placeholder="Optional" className="border-border bg-background" />
                                </div>
                            </div>

                            <div>
                                <FieldLabel>Address</FieldLabel>
                                <Input value={formData.address} onChange={(e) => updateField('address', e.target.value)} placeholder="123 Main St, City, State" className="border-border bg-background" />
                            </div>

                            <div>
                                <FieldLabel>Timezone</FieldLabel>
                                <Select value={formData.timezone || 'America/New_York'} onValueChange={(v) => updateField('timezone', v)}>
                                    <SelectTrigger className="border-border bg-background">
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {TIMEZONES.map((tz) => (
                                            <SelectItem key={tz} value={tz}>{tz.replace(/_/g, ' ')}</SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>

                            {/* Contact Info */}
                            <div>
                                <p className="mb-3 text-sm font-semibold text-foreground">Contact Information</p>
                                <div className="flex flex-col gap-3">
                                    <div className="flex items-center gap-3">
                                        <Phone className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
                                        <Input value={formData.phone} onChange={(e) => updateField('phone', e.target.value)} placeholder="Phone number" className="border-border bg-background" />
                                    </div>
                                    <div className="flex items-center gap-3">
                                        <Mail className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
                                        <Input type="email" value={formData.email} onChange={(e) => updateField('email', e.target.value)} placeholder="Email address" className="border-border bg-background" />
                                    </div>
                                    <div className="flex items-center gap-3">
                                        <Globe className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
                                        <Input value={formData.website} onChange={(e) => updateField('website', e.target.value)} placeholder="https://yoursite.com" className="border-border bg-background" />
                                    </div>
                                    <div className="flex items-center gap-3">
                                        <AtSign className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
                                        <Input value={formData.instagram} onChange={(e) => updateField('instagram', e.target.value)} placeholder="@yourhandle (Instagram)" className="border-border bg-background" />
                                    </div>
                                    <div className="flex items-center gap-3">
                                        <MessageCircle className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
                                        <Input value={formData.whatsapp} onChange={(e) => updateField('whatsapp', e.target.value)} placeholder="WhatsApp number" className="border-border bg-background" />
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Right: Live preview */}
                    <div className="lg:col-span-2">
                        <div className="sticky top-4 rounded-2xl border border-border bg-card p-6">
                            <div className="mb-4 flex items-center justify-between">
                                <h3 className="text-sm font-semibold text-foreground">Your Business Preview</h3>
                                <button
                                    type="button"
                                    onClick={() => setActiveStep('branding')}
                                    className="text-xs text-primary hover:underline"
                                >
                                    Edit Branding
                                </button>
                            </div>

                            <div className="overflow-hidden rounded-xl border border-border">
                                <div
                                    className="h-20"
                                    style={{ background: `linear-gradient(135deg, ${activeTheme.primary}33, ${activeTheme.secondary}22)` }}
                                />
                                <div className="px-4 pb-5 -mt-8">
                                    <div
                                        className="flex h-16 w-16 items-center justify-center rounded-2xl border-4 border-card shadow-sm"
                                        style={{ backgroundColor: activeTheme.primary }}
                                    >
                                        {logoPreview ? (
                                            <img src={logoPreview} alt="Logo" className="h-full w-full rounded-xl object-cover" />
                                        ) : (
                                            <span className="text-2xl font-bold text-white">
                                                {(formData.name || shop.name).charAt(0)}
                                            </span>
                                        )}
                                    </div>
                                    <div className="mt-2">
                                        <p className="text-base font-bold text-foreground">{formData.name || shop.name}</p>
                                        {formData.tagline && (
                                            <p className="text-xs text-muted-foreground mt-0.5">{formData.tagline}</p>
                                        )}
                                        {formData.shop_type && (
                                            <Badge variant="outline" className="mt-2 text-xs">{formData.shop_type}</Badge>
                                        )}
                                    </div>
                                    <div className="mt-4 flex flex-col gap-2">
                                        {formData.address && (
                                            <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                                <MapPin className="h-3.5 w-3.5 flex-shrink-0" />
                                                <span className="truncate">{formData.address}</span>
                                            </div>
                                        )}
                                        {formData.phone && (
                                            <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                                <Phone className="h-3.5 w-3.5 flex-shrink-0" />
                                                <span>{formData.phone}</span>
                                            </div>
                                        )}
                                        {formData.website && (
                                            <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                                <Globe className="h-3.5 w-3.5 flex-shrink-0" />
                                                <span className="truncate">{formData.website}</span>
                                            </div>
                                        )}
                                        {formData.email && (
                                            <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                                <Mail className="h-3.5 w-3.5 flex-shrink-0" />
                                                <span className="truncate">{formData.email}</span>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* ══════════════════════════════════════════════════════════════
                STEP 3 — EXPERIENCE (Booking Preferences)
            ══════════════════════════════════════════════════════════════ */}
            {activeStep === 'experience' && (
                <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
                    {/* Left: Preference controls */}
                    <div className="lg:col-span-3 rounded-2xl border border-border bg-card p-6">
                        <h2 className="text-lg font-bold text-foreground">Client Experience</h2>
                        <p className="mt-0.5 mb-6 text-sm text-muted-foreground">
                            Configure how clients interact with your booking system.
                        </p>

                        {/* Core booking toggles */}
                        <div className="flex flex-col gap-3">
                            {[
                                { key: 'bookingEnabled', label: 'Booking Enabled', desc: 'Allow clients to book appointments online' },
                                { key: 'requireConfirmation', label: 'Require Confirmation', desc: 'Manually approve each booking request' },
                                { key: 'allowRescheduling', label: 'Allow Rescheduling', desc: 'Clients can reschedule their appointments' },
                                { key: 'allowCancellations', label: 'Allow Cancellations', desc: 'Clients can cancel their bookings' },
                            ].map(({ key, label, desc }) => (
                                <div key={key} className="flex items-center justify-between rounded-xl border border-border px-4 py-3.5">
                                    <div>
                                        <p className="text-sm font-medium text-foreground">{label}</p>
                                        <p className="text-xs text-muted-foreground">{desc}</p>
                                    </div>
                                    <Switch
                                        aria-label={label}
                                        checked={bookingPrefs[key as keyof typeof bookingPrefs] as boolean}
                                        onCheckedChange={(checked) => updateBookingPref(key as keyof BookingPrefs, checked)}
                                    />
                                </div>
                            ))}
                        </div>

                        {/* Booking Notice */}
                        <div className="mt-5">
                            <FieldLabel>Booking Notice</FieldLabel>
                            <Select value={bookingPrefs.bookingNotice} onValueChange={(v) => updateBookingPref('bookingNotice', v)}>
                                <SelectTrigger className="border-border bg-background">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="1">1 hour before</SelectItem>
                                    <SelectItem value="2">2 hours before</SelectItem>
                                    <SelectItem value="24">24 hours before</SelectItem>
                                    <SelectItem value="48">48 hours before</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>

                        {/* Client Communication */}
                        <div className="mt-6">
                            <p className="mb-4 text-sm font-semibold text-foreground">Client Communication</p>
                            <div className="flex flex-col gap-4">
                                <div>
                                    <FieldLabel>Reminder Preferences</FieldLabel>
                                    <Select value={bookingPrefs.reminderPreferences} onValueChange={(v) => updateBookingPref('reminderPreferences', v)}>
                                        <SelectTrigger className="border-border bg-background">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="email">Email</SelectItem>
                                            <SelectItem value="sms">SMS</SelectItem>
                                            <SelectItem value="both">Both</SelectItem>
                                            <SelectItem value="none">None</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>
                                <div>
                                    <FieldLabel>Reminder Time</FieldLabel>
                                    <Select value={bookingPrefs.reminderTime} onValueChange={(v) => updateBookingPref('reminderTime', v)}>
                                        <SelectTrigger className="border-border bg-background">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="1">1 hour before</SelectItem>
                                            <SelectItem value="24">24 hours before</SelectItem>
                                            <SelectItem value="48">48 hours before</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>
                                <div className="flex items-center justify-between rounded-xl border border-border px-4 py-3.5">
                                    <div>
                                        <p className="text-sm font-medium text-foreground">Follow Up</p>
                                        <p className="text-xs text-muted-foreground">Send follow-up messages after appointments</p>
                                    </div>
                                    <Switch
                                        checked={bookingPrefs.followUp}
                                        onCheckedChange={(checked) => updateBookingPref('followUp', checked)}
                                    />
                                </div>
                            </div>
                        </div>

                        {/* Additional Preferences */}
                        <div className="mt-6">
                            <p className="mb-4 text-sm font-semibold text-foreground">Additional Preferences</p>
                            <div className="flex flex-col gap-3">
                                {[
                                    { key: 'waitingList', label: 'Waiting List', desc: 'Allow clients to join a waiting list when fully booked' },
                                    { key: 'autoConfirm', label: 'Auto Confirm', desc: 'Automatically confirm bookings without manual review' },
                                ].map(({ key, label, desc }) => (
                                    <div key={key} className="flex items-center justify-between rounded-xl border border-border px-4 py-3.5">
                                        <div>
                                            <p className="text-sm font-medium text-foreground">{label}</p>
                                            <p className="text-xs text-muted-foreground">{desc}</p>
                                        </div>
                                        <Switch
                                            checked={bookingPrefs[key as keyof typeof bookingPrefs] as boolean}
                                            onCheckedChange={(checked) => updateBookingPref(key as keyof BookingPrefs, checked)}
                                        />
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>

                    {/* Right: Booking widget preview */}
                    <div className="lg:col-span-2">
                        <div className="sticky top-4 rounded-2xl border border-border bg-card p-6">
                            <h3 className="mb-4 text-sm font-semibold text-foreground">Preview</h3>
                            <div className="overflow-hidden rounded-xl border border-border bg-background">
                                <div
                                    className="px-4 py-3 border-b border-border"
                                    style={{ backgroundColor: `${activeTheme.primary}12` }}
                                >
                                    <p className="text-xs font-semibold text-foreground">{formData.name || shop.name}</p>
                                    <p className="text-xs text-muted-foreground">Book an appointment</p>
                                </div>
                                <div className="p-4">
                                    {[
                                        { step: 1, label: 'Choose Service', active: true },
                                        { step: 2, label: 'Select Date & Time', active: false },
                                        { step: 3, label: 'Your Details', active: false },
                                        { step: 4, label: 'Confirmation', active: false },
                                    ].map(({ step, label, active }) => (
                                        <div
                                            key={step}
                                            className={cn(
                                                'flex items-center gap-3 py-2 px-2 rounded-lg mb-0.5',
                                                active && 'bg-muted/50',
                                            )}
                                        >
                                            <div
                                                className={cn(
                                                    'h-6 w-6 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0',
                                                    !active && 'bg-muted text-muted-foreground',
                                                )}
                                                style={active ? { backgroundColor: activeTheme.primary, color: '#fff' } : {}}
                                            >
                                                {step}
                                            </div>
                                            <span className={cn(
                                                'text-sm',
                                                active ? 'font-semibold text-foreground' : 'text-muted-foreground',
                                            )}>
                                                {label}
                                            </span>
                                        </div>
                                    ))}

                                    <div className="mt-3 flex flex-col gap-1.5">
                                        {(services.slice(0, 2).length > 0 ? services.slice(0, 2) : [
                                            { name: 'Classic Service', duration_minutes: 30, cost: 25 },
                                            { name: 'Premium Service', duration_minutes: 60, cost: 55 },
                                        ]).map((svc, idx) => (
                                            <div key={idx} className="flex items-center justify-between rounded-lg border border-border px-3 py-2">
                                                <div>
                                                    <p className="text-xs font-medium text-foreground">{svc.name}</p>
                                                    <p className="text-xs text-muted-foreground">{svc.duration_minutes} min</p>
                                                </div>
                                                <p className="text-xs font-semibold" style={{ color: activeTheme.primary }}>
                                                    ${Number(svc.cost).toFixed(0)}
                                                </p>
                                            </div>
                                        ))}
                                    </div>

                                    <button
                                        type="button"
                                        className="mt-3 w-full rounded-lg py-2 text-xs font-semibold text-white transition-opacity hover:opacity-90"
                                        style={{ backgroundColor: bookingPrefs.bookingEnabled ? activeTheme.primary : '#6b7280' }}
                                    >
                                        {bookingPrefs.bookingEnabled ? 'Book Now' : 'Booking Unavailable'}
                                    </button>
                                </div>
                            </div>

                            <div className="mt-4 flex flex-col gap-1.5">
                                {[
                                    { label: 'Confirmation required', on: bookingPrefs.requireConfirmation },
                                    { label: 'Cancellations allowed', on: bookingPrefs.allowCancellations },
                                    { label: 'Rescheduling allowed', on: bookingPrefs.allowRescheduling },
                                    { label: 'Waiting list active', on: bookingPrefs.waitingList },
                                ].map(({ label, on }) => (
                                    <div key={label} className="flex items-center gap-2 text-xs">
                                        <div className={cn(
                                            'h-2 w-2 rounded-full flex-shrink-0',
                                            on ? 'bg-emerald-500' : 'bg-muted-foreground/30',
                                        )} />
                                        <span className={on ? 'text-foreground' : 'text-muted-foreground'}>{label}</span>
                                    </div>
                                ))}
                            </div>

                            {aiEnvironment && (
                                <div className="mt-4 rounded-xl border border-border bg-muted/20 p-3">
                                    <p className="text-xs font-semibold text-foreground mb-0.5">{aiEnvironment.environment_name}</p>
                                    <p className="text-xs text-muted-foreground">{aiEnvironment.status_label}</p>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {/* ══════════════════════════════════════════════════════════════
                STEP 4 — AVAILABILITY
            ══════════════════════════════════════════════════════════════ */}
            {activeStep === 'availability' && !addClosedDayView && (
                <div className="flex flex-col gap-6">
                    {/* Business Hours table */}
                    <div className="rounded-2xl border border-border bg-card p-6">
                        <h2 className="mb-0.5 text-lg font-bold text-foreground">Business Hours</h2>
                        <p className="mb-5 text-sm text-muted-foreground">Set your regular operating hours for each day of the week.</p>

                        <div className="overflow-hidden rounded-xl border border-border">
                            <table className="w-full">
                                <thead>
                                    <tr className="border-b border-border bg-muted/30">
                                        <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground w-28">Day</th>
                                        <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground">Open Time</th>
                                        <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground">Close Time</th>
                                        <th className="px-4 py-3 text-center text-xs font-semibold text-muted-foreground w-20">Open</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-border">
                                    {businessHours.map((bh, idx) => (
                                        <tr
                                            key={bh.day}
                                            className={cn('transition-colors', !bh.isOpen && 'opacity-50')}
                                        >
                                            <td className="px-4 py-3 text-sm font-medium text-foreground">
                                                {bh.day.slice(0, 3)}
                                            </td>
                                            <td className="px-4 py-3">
                                                <Input
                                                    type="time"
                                                    value={bh.openTime}
                                                    disabled={!bh.isOpen}
                                                    onChange={(e) => {
                                                        const next = [...businessHours];
                                                        next[idx] = { ...next[idx], openTime: e.target.value };
                                                        setBusinessHours(next);
                                                        markUnsaved();
                                                    }}
                                                    className="h-8 w-32 border-border bg-background text-sm"
                                                />
                                            </td>
                                            <td className="px-4 py-3">
                                                <Input
                                                    type="time"
                                                    value={bh.closeTime}
                                                    disabled={!bh.isOpen}
                                                    onChange={(e) => {
                                                        const next = [...businessHours];
                                                        next[idx] = { ...next[idx], closeTime: e.target.value };
                                                        setBusinessHours(next);
                                                        markUnsaved();
                                                    }}
                                                    className="h-8 w-32 border-border bg-background text-sm"
                                                />
                                            </td>
                                            <td className="px-4 py-3 text-center">
                                                <Switch
                                                    checked={bh.isOpen}
                                                    onCheckedChange={(checked) => {
                                                        const next = [...businessHours];
                                                        next[idx] = { ...next[idx], isOpen: checked };
                                                        setBusinessHours(next);
                                                        markUnsaved();
                                                    }}
                                                />
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>

                    {/* Closed Days & Holidays */}
                    <div className="rounded-2xl border border-border bg-card p-6">
                        <div className="mb-5 flex items-center justify-between">
                            <div>
                                <h2 className="text-lg font-bold text-foreground">Closed Days & Holidays</h2>
                                <p className="mt-0.5 text-sm text-muted-foreground">Manage specific days your shop will be closed.</p>
                            </div>
                            <Button size="sm" className="gap-2" onClick={() => setAddClosedDayView(true)}>
                                <Plus className="h-4 w-4" /> Add Closed Day
                            </Button>
                        </div>

                        {closeDaysLoading ? (
                            <div className="flex justify-center py-8">
                                <div className="h-6 w-6 animate-spin rounded-full border-2 border-border border-t-primary" />
                            </div>
                        ) : closeDays.length === 0 ? (
                            <div className="flex flex-col items-center gap-2 rounded-xl border-2 border-dashed border-border py-10 text-center">
                                <CalendarOff className="h-8 w-8 text-muted-foreground/40" />
                                <p className="text-sm text-muted-foreground">No closed days scheduled yet.</p>
                                <button
                                    type="button"
                                    onClick={() => setAddClosedDayView(true)}
                                    className="text-xs text-primary hover:underline"
                                >
                                    Add your first closed day
                                </button>
                            </div>
                        ) : (
                            <div className="overflow-hidden rounded-xl border border-border divide-y divide-border">
                                {closeDays.map((day) => (
                                    <div key={day.id} className="flex items-center justify-between px-4 py-3 hover:bg-muted/20 transition-colors">
                                        <div className="flex items-center gap-3">
                                            <CalendarOff className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
                                            <div>
                                                <p className="text-sm font-medium text-foreground">
                                                    {day.name || day.reason || new Date(day.date).toLocaleDateString(undefined, { month: 'long', day: 'numeric' })}
                                                </p>
                                                <p className="text-xs text-muted-foreground">
                                                    {new Date(day.date).toLocaleDateString(undefined, {
                                                        weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
                                                    })}
                                                </p>
                                                {(day.notes || day.repeatYearly) && (
                                                    <p className="text-xs text-muted-foreground">
                                                        {day.notes || 'Repeats every year'}{day.notes && day.repeatYearly ? ' · Repeats every year' : ''}
                                                    </p>
                                                )}
                                            </div>
                                        </div>
                                        <button
                                            type="button"
                                            onClick={() => deleteCloseDay(day.id)}
                                            className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground hover:bg-red-500/10 hover:text-red-400 transition-colors"
                                        >
                                            <Trash2 className="h-3.5 w-3.5" />
                                        </button>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* Add Closed Day sub-view */}
            {activeStep === 'availability' && addClosedDayView && (
                <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
                    <div className="lg:col-span-3 rounded-2xl border border-border bg-card p-6">
                        <div className="mb-5 flex items-center gap-3">
                            <button
                                type="button"
                                onClick={() => {
                                    setAddClosedDayView(false);
                                    setClosedDayName('');
                                    setClosedDayDate('');
                                    setClosedDayRepeat(false);
                                    setClosedDayNotes('');
                                }}
                                className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground hover:bg-muted transition-colors"
                            >
                                <ChevronLeft className="h-4 w-4" />
                            </button>
                            <div>
                                <h2 className="text-lg font-bold text-foreground">Add Closed Day</h2>
                                <p className="text-sm text-muted-foreground">Mark a specific day as closed for your shop.</p>
                            </div>
                        </div>

                        <div className="flex flex-col gap-5">
                            <div>
                                <FieldLabel>Name</FieldLabel>
                                <Input
                                    value={closedDayName}
                                    onChange={(e) => setClosedDayName(e.target.value)}
                                    placeholder="e.g. Christmas, Renovation Day"
                                    className="border-border bg-background"
                                />
                            </div>
                            <div>
                                <FieldLabel>Date</FieldLabel>
                                <Input
                                    type="date"
                                    value={closedDayDate}
                                    onChange={(e) => setClosedDayDate(e.target.value)}
                                    className="border-border bg-background"
                                />
                            </div>
                            <div className="flex items-center justify-between rounded-xl border border-border px-4 py-3.5">
                                <div>
                                    <p className="text-sm font-medium text-foreground">Repeat Yearly</p>
                                    <p className="text-xs text-muted-foreground">Auto-mark this day closed every year</p>
                                </div>
                                <Switch
                                    aria-label="Repeat Yearly"
                                    checked={closedDayRepeat}
                                    onCheckedChange={setClosedDayRepeat}
                                />
                            </div>
                            <div>
                                <FieldLabel>Notes (Optional)</FieldLabel>
                                <Textarea
                                    rows={3}
                                    value={closedDayNotes}
                                    onChange={(e) => setClosedDayNotes(e.target.value)}
                                    placeholder="Add any additional notes..."
                                    className="resize-none border-border bg-background"
                                />
                            </div>
                            <Button
                                type="button"
                                className="w-full gap-2"
                                disabled={!closedDayDate}
                                onClick={addClosedDayFromForm}
                            >
                                <CalendarOff className="h-4 w-4" />
                                Mark as Closed
                            </Button>
                        </div>
                    </div>

                    <div className="lg:col-span-2">
                        <div className="rounded-2xl border border-border bg-card p-6">
                            <h3 className="mb-4 text-sm font-semibold text-foreground">Upcoming Closed Days</h3>
                            {closeDaysLoading ? (
                                <div className="flex justify-center py-6">
                                    <div className="h-6 w-6 animate-spin rounded-full border-2 border-border border-t-primary" />
                                </div>
                            ) : closeDays.length === 0 ? (
                                <p className="text-sm text-center text-muted-foreground py-6">No closed days yet.</p>
                            ) : (
                                <div className="flex flex-col gap-2">
                                    {closeDays.slice(0, 6).map((day) => (
                                        <div key={day.id} className="rounded-xl border border-border px-3 py-2.5">
                                            <p className="text-xs font-medium text-foreground">
                                                {day.name || day.reason || 'Closed Day'}
                                            </p>
                                            <p className="text-xs text-muted-foreground">
                                                {new Date(day.date).toLocaleDateString(undefined, {
                                                    month: 'short', day: 'numeric', year: 'numeric',
                                                })}
                                            </p>
                                            {day.repeatYearly && <p className="text-xs text-muted-foreground">Repeats yearly</p>}
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {/* ── Step footer ── */}
            <div
                className="fixed bottom-0 left-0 right-0 z-30 border-t backdrop-blur"
                style={{
                    borderColor: '#e5e7eb',
                    backgroundColor: 'rgba(249,250,251,0.92)',
                }}
            >
                <div className="mx-auto flex max-w-[1700px] items-center justify-between px-8 py-4">
                    <div className="flex items-center gap-2 text-sm">
                        {saved ? (
                            <>
                                <CircleCheck className="h-4 w-4 text-emerald-500" />
                                <span className="text-[#6b7280]">All changes saved</span>
                            </>
                        ) : (
                            <span className="text-amber-500 text-xs">Unsaved changes</span>
                        )}
                    </div>
                    <div className="flex items-center gap-3">
                        {activeStep === 'branding' && (
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => setGenerateDataDialogOpen(true)}
                                className="border-amber-500/60 text-amber-600 hover:bg-amber-50 dark:hover:bg-amber-500/10"
                            >
                                Generate Sample Data
                            </Button>
                        )}
                        {(!isFirstStep || (activeStep === 'availability' && addClosedDayView)) && (
                            <Button variant="outline" onClick={goBack}>
                                Back
                            </Button>
                        )}
                        <Button
                            onClick={isLastStep ? () => handleSave(false) : goNext}
                            disabled={saving}
                            className="bg-primary px-6 text-primary-foreground hover:bg-primary/90"
                        >
                            {saving ? 'Saving...' : isLastStep ? 'Save Settings' : 'Save & Continue'}
                        </Button>
                    </div>
                </div>
            </div>

            {/* ── Dialogs ── */}
            <Dialog open={openServiceDialog} onOpenChange={(o) => { if (!o) setOpenServiceDialog(false); }}>
                <DialogContent className="sm:max-w-md">
                    <DialogHeader>
                        <DialogTitle>{serviceFormData.id ? 'Edit Service' : 'New Service'}</DialogTitle>
                    </DialogHeader>
                    <div className="flex flex-col gap-4 py-2">
                        <div>
                            <FieldLabel>Name</FieldLabel>
                            <Input value={serviceFormData.name} onChange={(e) => setServiceFormData({ ...serviceFormData, name: e.target.value })} className="border-border bg-background" />
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <FieldLabel>Cost ($)</FieldLabel>
                                <Input type="number" value={serviceFormData.cost} onChange={(e) => setServiceFormData({ ...serviceFormData, cost: parseFloat(e.target.value) })} className="border-border bg-background" />
                            </div>
                            <div>
                                <FieldLabel>Duration (min)</FieldLabel>
                                <Input type="number" value={serviceFormData.duration_minutes} onChange={(e) => setServiceFormData({ ...serviceFormData, duration_minutes: parseInt(e.target.value) })} className="border-border bg-background" />
                            </div>
                        </div>
                        <div>
                            <FieldLabel>Description</FieldLabel>
                            <Textarea rows={2} value={serviceFormData.description} onChange={(e) => setServiceFormData({ ...serviceFormData, description: e.target.value })} className="resize-none border-border bg-background" />
                        </div>
                    </div>
                    <DialogFooter className="gap-2">
                        <Button variant="outline" onClick={() => setOpenServiceDialog(false)}>Cancel</Button>
                        <Button onClick={handleServiceSubmit} disabled={!serviceFormData.name}>Save</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            <Dialog open={generateDataDialogOpen} onOpenChange={(o) => { if (!o) setGenerateDataDialogOpen(false); }}>
                <DialogContent className="sm:max-w-sm">
                    <DialogHeader><DialogTitle>Generate Sample Data</DialogTitle></DialogHeader>
                    <p className="text-sm text-muted-foreground">This will generate 30 days of sample data for your shop. Proceed?</p>
                    <DialogFooter className="gap-2">
                        <Button variant="outline" onClick={() => setGenerateDataDialogOpen(false)}>Cancel</Button>
                        <Button onClick={confirmGenerateData}>Generate</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            <Dialog open={deleteServiceConfirmId !== null} onOpenChange={(o) => { if (!o) setDeleteServiceConfirmId(null); }}>
                <DialogContent className="sm:max-w-sm">
                    <DialogHeader><DialogTitle>Delete Service</DialogTitle></DialogHeader>
                    <p className="text-sm text-muted-foreground">Delete this service? This cannot be undone.</p>
                    <DialogFooter className="gap-2">
                        <Button variant="outline" onClick={() => setDeleteServiceConfirmId(null)}>Cancel</Button>
                        <Button variant="destructive" onClick={confirmDeleteService}>Delete</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
};

export default ShopSettingsPage;
