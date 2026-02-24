/**
 * VoiceRegistrationFlow.tsx
 *
 * A self-contained conversational registration wizard rendered in the AI assistant's
 * right panel when `activeViewer === 'register'`.
 *
 * It guides the user step-by-step through:
 *   1. Account type selection (Customer / Shop Owner)
 *   2. Email → Username → Password
 *   3. (Shop Owner only) Shop name → Shop type → Address details
 *   4. Confirmation summary
 *   5. Submit → success / error
 *
 * At each step it fires a callback so the parent (MasterAIAgent) can speak the prompt
 * and append it to the chat history.
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
    Box,
    Typography,
    TextField,
    Button,
    Chip,
    CircularProgress,
    Alert,
    Stack,
    Fade,
    LinearProgress,
    MenuItem,
    Divider,
    InputAdornment,
    IconButton,
} from '@mui/material';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import PersonIcon from '@mui/icons-material/Person';
import StoreIcon from '@mui/icons-material/Store';
import EmailIcon from '@mui/icons-material/Email';
import LockIcon from '@mui/icons-material/Lock';
import BadgeIcon from '@mui/icons-material/Badge';
import LocationCityIcon from '@mui/icons-material/LocationCity';
import Visibility from '@mui/icons-material/Visibility';
import VisibilityOff from '@mui/icons-material/VisibilityOff';
import CheckIcon from '@mui/icons-material/Check';
import CloseIcon from '@mui/icons-material/Close';
import axios from 'axios';

// ─── Types ────────────────────────────────────────────────────────────────────

type AccountType = 'customer' | 'shop_owner' | null;

type RegistrationStep =
    | 'account_type'
    | 'email'
    | 'username'
    | 'password'
    | 'shop_name'
    | 'shop_type'
    | 'shop_address'
    | 'confirm'
    | 'submitting'
    | 'done'
    | 'error';

interface CollectedData {
    accountType: AccountType;
    email: string;
    username: string;
    password: string;
    shopName: string;
    shopType: string;
    shopAddress: string;
    shopCity: string;
    shopState: string;
    shopZip: string;
    shopPhone: string;
}

interface ValidationState {
    email: 'idle' | 'checking' | 'available' | 'taken' | 'invalid';
    username: 'idle' | 'checking' | 'available' | 'taken';
    shopName: 'idle' | 'checking' | 'available' | 'taken';
}

interface VoiceRegistrationFlowProps {
    isDarkMode: boolean;
    theme: {
        text: string;
        textSecondary: string;
        accent: string;
        cardBg: string;
        cardBorder: string;
        inputBg: string;
        iconColor: string;
    };
    /** Called when the AI should speak a prompt and append it to chat */
    onAISpeak: (text: string) => void;
    /** Called when the user cancels or completes registration */
    onClose: (success?: boolean) => void;
    /** Pre-fill account type if the AI already collected it */
    prefilledAccountType?: AccountType;
}

// ─── Constants ─────────────────────────────────────────────────────────────────

const SHOP_TYPES = [
    'Barber Shop',
    'Hair Salon',
    'Nail Salon',
    'Spa & Wellness',
    'Medical Clinic',
    'Dental Office',
    'Veterinary Clinic',
    'Auto Repair',
    'Tire Shop',
    'Restaurant / Café',
    'Government Office',
    'Bank / Finance',
    'Pharmacy',
    'Other',
];

const STEPS_FOR_CUSTOMER: RegistrationStep[] = ['account_type', 'email', 'username', 'password', 'confirm'];
const STEPS_FOR_SHOP_OWNER: RegistrationStep[] = ['account_type', 'email', 'username', 'password', 'shop_name', 'shop_type', 'shop_address', 'confirm'];

