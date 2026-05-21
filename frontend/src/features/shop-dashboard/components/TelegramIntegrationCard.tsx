import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
    Box,
    Card,
    CardContent,
    Typography,
    Button,
    Chip,
    CircularProgress,
    Alert,
    Switch,
    FormControlLabel,
    Divider,
    Stack,
    Paper,
    IconButton,
    Tooltip,
} from '@mui/material';
import TelegramIcon from '@mui/icons-material/Telegram';
import LinkOffIcon from '@mui/icons-material/LinkOff';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import api from '../../../services/api';

interface TelegramStatus {
    configured: boolean;
    connected: boolean;
    enabled: boolean;
    chat_id: string | null;
}

interface TelegramConnectInfo {
    token: string;
    bot_username: string;
    deep_link: string;
    expires_in: number;
}

interface TelegramIntegrationCardProps {
    shopId: number;
}

const TelegramIntegrationCard: React.FC<TelegramIntegrationCardProps> = ({ shopId }) => {
    const [status, setStatus] = useState<TelegramStatus | null>(null);
    const [loading, setLoading] = useState(true);
    const [connectInfo, setConnectInfo] = useState<TelegramConnectInfo | null>(null);
    const [connectLoading, setConnectLoading] = useState(false);
    const [toggleLoading, setToggleLoading] = useState(false);
    const [disconnectLoading, setDisconnectLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [copied, setCopied] = useState(false);

    // Poll for connection after generating a link
    const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const connectInfoRef = useRef<TelegramConnectInfo | null>(null);
    connectInfoRef.current = connectInfo;

    const fetchStatus = useCallback(async () => {
        try {
            const res = await api.get<TelegramStatus>(`/shops/${shopId}/telegram/status`);
            setStatus(res.data);
            return res.data;
        } catch (err: any) {
            setError(err?.response?.data?.detail || 'Failed to load Telegram status');
            return null;
        } finally {
            setLoading(false);
        }
    }, [shopId]);

    useEffect(() => {
        fetchStatus();
    }, [fetchStatus]);

    // Start polling once a connect link is generated; stop when connected or unmounted
    useEffect(() => {
        if (connectInfo && !status?.connected) {
            pollRef.current = setInterval(async () => {
                const latest = await fetchStatus();
                if (latest?.connected) {
                    setConnectInfo(null);
                    if (pollRef.current) clearInterval(pollRef.current);
                }
            }, 3000);
        } else {
            if (pollRef.current) {
                clearInterval(pollRef.current);
                pollRef.current = null;
            }
        }
        return () => {
            if (pollRef.current) clearInterval(pollRef.current);
        };
    }, [connectInfo, status?.connected, fetchStatus]);

    const handleGenerateLink = async () => {
        setConnectLoading(true);
        setError(null);
        try {
            const res = await api.post<TelegramConnectInfo>(`/shops/${shopId}/telegram/connect`);
            setConnectInfo(res.data);
        } catch (err: any) {
            setError(err?.response?.data?.detail || 'Failed to generate connection link');
        } finally {
            setConnectLoading(false);
        }
    };

    const handleDisconnect = async () => {
        setDisconnectLoading(true);
        setError(null);
        try {
            await api.delete(`/shops/${shopId}/telegram/disconnect`);
            setConnectInfo(null);
            await fetchStatus();
        } catch (err: any) {
            setError(err?.response?.data?.detail || 'Failed to disconnect');
        } finally {
            setDisconnectLoading(false);
        }
    };

    const handleToggle = async (enabled: boolean) => {
        setToggleLoading(true);
        setError(null);
        try {
            await api.post(`/shops/${shopId}/telegram/toggle`, { enabled });
            setStatus((prev) => prev ? { ...prev, enabled } : prev);
        } catch (err: any) {
            setError(err?.response?.data?.detail || 'Failed to update notification setting');
        } finally {
            setToggleLoading(false);
        }
    };

    const handleCopy = () => {
        if (connectInfo?.deep_link) {
            navigator.clipboard.writeText(connectInfo.deep_link);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        }
    };

    if (loading) {
        return (
            <Box display="flex" justifyContent="center" py={4}>
                <CircularProgress />
            </Box>
        );
    }

    return (
        <Card variant="outlined" sx={{ borderRadius: 3 }}>
            <CardContent sx={{ p: 3 }}>
                {/* Header */}
                <Box display="flex" alignItems="center" gap={1.5} mb={2}>
                    <TelegramIcon sx={{ color: '#229ED9', fontSize: 28 }} />
                    <Box flex={1}>
                        <Typography variant="h6" sx={{ fontWeight: 700, lineHeight: 1.2 }}>
                            Telegram
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                            Receive approvals and chat with your AI team from Telegram
                        </Typography>
                    </Box>
                    {status?.connected ? (
                        <Chip
                            label="Connected"
                            color="success"
                            size="small"
                            icon={<CheckCircleOutlineIcon />}
                        />
                    ) : (
                        <Chip label="Not connected" size="small" variant="outlined" />
                    )}
                </Box>

                {error && (
                    <Alert severity="error" onClose={() => setError(null)} sx={{ mb: 2 }}>
                        {error}
                    </Alert>
                )}

                {/* Server not configured */}
                {!status?.configured && (
                    <Alert severity="info" sx={{ mb: 0 }}>
                        Telegram integration is not enabled on this server. Contact your administrator to set the <code>TELEGRAM_BOT_TOKEN</code> environment variable.
                    </Alert>
                )}

                {/* Connected state */}
                {status?.configured && status?.connected && (
                    <Box>
                        <Paper
                            variant="outlined"
                            sx={{ p: 2, borderRadius: 2, mb: 2, bgcolor: 'action.hover' }}
                        >
                            <Typography variant="body2" color="text.secondary" mb={0.5}>
                                Linked chat ID
                            </Typography>
                            <Typography variant="body1" sx={{ fontWeight: 600, fontFamily: 'monospace' }}>
                                {status.chat_id}
                            </Typography>
                        </Paper>

                        <FormControlLabel
                            sx={{ mb: 2 }}
                            control={
                                <Switch
                                    checked={status.enabled}
                                    onChange={(e) => handleToggle(e.target.checked)}
                                    disabled={toggleLoading}
                                    color="primary"
                                />
                            }
                            label={
                                <Box>
                                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                                        Notifications enabled
                                    </Typography>
                                    <Typography variant="caption" color="text.secondary">
                                        Receive approval requests and summaries in Telegram
                                    </Typography>
                                </Box>
                            }
                        />

                        <Divider sx={{ my: 2 }} />

                        <Stack direction="row" spacing={1} flexWrap="wrap">
                            <Button
                                variant="outlined"
                                color="error"
                                size="small"
                                startIcon={<LinkOffIcon />}
                                onClick={handleDisconnect}
                                disabled={disconnectLoading}
                            >
                                {disconnectLoading ? 'Disconnecting…' : 'Disconnect'}
                            </Button>
                        </Stack>
                    </Box>
                )}

                {/* Not connected — setup flow */}
                {status?.configured && !status?.connected && (
                    <Box>
                        {/* Step-by-step instructions */}
                        {!connectInfo && (
                            <Box mb={2}>
                                <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1.5 }}>
                                    How to connect
                                </Typography>
                                <Stack spacing={1.5}>
                                    {[
                                        'Click "Get Connection Link" below',
                                        'Open the link in Telegram — it opens your ZeroQwait bot',
                                        'Tap Start in Telegram to confirm the connection',
                                        "Done! You'll start receiving approvals and updates here",
                                    ].map((step, i) => (
                                        <Box key={i} display="flex" alignItems="flex-start" gap={1.5}>
                                            <Box
                                                sx={{
                                                    width: 22,
                                                    height: 22,
                                                    borderRadius: '50%',
                                                    bgcolor: 'primary.main',
                                                    color: 'primary.contrastText',
                                                    display: 'flex',
                                                    alignItems: 'center',
                                                    justifyContent: 'center',
                                                    fontSize: 11,
                                                    fontWeight: 700,
                                                    flexShrink: 0,
                                                    mt: 0.1,
                                                }}
                                            >
                                                {i + 1}
                                            </Box>
                                            <Typography variant="body2">{step}</Typography>
                                        </Box>
                                    ))}
                                </Stack>

                                <Box mt={2.5}>
                                    <Button
                                        variant="contained"
                                        startIcon={<TelegramIcon />}
                                        onClick={handleGenerateLink}
                                        disabled={connectLoading}
                                        sx={{
                                            bgcolor: '#229ED9',
                                            '&:hover': { bgcolor: '#1a8abf' },
                                        }}
                                    >
                                        {connectLoading ? 'Generating…' : 'Get Connection Link'}
                                    </Button>
                                </Box>
                            </Box>
                        )}

                        {/* Show deep link once generated */}
                        {connectInfo && (
                            <Box>
                                <Alert severity="info" sx={{ mb: 2 }}>
                                    Link expires in {Math.round(connectInfo.expires_in / 60)} minutes. Waiting for you to tap Start in Telegram…
                                </Alert>

                                <Paper
                                    variant="outlined"
                                    sx={{
                                        p: 2,
                                        borderRadius: 2,
                                        mb: 2,
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: 1,
                                    }}
                                >
                                    <Typography
                                        variant="body2"
                                        sx={{
                                            flex: 1,
                                            fontFamily: 'monospace',
                                            wordBreak: 'break-all',
                                            fontSize: 12,
                                        }}
                                    >
                                        {connectInfo.deep_link}
                                    </Typography>
                                    <Tooltip title={copied ? 'Copied!' : 'Copy link'}>
                                        <IconButton size="small" onClick={handleCopy}>
                                            <ContentCopyIcon fontSize="small" />
                                        </IconButton>
                                    </Tooltip>
                                </Paper>

                                <Stack direction="row" spacing={1.5} flexWrap="wrap">
                                    <Button
                                        variant="contained"
                                        startIcon={<TelegramIcon />}
                                        href={connectInfo.deep_link}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        endIcon={<OpenInNewIcon fontSize="small" />}
                                        sx={{
                                            bgcolor: '#229ED9',
                                            '&:hover': { bgcolor: '#1a8abf' },
                                        }}
                                    >
                                        Open in Telegram
                                    </Button>
                                    <Button
                                        variant="outlined"
                                        size="small"
                                        onClick={() => setConnectInfo(null)}
                                    >
                                        Cancel
                                    </Button>
                                </Stack>

                                <Box display="flex" alignItems="center" gap={1} mt={2}>
                                    <CircularProgress size={14} />
                                    <Typography variant="caption" color="text.secondary">
                                        Waiting for connection…
                                    </Typography>
                                </Box>
                            </Box>
                        )}
                    </Box>
                )}
            </CardContent>
        </Card>
    );
};

export default TelegramIntegrationCard;
