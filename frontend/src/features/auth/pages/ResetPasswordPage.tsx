import React, { useState, useEffect } from 'react';
import {
    Typography,
    TextField,
    Button,
    Box,
    Alert,
    Stack,
} from '@mui/material';
import LockResetIcon from '@mui/icons-material/LockReset';
import { useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import AuthPageShell from '../components/AuthPageShell';



const ResetPasswordPage: React.FC = () => {
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();
    const [token, setToken] = useState('');
    const [newPassword, setNewPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [loading, setLoading] = useState(false);
    const [success, setSuccess] = useState(false);
    const [error, setError] = useState('');

    useEffect(() => {
        const tokenParam = searchParams.get('token');
        if (!tokenParam) {
            setError('Invalid reset link. Please request a new password reset.');
        } else {
            setToken(tokenParam);
        }
    }, [searchParams]);

    const submitPasswordReset = async () => {
        setError('');

        // Validate passwords match
        if (newPassword !== confirmPassword) {
            setError('Passwords do not match');
            return;
        }

        // Validate password length
        if (newPassword.length < 6) {
            setError('Password must be at least 6 characters long');
            return;
        }

        setLoading(true);

        try {
            await axios.post(`/auth/reset-password`, null, {
                params: {
                    token,
                    new_password: newPassword
                }
            });
            setSuccess(true);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to reset password');
        } finally {
            setLoading(false);
        }
    };

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        void submitPasswordReset();
    };

    if (success) {
        return (
            <AuthPageShell
                icon={<LockResetIcon />}
                iconBgColor="success.main"
                title="Password Reset Successful"
                description="Your password has been updated. You can sign back in immediately with the new one."
            >
                <Stack spacing={2}>
                    <Alert severity="success">
                        Your password has been reset successfully.
                    </Alert>
                    <Button
                        fullWidth
                        variant="contained"
                        onClick={() => navigate('/login')}
                    >
                        Go to Login
                    </Button>
                </Stack>
            </AuthPageShell>
        );
    }

    return (
        <AuthPageShell
            icon={<LockResetIcon />}
            title="Set New Password"
            description="Enter a new password below. Reset links are single-use and expire after a short time."
        >
            <Box component="form" onSubmit={handleSubmit}>
                <Stack spacing={2}>
                    {error ? <Alert severity="error">{error}</Alert> : null}
                    <TextField
                        required
                        fullWidth
                        name="newPassword"
                        label="New Password"
                        type="password"
                        id="newPassword"
                        autoComplete="new-password"
                        value={newPassword}
                        onChange={(e) => setNewPassword(e.target.value)}
                        disabled={!token}
                    />
                    <TextField
                        required
                        fullWidth
                        name="confirmPassword"
                        label="Confirm New Password"
                        type="password"
                        id="confirmPassword"
                        autoComplete="new-password"
                        value={confirmPassword}
                        onChange={(e) => setConfirmPassword(e.target.value)}
                        disabled={!token}
                    />
                    <Button
                        type="submit"
                        fullWidth
                        variant="contained"
                        disabled={loading || !token}
                        size="large"
                        onClick={() => {
                            if (!loading && token) {
                                void submitPasswordReset();
                            }
                        }}
                    >
                        {loading ? 'Resetting...' : 'Reset Password'}
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

export default ResetPasswordPage;
