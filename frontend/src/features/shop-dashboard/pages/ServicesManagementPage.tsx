import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../../../services/api';
import {
    Alert,
    Box,
    Button,
    Card,
    CircularProgress,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    IconButton,
    InputAdornment,
    Menu,
    MenuItem,
    Select,
    Stack,
    TextField,
    Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import AccessTimeRoundedIcon from '@mui/icons-material/AccessTimeRounded';
import ArrowForwardRoundedIcon from '@mui/icons-material/ArrowForwardRounded';
import ChevronRightRoundedIcon from '@mui/icons-material/ChevronRightRounded';
import ContentCopyRoundedIcon from '@mui/icons-material/ContentCopyRounded';
import DeleteOutlineRoundedIcon from '@mui/icons-material/DeleteOutlineRounded';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import MoreHorizRoundedIcon from '@mui/icons-material/MoreHorizRounded';
import TrendingUpRoundedIcon from '@mui/icons-material/TrendingUpRounded';
import { useShop } from '../../../contexts/ShopContext';

type CatalogSection = 'popular' | 'specialized';

interface ShopService {
    id: number;
    shop_id: number;
    name: string;
    description: string | null;
    duration_minutes: number;
    cost: number;
    currency: string;
    catalog_section?: CatalogSection;
    is_active: boolean;
}

interface ServiceFormData {
    id?: number;
    name: string;
    description: string;
    duration_minutes: number;
    cost: number;
    catalog_section: CatalogSection;
}

interface ServiceStat {
    name: string;
    value: number;
}

const sectionLabel: Record<CatalogSection, string> = {
    popular: 'Popular Services',
    specialized: 'Specialized Treatments',
};

const catalogSerifFont = '"Iowan Old Style", "Baskerville", "Palatino Linotype", "Book Antiqua", Georgia, serif';
const catalogSansFont = '"Inter", "Segoe UI", "Roboto", "Helvetica Neue", Arial, sans-serif';
const catalogColors = {
    canvas: '#ffffff',
    text: '#141923',
    bodyText: '#6f737b',
    mutedText: '#777b83',
    border: '#e7e6e2',
    divider: '#e9e8e4',
    green: '#315b44',
    greenDark: '#264a38',
    iconGreen: '#426e58',
    iconWash: '#edf3ef',
    durationBg: '#f1f2f1',
    danger: '#df3f3b',
};

const emptyForm = (catalogSection: CatalogSection): ServiceFormData => ({
    id: undefined,
    name: '',
    description: '',
    duration_minutes: 60,
    cost: 0,
    catalog_section: catalogSection,
});

const normalizeSection = (service: ShopService, index: number): CatalogSection => {
    if (service.catalog_section === 'popular' || service.catalog_section === 'specialized') {
        return service.catalog_section;
    }
    return index < 3 ? 'popular' : 'specialized';
};

const formatCurrency = (amount: number, currency = 'USD') =>
    new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency,
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    }).format(Number.isFinite(amount) ? amount : 0);

const SectionMark = () => (
    <Box
        aria-hidden
        sx={{
            width: 26,
            height: 26,
            borderRadius: '50%',
            bgcolor: catalogColors.iconWash,
            color: catalogColors.iconGreen,
            display: 'grid',
            placeItems: 'center',
            flex: '0 0 auto',
        }}
    >
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none">
            <path d="M12 4c2.1 1.7 2.1 4.9 0 6.6C9.9 8.9 9.9 5.7 12 4Z" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M6.2 10.2c2.7-.2 5 2.1 4.8 4.8-2.7.2-5-2.1-4.8-4.8Z" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M17.8 10.2c.2 2.7-2.1 5-4.8 4.8-.2-2.7 2.1-5 4.8-4.8Z" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M12 10.8v6.6" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
        </svg>
    </Box>
);

