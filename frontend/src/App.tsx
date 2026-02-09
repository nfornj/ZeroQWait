import React, { Suspense } from "react";
import { Routes, Route } from "react-router-dom";
import dayjs from "dayjs";
import utc from "dayjs/plugin/utc";
import timezone from "dayjs/plugin/timezone";
import { CircularProgress, Box } from "@mui/material";

dayjs.extend(utc);
dayjs.extend(timezone);
// ThemeProvider is now imported from our context which handles dynamic theming
import { ThemeProvider } from "./contexts/ThemeContext";

// Context
import { ShopProvider } from "./contexts/ShopContext";

// Components
import Navbar from "./components/Navbar";
import ProtectedRoute from "./components/ProtectedRoute";
import SubdomainHandler from "./components/SubdomainHandler";

// Layouts
import ShopLayout from "./layouts/ShopLayout";
import PublicLayout from "./layouts/PublicLayout";

// Lazy Loaded Pages - Auth
const LoginPage = React.lazy(() => import("./features/auth/pages/LoginPage"));
const RegisterCustomerPage = React.lazy(() => import("./features/auth/pages/RegisterCustomerPage"));
const RegisterShopOwnerPage = React.lazy(() => import("./features/auth/pages/RegisterShopOwnerPage"));
const ForgotPasswordPage = React.lazy(() => import("./features/auth/pages/ForgotPasswordPage"));
const ResetPasswordPage = React.lazy(() => import("./features/auth/pages/ResetPasswordPage"));

// Lazy Loaded Pages - Shop Dashboard
const ShopDashboardPage = React.lazy(() => import("./features/shop-dashboard/pages/ShopDashboardPage"));
const ShopAnalyticsPage = React.lazy(() => import("./features/shop-dashboard/pages/ShopAnalyticsPage"));
const ShopSettingsPage = React.lazy(() => import("./features/shop-dashboard/pages/ShopSettingsPage"));
const ServicesManagementPage = React.lazy(() => import("./features/shop-dashboard/pages/ServicesManagementPage"));
const EmployeeManagementPage = React.lazy(() => import("./features/shop-dashboard/pages/EmployeeManagementPage"));
const EmployeeQueuePage = React.lazy(() => import("./features/shop-dashboard/pages/EmployeeQueuePage"));
const QueueManagementPage = React.lazy(() => import("./features/shop-dashboard/pages/QueueManagementPage"));
const ShopRegistrationPage = React.lazy(() => import("./features/shop-dashboard/pages/ShopRegistrationPage"));
const MasterDashboardPage = React.lazy(() => import("./features/admin/pages/MasterDashboardPage"));

// Lazy Loaded Pages - Public Booking
const HomePage = React.lazy(() => import("./features/public-booking/pages/HomePage"));
const PricingPage = React.lazy(() => import("./features/public-booking/pages/PricingPage"));
const SearchPage = React.lazy(() => import("./features/public-booking/pages/SearchPage"));
const FavoritesPage = React.lazy(() => import("./features/public-booking/pages/FavoritesPage"));
const NotFoundPage = React.lazy(() => import("./features/public-booking/pages/NotFoundPage"));
const PublicShopPage = React.lazy(() => import("./features/public-booking/pages/PublicShopPage"));
const QueueViewPage = React.lazy(() => import("./features/public-booking/pages/QueueViewPage"));
const InShopDisplayPage = React.lazy(() => import("./features/public-booking/pages/InShopDisplayPage"));
const QueueCounterPage = React.lazy(() => import("./features/public-booking/pages/QueueCounterPage"));
const AIShopPublicPage = React.lazy(() => import("./features/public-booking/pages/AIShopPublicPage"));
const WidgetPage = React.lazy(() => import("./features/public-booking/pages/WidgetPage"));

// Auth Components (Lazy loaded if needed, or imported directly if they export default)
// Assuming they are default exports from the components files
const SignInSide = React.lazy(() => import("./features/auth/components/auth-sign-in/SignInSide"));
const ShopOwnerSignUp = React.lazy(() => import("./features/auth/components/auth-sign-up/ShopOwnerSignUp"));

const LoadingFallback = () => (
  <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
    <CircularProgress />
  </Box>
);

const App: React.FC = () => {
  console.log("App Version Check: v2.0 - Forced Update"); // CACHE BUSTER
  return (
    <ShopProvider>
      <ThemeProvider>
        <Suspense fallback={<LoadingFallback />}>
          <Routes>
            {/* Auth Pages (No Navbar) */}
            <Route path="/signin" element={<SignInSide />} />
            <Route path="/login" element={<SignInSide />} />
            <Route path="/signup" element={<ShopOwnerSignUp />} />
            <Route path="/register" element={<ShopOwnerSignUp />} />
            <Route path="/register/shop-owner" element={<ShopOwnerSignUp />} />
            <Route path="/register/customer" element={<ShopOwnerSignUp />} />

            {/* Subdomain Handler replaces specific Landing Page route to handle both root and subdomains */}
            <Route path="/" element={<SubdomainHandler />} />
            <Route path="/ai" element={<SubdomainHandler />} />

            {/* Public Routes with Navbar */}
            <Route element={<PublicLayout />}>
              <Route path="/home" element={<HomePage />} />
              <Route path="/forgot-password" element={<ForgotPasswordPage />} />
              <Route path="/reset-password" element={<ResetPasswordPage />} />
              <Route path="/pricing" element={<PricingPage />} />
              <Route path="/search" element={<SearchPage />} />
              <Route path="/queue-counter" element={<QueueCounterPage />} />
            </Route>

            {/* Standalone Status Page (No Global Navbar) */}
            <Route path="/queue/:shopId" element={<QueueViewPage />} />

            {/* In-Shop Display (No Layout - Fullscreen) */}
            <Route path="/display/:shopId" element={<InShopDisplayPage />} />

            {/* AI Agentic Shop Display */}
            <Route path="/shop-ai/:shopId" element={<AIShopPublicPage />} />

            {/* Embeddable Widget (No Layout - For iframe embedding) */}
            <Route path="/widget/:shopId" element={<WidgetPage />} />

            {/* Vanity URL Route (No Global Navbar) */}
            <Route path="/s/:slug" element={<PublicShopPage />} />

            {/* Shop Registration (Standalone or Public?) - Let's keep it Public for now */}
            <Route path="/register-shop" element={<ShopOwnerSignUp />} />

            {/* Employee Queue Management (Public Layout) */}
            <Route element={<PublicLayout />}>
              <Route path="/employee-dashboard" element={<EmployeeQueuePage />} />
            </Route>

            {/* Shop Owner Portal Routes (No Global Navbar) */}
            <Route element={<ShopLayout />}>
              <Route path="/dashboard" element={<ShopDashboardPage />} />
              <Route path="/employees" element={<EmployeeManagementPage />} />
              <Route path="/services" element={<ServicesManagementPage />} />
              <Route path="/settings" element={<ShopSettingsPage />} />
              <Route path="/queues" element={<QueueManagementPage />} />
              <Route path="/analytics" element={<ShopAnalyticsPage />} />
              <Route path="/master-dashboard" element={<MasterDashboardPage />} />
            </Route>

            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </Suspense>
      </ThemeProvider>
    </ShopProvider>
  );
}

export default App;
