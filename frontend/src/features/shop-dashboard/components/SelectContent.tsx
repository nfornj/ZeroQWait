import * as React from 'react';
import { LogOut, User, Store } from 'lucide-react';
import { useLocation } from 'react-router-dom';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Skeleton } from '@/components/ui/skeleton';
import { useShop } from '../../../contexts/ShopContext';
import { useAuth } from '../../../contexts/AuthContext';

function getInitials(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return 'S';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
}

export default function SelectContent() {
  const location = useLocation();
  const { shop, loading } = useShop();
  const { user, logout } = useAuth();
  const isEmployee = user?.role === 'employee' || location.pathname.startsWith('/employee-dashboard');
  const logoSrc = shop?.id && shop?.logo_url ? `/api/shops/${shop.id}/logo` : undefined;

  if (isEmployee) {
    return (
      <div className="rounded-xl border border-border bg-muted/40 p-3">
        <div className="flex items-center gap-3">
          <Avatar className="h-9 w-9 flex-shrink-0">
            <AvatarImage src={user?.profile_photo_url} alt={user?.username || 'Employee'} />
            <AvatarFallback className="text-xs">
              <User className="h-4 w-4" />
            </AvatarFallback>
          </Avatar>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold text-foreground">{user?.username || 'Employee'}</p>
            <p className="truncate text-xs text-muted-foreground">{user?.email || 'Queue workspace'}</p>
          </div>
        </div>
        <button
          type="button"
          onClick={logout}
          className="mt-3 flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-xs text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
        >
          <LogOut className="h-3.5 w-3.5" />
          Logout
        </button>
      </div>
    );
  }

  return (
    <div className="px-2 py-3">
      <div className="flex items-center gap-2.5">
        <Avatar className="h-8 w-8 flex-shrink-0 rounded-lg border border-border">
          <AvatarImage src={logoSrc} alt={shop?.name || 'Shop'} />
          <AvatarFallback className="rounded-lg text-xs" style={{ backgroundColor: 'var(--owner-primary, #7c3aed)', color: '#fff' }}>
            {shop?.name ? getInitials(shop.name) : <Store className="h-4 w-4" />}
          </AvatarFallback>
        </Avatar>
        <div className="min-w-0 flex-1">
          {loading || !shop ? (
            <>
              <Skeleton className="h-4 w-28 mb-1" />
              <Skeleton className="h-3 w-20" />
            </>
          ) : (
            <>
              <p className="truncate text-[0.9rem] font-semibold leading-tight text-foreground">{shop.name}</p>
              {shop.city && shop.shop_type && (
                <p className="truncate text-xs text-muted-foreground">
                  {shop.city} • {shop.shop_type}
                </p>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