const ServiceGlyph = ({ name }: { name: string }) => {
    const normalizedName = name.toLowerCase();
    const isChiro = normalizedName.includes('chiro');
    const isDeep = normalizedName.includes('deep') || normalizedName.includes('tissue');

    if (isChiro) {
        return (
            <svg viewBox="0 0 48 48" width="34" height="34" fill="none">
                <path d="M24 8c-2.5 2.2-2.5 5.5 0 7.8 2.5-2.3 2.5-5.6 0-7.8Z" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M24 16c-5 1.6-6.2 6.1-3 9.3 3.1 3.1 8.3 2.1 9.7-2" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M23.5 25.4c-5.1 1.4-6.5 6.1-3.2 9.3 3.5 3.4 9.2 1.6 10.1-3.1" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M22.8 35c-2.1 1.2-2.5 3.8-.8 5.5 2.1 2.1 5.6 1 6.2-1.9" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
        );
    }

    if (isDeep) {
        return (
            <svg viewBox="0 0 48 48" width="34" height="34" fill="none">
                <path d="M17 13c0-3.1 3.3-5.1 6-3.7l3.8 2c2.5 1.3 2.6 4.8.2 6.3l-2.8 1.8" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M14 21c0-3 3.3-4.8 5.8-3.2l8.6 5.2c2.8 1.7 2.3 5.9-.8 6.9l-11.2 3.5" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M15.6 31c-2.5 1.4-2.3 5.2.3 6.3l12.2 5c3.6 1.5 7.3-1.7 6.4-5.5l-.4-1.6" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M33.8 30.2l1.2-3.7 3.4-1.7-3.8-1.1-1.8-3.2-1.1 3.6-3.3 1.8 3.7 1.1 1.7 3.2Z" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
        );
    }

    return (
        <svg viewBox="0 0 48 48" width="34" height="34" fill="none">
            <path d="M9 30h29c2.8 0 5 2.2 5 5H14c-2.8 0-5-2.2-5-5Z" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M13 35v5M38 35v5" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" />
            <path d="M17.5 27.5c2.8-2.4 6.2-3.7 10-3.7H30c2.1 0 3.8 1.7 3.8 3.8V30" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M28.8 23.8c-1.6-1.6-1.6-4.2 0-5.8s4.2-1.6 5.8 0 1.6 4.2 0 5.8" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M25.5 20c-2.6.6-4.3 2.2-5.1 4.8M36.8 12.2v5.6M34 15h5.6" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" />
        </svg>
    );
};

const ServiceIconBadge = ({ name }: { name: string }) => (
    <Box
        sx={{
            width: { xs: 68, md: 58, lg: 62 },
            height: { xs: 68, md: 58, lg: 62 },
            borderRadius: '50%',
            bgcolor: catalogColors.iconWash,
            color: catalogColors.iconGreen,
            display: 'grid',
            placeItems: 'center',
            boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.92), 0 20px 30px rgba(49,77,60,0.07)',
            flex: '0 0 auto',
        }}
    >
        <ServiceGlyph name={name} />
    </Box>
);

interface ServiceCardProps {
    service: ShopService;
    variant?: 'featured' | 'compact';
    onEdit: (service: ShopService) => void;
    onDuplicate: (service: ShopService) => void;
    onDelete: (service: ShopService) => void;
    onMenuOpen: (event: React.MouseEvent<HTMLElement>, service: ShopService) => void;
}

const serviceCardSx = {
    borderRadius: '16px',
    border: `1px solid ${catalogColors.border}`,
    bgcolor: '#fff',
    boxShadow: '0 12px 28px rgba(24, 30, 28, 0.045), 0 2px 7px rgba(24, 30, 28, 0.03)',
};

