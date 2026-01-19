import React, { createContext, useState, useEffect, useContext } from "react";
import axios from "axios";
import { isTokenExpired } from "../utils/authHelpers";

interface User {
  id: number;
  username: string;
  email: string;
  role: "customer" | "shop_owner" | "employee";
  profile_photo_url?: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (
    username: string,
    email: string,
    password: string,
    role?: "customer" | "shop_owner"
  ) => Promise<void>;
  logout: () => void;
  loading: boolean;
  error: string | null;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(
    localStorage.getItem("token")
  );
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(!!token);

  // Define logout early so it can be used in useEffects
  const logout = React.useCallback(() => {
    localStorage.removeItem("token");
    setToken(null);
    setUser(null);
    setIsAuthenticated(false);
  }, []);

  // Check token expiration on mount and periodically
  useEffect(() => {
    // Check for token in URL (passed from cross-domain redirect)
    const params = new URLSearchParams(window.location.search);
    const urlToken = params.get("token");

    if (urlToken) {
      console.log("[AuthContext] Token found in URL, saving to localStorage");
      localStorage.setItem("token", urlToken);
      setToken(urlToken);
      setIsAuthenticated(true);

      // Clean URL without reloading
      const newUrl = window.location.pathname;
      window.history.replaceState({}, document.title, newUrl);
    }

    const checkTokenExpiration = () => {
      const storedToken = localStorage.getItem('token');
      if (storedToken && isTokenExpired(storedToken)) {
        logout();
        window.location.href = '/login';
      }
    };

    // Check immediately on mount (if no URL token was just set)
    if (!urlToken) {
      checkTokenExpiration();
    }

    // Check every minute
    const interval = setInterval(checkTokenExpiration, 60000);

    return () => clearInterval(interval);
  }, []);

  // Set up axios interceptors for authentication
  useEffect(() => {
    // Request interceptor - add token to headers
    const requestInterceptor = axios.interceptors.request.use(
      (config) => {
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor - handle 401 Unauthorized
    const responseInterceptor = axios.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response?.status === 401) {
          // Token expired or invalid - auto logout
          logout();
          // Redirect to login page
          window.location.href = '/login';
        }
        return Promise.reject(error);
      }
    );

    return () => {
      axios.interceptors.request.eject(requestInterceptor);
      axios.interceptors.response.eject(responseInterceptor);
    };
  }, [token, logout]);

  // Fetch user data if token exists
  useEffect(() => {
    const fetchUser = async () => {
      if (token) {
        try {
          setLoading(true);
          console.log("[AuthContext] Fetching user data with token:", token.substring(0, 20) + "...");
          const response = await axios.get("/users/me");
          console.log("[AuthContext] User data received:", response.data);
          setUser(response.data);
          setIsAuthenticated(true);
        } catch (err: any) {
          console.error("[AuthContext] Error fetching user:", err.response?.status, err.response?.data);
          // Only logout if it's not a 401 (interceptor handles that)
          if (err.response?.status !== 401) {
            logout();
          }
        } finally {
          setLoading(false);
        }
      }
    };

    fetchUser();
  }, [token, logout]);

  const login = async (username: string, password: string) => {
    try {
      setLoading(true);
      setError(null);

      const formData = new FormData();
      formData.append("username", username);
      formData.append("password", password);

      const response = await axios.post("/auth/token", formData);
      const { access_token } = response.data;

      localStorage.setItem("token", access_token);
      setToken(access_token);

      // Fetch user data
      const userResponse = await axios.get("/users/me", {
        headers: { Authorization: `Bearer ${access_token}` },
      });

      setUser(userResponse.data);
      setIsAuthenticated(true);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Login failed");
    } finally {
      setLoading(false);
    }
  };

  const register = async (
    username: string,
    email: string,
    password: string,
    role: "customer" | "shop_owner" = "customer"
  ) => {
    try {
      setLoading(true);
      setError(null);

      await axios.post("/users", {
        username,
        email,
        password,
        role,
      });

      // Login after successful registration
      await login(username, password);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Registration failed");
      throw err; // Re-throw to prevent navigation
    } finally {
      setLoading(false);
    }
  };

  console.log("[AuthContext] Current state:", { user, token: token ? token.substring(0, 20) + "..." : null, isAuthenticated, loading });

  const value = {
    user,
    token,
    isAuthenticated,
    login,
    register,
    logout,
    loading,
    error,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export default AuthContext;
