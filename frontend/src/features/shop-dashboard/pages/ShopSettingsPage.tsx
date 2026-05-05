import React, { useState, useEffect, useCallback } from 'react';
import {
    Palette, Building2, Sparkles, CalendarDays,
    Upload, Check, Lightbulb, CircleCheck, Trash2, Pencil,
    CalendarOff, Plus,
} from 'lucide-react';
import api from '../../../services/api';
import { useThemeContext, ThemePreset } from '../../../contexts/ThemeContext';
import { Button } from '../../../components/ui/button';
import { Input } from '../../../components/ui/input';
import { Textarea } from '../../../components/ui/textarea';
import { Badge } from '../../../components/ui/badge';
import {
    Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle,
} from '../../../components/ui/dialog';
import { cn } from '../../../lib/utils';

// ─── Constants ────────────────────────────────────────────────────────────────

const THEMES: { id: ThemePreset; name: string; primary: string; secondary: string }[] = [
    { id: 'default', name: 'Coral', primary: '#FF5A5F', secondary: '#00A699' },
    { id: 'ocean', name: 'Ocean', primary: '#0077B6', secondary: '#48CAE4' },
    { id: 'forest', name: 'Forest', primary: '#2D6A4F', secondary: '#D8F3DC' },
    { id: 'sunset', name: 'Sunset', primary: '#E07A5F', secondary: '#F2CC8F' },
    { id: 'midnight', name: 'Midnight', primary: '#7209B7', secondary: '#4361EE' },
    { id: 'corporate', name: 'Corporate', primary: '#2B2D42', secondary: '#8D99AE' },
];

const STEPS = [
    { id: 'branding', icon: Palette, label: 'Branding', sub: 'Logo, colors & identity' },
    { id: 'business', icon: Building2, label: 'Business Info', sub: 'Shop details & contact' },
    { id: 'experience', icon: Sparkles, label: 'Experience', sub: 'Preferences & environment' },
    { id: 'availability', icon: CalendarDays, label: 'Availability', sub: 'Schedule & closed days' },
];

const DESCRIPTION_MAX = 200;