function ServiceCard({ service, variant = 'featured', onEdit, onDuplicate, onDelete, onMenuOpen }: ServiceCardProps) {
    if (variant === 'compact') {
        return (
            <Card
                variant="outlined"
                sx={{
                    ...serviceCardSx,
                    minHeight: { xs: 300, md: 276, lg: 286 },
                    p: { xs: 2.25, md: 2.15, lg: 2.35 },
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    minWidth: 0,
                    width: '100%',
                    overflow: 'hidden',
                }}
            >
                <Box>
                    <Stack direction="row" alignItems="flex-start" gap={{ xs: 1.75, md: 1.65 }}>
                        <ServiceIconBadge name={service.name} />
                        <Box sx={{ flex: 1, minWidth: 0 }}>
                            <Stack direction="row" justifyContent="space-between" alignItems="flex-start" gap={2}>
                                <Typography
                                    component="h3"
                                    sx={{
                                        color: catalogColors.text,
                                        fontFamily: catalogSerifFont,
                                        fontSize: { xs: 24, md: 21, lg: 22 },
                                        lineHeight: 1.04,
                                        fontWeight: 700,
                                        letterSpacing: 0,
                                    }}
                                >
                                    {service.name}
                                </Typography>
                                <IconButton
                                    aria-label={`More actions for ${service.name}`}
                                    onClick={(event) => onMenuOpen(event, service)}
                                    sx={{ color: catalogColors.text, mt: -1.2, mr: -1, p: 0.5 }}
                                >
                                    <MoreHorizRoundedIcon />
                                </IconButton>
                            </Stack>

                            <Stack direction="row" justifyContent="space-between" alignItems="center" gap={1.5} sx={{ mt: 1.1 }}>
                                <DurationPill minutes={service.duration_minutes} />
                                <Typography
                                    sx={{
                                        color: catalogColors.green,
                                        fontSize: { xs: 17, md: 16, lg: 17 },
                                        lineHeight: 1.2,
                                        fontWeight: 800,
                                        whiteSpace: 'nowrap',
                                    }}
                                >
                                    {formatCurrency(service.cost, service.currency)}
                                </Typography>
                            </Stack>

                            <Typography
                                sx={{
                                    color: catalogColors.bodyText,
                                    mt: 1.6,
                                    fontSize: { xs: 15, md: 14.25, lg: 14.5 },
                                    lineHeight: 1.48,
                                    maxWidth: 620,
                                }}
                            >
                                {service.description || 'Describe this service so clients know what to expect.'}
                            </Typography>
                        </Box>
                    </Stack>
                </Box>

                <ServiceCardActions
                    service={service}
                    onEdit={onEdit}
                    onDuplicate={onDuplicate}
                    onDelete={onDelete}
                />
            </Card>
        );
    }

    return (
        <Card
            variant="outlined"
            sx={{
                ...serviceCardSx,
                minHeight: { xs: 318, md: 284, lg: 292 },
                p: { xs: 2.25, md: 2.15, lg: 2.35 },
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                minWidth: 0,
                width: '100%',
                overflow: 'hidden',
            }}
        >
            <Box>
                <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
                    <ServiceIconBadge name={service.name} />
                    <IconButton
                        aria-label={`More actions for ${service.name}`}
                        onClick={(event) => onMenuOpen(event, service)}
                        sx={{ color: catalogColors.text, mt: -1, mr: -1, p: 0.5 }}
                    >
                        <MoreHorizRoundedIcon />
                    </IconButton>
                </Stack>

                <Stack direction="row" justifyContent="space-between" alignItems="flex-start" gap={1.5} sx={{ mt: 2.1 }}>
                    <Box sx={{ minWidth: 0 }}>
                        <Typography
                            component="h3"
                            sx={{
                                color: catalogColors.text,
                                fontFamily: catalogSerifFont,
                                fontSize: { xs: 24, md: 21, lg: 22 },
                                lineHeight: 1.04,
                                fontWeight: 700,
                                letterSpacing: 0,
                            }}
                        >
                            {service.name}
                        </Typography>
                        <Box sx={{ mt: 1.25 }}>
                            <DurationPill minutes={service.duration_minutes} />
                        </Box>
                    </Box>
                    <Typography
                        sx={{
                            color: catalogColors.green,
                            fontSize: { xs: 17, md: 16, lg: 17 },
                            lineHeight: 1.2,
                            fontWeight: 800,
                            whiteSpace: 'nowrap',
                            mt: 0.6,
                        }}
                    >
                        {formatCurrency(service.cost, service.currency)}
                    </Typography>
                </Stack>

                <Typography
                    sx={{
                        color: catalogColors.bodyText,
                        mt: 1.65,
                        fontSize: { xs: 15, md: 14.25, lg: 14.5 },
                        lineHeight: 1.48,
                        maxWidth: 490,
                    }}
                >
                    {service.description || 'Describe this service so clients know what to expect.'}
                </Typography>
            </Box>

            <ServiceCardActions
                service={service}
                onEdit={onEdit}
                onDuplicate={onDuplicate}
                onDelete={onDelete}
            />
        </Card>
    );
}

function DurationPill({ minutes }: { minutes: number }) {
    return (
        <Box
            sx={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 0.75,
                px: 1,
                py: 0.32,
                borderRadius: 999,
                bgcolor: catalogColors.durationBg,
                color: '#6e737b',
                fontFamily: catalogSansFont,
                fontSize: { xs: 13.5, md: 12.5, lg: 13 },
                fontWeight: 700,
                lineHeight: 1,
                boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.95), 0 5px 10px rgba(26,31,29,0.045)',
            }}
        >
            <AccessTimeRoundedIcon sx={{ fontSize: { xs: 15.5, md: 14.5, lg: 15 }, color: '#b6bac0' }} />
            {minutes} min
        </Box>
    );
}

