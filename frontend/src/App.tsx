import React from "react";
import { Routes, Route } from "react-router-dom";
import dayjs from "dayjs";
import utc from "dayjs/plugin/utc";
import timezone from "dayjs/plugin/timezone";

dayjs.extend(utc);
dayjs.extend(timezone);
// ThemeProvider is now imported from our context which handles dynamic theming
import { ThemeProvider } from "./contexts/ThemeContext";

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
import ServicesManagementPage from "./pages/ServicesManagementPage";
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
import AIShopPublicPage from "./pages/AIShopPublicPage";

import SignInSide from "./auth-sign-in/SignInSide";
import ShopOwnerSignUp from "./auth-sign-up/ShopOwnerSignUp";
import LandingPage from "./landing-page/LandingPage";
import SubdomainHandler from "./components/SubdomainHandler";

function App() {
  return (
    <ShopProvider>
      <ThemeProvider>
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
          </Route>

          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </ThemeProvider>
    </ShopProvider>
  );
}

export default App;
