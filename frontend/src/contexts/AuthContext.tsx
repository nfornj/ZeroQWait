import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import axios from "axios";
import EmailPassword from "supertokens-auth-react/recipe/emailpassword";
import Session from "supertokens-auth-react/recipe/session";

interface User {
  id: number;
  username: string;
  email: string;
  role: "customer" | "shop_owner" | "employee" | "manager" | "SUPER_ADMIN" | "super_admin";
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

async function getSuperTokensAccessToken(): Promise<string | null> {
  try {
    return (await Session.getAccessToken()) || null;
  } catch {
    return null;
  }
}

function publicRoute(pathname: string): boolean {
  const publicPaths = [
    "/",
    "/login",
    "/signin",
    "/signup",
    "/register",
    "/ai",
    "/forgot-password",
    "/reset-password",
  ];
  return (
    publicPaths.includes(pathname) ||
    pathname.startsWith("/auth") ||
    pathname.startsWith("/shop-ai") ||
    pathname.startsWith("/queue/")
  );
}

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(localStorage.getItem("token"));
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);

  const clearAuthState = useCallback(() => {
    localStorage.removeItem("token");
    setToken(null);
    setUser(null);
    setIsAuthenticated(false);
  }, []);

  const refreshUser = useCallback(async () => {
    setLoading(true);
    try {
      const sessionExists = await Session.doesSessionExist();
      const accessToken = (await getSuperTokensAccessToken()) || localStorage.getItem("token");

      if (!sessionExists && !accessToken) {
        clearAuthState();
        return;
      }

      if (accessToken) {
        localStorage.setItem("token", accessToken);
        setToken(accessToken);
      }

      const response = await axios.get("/users/me", {
        headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined,
      });

      setUser(response.data);
      setIsAuthenticated(true);
    } catch (err: any) {
      if (err.response?.status === 401) {
        clearAuthState();
      } else {
        setError(err.response?.data?.detail || "Unable to load user session");
      }
    } finally {
      setLoading(false);
    }
  }, [clearAuthState]);

  const logout = useCallback(async () => {
    try {
      if (await Session.doesSessionExist()) {
        await Session.signOut();
      } else {
        await EmailPassword.signOut().catch(() => undefined);
      }
    } catch {
      // Clearing local state is still the right client-side outcome if the server session is already gone.
    } finally {
      clearAuthState();
    }
  }, [clearAuthState]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const urlToken = params.get("token");

    if (urlToken && window.location.pathname !== "/reset-password") {
      localStorage.setItem("token", urlToken);
      setToken(urlToken);
      window.history.replaceState({}, document.title, window.location.pathname);
    }

    void refreshUser();
  }, [refreshUser]);

  // Set up axios interceptors for authentication
  useEffect(() => {
    const requestInterceptor = axios.interceptors.request.use(
      (config) => {
        const accessToken = token || localStorage.getItem("token");
        if (accessToken) {
          config.headers.Authorization = `Bearer ${accessToken}`;
        }
        return config;
      },
      (requestError) => Promise.reject(requestError)
    );

    const responseInterceptor = axios.interceptors.response.use(
      (response) => response,
      (responseError) => {
        if (responseError.response?.status === 401) {
          void logout();
          if (!publicRoute(window.location.pathname)) {
            window.location.href = '/login';
          }
        }
        return Promise.reject(responseError);
      }
    );

    return () => {
      axios.interceptors.request.eject(requestInterceptor);
      axios.interceptors.response.eject(responseInterceptor);
    };
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

      await refreshUser();
    } catch (err: any) {
      setError(err.response?.data?.detail || "Login failed");
      throw err;
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

      const response = await axios.post("/auth/register", {
        username,
        email,
        password,
        role,
      });

      if (response.data?.access_token) {
        localStorage.setItem("token", response.data.access_token);
        setToken(response.data.access_token);
      }
      await refreshUser();
    } catch (err: any) {
      setError(err.response?.data?.detail || "Registration failed");
      throw err; // Re-throw to prevent navigation
    } finally {
      setLoading(false);
    }
  };

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