const AI_PROMPTS: Record<RegistrationStep, string> = {
    account_type: "Are you signing up as a shop owner, or as a customer looking to join queues?",
    email: "What's your email address?",
    username: "Great! Now choose a username — this is how you'll sign in.",
    password: "Create a secure password. It should be at least 8 characters.",
    shop_name: "What's the name of your business?",
    shop_type: "What type of business do you run?",
    shop_address: "Almost there! What's your shop's address?",
    confirm: "Here's a summary of your details. Does everything look correct?",
    submitting: "Creating your account, please hold on...",
    done: "You're all set! Your account has been created. You can log in now.",
    error: "Something went wrong during registration. Please try again.",
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function getStepProgress(step: RegistrationStep, accountType: AccountType): number {
    const steps = accountType === 'shop_owner' ? STEPS_FOR_SHOP_OWNER : STEPS_FOR_CUSTOMER;
    const idx = steps.indexOf(step);
    if (idx < 0) return 100;
    return Math.round(((idx + 1) / steps.length) * 100);
}

// ─── Component ────────────────────────────────────────────────────────────────

const VoiceRegistrationFlow: React.FC<VoiceRegistrationFlowProps> = ({
    isDarkMode,
    theme,
    onAISpeak,
    onClose,
    prefilledAccountType,
}) => {
    const [step, setStep] = useState<RegistrationStep>(
        prefilledAccountType ? 'email' : 'account_type'
    );
    const [data, setData] = useState<CollectedData>({
        accountType: prefilledAccountType || null,
        email: '',
        username: '',
        password: '',
        shopName: '',
        shopType: '',
        shopAddress: '',
        shopCity: '',
        shopState: '',
        shopZip: '',
        shopPhone: '',
    });
    const [validation, setValidation] = useState<ValidationState>({
        email: 'idle',
        username: 'idle',
        shopName: 'idle',
    });
    const [showPassword, setShowPassword] = useState(false);
    const [fieldError, setFieldError] = useState<string>('');
    const [successMessage, setSuccessMessage] = useState<string>('');

    const hasSpoken = useRef<Set<RegistrationStep>>(new Set());

    // Speak AI prompt once when step changes
    useEffect(() => {
        if (!hasSpoken.current.has(step) && step !== 'submitting') {
            hasSpoken.current.add(step);
            onAISpeak(AI_PROMPTS[step]);
        }
    }, [step, onAISpeak]);

    // Speak initial account type prompt if prefilled
    useEffect(() => {
        if (prefilledAccountType) {
            onAISpeak(AI_PROMPTS['email']);
            hasSpoken.current.add('email');
        }
    }, []); // eslint-disable-line react-hooks/exhaustive-deps

    // ── Real-time email validation ──────────────────────────────────────────
    const emailDebounce = useRef<NodeJS.Timeout | null>(null);
    useEffect(() => {
        if (!data.email) { setValidation(v => ({ ...v, email: 'idle' })); return; }
        if (!emailRegex.test(data.email)) { setValidation(v => ({ ...v, email: 'invalid' })); return; }

        setValidation(v => ({ ...v, email: 'checking' }));
        if (emailDebounce.current) clearTimeout(emailDebounce.current);
        emailDebounce.current = setTimeout(async () => {
            try {
                const res = await axios.get(`/api/users/check-email/${encodeURIComponent(data.email)}`);
                setValidation(v => ({ ...v, email: res.data.available ? 'available' : 'taken' }));
            } catch { setValidation(v => ({ ...v, email: 'available' })); }
        }, 600);
    }, [data.email]);

    // ── Real-time username validation ───────────────────────────────────────
    const usernameDebounce = useRef<NodeJS.Timeout | null>(null);
    useEffect(() => {
        if (!data.username || data.username.length < 3) {
            setValidation(v => ({ ...v, username: 'idle' })); return;
        }
        setValidation(v => ({ ...v, username: 'checking' }));
        if (usernameDebounce.current) clearTimeout(usernameDebounce.current);
        usernameDebounce.current = setTimeout(async () => {
            try {
                const res = await axios.get(`/api/users/check-username/${encodeURIComponent(data.username)}`);
                setValidation(v => ({ ...v, username: res.data.available ? 'available' : 'taken' }));
            } catch { setValidation(v => ({ ...v, username: 'available' })); }
        }, 600);
    }, [data.username]);

    // ── Real-time shop name slug validation ────────────────────────────────
    const shopNameDebounce = useRef<NodeJS.Timeout | null>(null);
    useEffect(() => {
        if (!data.shopName || data.shopName.length < 3) {
            setValidation(v => ({ ...v, shopName: 'idle' })); return;
        }
        setValidation(v => ({ ...v, shopName: 'checking' }));
        if (shopNameDebounce.current) clearTimeout(shopNameDebounce.current);
        shopNameDebounce.current = setTimeout(async () => {
            try {
                const res = await axios.get(`/api/shops/check-slug/${encodeURIComponent(data.shopName)}`);
                setValidation(v => ({ ...v, shopName: res.data.available ? 'available' : 'taken' }));
            } catch { setValidation(v => ({ ...v, shopName: 'available' })); }
        }, 600);
    }, [data.shopName]);

    // ── Navigation helpers ─────────────────────────────────────────────────
    const goTo = useCallback((nextStep: RegistrationStep) => {
        setFieldError('');
        setStep(nextStep);
    }, []);

    const handleSelectAccountType = (type: AccountType) => {
        setData(d => ({ ...d, accountType: type }));
        onAISpeak(
            type === 'shop_owner'
                ? "Great! Let's set up your shop owner account. What's your email address?"
                : "Perfect! Let's create your customer account. What's your email address?"
        );
        hasSpoken.current.add('email');
        goTo('email');
    };

    const handleNextEmail = () => {
        if (!emailRegex.test(data.email)) { setFieldError('Please enter a valid email address.'); return; }
        if (validation.email === 'taken') { setFieldError('That email is already registered. Try a different one or sign in.'); return; }
        if (validation.email === 'checking') { setFieldError('Still checking availability, please wait a moment.'); return; }
        goTo('username');
    };

    const handleNextUsername = () => {
        if (data.username.length < 3) { setFieldError('Username must be at least 3 characters.'); return; }
        if (/\s/.test(data.username)) { setFieldError('Username cannot contain spaces.'); return; }
        if (validation.username === 'taken') { setFieldError('That username is already taken. Please choose another.'); return; }
        if (validation.username === 'checking') { setFieldError('Still checking availability, please wait a moment.'); return; }
        goTo('password');
    };

    const handleNextPassword = () => {
        if (data.password.length < 8) { setFieldError('Password must be at least 8 characters.'); return; }
        if (data.accountType === 'shop_owner') {
            goTo('shop_name');
        } else {
            goTo('confirm');
        }
    };

    const handleNextShopName = () => {
        if (data.shopName.trim().length < 2) { setFieldError('Please enter your shop name.'); return; }
        if (validation.shopName === 'taken') { setFieldError('A shop with that name already exists. Please choose a different name.'); return; }
        if (validation.shopName === 'checking') { setFieldError('Checking name availability, please wait.'); return; }
        goTo('shop_type');
    };

    const handleNextShopType = () => {
        if (!data.shopType) { setFieldError('Please select your business type.'); return; }
        goTo('shop_address');
    };

    const handleNextShopAddress = () => {
        if (!data.shopAddress.trim()) { setFieldError('Please enter your street address.'); return; }
        if (!data.shopCity.trim()) { setFieldError('Please enter your city.'); return; }
        if (!data.shopState.trim()) { setFieldError('Please enter your state or province.'); return; }
        if (!data.shopZip.trim()) { setFieldError('Please enter your ZIP or postal code.'); return; }
        if (!data.shopPhone.trim()) { setFieldError('Please enter your business phone number.'); return; }
        goTo('confirm');
    };

    const handleSubmit = async () => {
        goTo('submitting');
        setFieldError('');
        try {
            // 1. Create user account
            const userPayload: any = {
                username: data.username,
                email: data.email,
                password: data.password,
                role: data.accountType,
                full_name: data.username,
            };
            const userRes = await axios.post('/api/users', userPayload);
            const createdUser = userRes.data;

            // 2. Login to get token
            const loginForm = new URLSearchParams();
            loginForm.append('username', data.email);
            loginForm.append('password', data.password);
            const tokenRes = await axios.post('/api/auth/token', loginForm, {
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
            });
            const token = tokenRes.data.access_token;

            // 3. Create shop (shop owners only)
            if (data.accountType === 'shop_owner') {
                const slug = data.shopName.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');
                await axios.post('/api/shops/', {
                    name: data.shopName,
                    slug: `${slug}-${Date.now().toString(36)}`,
                    shop_type: data.shopType,
                    description: `${data.shopName} — managed via ZeroQwait`,
                    address: data.shopAddress,
                    city: data.shopCity,
                    state: data.shopState,
                    zip_code: data.shopZip,
                    phone: data.shopPhone,
                    owner_id: createdUser.id,
                }, {
                    headers: { Authorization: `Bearer ${token}` }
                });
                setSuccessMessage(`Welcome, ${data.username}! Your shop "${data.shopName}" is ready. Log in to start managing your queue.`);
            } else {
                setSuccessMessage(`Welcome, ${data.username}! Your account is ready. Log in to start joining queues.`);
            }

            // Store token for convenience
            localStorage.setItem('access_token', token);
            goTo('done');
        } catch (err: any) {
            const detail = err?.response?.data?.detail || 'An unexpected error occurred.';
            setFieldError(detail);
            goTo('error');
        }
    };

    // ── Shared input styles ─────────────────────────────────────────────────
    const inputSx = {
        '& .MuiOutlinedInput-root': {
            bgcolor: theme.inputBg,
            color: theme.text,
            borderRadius: '14px',
            '& fieldset': { borderColor: theme.cardBorder },
            '&:hover fieldset': { borderColor: theme.accent },
            '&.Mui-focused fieldset': { borderColor: theme.accent },
        },
        '& .MuiInputLabel-root': { color: theme.textSecondary },
        '& .MuiInputLabel-root.Mui-focused': { color: theme.accent },
    };

    const primaryBtnSx = {
        borderRadius: '14px',
        bgcolor: theme.accent,
        color: isDarkMode ? '#000' : '#fff',
        fontWeight: 700,
        py: 1.5,
        fontSize: '1rem',
        textTransform: 'none',
        '&:hover': { bgcolor: isDarkMode ? '#f0abfc' : '#a21caf' },
        '&:disabled': { opacity: 0.4 },
    };

    const secondaryBtnSx = {
        borderRadius: '14px',
        color: theme.textSecondary,
        fontWeight: 600,
        textTransform: 'none',
        '&:hover': { bgcolor: isDarkMode ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.04)' },
    };

    // ── Validation icon helper ──────────────────────────────────────────────
    const ValidationIcon: React.FC<{ status: 'idle' | 'checking' | 'available' | 'taken' | 'invalid' }> = ({ status }) => {
        if (status === 'checking') return <CircularProgress size={16} sx={{ color: theme.textSecondary }} />;
        if (status === 'available') return <CheckIcon sx={{ color: '#22c55e', fontSize: 18 }} />;
        if (status === 'taken' || status === 'invalid') return <CloseIcon sx={{ color: '#ef4444', fontSize: 18 }} />;
        return null;
    };

    // ── Progress bar ────────────────────────────────────────────────────────
    const progress = getStepProgress(step, data.accountType);

    // ── Step-specific content ───────────────────────────────────────────────

    const renderContent = () => {
        switch (step) {

            // ── Account Type ────────────────────────────────────────────────
            case 'account_type':
                return (
                    <Stack spacing={3} alignItems="center">
                        <Typography variant="h6" fontWeight={700} sx={{ color: theme.text, textAlign: 'center' }}>
                            How will you use ZeroQwait?
                        </Typography>
                        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} sx={{ width: '100%' }}>
                            {/* Shop Owner Card */}
                            <Box
                                onClick={() => handleSelectAccountType('shop_owner')}
                                sx={{
                                    flex: 1, p: 3, borderRadius: '20px', cursor: 'pointer', textAlign: 'center',
                                    border: `2px solid ${theme.cardBorder}`, bgcolor: theme.cardBg,
                                    transition: 'all 0.25s ease',
                                    '&:hover': { border: `2px solid ${theme.accent}`, transform: 'translateY(-2px)', boxShadow: `0 8px 24px ${theme.accent}33` }
                                }}
                            >
                                <StoreIcon sx={{ fontSize: 44, color: theme.accent, mb: 1 }} />
                                <Typography variant="h6" fontWeight={700} sx={{ color: theme.text }}>Shop Owner</Typography>
                                <Typography variant="body2" sx={{ color: theme.textSecondary, mt: 0.5 }}>
                                    Manage queues, serve more customers
                                </Typography>
                                <Stack direction="row" spacing={1} justifyContent="center" mt={1.5} flexWrap="wrap" gap={0.5}>
                                    <Chip label="Free to start" size="small" sx={{ bgcolor: `${theme.accent}22`, color: theme.accent, fontWeight: 600 }} />
                                    <Chip label="3 shops included" size="small" sx={{ bgcolor: `${theme.accent}22`, color: theme.accent, fontWeight: 600 }} />
                                </Stack>
                            </Box>

                            {/* Customer Card */}
                            <Box
                                onClick={() => handleSelectAccountType('customer')}
                                sx={{
                                    flex: 1, p: 3, borderRadius: '20px', cursor: 'pointer', textAlign: 'center',
                                    border: `2px solid ${theme.cardBorder}`, bgcolor: theme.cardBg,
                                    transition: 'all 0.25s ease',
                                    '&:hover': { border: `2px solid ${theme.accent}`, transform: 'translateY(-2px)', boxShadow: `0 8px 24px ${theme.accent}33` }
                                }}
                            >
                                <PersonIcon sx={{ fontSize: 44, color: theme.accent, mb: 1 }} />
                                <Typography variant="h6" fontWeight={700} sx={{ color: theme.text }}>Customer</Typography>
                                <Typography variant="body2" sx={{ color: theme.textSecondary, mt: 0.5 }}>
                                    Join queues remotely, skip the wait
                                </Typography>
                                <Stack direction="row" spacing={1} justifyContent="center" mt={1.5}>
                                    <Chip label="Always free" size="small" sx={{ bgcolor: `${theme.accent}22`, color: theme.accent, fontWeight: 600 }} />
                                </Stack>
                            </Box>
                        </Stack>
                        <Button variant="text" onClick={() => onClose()} sx={secondaryBtnSx}>
                            Cancel
                        </Button>
                    </Stack>
                );

            // ── Email ───────────────────────────────────────────────────────
            case 'email':
                return (
                    <Stack spacing={3}>
                        <Typography variant="h6" fontWeight={700} sx={{ color: theme.text }}>
                            <EmailIcon sx={{ fontSize: 20, mr: 1, verticalAlign: 'middle', color: theme.accent }} />
                            Your Email Address
                        </Typography>
                        <TextField
                            fullWidth autoFocus
                            label="Email Address"
                            type="email"
                            value={data.email}
                            onChange={e => setData(d => ({ ...d, email: e.target.value }))}
                            onKeyPress={e => e.key === 'Enter' && handleNextEmail()}
                            sx={inputSx}
                            InputProps={{
                                endAdornment: (
                                    <InputAdornment position="end">
                                        <ValidationIcon status={validation.email} />
                                    </InputAdornment>
                                )
                            }}
                            helperText={
                                validation.email === 'taken' ? '❌ Email already registered'
                                    : validation.email === 'invalid' ? '❌ Invalid email format'
                                        : validation.email === 'available' ? '✅ Available'
                                            : ''
                            }
                            FormHelperTextProps={{
                                sx: { color: validation.email === 'available' ? '#22c55e' : '#ef4444' }
                            }}
                        />
                        <Stack direction="row" spacing={2}>
                            <Button fullWidth variant="outlined" onClick={() => goTo('account_type')} sx={secondaryBtnSx}>Back</Button>
                            <Button fullWidth variant="contained"
                                onClick={handleNextEmail}
                                disabled={validation.email === 'taken' || validation.email === 'invalid' || !data.email}
                                sx={primaryBtnSx}
                            >
                                Continue
                            </Button>
                        </Stack>
                    </Stack>
                );

            // ── Username ────────────────────────────────────────────────────
            case 'username':
                return (
                    <Stack spacing={3}>
                        <Typography variant="h6" fontWeight={700} sx={{ color: theme.text }}>
                            <BadgeIcon sx={{ fontSize: 20, mr: 1, verticalAlign: 'middle', color: theme.accent }} />
                            Choose a Username
                        </Typography>
                        <TextField
                            fullWidth autoFocus
                            label="Username"
                            value={data.username}
                            onChange={e => setData(d => ({ ...d, username: e.target.value.toLowerCase().replace(/[^a-z0-9_.-]/g, '') }))}
                            onKeyPress={e => e.key === 'Enter' && handleNextUsername()}
                            sx={inputSx}
                            InputProps={{
                                endAdornment: (
                                    <InputAdornment position="end">
                                        <ValidationIcon status={validation.username} />
                                    </InputAdornment>
                                )
                            }}
                            helperText={
                                validation.username === 'taken' ? '❌ Username already taken'
                                    : validation.username === 'available' ? '✅ Username available'
                                        : 'Lowercase letters, numbers, and _ . - only'
                            }
                            FormHelperTextProps={{
                                sx: {
                                    color: validation.username === 'available' ? '#22c55e'
                                        : validation.username === 'taken' ? '#ef4444'
                                            : theme.textSecondary
                                }
                            }}
                        />
                        <Stack direction="row" spacing={2}>
                            <Button fullWidth variant="outlined" onClick={() => goTo('email')} sx={secondaryBtnSx}>Back</Button>
                            <Button fullWidth variant="contained"
                                onClick={handleNextUsername}
                                disabled={validation.username === 'taken' || !data.username || data.username.length < 3}
                                sx={primaryBtnSx}
                            >
                                Continue
                            </Button>
                        </Stack>
                    </Stack>
                );

            // ── Password ────────────────────────────────────────────────────
            case 'password':
                const strength = data.password.length === 0 ? 0
                    : data.password.length < 8 ? 25
                        : data.password.length < 12 ? 60
                            : /[A-Z]/.test(data.password) && /[0-9]/.test(data.password) ? 100 : 80;
                const strengthColor = strength < 40 ? '#ef4444' : strength < 70 ? '#f59e0b' : '#22c55e';
                const strengthLabel = strength < 40 ? 'Weak' : strength < 70 ? 'Fair' : strength < 90 ? 'Good' : 'Strong';

                return (
                    <Stack spacing={3}>
                        <Typography variant="h6" fontWeight={700} sx={{ color: theme.text }}>
                            <LockIcon sx={{ fontSize: 20, mr: 1, verticalAlign: 'middle', color: theme.accent }} />
                            Create a Password
                        </Typography>
                        <TextField
                            fullWidth autoFocus
                            label="Password"
                            type={showPassword ? 'text' : 'password'}
                            value={data.password}
                            onChange={e => setData(d => ({ ...d, password: e.target.value }))}
                            onKeyPress={e => e.key === 'Enter' && handleNextPassword()}
                            sx={inputSx}
                            InputProps={{
                                endAdornment: (
                                    <InputAdornment position="end">
                                        <IconButton onClick={() => setShowPassword(s => !s)} edge="end" sx={{ color: theme.textSecondary }}>
                                            {showPassword ? <VisibilityOff /> : <Visibility />}
                                        </IconButton>
                                    </InputAdornment>
                                )
                            }}
                        />
                        {data.password.length > 0 && (
                            <Box>
                                <LinearProgress
                                    variant="determinate"
                                    value={strength}
                                    sx={{
                                        height: 6, borderRadius: 3,
                                        bgcolor: isDarkMode ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.08)',
                                        '& .MuiLinearProgress-bar': { bgcolor: strengthColor, borderRadius: 3 }
                                    }}
                                />
                                <Typography variant="caption" sx={{ color: strengthColor, fontWeight: 600, mt: 0.5, display: 'block' }}>
                                    {strengthLabel}
                                </Typography>
                            </Box>
                        )}
                        <Stack direction="row" spacing={2}>
                            <Button fullWidth variant="outlined" onClick={() => goTo('username')} sx={secondaryBtnSx}>Back</Button>
                            <Button fullWidth variant="contained"
                                onClick={handleNextPassword}
                                disabled={data.password.length < 8}
                                sx={primaryBtnSx}
                            >
                                Continue
                            </Button>
                        </Stack>
                    </Stack>
                );

            // ── Shop Name ───────────────────────────────────────────────────
            case 'shop_name':
                return (
                    <Stack spacing={3}>
                        <Typography variant="h6" fontWeight={700} sx={{ color: theme.text }}>
                            <StoreIcon sx={{ fontSize: 20, mr: 1, verticalAlign: 'middle', color: theme.accent }} />
                            Your Business Name
                        </Typography>
                        <TextField
                            fullWidth autoFocus
                            label="Shop / Business Name"
                            value={data.shopName}
                            onChange={e => setData(d => ({ ...d, shopName: e.target.value }))}
                            onKeyPress={e => e.key === 'Enter' && handleNextShopName()}
                            sx={inputSx}
                            InputProps={{
                                endAdornment: (
                                    <InputAdornment position="end">
                                        <ValidationIcon status={validation.shopName} />
                                    </InputAdornment>
                                )
                            }}
                            helperText={
                                validation.shopName === 'taken' ? '❌ A shop with this name already exists'
                                    : validation.shopName === 'available' ? '✅ Name available'
                                        : 'This will be your shop\'s unique URL on ZeroQwait'
                            }
                            FormHelperTextProps={{
                                sx: {
                                    color: validation.shopName === 'available' ? '#22c55e'
                                        : validation.shopName === 'taken' ? '#ef4444'
                                            : theme.textSecondary
                                }
                            }}
                        />
                        <Stack direction="row" spacing={2}>
                            <Button fullWidth variant="outlined" onClick={() => goTo('password')} sx={secondaryBtnSx}>Back</Button>
                            <Button fullWidth variant="contained"
                                onClick={handleNextShopName}
                                disabled={validation.shopName === 'taken' || !data.shopName || data.shopName.length < 2}
                                sx={primaryBtnSx}
                            >
                                Continue
                            </Button>
                        </Stack>
                    </Stack>
                );

            // ── Shop Type ───────────────────────────────────────────────────
            case 'shop_type':
                return (
                    <Stack spacing={3}>
                        <Typography variant="h6" fontWeight={700} sx={{ color: theme.text }}>
                            What type of business?
                        </Typography>
                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1.5 }}>
                            {SHOP_TYPES.map(type => (
                                <Chip
                                    key={type}
                                    label={type}
                                    clickable
                                    onClick={() => setData(d => ({ ...d, shopType: type }))}
                                    sx={{
                                        borderRadius: '12px',
                                        fontWeight: 600,
                                        border: `2px solid ${data.shopType === type ? theme.accent : theme.cardBorder}`,
                                        bgcolor: data.shopType === type ? `${theme.accent}22` : 'transparent',
                                        color: data.shopType === type ? theme.accent : theme.textSecondary,
                                        transition: 'all 0.2s ease',
                                        '&:hover': { border: `2px solid ${theme.accent}` }
                                    }}
                                />
                            ))}
                        </Box>
                        <Stack direction="row" spacing={2}>
                            <Button fullWidth variant="outlined" onClick={() => goTo('shop_name')} sx={secondaryBtnSx}>Back</Button>
                            <Button fullWidth variant="contained"
                                onClick={handleNextShopType}
                                disabled={!data.shopType}
                                sx={primaryBtnSx}
                            >
                                Continue
                            </Button>
                        </Stack>
                    </Stack>
                );

            // ── Shop Address ────────────────────────────────────────────────
            case 'shop_address':
                return (
                    <Stack spacing={2.5}>
                        <Typography variant="h6" fontWeight={700} sx={{ color: theme.text }}>
                            <LocationCityIcon sx={{ fontSize: 20, mr: 1, verticalAlign: 'middle', color: theme.accent }} />
                            Shop Address
                        </Typography>
                        <TextField fullWidth label="Street Address" value={data.shopAddress}
                            onChange={e => setData(d => ({ ...d, shopAddress: e.target.value }))}
                            sx={inputSx} />
                        <Stack direction="row" spacing={2}>
                            <TextField fullWidth label="City" value={data.shopCity}
                                onChange={e => setData(d => ({ ...d, shopCity: e.target.value }))}
                                sx={inputSx} />
                            <TextField fullWidth label="State / Province" value={data.shopState}
                                onChange={e => setData(d => ({ ...d, shopState: e.target.value }))}
                                sx={{ ...inputSx, flex: '0 0 140px' }} />
                        </Stack>
                        <Stack direction="row" spacing={2}>
                            <TextField fullWidth label="ZIP / Postal Code" value={data.shopZip}
                                onChange={e => setData(d => ({ ...d, shopZip: e.target.value }))}
                                sx={inputSx} />
                            <TextField fullWidth label="Business Phone" value={data.shopPhone}
                                onChange={e => setData(d => ({ ...d, shopPhone: e.target.value }))}
                                sx={inputSx} />
                        </Stack>
                        <Stack direction="row" spacing={2}>
                            <Button fullWidth variant="outlined" onClick={() => goTo('shop_type')} sx={secondaryBtnSx}>Back</Button>
                            <Button fullWidth variant="contained" onClick={handleNextShopAddress} sx={primaryBtnSx}>
                                Review
                            </Button>
                        </Stack>
                    </Stack>
                );

            // ── Confirm ─────────────────────────────────────────────────────
            case 'confirm':
                return (
                    <Stack spacing={3}>
                        <Typography variant="h6" fontWeight={700} sx={{ color: theme.text }}>
                            ✅ Review Your Details
                        </Typography>
                        <Box sx={{ p: 2.5, borderRadius: '16px', bgcolor: theme.cardBg, border: `1px solid ${theme.cardBorder}` }}>
                            <Stack spacing={1.5}>
                                <SummaryRow label="Account Type" value={data.accountType === 'shop_owner' ? '🏪 Shop Owner' : '👤 Customer'} theme={theme} />
                                <SummaryRow label="Email" value={data.email} theme={theme} />
                                <SummaryRow label="Username" value={data.username} theme={theme} />
                                <SummaryRow label="Password" value="••••••••" theme={theme} />
                                {data.accountType === 'shop_owner' && (
                                    <>
                                        <Divider sx={{ borderColor: theme.cardBorder, my: 0.5 }} />
                                        <SummaryRow label="Shop Name" value={data.shopName} theme={theme} />
                                        <SummaryRow label="Business Type" value={data.shopType} theme={theme} />
                                        <SummaryRow label="Address" value={`${data.shopAddress}, ${data.shopCity}, ${data.shopState} ${data.shopZip}`} theme={theme} />
                                        <SummaryRow label="Phone" value={data.shopPhone} theme={theme} />
                                    </>
                                )}
                            </Stack>
                        </Box>
                        <Alert severity="info" sx={{
                            borderRadius: '12px',
                            bgcolor: isDarkMode ? 'rgba(99,102,241,0.15)' : 'rgba(99,102,241,0.08)',
                            border: `1px solid rgba(99,102,241,0.3)`,
                            '& .MuiAlert-message': { color: theme.text }
                        }}>
                            {data.accountType === 'shop_owner'
                                ? 'Starting on the Free tier — up to 3 shops and 50 customers per queue.'
                                : 'Free customer account — join queues at any ZeroQwait shop.'}
                        </Alert>
                        <Stack direction="row" spacing={2}>
                            <Button fullWidth variant="outlined"
                                onClick={() => goTo(data.accountType === 'shop_owner' ? 'shop_address' : 'password')}
                                sx={secondaryBtnSx}
                            >
                                Go Back
                            </Button>
                            <Button fullWidth variant="contained" onClick={handleSubmit} sx={primaryBtnSx}>
                                Create Account
                            </Button>
                        </Stack>
                    </Stack>
                );

            // ── Submitting ──────────────────────────────────────────────────
            case 'submitting':
                return (
                    <Stack spacing={3} alignItems="center" justifyContent="center" sx={{ py: 6 }}>
                        <CircularProgress size={64} thickness={3} sx={{ color: theme.accent }} />
                        <Typography variant="h6" sx={{ color: theme.text, fontWeight: 600 }}>
                            Creating your account...
                        </Typography>
                        <Typography variant="body2" sx={{ color: theme.textSecondary, textAlign: 'center' }}>
                            This will only take a moment.
                        </Typography>
                    </Stack>
                );

            // ── Done ────────────────────────────────────────────────────────
            case 'done':
                return (
                    <Fade in>
                        <Stack spacing={3} alignItems="center" sx={{ py: 4, textAlign: 'center' }}>
                            <Box sx={{
                                width: 80, height: 80, borderRadius: '50%',
                                bgcolor: '#22c55e22', display: 'flex', alignItems: 'center', justifyContent: 'center',
                                animation: 'popIn 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275)',
                                '@keyframes popIn': {
                                    '0%': { transform: 'scale(0)', opacity: 0 },
                                    '100%': { transform: 'scale(1)', opacity: 1 }
                                }
                            }}>
                                <CheckCircleOutlineIcon sx={{ fontSize: 48, color: '#22c55e' }} />
                            </Box>
                            <Typography variant="h5" fontWeight={700} sx={{ color: theme.text }}>
                                You're all set! 🎉
                            </Typography>
                            <Typography variant="body1" sx={{ color: theme.textSecondary, maxWidth: '340px' }}>
                                {successMessage}
                            </Typography>
                            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} sx={{ width: '100%', maxWidth: '380px' }}>
                                <Button
                                    fullWidth variant="contained"
                                    href="/login"
                                    sx={primaryBtnSx}
                                >
                                    Sign In Now
                                </Button>
                                <Button
                                    fullWidth variant="outlined"
                                    onClick={() => onClose(true)}
                                    sx={secondaryBtnSx}
                                >
                                    Explore First
                                </Button>
                            </Stack>
                        </Stack>
                    </Fade>
                );

            // ── Error ───────────────────────────────────────────────────────
            case 'error':
                return (
                    <Stack spacing={3} alignItems="center" sx={{ py: 4, textAlign: 'center' }}>
                        <Box sx={{
                            width: 80, height: 80, borderRadius: '50%',
                            bgcolor: '#ef444422', display: 'flex', alignItems: 'center', justifyContent: 'center'
                        }}>
                            <ErrorOutlineIcon sx={{ fontSize: 48, color: '#ef4444' }} />
                        </Box>
                        <Typography variant="h6" fontWeight={700} sx={{ color: theme.text }}>
                            Something went wrong
                        </Typography>
                        <Alert severity="error" sx={{ borderRadius: '12px', textAlign: 'left' }}>
                            {fieldError}
                        </Alert>
                        <Stack direction="row" spacing={2} sx={{ width: '100%' }}>
                            <Button fullWidth variant="outlined" onClick={() => onClose()} sx={secondaryBtnSx}>
                                Cancel
                            </Button>
                            <Button fullWidth variant="contained" onClick={() => goTo('confirm')} sx={primaryBtnSx}>
                                Try Again
                            </Button>
                        </Stack>
                    </Stack>
                );

            default:
                return null;
        }
    };

    return (
        <Box sx={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column' }}>
            {/* Header */}
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 3 }}>
                <Box>
                    <Typography variant="h5" fontWeight={800} sx={{ color: theme.text }}>
                        Join ZeroQwait
                    </Typography>
                    <Typography variant="caption" sx={{ color: theme.textSecondary, letterSpacing: '0.05em' }}>
                        {step === 'done' ? 'Account created!' : step === 'error' ? 'Registration failed' : `Step ${getStepProgress(step, data.accountType)}%`}
                    </Typography>
                </Box>
                <IconButton onClick={() => onClose()} size="small" sx={{ color: theme.textSecondary }}>
                    <CloseIcon />
                </IconButton>
            </Box>

            {/* Progress bar */}
            {step !== 'done' && step !== 'error' && step !== 'submitting' && (
                <Box sx={{ mb: 3 }}>
                    <LinearProgress
                        variant="determinate"
                        value={progress}
                        sx={{
                            height: 4, borderRadius: 2,
                            bgcolor: isDarkMode ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)',
                            '& .MuiLinearProgress-bar': { bgcolor: theme.accent, borderRadius: 2, transition: 'transform 0.6s ease' }
                        }}
                    />
                </Box>
            )}

            {/* Field error banner (non-error step) */}
            {fieldError && step !== 'error' && (
                <Fade in>
                    <Alert severity="error" sx={{ mb: 2, borderRadius: '12px' }} onClose={() => setFieldError('')}>
                        {fieldError}
                    </Alert>
                </Fade>
            )}

            {/* Step Content */}
            <Box sx={{ flex: 1, overflowY: 'auto', pr: 0.5 }}>
                <Fade in key={step} timeout={300}>
                    <Box>{renderContent()}</Box>
                </Fade>
            </Box>
        </Box>
    );
};

// ── Summary Row sub-component ─────────────────────────────────────────────────

const SummaryRow: React.FC<{ label: string; value: string; theme: any }> = ({ label, value, theme }) => (
    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 2 }}>
        <Typography variant="body2" sx={{ color: theme.textSecondary, fontWeight: 500, flexShrink: 0 }}>
            {label}
        </Typography>
        <Typography variant="body2" sx={{ color: theme.text, fontWeight: 600, textAlign: 'right', wordBreak: 'break-all' }}>
            {value}
        </Typography>
    </Box>
);

export default VoiceRegistrationFlow;
