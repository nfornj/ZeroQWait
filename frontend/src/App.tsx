import React from "react";
import { Routes, Route } from "react-router-dom";
import { ThemeProvider, createTheme } from "@mui/material/styles";
import CssBaseline from "@mui/material/CssBaseline";

// Context
import { ShopProvider } from "./contexts/ShopContext";

// Components
import Navbar from "./components/Navbar";
import ProtectedRoute from "./components/ProtectedRoute";

// Pages
import HomePage from "./pages/HomePage";
import LoginPage from "./pages/LoginPage";
import RegisterCustomerPage from "./pages/RegisterCustomerPage";
import RegisterShopOwnerPage from "./pages/RegisterShopOwnerPage";
import PricingPage from "./pages/PricingPage";
import SearchPage from "./pages/SearchPage";
import FavoritesPage from "./pages/FavoritesPage";
import NotFoundPage from "./pages/NotFoundPage";
import ShopRegistrationPage from "./pages/ShopRegistrationPage";
import ShopDashboardPage from "./pages/ShopDashboardPage";
import ShopAnalyticsPage from "./pages/ShopAnalyticsPage";
import ShopSettingsPage from "./pages/ShopSettingsPage";
import EmployeeManagementPage from "./pages/EmployeeManagementPage";
import EmployeeQueuePage from "./pages/EmployeeQueuePage";
import QueueManagementPage from "./pages/QueueManagementPage";
import QueueViewPage from "./pages/QueueViewPage";
import InShopDisplayPage from "./pages/InShopDisplayPage";
import WidgetPage from "./pages/WidgetPage";
import ForgotPasswordPage from "./pages/ForgotPasswordPage";
import ResetPasswordPage from "./pages/ResetPasswordPage";
import ShopLayout from "./layouts/ShopLayout";
import PublicShopPage from "./pages/PublicShopPage";
import PublicLayout from "./layouts/PublicLayout";
import QueueCounterPage from "./pages/QueueCounterPage";