function ServiceCardActions({
    service,
    onEdit,
    onDuplicate,
    onDelete,
}: {
    service: ShopService;
    onEdit: (service: ShopService) => void;
    onDuplicate: (service: ShopService) => void;
    onDelete: (service: ShopService) => void;
}) {
    return (
        <Stack
            direction="row"
            justifyContent="space-around"
            alignItems="center"
            sx={{
                borderTop: `1px solid ${catalogColors.divider}`,
                mt: 2.3,
                pt: 1.55,
                gap: { xs: 0.4, sm: 1 },
            }}
        >
            <CardAction icon={<EditOutlinedIcon />} label="Edit" onClick={() => onEdit(service)} />
            <CardAction icon={<ContentCopyRoundedIcon />} label="Duplicate" onClick={() => onDuplicate(service)} />
            <CardAction
                icon={<DeleteOutlineRoundedIcon />}
                label="Delete"
                tone="danger"
                onClick={() => onDelete(service)}
            />
        </Stack>
    );
}

function CardAction({
    icon,
    label,
    tone = 'default',
    onClick,
}: {
    icon: React.ReactElement;
    label: string;
    tone?: 'default' | 'danger';
    onClick: () => void;
}) {
    const actionColor = tone === 'danger' ? catalogColors.danger : '#30353b';
    const iconColor = tone === 'danger' ? catalogColors.danger : '#5d6269';

    return (
        <Button
            onClick={onClick}
            startIcon={React.cloneElement(icon, { sx: { fontSize: 19 } })}
            sx={{
                fontFamily: catalogSansFont,
                color: `${actionColor} !important`,
                fontSize: { xs: 13.5, md: 13, lg: 13.5 },
                fontWeight: 700,
                px: { xs: 0.5, md: 1.2 },
                minWidth: 'auto',
                '& .MuiButton-startIcon': {
                    mr: { xs: 0.9, md: 0.65, lg: 0.8 },
                    color: `${iconColor} !important`,
                },
                '&:hover': { bgcolor: 'transparent' },
            }}
        >
            {label}
        </Button>
    );
}

function SectionHeader({ title }: { title: string }) {
    return (
        <Stack direction="row" alignItems="center" gap={1.2} sx={{ mb: { xs: 2.4, md: 2 } }}>
            <SectionMark />
            <Typography
                component="h2"
                sx={{
                    color: catalogColors.text,
                    fontFamily: catalogSansFont,
                    fontSize: { xs: 20, md: 20.5, lg: 21 },
                    fontWeight: 700,
                    letterSpacing: 0,
                }}
            >
                {title}
            </Typography>
        </Stack>
    );
}

function AddServiceCard({ onClick }: { onClick: () => void }) {
    return (
        <Box
            component="button"
            onClick={onClick}
            aria-label="Add a new service"
            sx={{
                ...serviceCardSx,
                minHeight: { xs: 260, md: 276, lg: 286 },
                width: '100%',
                borderStyle: 'dashed',
                borderWidth: 2,
                borderColor: '#d8d9d3',
                boxShadow: 'none',
                bgcolor: catalogColors.canvas,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                textAlign: 'center',
                p: { xs: 2.5, md: 2.25 },
                font: 'inherit',
                transition: 'border-color 160ms ease, box-shadow 160ms ease, transform 160ms ease',
                '&:hover': {
                    borderColor: '#b9c7bc',
                    boxShadow: '0 12px 28px rgba(26,31,29,0.06)',
                    transform: 'translateY(-1px)',
                },
            }}
        >
            <Box>
                <Box
                    sx={{
                        width: { xs: 48, md: 42 },
                        height: { xs: 48, md: 42 },
                        mx: 'auto',
                        borderRadius: '50%',
                        bgcolor: '#fff',
                        border: '1px solid #ddded9',
                        boxShadow: '0 6px 16px rgba(25, 31, 28, 0.12)',
                        display: 'grid',
                        placeItems: 'center',
                        color: catalogColors.text,
                    }}
                >
                    <AddIcon sx={{ fontSize: { xs: 26, md: 23 } }} />
                </Box>
                <Typography sx={{ mt: 2.1, color: catalogColors.text, fontFamily: catalogSansFont, fontSize: { xs: 17, md: 15.5 }, fontWeight: 700 }}>
                    Add a new service
                </Typography>
                <Typography sx={{ mt: 0.75, color: catalogColors.mutedText, fontFamily: catalogSansFont, fontSize: { xs: 14.5, md: 13.5 }, lineHeight: 1.45 }}>
                    Expand your offerings and<br />delight your clients.
                </Typography>
                <Stack direction="row" alignItems="center" justifyContent="center" gap={0.8} sx={{ mt: 1.9, color: catalogColors.green }}>
                    <AddIcon sx={{ fontSize: 18 }} />
                    <Typography sx={{ fontFamily: catalogSansFont, fontSize: { xs: 15.5, md: 14.5 }, fontWeight: 700 }}>Add Service</Typography>
                </Stack>
            </Box>
        </Box>
    );
}

