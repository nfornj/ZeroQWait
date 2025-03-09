import React, { createContext, useState, useEffect, useContext } from "react";
import axios from "axios";

interface User {
  id: number;
  username: string;
  email: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (
    username: string,
    email: string,
    password: string
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

  // Set up axios interceptor for authentication
  useEffect(() => {
    const interceptor = axios.interceptors.request.use(
      (config) => {
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    return () => {
      axios.interceptors.request.eject(interceptor);
    };
  }, [token]);

  // Fetch user data if token exists
  useEffect(() => {
    const fetchUser = async () => {
      if (token) {
        try {
          setLoading(true);
          const response = await axios.get("/api/users/me");
          setUser(response.data);
          setIsAuthenticated(true);
        } catch (err) {
          console.error("Error fetching user:", err);
          logout();
        } finally {
          setLoading(false);
        }
      }
    };

    fetchUser();
  }, [token]);

  const login = async (username: string, password: string) => {
    try {
      setLoading(true);
      setError(null);

      const formData = new FormData();
      formData.append("username", username);
      formData.append("password", password);

      const response = await axios.post("/api/token", formData);
      const { access_token } = response.data;

      localStorage.setItem("token", access_token);
      setToken(access_token);

      // Fetch user data
      const userResponse = await axios.get("/api/users/me", {
        headers: { Authorization: `Bearer ${access_token}` },
      });

      setUser(userResponse.data);
      setIsAuthenticated(true);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Login failed");
      console.error("Login error:", err);
    } finally {
      setLoading(false);
    }
  };

  const register = async (
    username: string,
    email: string,
    password: string
  ) => {
    try {
      setLoading(true);
      setError(null);

      await axios.post("/api/users", {
        username,
        email,
        password,
      });

      // Login after successful registration
      await login(username, password);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Registration failed");
      console.error("Registration error:", err);
    } finally {
      setLoading(false);
    }
  };

  const logout = () => {
    localStorage.removeItem("token");
    setToken(null);
    setUser(null);
    setIsAuthenticated(false);
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
