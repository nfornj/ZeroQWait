import React, { useState } from "react";
import { Link as RouterLink, useNavigate } from "react-router-dom";
import axios from "axios";
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
        // Try to redirect to shop subdomain, but fallback to regular dashboard
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
      if (!token) {
        navigate("/dashboard");
        return;
      }

      // Fetch user's shops using axios (uses configured baseURL)
      const response = await axios.get("/shops/my-shops", {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      const shops = response.data;
      console.log("[LoginPage] Shops fetched:", shops);

      if (shops && shops.length > 0) {
        const shop = shops[0];
        // The shop should have a slug - use it or generate from name
        const shopSlug = shop.slug || shop.name.toLowerCase().replace(/\s+/g, "-");

        console.log("[LoginPage] Shop slug:", shopSlug);

        // Build the subdomain URL
        const currentHost = window.location.hostname;
        const protocol = window.location.protocol;
        let newUrl = "";

        if (currentHost.includes("nip.io") || currentHost.includes("np.io")) {
          // nip.io / np.io URLs logic
          // Check if we are already on a subdomain or the base IP
          // Base IP format: 192.168.2.88.nip.io or 192.168.2.88.np.io
          const isBaseDomain = currentHost.match(/^\d+\.\d+\.\d+\.\d+\.(nip|np)\.io$/);

          if (isBaseDomain) {
            // We are on the base, prepend slug
            newUrl = `${protocol}//${shopSlug}.${currentHost}`;
          } else {
            // We might be on www.192... or another subdomain.
            // We want to REPLACE the subdomain with the shop slug.
            // Strategy: Find the part that looks like an IP + suffix
            const ipSuffixMatch = currentHost.match(/(\d+\.\d+\.\d+\.\d+\.(nip|np)\.io)$/);
            if (ipSuffixMatch) {
              const baseHost = ipSuffixMatch[1];
              newUrl = `${protocol}//${shopSlug}.${baseHost}`;
            } else {
              // Fallback: just append if we can't parse it well, or replace first part
              const parts = currentHost.split(".");
              if (parts.length >= 6) {
                const baseParts = parts.slice(-6); // loose heuristic
                const baseHost = baseParts.join(".");
                newUrl = `${protocol}//${shopSlug}.${baseHost}`;
              } else {
                newUrl = `${protocol}//${shopSlug}.${currentHost}`;
              }
            }
          }
        } else if (currentHost === "localhost" || currentHost === "127.0.0.1") {
          console.log("[LoginPage] Localhost detected, navigating to /dashboard");
          navigate("/dashboard");
          return;
        } else {
          // Regular domain logic
          const parts = currentHost.split(".");
          // If 2 parts (example.com), prepend.
          // If > 2 parts (www.example.com), replace first part? 
          // Let's assume we always prepend to the "root" domain.
          // Ideally we should know the root domain.
          // For now, if it starts with www, replace it.
          if (parts[0] === "www") {
            newUrl = `${protocol}//${shopSlug}.${parts.slice(1).join(".")}`;
          } else if (parts.length === 2) {
            newUrl = `${protocol}//${shopSlug}.${currentHost}`;
          } else {
            // Assume we are on a subdomain, replace it? Or prepend?
            // Safest to assume we are replacing the current subdomain if it exists
            // or prepending if we are at root.
            // Let's just prepend to the *registrable* domain if possible.
            // Simple heuristic: keep last 2 parts.
            const baseDomain = parts.slice(-2).join(".");
            newUrl = `${protocol}//${shopSlug}.${baseDomain}`;
          }
        }

        newUrl += `/dashboard?token=${token}`;
        console.log("[LoginPage] Redirecting to subdomain:", newUrl);
        window.location.href = newUrl;
        return;
      }
    } catch (error) {
      console.error("[LoginPage] Error redirecting:", error);
    }

    // Fallback
    console.log("[LoginPage] Fallback: navigating to /dashboard");
    navigate("/dashboard");
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
          <Box justifyContent="space-between">
            <Box>
              <Link
                component={RouterLink}
                to="/forgot-password"
                variant="body2"
              >
                Forgot password?
              </Link>
            </Box>
            <Box>
              <Link component={RouterLink} to="/pricing" variant="body2">
                {"Don't have an account? Sign Up"}
              </Link>
            </Box>
          </Box>
        </Box>
      </Paper>
    </Container>
  );
};

export default LoginPage;
