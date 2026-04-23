import React from "react";
import { Routes, Route } from "react-router-dom";
import { Navigate } from "react-router-dom";
// ThemeProvider is now imported from our context which handles dynamic theming
import { ThemeProvider } from "./contexts/ThemeContext";

// Context
import { ShopProvider } from "./contexts/ShopContext";

import ProtectedRoute from "./components/ProtectedRoute";
import AppErrorBoundary from "./components/AppErrorBoundary";

import PricingPage from "./features/public-booking/pages/PricingPage";
import SearchPage from "./features/public-booking/pages/SearchPage";
import NotFoundPage from "./features/public-booking/pages/NotFoundPage";
import ShopDashboardPage from "./features/shop-dashboard/pages/ShopDashboardPage";
import ShopSettingsPage from "./features/shop-dashboard/pages/ShopSettingsPage";
import EmployeeManagementPage from "./features/shop-dashboard/pages/EmployeeManagementPage";
import EmployeeQueuePage from "./features/shop-dashboard/pages/EmployeeQueuePage";
import QueueManagementPage from "./features/shop-dashboard/pages/QueueManagementPage";
import QueueDetailPage from "./features/shop-dashboard/pages/QueueDetailPage";
import InShopDisplayPage from "./features/public-booking/pages/InShopDisplayPage";
import WidgetPage from "./features/public-booking/pages/WidgetPage";
import ForgotPasswordPage from "./features/auth/pages/ForgotPasswordPage";
import ResetPasswordPage from "./features/auth/pages/ResetPasswordPage";
import ShopLayout from "./layouts/ShopLayout";
// PublicShopPage is used via SubdomainHandler (subdomain routing only)
import PublicLayout from "./layouts/PublicLayout";
import AgentInbox from "./features/agent-inbox/AgentInbox";
import MasterDashboardPage from "./features/admin/pages/MasterDashboardPage";
import ServicesManagementPage from "./features/shop-dashboard/pages/ServicesManagementPage";
import AppointmentsPage from "./features/shop-dashboard/pages/AppointmentsPage";
import OwnerDashboardPage from "./features/shop-dashboard/pages/OwnerDashboardPage";
import { useAuth } from "./contexts/AuthContext";

import SignInSide from "./features/auth/components/auth-sign-in/SignInSide";
import ShopOwnerSignUp from "./features/auth/components/auth-sign-up/ShopOwnerSignUp";
import SubdomainHandler from "./components/SubdomainHandler";
import AIShopPublicPage from "./features/public-booking/pages/AIShopPublicPage";
import QueueViewPage from "./features/public-booking/pages/QueueViewPage";

function App() {
  const { user } = useAuth();

  const OwnerOnly = ({ children }: { children: React.ReactNode }) => {
    if (user?.role === "employee") {
      return <Navigate to="/employee-dashboard" replace />;
    }
    return <>{children}</>;
  };

  const DashboardEntry = () => {
    if (user?.role === "employee") {
      return <Navigate to="/employee-dashboard" replace />;
    }
    return <OwnerDashboardPage />;
  };

  return (
    <ShopProvider>
      <ThemeProvider>
        <Routes>
          {/* Auth Pages (No Navbar) */}
          <Route path="/login" element={<SignInSide />} />
          <Route path="/signup" element={<ShopOwnerSignUp />} />

          <Route path="/" element={<SubdomainHandler />} />
          <Route path="/ai" element={<Navigate to="/" replace />} />

          {/* AI Shop page (localhost dev mode) */}
          <Route path="/shop-ai/:shopId" element={<AIShopPublicPage />} />
          <Route path="/queue/:shopId" element={<QueueViewPage />} />

          {/* Public Routes with Navbar */}
          <Route element={<PublicLayout />}>
            <Route path="/home" element={<Navigate to="/" replace />} />
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
            <Route path="/reset-password" element={<ResetPasswordPage />} />
            <Route path="/pricing" element={<PricingPage />} />
            <Route path="/search" element={<SearchPage />} />
          </Route>

          {/* In-Shop Display (No Layout - Fullscreen) */}
          <Route path="/display/:shopId" element={<InShopDisplayPage />} />

          {/* Embeddable Widget (No Layout - For iframe embedding) */}
          <Route path="/widget/:shopId" element={<WidgetPage />} />



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
            <Route path="/dashboard" element={<DashboardEntry />} />
            <Route path="/employee-dashboard" element={<EmployeeQueuePage />} />
            <Route path="/overview" element={<OwnerOnly><ShopDashboardPage /></OwnerOnly>} />
            <Route path="/employees" element={<OwnerOnly><EmployeeManagementPage /></OwnerOnly>} />
            <Route path="/settings" element={<OwnerOnly><ShopSettingsPage /></OwnerOnly>} />
            <Route path="/queues" element={<OwnerOnly><QueueManagementPage /></OwnerOnly>} />
            <Route path="/queues/:queueId" element={<OwnerOnly><QueueDetailPage /></OwnerOnly>} />
            <Route path="/services" element={<OwnerOnly><ServicesManagementPage /></OwnerOnly>} />
            <Route path="/appointments" element={<OwnerOnly><AppointmentsPage /></OwnerOnly>} />
          <Route path="/agent-inbox" element={<OwnerOnly><AgentInbox /></OwnerOnly>} />
          </Route>

          {/* Admin Portal — super_admin only, standalone (no ShopLayout) */}
          <Route
            path="/admin"
            element={
              <ProtectedRoute>
                <MasterDashboardPage />
              </ProtectedRoute>
            }
          />
          {/* Legacy redirect: /master-dashboard → /admin */}
          <Route path="/master-dashboard" element={<Navigate to="/admin" replace />} />

          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </ThemeProvider>
    </ShopProvider>
  );
}

export default App;
