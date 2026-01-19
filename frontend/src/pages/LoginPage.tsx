import React, { useState } from "react";
import { Link as RouterLink, useNavigate } from "react-router-dom";
import {
  Container,
  Typography,
  Box,
  TextField,
  Button,
  Link,
  Grid,
  Paper,
  Avatar,
  Alert,
  CircularProgress,
} from "@mui/material";
import LockOutlinedIcon from "@mui/icons-material/LockOutlined";
import { useAuth } from "../contexts/AuthContext";

const LoginPage: React.FC = () => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [formErrors, setFormErrors] = useState<{
    username?: string;
    password?: string;
  }>({});
  const { login, loading, error, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  const { user } = useAuth();

  // Navigate based on user role after successful login
  React.useEffect(() => {
    console.log("[LoginPage] useEffect triggered", {
      isAuthenticated,
      loading,
      error,
      user,
    });
    if (isAuthenticated && !loading && !error && user) {
      console.log("[LoginPage] User role:", user.role);
      if (user.role === "shop_owner") {
        // Redirect to shop subdomain dashboard
        redirectToShopDashboard();
      } else if (user.role === "employee") {
        console.log("[LoginPage] Redirecting to /employee-dashboard");
        navigate("/employee-dashboard");
      } else {
        console.log("[LoginPage] Redirecting to home");
        navigate("/");
      }
    }
  }, [isAuthenticated, loading, error, user, navigate]);

  // Function to redirect to shop-specific subdomain
  const redirectToShopDashboard = async () => {
    try {
      const token = localStorage.getItem("token");
      if (!token) return;

      // Build API URL correctly - use relative path
      const apiUrl = "/api";

      // Fetch user's shops
      const response = await fetch(`${apiUrl}/shops/my-shops`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const shops = await response.json();
        console.log("[LoginPage] Shops fetched:", shops);
        if (shops && shops.length > 0) {
          const shop = shops[0];
          const shopSlug =
            shop.slug || shop.name.toLowerCase().replace(/\s+/g, "-");

          console.log("[LoginPage] Redirecting to shop:", shopSlug);

          // Get current host parts
          const currentHost = window.location.hostname;
          const hostParts = currentHost.split(".");

          // Build new subdomain URL
          let newUrl = `http://${shopSlug}.`;
          if (currentHost.includes("nip.io")) {
            // For nip.io URLs: shop.192.168.2.88.nip.io
            newUrl += hostParts.slice(-3).join(".");
          } else if (currentHost.includes("localhost")) {
            // For localhost: shop.localhost
            newUrl += "localhost";
          } else {
            // For other domains: shop.yourdomain.com
            newUrl += hostParts.slice(-2).join(".");
          }

          newUrl += "/dashboard";
          console.log("[LoginPage] Redirecting to:", newUrl);
          window.location.href = newUrl;
        }
      }
    } catch (error) {
      console.error("Error fetching shops:", error);
      // Fallback to regular dashboard if fetch fails
      navigate("/dashboard");
    }
  };

  const validateForm = () => {
    const errors: { username?: string; password?: string } = {};
    let isValid = true;

    if (!username.trim()) {
      errors.username = "Username is required";
      isValid = false;
    }

    if (!password) {
      errors.password = "Password is required";
      isValid = false;
    }

    setFormErrors(errors);
    return isValid;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (validateForm()) {
      await login(username, password);
      // Navigation will happen automatically via useEffect if login succeeds
    }
  };

  return (
    <Container component="main" maxWidth="xs">
      <Paper
        elevation={3}
        sx={{
          mt: 8,
          p: 4,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
        }}
      >
        <Avatar sx={{ m: 1, bgcolor: "primary.main" }}>
          <LockOutlinedIcon />
        </Avatar>
        <Typography component="h1" variant="h5">
          Sign in
        </Typography>

        {error && (
          <Alert severity="error" sx={{ width: "100%", mt: 2 }}>
            {error}
          </Alert>
        )}

        <Box
          component="form"
          onSubmit={handleSubmit}
          sx={{ mt: 1, width: "100%" }}
        >
          <TextField
            margin="normal"
            required
            fullWidth
            id="username"
            label="Username"
            name="username"
            autoComplete="username"
            autoFocus
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            error={!!formErrors.username}
            helperText={formErrors.username}
            disabled={loading}
          />
          <TextField
            margin="normal"
            required
            fullWidth
            name="password"
            label="Password"
            type="password"
            id="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            error={!!formErrors.password}
            helperText={formErrors.password}
            disabled={loading}
          />
          <Button
            type="submit"
            fullWidth
            variant="contained"
            sx={{ mt: 3, mb: 2 }}
            disabled={loading}
          >
            {loading ? <CircularProgress size={24} /> : "Sign In"}
          </Button>
          <Grid container justifyContent="space-between">
            <Grid item>
              <Link
                component={RouterLink}
                to="/forgot-password"
                variant="body2"
              >
                Forgot password?
              </Link>
            </Grid>
            <Grid item>
              <Link component={RouterLink} to="/pricing" variant="body2">
                {"Don't have an account? Sign Up"}
              </Link>
            </Grid>
          </Grid>
        </Box>
      </Paper>
    </Container>
  );
};

export default LoginPage;