const ServicesManagementPage: React.FC = () => {
    const navigate = useNavigate();
    const { shop } = useShop();
    const popularScrollerRef = useRef<HTMLDivElement | null>(null);
    const [services, setServices] = useState<ShopService[]>([]);
    const [serviceStats, setServiceStats] = useState<ServiceStat[]>([]);
    const [loading, setLoading] = useState(true);
    const [openDialog, setOpenDialog] = useState(false);
    const [formData, setFormData] = useState<ServiceFormData>(() => emptyForm('popular'));
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);
    const [submitting, setSubmitting] = useState(false);
    const [deleteConfirmService, setDeleteConfirmService] = useState<ShopService | null>(null);
    const [menuAnchor, setMenuAnchor] = useState<HTMLElement | null>(null);
    const [menuService, setMenuService] = useState<ShopService | null>(null);

    const fetchCatalogData = async () => {
        if (!shop) return;

        setLoading(true);
        setError(null);

        try {
            const servicesResponse = await api.get(`/shops/${shop.id}/services`);
            setServices(Array.isArray(servicesResponse.data) ? servicesResponse.data : []);

            try {
                const analyticsResponse = await api.get(`/analytics/services/${shop.id}?days=30`);
                setServiceStats(Array.isArray(analyticsResponse.data) ? analyticsResponse.data : []);
            } catch {
                setServiceStats([]);
            }
        } catch {
            setError('Failed to load services');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (shop) {
            void fetchCatalogData();
        } else {
            setLoading(false);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [shop?.id]);

    const normalizedServices = useMemo(
        () =>
            services
                .filter((service) => service.is_active !== false)
                .map((service, index) => ({
                    ...service,
                    catalog_section: normalizeSection(service, index),
                })),
        [services]
    );

    const popularServices = normalizedServices.filter((service) => service.catalog_section === 'popular');
    const specializedServices = normalizedServices.filter((service) => service.catalog_section === 'specialized');
    const activeServicesCount = normalizedServices.length;
    const mostBookedService = serviceStats[0]?.name || popularServices[0]?.name || normalizedServices[0]?.name || 'None yet';

    const handleOpenDialog = (catalogSection: CatalogSection, service?: ShopService) => {
        if (service) {
            setFormData({
                id: service.id,
                name: service.name,
                description: service.description || '',
                duration_minutes: service.duration_minutes,
                cost: service.cost,
                catalog_section: normalizeSection(service, 0),
            });
        } else {
            setFormData(emptyForm(catalogSection));
        }
        setError(null);
        setOpenDialog(true);
    };

    const closeMenu = () => {
        setMenuAnchor(null);
        setMenuService(null);
    };

    const handleMenuOpen = (event: React.MouseEvent<HTMLElement>, service: ShopService) => {
        setMenuAnchor(event.currentTarget);
        setMenuService(service);
    };

    const servicePayload = {
        name: formData.name.trim(),
        description: formData.description.trim(),
        duration_minutes: Number.isFinite(formData.duration_minutes) ? formData.duration_minutes : 0,
        cost: Number.isFinite(formData.cost) ? formData.cost : 0,
        catalog_section: formData.catalog_section,
    };

    const handleSubmit = async () => {
        if (!shop || !servicePayload.name) return;

        setSubmitting(true);
        setError(null);

        try {
            if (formData.id) {
                await api.put(`/shops/${shop.id}/services/${formData.id}`, servicePayload);
                setSuccess('Service updated successfully');
            } else {
                await api.post(`/shops/${shop.id}/services`, servicePayload);
                setSuccess('Service created successfully');
            }

            setOpenDialog(false);
            await fetchCatalogData();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to save service');
        } finally {
            setSubmitting(false);
        }
    };

    const handleDuplicate = async (service: ShopService) => {
        if (!shop) return;

        closeMenu();
        setSubmitting(true);
        setError(null);

        try {
            await api.post(`/shops/${shop.id}/services`, {
                name: `${service.name} Copy`,
                description: service.description || '',
                duration_minutes: service.duration_minutes,
                cost: service.cost,
                currency: service.currency || 'USD',
                catalog_section: normalizeSection(service, 0),
            });
            setSuccess('Service duplicated successfully');
            await fetchCatalogData();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to duplicate service');
        } finally {
            setSubmitting(false);
        }
    };

    const confirmDelete = async () => {
        if (!shop || !deleteConfirmService) return;

        try {
            await api.delete(`/shops/${shop.id}/services/${deleteConfirmService.id}`);
            setSuccess('Service deleted successfully');
            setDeleteConfirmService(null);
            await fetchCatalogData();
        } catch {
            setError('Failed to delete service');
            setDeleteConfirmService(null);
        }
    };

    const scrollPopularServices = () => {
        popularScrollerRef.current?.scrollBy({ left: 420, behavior: 'smooth' });
    };

    const renderServiceGrid = (sectionServices: ShopService[]) => (
        <Box
            sx={{
                display: 'grid',
                gridTemplateColumns: {
                    xs: '1fr',
                    sm: 'repeat(2, minmax(0, 1fr))',
                    md: 'repeat(3, minmax(0, 1fr))',
                },
                gap: { xs: 2, md: 2.2 },
            }}
        >
            {sectionServices.map((service) => (
                <ServiceCard
                    key={service.id}
                    service={service}
                    onEdit={(selectedService) => handleOpenDialog(normalizeSection(selectedService, 0), selectedService)}
                    onDuplicate={handleDuplicate}
                    onDelete={setDeleteConfirmService}
                    onMenuOpen={handleMenuOpen}
                />
            ))}
        </Box>
    );

    return (
        <Box
            sx={{
                width: '100%',
                minHeight: 'calc(100vh - var(--navbar-h))',
                bgcolor: catalogColors.canvas,
                color: catalogColors.text,
                fontFamily: catalogSansFont,
                px: { xs: 2, md: 3 },
                pt: { xs: 2, md: 2.25 },
                pb: 5,
            }}
        >
            <Box sx={{ maxWidth: 1320, mx: 'auto', position: 'relative' }}>
                <Stack
                    direction={{ xs: 'column', lg: 'row' }}
                    justifyContent="space-between"
                    alignItems={{ xs: 'stretch', lg: 'flex-start' }}
                    gap={{ xs: 2.5, lg: 3.5 }}
                    sx={{ mb: { xs: 4, md: 4.5 } }}
                >
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 3, flex: 1 }}>
                        <Box>
                            <Typography
                                component="h1"
                                sx={{
                                    fontFamily: catalogSerifFont,
                                    fontSize: { xs: 34, sm: 38, md: 40, lg: 42 },
                                    lineHeight: 1,
                                    fontWeight: 500,
                                    letterSpacing: 0,
                                    color: catalogColors.text,
                                }}
                            >
                                Service Catalog
                            </Typography>
                            <Typography
                                sx={{
                                    mt: { xs: 1.5, md: 1.35 },
                                    color: catalogColors.mutedText,
                                    fontFamily: catalogSansFont,
                                    fontSize: { xs: 16, md: 16.5, lg: 17 },
                                    lineHeight: 1.45,
                                    maxWidth: 620,
                                }}
                            >
                                Curate your menu with pricing, duration,<br />
                                and descriptions for your clients.
                            </Typography>
                        </Box>
                        <Button
                            variant="contained"
                            startIcon={<AddIcon sx={{ fontSize: 24 }} />}
                            onClick={() => handleOpenDialog('popular')}
                            sx={{
                                display: { xs: 'none', md: 'inline-flex' },
                                mt: 1.45,
                                bgcolor: `${catalogColors.green} !important`,
                                color: '#fff !important',
                                borderRadius: '11px',
                                minHeight: 46,
                                px: 2.15,
                                fontFamily: catalogSansFont,
                                fontSize: 15,
                                fontWeight: 700,
                                boxShadow: '0 16px 28px rgba(49,91,68,0.24), inset 0 1px 0 rgba(255,255,255,0.18)',
                                '&:hover': { bgcolor: `${catalogColors.greenDark} !important` },
                            }}
                        >
                            Add Service
                        </Button>
                    </Box>

                    <Card
                        variant="outlined"
                        sx={{
                            ...serviceCardSx,
                            width: { xs: '100%', lg: 400, xl: 430 },
                            minHeight: { md: 112, lg: 120 },
                            borderRadius: '16px',
                            p: { xs: 2.25, md: 2.1, lg: 2.25 },
                            alignSelf: { lg: 'flex-start' },
                        }}
                    >
                        <Stack direction="row" gap={1.8} alignItems="center">
                            <Box
                                sx={{
                                    width: { xs: 68, md: 58, lg: 62 },
                                    height: { xs: 68, md: 58, lg: 62 },
                                    borderRadius: '50%',
                                    bgcolor: catalogColors.iconWash,
                                    color: catalogColors.iconGreen,
                                    display: 'grid',
                                    placeItems: 'center',
                                }}
                            >
                                <TrendingUpRoundedIcon sx={{ fontSize: { xs: 34, md: 30, lg: 32 } }} />
                            </Box>
                            <Box>
                                <Typography sx={{ fontFamily: catalogSansFont, fontSize: { xs: 16, md: 15.25, lg: 15.75 }, fontWeight: 700, color: catalogColors.text }}>
                                    You have {activeServicesCount} active services
                                </Typography>
                                <Typography sx={{ mt: 0.65, color: '#666b73', fontFamily: catalogSansFont, fontSize: { xs: 15, md: 14.25, lg: 14.75 } }}>
                                    Most booked: <Box component="span" sx={{ color: '#30343a', fontWeight: 500 }}>{mostBookedService}</Box>
                                </Typography>
                                <Button
                                    onClick={() => navigate('/overview')}
                                    endIcon={<ArrowForwardRoundedIcon />}
                                    sx={{
                                        mt: 0.75,
                                        color: `${catalogColors.green} !important`,
                                        fontFamily: catalogSansFont,
                                        fontSize: { xs: 14.5, md: 14, lg: 14.5 },
                                        fontWeight: 700,
                                        minWidth: 'auto',
                                        p: 0,
                                        '&:hover': { bgcolor: 'transparent', textDecoration: 'underline' },
                                    }}
                                >
                                    View insights
                                </Button>
                            </Box>
                        </Stack>
                    </Card>

                    <Button
                        variant="contained"
                        startIcon={<AddIcon />}
                        onClick={() => handleOpenDialog('popular')}
                        sx={{
                            display: { xs: 'inline-flex', md: 'none' },
                            alignSelf: 'flex-start',
                            bgcolor: `${catalogColors.green} !important`,
                            color: '#fff !important',
                            fontFamily: catalogSansFont,
                            fontWeight: 700,
                            '&:hover': { bgcolor: `${catalogColors.greenDark} !important` },
                        }}
                    >
                        Add Service
                    </Button>
                </Stack>

                {error && <Alert severity="error" onClose={() => setError(null)} sx={{ mb: 3 }}>{error}</Alert>}
                {success && <Alert severity="success" onClose={() => setSuccess(null)} sx={{ mb: 3 }}>{success}</Alert>}

                {loading ? (
                    <Box display="flex" justifyContent="center" alignItems="center" minHeight={320}>
                        <CircularProgress />
                    </Box>
                ) : (
                    <>
                        <Box component="section" sx={{ mb: { xs: 4.5, md: 4.25 }, position: 'relative' }}>
                            <SectionHeader title={sectionLabel.popular} />
                            <Box
                                ref={popularScrollerRef}
                                sx={{
                                    overflowX: 'visible',
                                    scrollbarWidth: 'none',
                                    '&::-webkit-scrollbar': { display: 'none' },
                                }}
                            >
                                {renderServiceGrid(popularServices)}
                            </Box>
                            <IconButton
                                aria-label="Scroll popular services"
                                onClick={scrollPopularServices}
                                sx={{
                                    display: { xs: 'none', xl: popularServices.length > 3 ? 'inline-flex' : 'none' },
                                    position: 'absolute',
                                    right: -58,
                                    top: '50%',
                                    width: 46,
                                    height: 46,
                                    bgcolor: '#fff',
                                    color: catalogColors.text,
                                    boxShadow: '0 10px 24px rgba(27,31,35,0.14)',
                                    border: '1px solid #ececea',
                                    '&:hover': { bgcolor: '#fff' },
                                }}
                            >
                                <ChevronRightRoundedIcon sx={{ fontSize: 27 }} />
                            </IconButton>
                        </Box>

                        <Box component="section">
                            <SectionHeader title={sectionLabel.specialized} />
                            <Box
                                sx={{
                                    display: 'grid',
                                    gridTemplateColumns: {
                                        xs: '1fr',
                                        sm: 'repeat(2, minmax(0, 1fr))',
                                        md: 'repeat(3, minmax(0, 1fr))',
                                    },
                                    gap: { xs: 2, md: 2.2 },
                                    alignItems: 'stretch',
                                }}
                            >
                                {specializedServices.map((service) => (
                                    <ServiceCard
                                        key={service.id}
                                        variant="compact"
                                        service={service}
                                        onEdit={(selectedService) => handleOpenDialog('specialized', selectedService)}
                                        onDuplicate={handleDuplicate}
                                        onDelete={setDeleteConfirmService}
                                        onMenuOpen={handleMenuOpen}
                                    />
                                ))}
                                <AddServiceCard onClick={() => handleOpenDialog('specialized')} />
                            </Box>
                        </Box>
                    </>
                )}
            </Box>

            <Menu
                anchorEl={menuAnchor}
                open={Boolean(menuAnchor)}
                onClose={closeMenu}
                anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
                transformOrigin={{ vertical: 'top', horizontal: 'right' }}
            >
                <MenuItem
                    onClick={() => {
                        if (menuService) handleOpenDialog(normalizeSection(menuService, 0), menuService);
                        closeMenu();
                    }}
                >
                    <EditOutlinedIcon fontSize="small" sx={{ mr: 1.5 }} /> Edit
                </MenuItem>
                <MenuItem
                    onClick={() => {
                        if (menuService) void handleDuplicate(menuService);
                    }}
                >
                    <ContentCopyRoundedIcon fontSize="small" sx={{ mr: 1.5 }} /> Duplicate
                </MenuItem>
                <MenuItem
                    onClick={() => {
                        if (menuService) setDeleteConfirmService(menuService);
                        closeMenu();
                    }}
                    sx={{ color: catalogColors.danger }}
                >
                    <DeleteOutlineRoundedIcon fontSize="small" sx={{ mr: 1.5 }} /> Delete
                </MenuItem>
            </Menu>

            <Dialog open={openDialog} onClose={() => setOpenDialog(false)} maxWidth="sm" fullWidth>
                <DialogTitle>{formData.id ? 'Edit Service' : 'Add New Service'}</DialogTitle>
                <DialogContent>
                    <Stack sx={{ pt: 1.5 }} spacing={2.2}>
                        <TextField
                            label="Service Name"
                            value={formData.name}
                            onChange={(event) => setFormData({ ...formData, name: event.target.value })}
                            fullWidth
                            required
                        />
                        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
                            <TextField
                                label="Price"
                                type="number"
                                value={formData.cost}
                                onChange={(event) => setFormData({ ...formData, cost: Number(event.target.value) })}
                                fullWidth
                                required
                                InputProps={{
                                    startAdornment: <InputAdornment position="start">$</InputAdornment>,
                                }}
                            />
                            <TextField
                                label="Duration"
                                type="number"
                                value={formData.duration_minutes}
                                onChange={(event) => setFormData({ ...formData, duration_minutes: Number(event.target.value) })}
                                fullWidth
                                required
                                InputProps={{
                                    endAdornment: <InputAdornment position="end">min</InputAdornment>,
                                }}
                            />
                        </Stack>
                        <Select
                            native
                            value={formData.catalog_section}
                            onChange={(event) =>
                                setFormData({
                                    ...formData,
                                    catalog_section: event.target.value as CatalogSection,
                                })
                            }
                            inputProps={{ 'aria-label': 'Catalog section' }}
                            fullWidth
                        >
                            <option value="popular">Popular Services</option>
                            <option value="specialized">Specialized Treatments</option>
                        </Select>
                        <TextField
                            label="Description"
                            value={formData.description}
                            onChange={(event) => setFormData({ ...formData, description: event.target.value })}
                            fullWidth
                            multiline
                            rows={3}
                        />
                    </Stack>
                </DialogContent>
                <DialogActions sx={{ px: 3, pb: 2.5 }}>
                    <Button onClick={() => setOpenDialog(false)}>Cancel</Button>
                    <Button
                        onClick={handleSubmit}
                        variant="contained"
                        disabled={submitting || !servicePayload.name || servicePayload.cost < 0 || servicePayload.duration_minutes <= 0}
                    >
                        {submitting ? 'Saving...' : 'Save'}
                    </Button>
                </DialogActions>
            </Dialog>

            <Dialog open={Boolean(deleteConfirmService)} onClose={() => setDeleteConfirmService(null)}>
                <DialogTitle>Delete Service</DialogTitle>
                <DialogContent>
                    <Typography>
                        Are you sure you want to delete {deleteConfirmService?.name || 'this service'}? This cannot be undone.
                    </Typography>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setDeleteConfirmService(null)}>Cancel</Button>
                    <Button variant="contained" color="error" onClick={confirmDelete}>Delete</Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
};

export default ServicesManagementPage;
