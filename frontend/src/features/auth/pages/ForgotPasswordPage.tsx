import React, { useState } from 'react';
import {
    Typography,
    TextField,
    Button,
    Box,
    Alert,
    Stack,
} from '@mui/material';
import LockOutlinedIcon from '@mui/icons-material/LockOutlined';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import AuthPageShell from '../components/AuthPageShell';



const ForgotPasswordPage: React.FC = () => {
    const navigate = useNavigate();
    const [email, setEmail] = useState('');
    const [loading, setLoading] = useState(false);
    const [success, setSuccess] = useState(false);
    const [error, setError] = useState('');

    const submitResetRequest = async () => {
        setLoading(true);
        setError('');

        try {
            await axios.post(`/auth/forgot-password`, null, {
                params: { email }
            });
            setSuccess(true);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to send reset email');
        } finally {
            setLoading(false);
        }
    };

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        void submitResetRequest();
    };

    if (success) {
        return (
            <AuthPageShell
                icon={<LockOutlinedIcon />}
                iconBgColor="success.main"
                title="Check Your Email"
                description="If an account exists with that email address, ZeroQwait will send password reset instructions."
            >
                <Stack spacing={2}>
                    <Alert severity="success">
                        If an account exists with that email, we&apos;ve sent password reset instructions.
                    </Alert>
                    <Typography variant="body2" color="text.secondary">
                        Check your inbox for the reset link. The link expires in 1 hour.
                    </Typography>
                    <Button
                        fullWidth
                        variant="contained"
                        onClick={() => navigate('/login')}
                    >
                        Back to Login
                    </Button>
                </Stack>
            </AuthPageShell>
        );
    }

    return (
        <AuthPageShell
            icon={<LockOutlinedIcon />}
            iconBgColor="error.main"
            title="Reset Password"
            description="Enter your email address and ZeroQwait will send you a secure reset link."
        >
            <Box component="form" onSubmit={handleSubmit}>
                <Stack spacing={2}>
                    {error ? <Alert severity="error">{error}</Alert> : null}
                    <TextField
                        required
                        fullWidth
                        id="email"
                        label="Email Address"
                        name="email"
                        autoComplete="email"
                        autoFocus
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                    />
                    <Button
                        type="submit"
                        fullWidth
                        variant="contained"
                        disabled={loading}
                        size="large"
                        onClick={() => {
                            if (!loading) {
                                void submitResetRequest();
                            }
                        }}
                    >
                        {loading ? 'Sending...' : 'Send Reset Link'}
                    </Button>
                    <Button
                        fullWidth
                        variant="text"
                        onClick={() => navigate('/login')}
                    >
                        Back to Login
                    </Button>
                </Stack>
            </Box>
        </AuthPageShell>
    );
};

export default ForgotPasswordPage;