interface ShopAIEnvironmentResponse {
    shop_id: number; subscription_tier: string; environment_name: string;
    environment_summary: string; operating_mode: string; status_label: string;
    uses_default: boolean; can_customize: boolean;
    capabilities: string[]; experience_notes: string[];
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function FieldLabel({ children }: { children: React.ReactNode }) {
    return <p className="mb-1.5 text-sm font-medium text-foreground">{children}</p>;
}

// ─── Main Component ───────────────────────────────────────────────────────────

const ShopSettingsPage: React.FC = () => {
    const { themePreset, setThemePreset } = useThemeContext();
    const presetTheme = THEMES.find((t) => t.id === themePreset) || THEMES[0];

    const [shop, setShop] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [activeStep, setActiveStep] = useState('branding');
    const [saved, setSaved] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // General / Branding
    const [logoFile, setLogoFile] = useState<File | null>(null);
    const [logoPreview, setLogoPreview] = useState('');
    const [formData, setFormData] = useState({
        name: '', description: '', phone: '', website: '',
        primary_color: presetTheme.primary, secondary_color: presetTheme.secondary,
        accent_color: '', background_color: '', logo_url: '', slug: '',
        dashboard_gradient: 'violet' as string,
    });

    // Services
    const [services, setServices] = useState<any[]>([]);
    const [serviceLoading, setServiceLoading] = useState(false);
    const [openServiceDialog, setOpenServiceDialog] = useState(false);
    const [serviceFormData, setServiceFormData] = useState({
        id: undefined as number | undefined,
        name: '', description: '', duration_minutes: 30, cost: 0.0,
    });
    const [generateDataDialogOpen, setGenerateDataDialogOpen] = useState(false);
    const [deleteServiceConfirmId, setDeleteServiceConfirmId] = useState<number | null>(null);

    // AI / Experience
    const [llmLoading, setLlmLoading] = useState(false);
    const [llmError, setLlmError] = useState<string | null>(null);
    const [aiEnvironment, setAiEnvironment] = useState<ShopAIEnvironmentResponse | null>(null);

    // Availability / Close Days
    const [closeDays, setCloseDays] = useState<any[]>([]);
    const [closeDaysLoading, setCloseDaysLoading] = useState(false);
    const [newCloseDate, setNewCloseDate] = useState('');
    const [newCloseReason, setNewCloseReason] = useState('');

    // ── Data fetching ────────────────────────────────────────────────────────

    const fetchShop = useCallback(async () => {
        try {
            const res = await api.get('/shops/my-shops');
            if (res.data.length > 0) {
                const s = res.data[0];
                setShop(s);
                setFormData({
                    name: s.name, description: s.description || '',
                    phone: s.phone, website: s.website || '',
                    primary_color: s.primary_color || presetTheme.primary,
                    secondary_color: s.secondary_color || presetTheme.secondary,
                    accent_color: s.accent_color || '', background_color: s.background_color || '',
                    logo_url: s.logo_url || '', slug: s.slug || '',
                    dashboard_gradient: s.dashboard_gradient || 'violet',
                });
                if (s.logo_url) setLogoPreview(s.logo_url);
                fetchServices(s.id);
                fetchCloseDays(s.id);
                fetchLLMSettings(s.id);
            }
            setLoading(false);
        } catch { setError('Failed to load shop settings'); setLoading(false); }
    }, [presetTheme.primary, presetTheme.secondary]);

    useEffect(() => { fetchShop(); }, [fetchShop]);

    const fetchServices = async (shopId: number) => {
        setServiceLoading(true);
        try { const r = await api.get(`/shops/${shopId}/services`); setServices(r.data); }
        catch { /* silent */ } finally { setServiceLoading(false); }
    };

    const fetchCloseDays = async (shopId: number) => {
        setCloseDaysLoading(true);
        try { const r = await api.get(`/shops/${shopId}/close-days`); setCloseDays(r.data); }
        catch { /* silent */ } finally { setCloseDaysLoading(false); }
    };

    const fetchLLMSettings = async (shopId: number) => {
        setLlmLoading(true);
        try { const r = await api.get<ShopAIEnvironmentResponse>(`/shops/${shopId}/llm-settings`); setAiEnvironment(r.data); }
        catch (e: any) { setLlmError(e.response?.data?.detail || 'Failed to load AI settings'); }
        finally { setLlmLoading(false); }
    };

    // ── Handlers ─────────────────────────────────────────────────────────────

    const markUnsaved = () => setSaved(false);

    const updateField = (key: string, val: string) => {
        setFormData((p) => ({ ...p, [key]: val }));
        markUnsaved();
    };

    const handleSave = async () => {
        if (!shop) return;
        setSaving(true);
        setError(null);
        try {
            await api.put(`/shops/${shop.id}`, formData);
            if (logoFile) {
                const fd = new FormData();
                fd.append('file', logoFile);
                await api.put(`/shops/${shop.id}/logo`, fd);
            }
            setSaved(true);
            setTimeout(() => window.location.reload(), 800);
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

    const addCloseDay = async () => {
        if (!newCloseDate) return;
        try {
            await api.post(`/shops/${shop.id}/close-days`, null, {
                params: { date_str: newCloseDate, reason: newCloseReason },
            });
            setNewCloseDate(''); setNewCloseReason('');
            fetchCloseDays(shop.id);
        } catch { setError('Failed to add close day'); }
    };

    const deleteCloseDay = async (id: number) => {
        try { await api.delete(`/shops/${shop.id}/close-days/${id}`); fetchCloseDays(shop.id); }
        catch { setError('Failed to remove close day'); }
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
    const stepIndex = STEPS.findIndex((s) => s.id === activeStep);

    // ── Render ────────────────────────────────────────────────────────────────
    return (
        <div className="flex min-h-full flex-col pb-24">
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
                                {/* Number / icon badge */}
                                <div
                                    className={cn(
                                        'flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full text-sm font-semibold transition-colors',
                                        isActive
                                            ? 'bg-primary text-primary-foreground'
                                            : 'border border-border bg-background text-muted-foreground',
                                    )}
                                >
                                    {isActive ? <Icon className="h-4 w-4" /> : idx + 1}
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
                                {/* Active underline */}
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
                                Set your logo and brand colors. These will be reflected across your workspace and booking pages.
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
                                                <span className="text-xs text-muted-foreground">PNG, JPG or SVG. Max 2MB</span>
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
                                    <FieldLabel>Choose your brand colors</FieldLabel>
                                    <p className="mb-3 text-xs text-muted-foreground">Select a theme color that represents your brand.</p>
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

                            {/* Live Preview */}
                            <div className="mt-6">
                                <FieldLabel>Live Preview</FieldLabel>
                                <div
                                    className="overflow-hidden rounded-xl border border-border bg-gradient-to-br from-background to-muted/40 p-5"
                                    style={{ borderLeftColor: activeTheme.primary, borderLeftWidth: 3 }}
                                >
                                    <div className="flex items-center gap-4">
                                        {logoPreview ? (
                                            <img
                                                src={logoPreview}
                                                alt="Logo"
                                                className="h-14 w-14 flex-shrink-0 rounded-xl object-cover"
                                            />
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
                                        <div>
                                            <p className="text-base font-bold text-foreground">
                                                {formData.name || shop.name}
                                            </p>
                                            {formData.description && (
                                                <p className="mt-0.5 text-sm text-muted-foreground line-clamp-1">
                                                    {formData.description}
                                                </p>
                                            )}
                                        </div>
                                        <div
                                            className="ml-auto h-3 w-3 flex-shrink-0 rounded-full"
                                            style={{ backgroundColor: activeTheme.primary }}
                                        />
                                    </div>
                                </div>
                            </div>

                            {/* Tip */}
                            <div className="mt-4 flex items-start gap-2.5 rounded-xl bg-muted/40 px-4 py-3">
                                <Lightbulb className="mt-0.5 h-4 w-4 flex-shrink-0 text-amber-500" />
                                <p className="text-sm text-muted-foreground">
                                    Tip: A strong brand helps build trust and makes your shop memorable.
                                </p>
                            </div>
                        </div>
                    </div>

                    {/* Right: Business Details */}
                    <div className="lg:col-span-2">
                        <div className="rounded-2xl border border-border bg-card p-6">
                            <h2 className="text-lg font-bold text-foreground">Business Details</h2>
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
                                    <FieldLabel>Description</FieldLabel>
                                    <Textarea
                                        rows={4}
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

                                <div className="grid grid-cols-2 gap-3">
                                    <div>
                                        <FieldLabel>Phone</FieldLabel>
                                        <Input
                                            value={formData.phone}
                                            onChange={(e) => updateField('phone', e.target.value)}
                                            className="border-border bg-background"
                                        />
                                    </div>
                                    <div>
                                        <FieldLabel>Website</FieldLabel>
                                        <Input
                                            value={formData.website}
                                            onChange={(e) => updateField('website', e.target.value)}
                                            placeholder="https://"
                                            className="border-border bg-background"
                                        />
                                    </div>
                                </div>
                            </div>

                            {/* AI assist card */}
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
                STEP 2 — BUSINESS INFO (Services)
            ══════════════════════════════════════════════════════════════ */}
            {activeStep === 'business' && (
                <div className="rounded-2xl border border-border bg-card p-6">
                    <div className="mb-5 flex items-center justify-between">
                        <div>
                            <h2 className="text-lg font-bold text-foreground">Manage Services</h2>
                            <p className="mt-0.5 text-sm text-muted-foreground">Add and manage the services your shop offers.</p>
                        </div>
                        <Button
                            size="sm"
                            className="gap-2"
                            onClick={() => {
                                setServiceFormData({ id: undefined, name: '', description: '', duration_minutes: 30, cost: 0.0 });
                                setOpenServiceDialog(true);
                            }}
                        >
                            <Plus className="h-4 w-4" /> Add Service
                        </Button>
                    </div>

                    {serviceLoading ? (
                        <div className="flex justify-center py-12">
                            <div className="h-8 w-8 animate-spin rounded-full border-2 border-border border-t-primary" />
                        </div>
                    ) : services.length === 0 ? (
                        <div className="flex flex-col items-center gap-3 rounded-xl border-2 border-dashed border-border py-16 text-center">
                            <p className="text-sm font-medium text-foreground">No services yet</p>
                            <p className="text-xs text-muted-foreground">Add your first service to get started.</p>
                        </div>
                    ) : (
                        <div className="overflow-hidden rounded-xl border border-border">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="border-b border-border bg-muted/30">
                                        <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground">Name</th>
                                        <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground">Cost</th>
                                        <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground">Duration</th>
                                        <th className="px-4 py-3 text-right text-xs font-semibold text-muted-foreground">Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {services.map((svc, idx) => (
                                        <tr
                                            key={svc.id}
                                            className={cn(
                                                'hover:bg-muted/20 transition-colors',
                                                idx < services.length - 1 && 'border-b border-border/50',
                                            )}
                                        >
                                            <td className="px-4 py-3 font-medium text-foreground">{svc.name}</td>
                                            <td className="px-4 py-3 text-muted-foreground">${Number(svc.cost).toFixed(2)}</td>
                                            <td className="px-4 py-3 text-muted-foreground">{svc.duration_minutes} min</td>
                                            <td className="px-4 py-3">
                                                <div className="flex justify-end gap-1">
                                                    <button
                                                        type="button"
                                                        onClick={() => {
                                                            setServiceFormData({ id: svc.id, name: svc.name, description: svc.description, duration_minutes: svc.duration_minutes, cost: svc.cost });
                                                            setOpenServiceDialog(true);
                                                        }}
                                                        className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
                                                    >
                                                        <Pencil className="h-3.5 w-3.5" />
                                                    </button>
                                                    <button
                                                        type="button"
                                                        onClick={() => setDeleteServiceConfirmId(svc.id)}
                                                        className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground hover:bg-red-500/10 hover:text-red-400 transition-colors"
                                                    >
                                                        <Trash2 className="h-3.5 w-3.5" />
                                                    </button>
                                                </div>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>
            )}

            {/* ══════════════════════════════════════════════════════════════
                STEP 3 — EXPERIENCE (AI Environment)
            ══════════════════════════════════════════════════════════════ */}
            {activeStep === 'experience' && (
                <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
                    <div className="lg:col-span-2 rounded-2xl border border-border bg-card p-6">
                        <h2 className="text-lg font-bold text-foreground">AI Environment</h2>
                        <p className="mt-0.5 mb-5 text-sm text-muted-foreground">
                            Your shop runs inside a ZeroQwait-managed AI environment built for owner operations, approvals, and day-to-day assistance.
                        </p>

                        {llmError && (
                            <div className="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-400">{llmError}</div>
                        )}

                        {llmLoading ? (
                            <div className="flex justify-center py-12">
                                <div className="h-8 w-8 animate-spin rounded-full border-2 border-border border-t-primary" />
                            </div>
                        ) : aiEnvironment ? (
                            <div className="flex flex-col gap-5">
                                <div>
                                    <h3 className="text-xl font-bold text-foreground">{aiEnvironment.environment_name}</h3>
                                    <p className="mt-1 text-sm text-muted-foreground">{aiEnvironment.environment_summary}</p>
                                </div>
                                <div className="flex flex-wrap gap-2">
                                    <Badge>{aiEnvironment.status_label}</Badge>
                                    <Badge variant="outline">{aiEnvironment.operating_mode}</Badge>
                                    <Badge variant="outline">Plan: {aiEnvironment.subscription_tier}</Badge>
                                </div>
                                <div className="rounded-xl border border-blue-500/20 bg-blue-500/5 px-4 py-3 text-sm text-blue-400">
                                    ZeroQwait manages the underlying AI stack automatically so your team can focus on running the business.
                                </div>
                                <div>
                                    <p className="mb-3 text-sm font-semibold text-foreground">What Your AI Team Handles</p>
                                    <div className="flex flex-col gap-2">
                                        {aiEnvironment.capabilities.map((item) => (
                                            <div key={item} className="flex items-start gap-2.5 rounded-xl border border-border px-3.5 py-3">
                                                <CircleCheck className="mt-0.5 h-4 w-4 flex-shrink-0 text-emerald-500" />
                                                <span className="text-sm text-foreground">{item}</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            </div>
                        ) : null}
                    </div>

                    <div className="flex flex-col gap-4">
                        <div className="rounded-2xl border border-border bg-card p-5">
                            <p className="text-xs text-muted-foreground">Environment Status</p>
                            <p className="mt-1 text-base font-bold text-foreground">
                                {aiEnvironment?.uses_default ? 'Managed by ZeroQwait' : 'Managed with internal override'}
                            </p>
                            <p className="mt-3 text-sm text-muted-foreground">
                                Technical model, provider, and infrastructure choices are handled centrally.
                            </p>
                        </div>
                        <div className="rounded-2xl border border-border bg-card p-5">
                            <p className="mb-3 text-sm font-semibold text-foreground">How ZeroQwait Runs It</p>
                            <div className="flex flex-col gap-2">
                                {(aiEnvironment?.experience_notes || []).map((note) => (
                                    <div key={note} className="rounded-xl border border-border px-3.5 py-3">
                                        <p className="text-sm text-muted-foreground">{note}</p>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* ══════════════════════════════════════════════════════════════
                STEP 4 — AVAILABILITY (Schedule & Close Days)
            ══════════════════════════════════════════════════════════════ */}
            {activeStep === 'availability' && (
                <div className="rounded-2xl border border-border bg-card p-6">
                    <h2 className="mb-0.5 text-lg font-bold text-foreground">Operating Schedule</h2>
                    <p className="mb-5 text-sm text-muted-foreground">
                        Manage your shop&apos;s off-days and upcoming closures.
                    </p>

                    <div className="mb-4 rounded-xl border border-blue-500/20 bg-blue-500/5 px-4 py-3 text-sm text-blue-400">
                        We&apos;re working on advanced weekly scheduling. For now, you can manage your shop&apos;s off-days below.
                    </div>

                    <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
                        {/* Add close date */}
                        <div>
                            <p className="mb-3 text-sm font-semibold text-foreground">Add Close Date</p>
                            <div className="rounded-2xl border border-border bg-background p-5">
                                <div className="flex flex-col gap-4">
                                    <div>
                                        <FieldLabel>Select Date</FieldLabel>
                                        <Input
                                            type="date"
                                            value={newCloseDate}
                                            onChange={(e) => setNewCloseDate(e.target.value)}
                                            className="border-border bg-background"
                                        />
                                    </div>
                                    <div>
                                        <FieldLabel>Reason (Optional)</FieldLabel>
                                        <Input
                                            placeholder="e.g. Public Holiday, Renovation"
                                            value={newCloseReason}
                                            onChange={(e) => setNewCloseReason(e.target.value)}
                                            className="border-border bg-background"
                                        />
                                    </div>
                                    <Button
                                        type="button"
                                        className="w-full gap-2"
                                        disabled={!newCloseDate}
                                        onClick={addCloseDay}
                                    >
                                        <CalendarOff className="h-4 w-4" />
                                        Mark as Closed
                                    </Button>
                                </div>
                            </div>
                        </div>

                        {/* Upcoming close dates */}
                        <div>
                            <p className="mb-3 text-sm font-semibold text-foreground">Upcoming Close Dates</p>
                            <div className="max-h-[320px] overflow-y-auto rounded-2xl border border-border bg-background">
                                {closeDaysLoading ? (
                                    <div className="flex justify-center py-8">
                                        <div className="h-6 w-6 animate-spin rounded-full border-2 border-border border-t-primary" />
                                    </div>
                                ) : closeDays.length === 0 ? (
                                    <div className="px-4 py-8 text-center text-sm text-muted-foreground">No upcoming off-days.</div>
                                ) : (
                                    <div className="divide-y divide-border">
                                        {closeDays.map((day) => (
                                            <div key={day.id} className="flex items-center justify-between px-4 py-3">
                                                <div>
                                                    <p className="text-sm font-medium text-foreground">
                                                        {new Date(day.date).toLocaleDateString(undefined, {
                                                            weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
                                                        })}
                                                    </p>
                                                    <p className="text-xs text-muted-foreground">{day.reason || 'No reason provided'}</p>
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
                    </div>
                </div>
            )}

            {/* ── Sticky footer ── */}
            <div className="fixed bottom-0 left-0 right-0 z-30 border-t border-border bg-background/90 backdrop-blur">
                <div className="mx-auto flex max-w-[1700px] items-center justify-between px-8 py-4">
                    <div className="flex items-center gap-2 text-sm">
                        {saved ? (
                            <>
                                <CircleCheck className="h-4 w-4 text-emerald-500" />
                                <span className="text-muted-foreground">All changes saved</span>
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
                        <Button
                            onClick={handleSave}
                            disabled={saving}
                            className="bg-primary px-6 text-primary-foreground hover:bg-primary/90"
                        >
                            {saving ? 'Saving...' : 'Save Changes'}
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
                    <p className="text-sm text-muted-foreground">This will generate 30 days of sample data. Proceed?</p>
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