// Create a modern, Airbnb-inspired theme
const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: "#FF5A5F", // Airbnb coral/pink
      light: "#FF8A80",
      dark: "#C62828",
      contrastText: "#FFFFFF",
    },
    secondary: {
      main: "#00A699", // Teal accent
      light: "#4DB6AC",
      dark: "#00695C",
      contrastText: "#FFFFFF",
    },
    background: {
      default: "#FAFAFA",
      paper: "#FFFFFF",
    },
    text: {
      primary: "#222222", // Airbnb's dark gray
      secondary: "#717171", // Airbnb's medium gray
    },
  },
  typography: {
    fontFamily: '"Circular", "Helvetica Neue", Helvetica, Arial, sans-serif',
    h1: {
      fontWeight: 600,
      fontSize: '2.5rem',
      lineHeight: 1.2,
      color: '#222222',
    },
    h2: {
      fontWeight: 600,
      fontSize: '2rem',
      lineHeight: 1.3,
      color: '#222222',
    },
    h3: {
      fontWeight: 600,
      fontSize: '1.5rem',
      lineHeight: 1.3,
      color: '#222222',
    },
    h4: {
      fontWeight: 600,
      fontSize: '1.25rem',
      lineHeight: 1.4,
      color: '#222222',
    },
    h5: {
      fontWeight: 500,
      fontSize: '1.125rem',
      lineHeight: 1.4,
      color: '#222222',
    },
    h6: {
      fontWeight: 500,
      fontSize: '1rem',
      lineHeight: 1.4,
      color: '#222222',
    },
    body1: {
      fontSize: '1rem',
      lineHeight: 1.5,
      color: '#222222',
    },
    body2: {
      fontSize: '0.875rem',
      lineHeight: 1.5,
      color: '#717171',
    },
  },
  shape: {
    borderRadius: 12, // More rounded corners like Airbnb
  },
  shadows: [
    'none',
    '0px 1px 2px rgba(0, 0, 0, 0.08), 0px 4px 12px rgba(0, 0, 0, 0.05)',
    '0px 2px 4px rgba(0, 0, 0, 0.08), 0px 8px 16px rgba(0, 0, 0, 0.08)',
    '0px 4px 8px rgba(0, 0, 0, 0.12), 0px 16px 24px rgba(0, 0, 0, 0.08)',
    '0px 8px 16px rgba(0, 0, 0, 0.12), 0px 16px 32px rgba(0, 0, 0, 0.08)',
    '0px 8px 16px rgba(0, 0, 0, 0.12), 0px 16px 32px rgba(0, 0, 0, 0.08)',
    '0px 8px 16px rgba(0, 0, 0, 0.12), 0px 16px 32px rgba(0, 0, 0, 0.08)',
    '0px 8px 16px rgba(0, 0, 0, 0.12), 0px 16px 32px rgba(0, 0, 0, 0.08)',
    '0px 8px 16px rgba(0, 0, 0, 0.12), 0px 16px 32px rgba(0, 0, 0, 0.08)',
    '0px 8px 16px rgba(0, 0, 0, 0.12), 0px 16px 32px rgba(0, 0, 0, 0.08)',
    '0px 8px 16px rgba(0, 0, 0, 0.12), 0px 16px 32px rgba(0, 0, 0, 0.08)',
    '0px 8px 16px rgba(0, 0, 0, 0.12), 0px 16px 32px rgba(0, 0, 0, 0.08)',
    '0px 8px 16px rgba(0, 0, 0, 0.12), 0px 16px 32px rgba(0, 0, 0, 0.08)',
    '0px 8px 16px rgba(0, 0, 0, 0.12), 0px 16px 32px rgba(0, 0, 0, 0.08)',
    '0px 8px 16px rgba(0, 0, 0, 0.12), 0px 16px 32px rgba(0, 0, 0, 0.08)',
    '0px 8px 16px rgba(0, 0, 0, 0.12), 0px 16px 32px rgba(0, 0, 0, 0.08)',
    '0px 8px 16px rgba(0, 0, 0, 0.12), 0px 16px 32px rgba(0, 0, 0, 0.08)',
    '0px 8px 16px rgba(0, 0, 0, 0.12), 0px 16px 32px rgba(0, 0, 0, 0.08)',
    '0px 8px 16px rgba(0, 0, 0, 0.12), 0px 16px 32px rgba(0, 0, 0, 0.08)',
    '0px 8px 16px rgba(0, 0, 0, 0.12), 0px 16px 32px rgba(0, 0, 0, 0.08)',
    '0px 8px 16px rgba(0, 0, 0, 0.12), 0px 16px 32px rgba(0, 0, 0, 0.08)',
    '0px 8px 16px rgba(0, 0, 0, 0.12), 0px 16px 32px rgba(0, 0, 0, 0.08)',
    '0px 8px 16px rgba(0, 0, 0, 0.12), 0px 16px 32px rgba(0, 0, 0, 0.08)',
    '0px 8px 16px rgba(0, 0, 0, 0.12), 0px 16px 32px rgba(0, 0, 0, 0.08)',
    '0px 8px 16px rgba(0, 0, 0, 0.12), 0px 16px 32px rgba(0, 0, 0, 0.08)'
  ],
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          fontWeight: 600,
          borderRadius: 8,
          padding: '12px 24px',
          fontSize: '1rem',
        },
        contained: {
          boxShadow: 'none',
          '&:hover': {
            boxShadow: '0px 2px 4px rgba(0, 0, 0, 0.18)',
          },
        },
        outlined: {
          borderWidth: 2,
          '&:hover': {
            borderWidth: 2,
          },
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 12,
          border: '1px solid #EBEBEB',
          boxShadow: '0px 1px 2px rgba(0, 0, 0, 0.08), 0px 4px 12px rgba(0, 0, 0, 0.05)',
          '&:hover': {
            boxShadow: '0px 2px 4px rgba(0, 0, 0, 0.08), 0px 8px 16px rgba(0, 0, 0, 0.08)',
            transform: 'translateY(-2px)',
            transition: 'all 0.2s ease-in-out',
          },
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundColor: '#FFFFFF',
          color: '#222222',
          boxShadow: '0px 1px 2px rgba(0, 0, 0, 0.08), 0px 4px 12px rgba(0, 0, 0, 0.05)',
          borderBottom: '1px solid #EBEBEB',
        },
      },
    },
  },
});

function App() {
  return (
    <ShopProvider>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <Routes>
        {/* Public Routes with Navbar */}
        <Route element={<PublicLayout />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route path="/register/customer" element={<RegisterCustomerPage />} />
          <Route path="/register/shop-owner" element={<RegisterShopOwnerPage />} />
          <Route path="/pricing" element={<PricingPage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/queue/:shopId" element={<QueueViewPage />} />
          <Route path="/queue-counter" element={<QueueCounterPage />} />
        </Route>

        {/* In-Shop Display (No Layout - Fullscreen) */}
        <Route path="/display/:shopId" element={<InShopDisplayPage />} />

        {/* Embeddable Widget (No Layout - For iframe embedding) */}
        <Route path="/widget/:shopId" element={<WidgetPage />} />

        {/* Vanity URL Route (No Global Navbar) */}
        <Route path="/s/:slug" element={<PublicShopPage />} />

        {/* Shop Registration (Standalone or Public?) - Let's keep it Public for now */}
        <Route element={<PublicLayout />}>
          <Route path="/register-shop" element={<ShopRegistrationPage />} />
        </Route>

        {/* Employee Queue Management (Public Layout) */}
        <Route element={<PublicLayout />}>
          <Route path="/employee-dashboard" element={<EmployeeQueuePage />} />
        </Route>

        {/* Shop Owner Portal Routes (No Global Navbar) */}
        <Route element={<ShopLayout />}>
          <Route path="/dashboard" element={<ShopDashboardPage />} />
          <Route path="/analytics" element={<ShopAnalyticsPage />} />
          <Route path="/employees" element={<EmployeeManagementPage />} />
          <Route path="/settings" element={<ShopSettingsPage />} />
          <Route path="/queues" element={<QueueManagementPage />} />
        </Route>

        <Route path="*" element={<NotFoundPage />} />
      </Routes>
      </ThemeProvider>
    </ShopProvider>
  );
}

export default App;
