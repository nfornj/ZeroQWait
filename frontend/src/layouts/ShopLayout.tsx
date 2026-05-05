import React from 'react';
import { useLocation, Outlet } from 'react-router-dom';
import AppNavbar from '../features/shop-dashboard/components/AppNavbar';
import SideMenu from '../features/shop-dashboard/components/SideMenu';
import { useOwnerBrand } from '../hooks/useOwnerBrand';

const ShopLayout: React.FC = () => {
  const location = useLocation();
  const ownerBrand = useOwnerBrand();
  const isAgentRoute = location.pathname === '/dashboard';

  return (
    <div
      className="flex h-screen overflow-hidden bg-background"
      style={{
        '--owner-primary': ownerBrand.primary,
        '--owner-secondary': ownerBrand.secondary,
        '--owner-glass-bg': ownerBrand.glass.bg,
        '--owner-glass-bg-strong': ownerBrand.glass.bgStrong,
        '--owner-glass-border': ownerBrand.glass.border,
        '--owner-glass-shadow': ownerBrand.glass.shadow,
      } as React.CSSProperties}
    >
      <SideMenu />

      <div className="flex min-w-0 flex-1 flex-col">
        <AppNavbar />

        <main className={`flex-1 ${isAgentRoute ? 'overflow-hidden' : 'overflow-auto'}`}>
          <div
            className={
              isAgentRoute
                ? 'flex h-full flex-col'
                : 'px-6 pb-10 pt-4'
            }
          >
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
};

export default ShopLayout;
