import React from "react";
import { Routes, Route } from "react-router-dom";
// ThemeProvider is now imported from our context which handles dynamic theming
import { ThemeProvider } from "./contexts/ThemeContext";

// Context
import { ShopProvider } from "./contexts/ShopContext";

// Components
import Navbar from "./components/Navbar";
import ProtectedRoute from "./components/ProtectedRoute";
import AppErrorBoundary from "./components/AppErrorBoundary";

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
import ShopSettingsPage from "./pages/ShopSettingsPage";
import EmployeeManagementPage from "./pages/EmployeeManagementPage";
import EmployeeQueuePage from "./pages/EmployeeQueuePage";
import QueueManagementPage from "./pages/QueueManagementPage";
import InShopDisplayPage from "./pages/InShopDisplayPage";
import WidgetPage from "./pages/WidgetPage";
import ForgotPasswordPage from "./pages/ForgotPasswordPage";
import ResetPasswordPage from "./pages/ResetPasswordPage";
import ShopLayout from "./layouts/ShopLayout";
// PublicShopPage is used via SubdomainHandler (subdomain routing only)
import PublicLayout from "./layouts/PublicLayout";
import QueueCounterPage from "./pages/QueueCounterPage";
import AgentInbox from "./features/agent-inbox/AgentInbox";

import SignInSide from "./auth-sign-in/SignInSide";
import ShopOwnerSignUp from "./auth-sign-up/ShopOwnerSignUp";
import LandingPage from "./landing-page/LandingPage";
import SubdomainHandler from "./components/SubdomainHandler";
import AIShopPublicPage from "./features/public-booking/pages/AIShopPublicPage";

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

          <Route path="/" element={<SubdomainHandler />} />
          <Route path="/ai" element={<SubdomainHandler />} />

          {/* AI Shop page (localhost dev mode) */}
          <Route path="/shop-ai/:shopId" element={<AIShopPublicPage />} />
          <Route path="/queue/:shopId" element={<AIShopPublicPage />} />

          {/* Public Routes with Navbar */}
          <Route element={<PublicLayout />}>
            <Route path="/home" element={<HomePage />} />
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
            <Route path="/reset-password" element={<ResetPasswordPage />} />
            <Route path="/pricing" element={<PricingPage />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/queue-counter" element={<QueueCounterPage />} />
          </Route>

          {/* In-Shop Display (No Layout - Fullscreen) */}
          <Route path="/display/:shopId" element={<InShopDisplayPage />} />

          {/* Embeddable Widget (No Layout - For iframe embedding) */}
          <Route path="/widget/:shopId" element={<WidgetPage />} />



          {/* Shop Registration (Standalone or Public?) - Let's keep it Public for now */}
          <Route path="/register-shop" element={<ShopOwnerSignUp />} />

          {/* Employee Queue Management (Public Layout) */}
          <Route element={<PublicLayout />}>
            <Route path="/employee-dashboard" element={<EmployeeQueuePage />} />
          </Route>

          {/* Shop Owner Portal Routes (No Global Navbar) */}
          <Route
            element={
              <ProtectedRoute>
                <AppErrorBoundary>
                  <ShopLayout />
                </AppErrorBoundary>
              </ProtectedRoute>
            }
          >
            <Route path="/dashboard" element={<AgentInbox />} />
            <Route path="/overview" element={<ShopDashboardPage />} />
            <Route path="/employees" element={<EmployeeManagementPage />} />
            <Route path="/settings" element={<ShopSettingsPage />} />
            <Route path="/queues" element={<QueueManagementPage />} />
            <Route path="/agent-inbox" element={<AgentInbox />} />
          </Route>

          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </ThemeProvider>
    </ShopProvider>
  );
}

export default App;
