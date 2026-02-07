import React, { useState, useEffect } from "react";
import { Link as RouterLink, useNavigate } from "react-router-dom";
import {
    Container,
    Typography,
    Box,
    TextField,
    Button,
    Link,
    Paper,
    Avatar,
    Alert,
    CircularProgress,
    Chip,
} from "@mui/material";
import StoreIcon from "@mui/icons-material/Store";
import { useAuth } from "../../../contexts/AuthContext";
import axios from "axios";

const RegisterShopOwnerPage: React.FC = () => {
    const [formData, setFormData] = useState({
        username: "",
        email: "",
        password: "",
        confirmPassword: "",
    });
    const [formErrors, setFormErrors] = useState<{ [key: string]: string }>({});
    const [formSubmissionError, setFormSubmissionError] = useState('');
    const { register, loading, error, isAuthenticated } = useAuth();
    const navigate = useNavigate();

    // Navigate to shop registration after successful signup
    React.useEffect(() => {
        if (isAuthenticated && !loading && !error) {
            navigate("/register-shop");
        }
    }, [isAuthenticated, loading, error, navigate]);

    const validateForm = () => {
        const errors: { [key: string]: string } = {};

        if (!formData.username.trim()) {
            errors.username = "Username is required";
        }

        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!formData.email.trim()) {
            errors.email = "Email is required";
        } else if (!emailRegex.test(formData.email)) {
            errors.email = "Invalid email format";
        }

        if (!formData.password) {
            errors.password = "Password is required";
        } else if (formData.password.length < 6) {
            errors.password = "Password must be at least 6 characters";
        }

        if (formData.password !== formData.confirmPassword) {
            errors.confirmPassword = "Passwords do not match";
        }

        setFormErrors(errors);
        return Object.keys(errors).length === 0;
    };

    // Real-time username validation
    useEffect(() => {
        const checkUsername = async () => {
            if (formData.username && formData.username.length >= 3) {

                try {
                    const response = await axios.get(`/check-username/${formData.username}`);
                    if (!response.data.available) {
                        setFormErrors(prev => ({ ...prev, username: "Username already taken" }));
                    } else {
                        setFormErrors(prev => {
                            const { username, ...rest } = prev;
                            return rest;
                        });
                    }
                } catch (err) {
                    // Silently fail - user will get error on submit if needed
                } finally {
                    // setCheckingUsername(false);
                }
            }
        };

        const timer = setTimeout(checkUsername, 500);
        return () => clearTimeout(timer);
    }, [formData.username]);

    // Real-time email validation
    useEffect(() => {
        const checkEmail = async () => {
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (formData.email && emailRegex.test(formData.email)) {

                try {
                    const response = await axios.get(`/check-email/${formData.email}`);
                    if (!response.data.available) {
                        setFormErrors(prev => ({ ...prev, email: "Email already registered" }));
                    } else {
                        setFormErrors(prev => {
                            const { email, ...rest } = prev;
                            return rest;
                        });
                    }
                } catch (err) {
                    // Silently fail - user will get error on submit if needed
                } finally {
                    // setCheckingEmail(false);
                }
            }
        };

        const timer = setTimeout(checkEmail, 500);
        return () => clearTimeout(timer);
    }, [formData.email]);

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setFormData({ ...formData, [e.target.name]: e.target.value });
        // Don't clear errors on change - let real-time validation handle it
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();

        if (validateForm()) {
            try {
                await register(formData.username, formData.email, formData.password, "shop_owner");
            } catch (err) {
                // Error displayed via AuthContext - stay on page
            }
        }
    };

    return (
        <Container component="main" maxWidth="sm">
            <Box
                sx={{
                    marginTop: 8,
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                }}
            >
                <Paper elevation={3} sx={{ p: 4, width: "100%" }}>
                    <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
                        <Avatar sx={{ m: 1, bgcolor: "secondary.main" }}>
                            <StoreIcon />
                        </Avatar>
                        <Typography component="h1" variant="h5">
                            Start Managing Your Queue
                        </Typography>
                        <Typography variant="body2" color="textSecondary" sx={{ mt: 1, textAlign: "center" }}>
                            Create your business account and grow your business
                        </Typography>
                    </Box>

                    {/* Free tier info */}
                    <Alert severity="info" sx={{ mt: 3 }}>
                        <Box sx={{ display: "flex", alignItems: "center", gap: 1, flexWrap: "wrap" }}>
                            <Typography variant="body2">
                                Starting with <strong>Free Tier</strong>
                            </Typography>
                            <Chip label="Up to 3 shops" size="small" color="primary" variant="outlined" />
                            <Chip label="50 customers per queue" size="small" color="primary" variant="outlined" />
                        </Box>
                    </Alert>

                    {formSubmissionError && (
                        <Alert severity="error" sx={{ mt: 2 }}>
                            {formSubmissionError}
                        </Alert>
                    )}

                    <Box component="form" onSubmit={handleSubmit} sx={{ mt: 3 }}>
                        <TextField
                            required
                            fullWidth
                            id="username"
                            label="Username"
                            name="username"
                            autoComplete="username"
                            value={formData.username}
                            onChange={handleChange}
                            error={!!formErrors.username}
                            helperText={formErrors.username}
                            disabled={loading}
                            sx={{ mb: 2 }}
                        />

                        <TextField
                            required
                            fullWidth
                            id="email"
                            label="Business Email"
                            name="email"
                            autoComplete="email"
                            value={formData.email}
                            onChange={handleChange}
                            error={!!formErrors.email}
                            helperText={formErrors.email}
                            disabled={loading}
                            sx={{ mb: 2 }}
                        />

                        <TextField
                            required
                            fullWidth
                            name="password"
                            label="Password"
                            type="password"
                            id="password"
                            autoComplete="new-password"
                            value={formData.password}
                            onChange={handleChange}
                            error={!!formErrors.password}
                            helperText={formErrors.password}
                            disabled={loading}
                            sx={{ mb: 2 }}
                        />

                        <TextField
                            required
                            fullWidth
                            name="confirmPassword"
                            label="Confirm Password"
                            type="password"
                            id="confirmPassword"
                            value={formData.confirmPassword}
                            onChange={handleChange}
                            error={!!formErrors.confirmPassword}
                            helperText={formErrors.confirmPassword}
                            disabled={loading}
                            sx={{ mb: 3 }}
                        />

                        <Button
                            type="submit"
                            fullWidth
                            variant="contained"
                            color="secondary"
                            size="large"
                            disabled={loading}
                            sx={{ mb: 2 }}
                        >
                            {loading ? <CircularProgress size={24} /> : "Create Business Account"}
                        </Button>

                        <Box sx={{ textAlign: "center" }}>
                            <Link component={RouterLink} to="/login" variant="body2">
                                Already have an account? Sign in
                            </Link>
                        </Box>

                        <Box sx={{ textAlign: "center", mt: 1 }}>
                            <Link component={RouterLink} to="/register/customer" variant="body2">
                                Just want to join queues? Register as customer
                            </Link>
                        </Box>

                        <Box sx={{ textAlign: "center", mt: 2 }}>
                            <Link component={RouterLink} to="/pricing" variant="body2">
                                View pricing plans
                            </Link>
                        </Box>
                    </Box>
                </Paper>
            </Box>
        </Container>
    );
};

export default RegisterShopOwnerPage;
