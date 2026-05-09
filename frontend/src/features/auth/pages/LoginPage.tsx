import React, { useState } from "react";
import { Link as RouterLink, useNavigate } from "react-router-dom";
import axios from "axios";
import { Loader2, LockKeyhole } from "lucide-react";
import { useAuth } from "../../../contexts/AuthContext";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const LoginPage: React.FC = () => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [formErrors, setFormErrors] = useState<{ username?: string; password?: string }>({});
  const { login, loading, error, isAuthenticated, user } = useAuth();
  const navigate = useNavigate();

  React.useEffect(() => {
    console.log("[LoginPage] useEffect triggered", { isAuthenticated, loading, error, user });
    if (isAuthenticated && !loading && !error && user) {
      const role = user.role?.toString().toUpperCase().trim() || "";
      console.log("[LoginPage] Normalized role check:", `"${role}"`);

      if (role === "SHOP_OWNER") {
        void redirectToShopDashboard();
      } else if (role === "EMPLOYEE") {
        console.log("[LoginPage] Redirecting to /employee-dashboard");
        navigate("/employee-dashboard");
      } else if (role === "SUPER_ADMIN") {
        console.log("[LoginPage] Redirecting to /admin (HARD NAV)");
        window.location.href = "/admin";
      } else {
        console.log("[LoginPage] Redirecting to home (Role mismatch)");
        navigate("/");
      }
    }
  }, [isAuthenticated, loading, error, user, navigate]);

  const redirectToShopDashboard = async () => {
    try {
      const token = localStorage.getItem("token");
      if (!token) {
        navigate("/dashboard");
        return;
      }

      const response = await axios.get("/shops/my-shops", {
        headers: { Authorization: `Bearer ${token}` },
      });

      const shops = response.data;
      console.log("[LoginPage] Shops fetched:", shops);

      if (shops && shops.length > 0) {
        const shop = shops[0];
        const shopSlug = shop.slug || shop.name.toLowerCase().replace(/\s+/g, "-");
        console.log("[LoginPage] Shop slug:", shopSlug);

        const currentHost = window.location.hostname;
        const protocol = window.location.protocol;
        let newUrl = "";

        if (currentHost.includes("nip.io") || currentHost.includes("np.io")) {
          const isBaseDomain = currentHost.match(/^\d+\.\d+\.\d+\.\d+\.(nip|np)\.io$/);

          if (isBaseDomain) {
            newUrl = `${protocol}//${shopSlug}.${currentHost}`;
          } else {
            const ipSuffixMatch = currentHost.match(/(\d+\.\d+\.\d+\.\d+\.(nip|np)\.io)$/);
            if (ipSuffixMatch) {
              const baseHost = ipSuffixMatch[1];
              newUrl = `${protocol}//${shopSlug}.${baseHost}`;
            } else {
              const parts = currentHost.split(".");
              if (parts.length >= 6) {
                const baseParts = parts.slice(-6);
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
          const parts = currentHost.split(".");
          if (parts[0] === "www") {
            newUrl = `${protocol}//${shopSlug}.${parts.slice(1).join(".")}`;
          } else if (parts.length === 2) {
            newUrl = `${protocol}//${shopSlug}.${currentHost}`;
          } else {
            const baseDomain = parts.slice(-2).join(".");
            newUrl = `${protocol}//${shopSlug}.${baseDomain}`;
          }
        }

        newUrl += `/dashboard?token=${token}`;
        console.log("[LoginPage] Redirecting to subdomain:", newUrl);
        window.location.href = newUrl;
        return;
      }
    } catch (redirectError) {
      console.error("[LoginPage] Error redirecting:", redirectError);
    }

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
    }
  };

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-4 py-12">
      <Card>
        <CardHeader className="items-center text-center">
          <Avatar className="mb-2 bg-primary text-primary-foreground">
            <AvatarFallback>
              <LockKeyhole className="size-5" />
            </AvatarFallback>
          </Avatar>
          <CardTitle>Sign in</CardTitle>
        </CardHeader>
        <CardContent>
          {error && (
            <Alert variant="destructive" className="mb-4">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-2">
              <Label htmlFor="username">Username</Label>
              <Input
                id="username"
                name="username"
                autoComplete="username"
                autoFocus
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                aria-invalid={!!formErrors.username}
                disabled={loading}
              />
              {formErrors.username && <p className="text-sm text-destructive">{formErrors.username}</p>}
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                aria-invalid={!!formErrors.password}
                disabled={loading}
              />
              {formErrors.password && <p className="text-sm text-destructive">{formErrors.password}</p>}
            </div>

            <Button type="submit" disabled={loading}>
              {loading && <Loader2 data-icon="inline-start" className="animate-spin" />}
              Sign In
            </Button>

            <div className="flex flex-col gap-2 text-sm sm:flex-row sm:justify-between">
              <RouterLink className="text-primary hover:underline" to="/forgot-password">
                Forgot password?
              </RouterLink>
              <RouterLink className="text-primary hover:underline" to="/pricing">
                Don't have an account? Sign Up
              </RouterLink>
            </div>
          </form>
        </CardContent>
      </Card>
    </main>
  );
};

export default LoginPage;
