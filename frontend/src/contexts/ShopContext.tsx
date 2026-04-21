import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import api from '../services/api';
import { useAuth } from './AuthContext';

interface Shop {
  id: number;
  name: string;
  slug: string;
  logo_url?: string;
  primary_color?: string;
  secondary_color?: string;
  city?: string;
  state?: string;
  shop_type?: string;
}

interface ShopContextType {
  shop: Shop | null;
  shopSlug: string | null;
  loading: boolean;
  shopsLoading: boolean;
  error: string | null;
  ownedShops: Shop[];
  setShop: (shop: Shop | null) => void;
  fetchShopBySlug: (slug: string) => Promise<Shop | null>;
  refreshOwnedShops: () => Promise<Shop[]>;
  selectOwnedShop: (shopId: number) => void;
}

const ShopContext = createContext<ShopContextType | undefined>(undefined);

const ACTIVE_SHOP_STORAGE_KEY = 'zeroq_active_owner_shop_id';

export const ShopProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, isAuthenticated, loading: authLoading } = useAuth();
  const [shop, setShop] = useState<Shop | null>(null);
  const [shopSlug, setShopSlug] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [shopsLoading, setShopsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ownedShops, setOwnedShops] = useState<Shop[]>([]);

  // Extract subdomain from current hostname
  const getSubdomainFromHost = (): string | null => {
    const hostname = window.location.hostname;
    const parts = hostname.split('.');

    // Handle local development (localhost, 127.0.0.1)
    if (hostname === 'localhost' || hostname === '127.0.0.1' || hostname.startsWith('127.0.0')) {
      return null;
    }

    // Handle IP.nip.io format (e.g., shopname.192.168.2.88.nip.io)
    if (hostname.includes('nip.io')) {
      // For 192.168.2.88.nip.io, parts = ['shopname', '192', '168', '2', '88', 'nip', 'io']
      // For 192.168.2.88.nip.io, we want 'shopname'
      if (parts.length > 1 && !parts[0].match(/^\d+$/)) {
        return parts[0];
      }
    }

    // Handle regular domain format (e.g., shopname.example.com)
    if (parts.length > 2 && !parts[0].match(/^(www|mail|ftp)$/)) {
      return parts[0];
    }

    return null;
  };

  const applySelectedShop = useCallback((nextShop: Shop | null) => {
    setShop(nextShop);
    setShopSlug(nextShop?.slug || null);

    if (nextShop?.id) {
      localStorage.setItem(ACTIVE_SHOP_STORAGE_KEY, String(nextShop.id));
    } else {
      localStorage.removeItem(ACTIVE_SHOP_STORAGE_KEY);
    }
  }, []);

  const resolvePreferredOwnedShop = useCallback((shops: Shop[]): Shop | null => {
    if (!shops.length) return null;

    const storedShopId = Number(localStorage.getItem(ACTIVE_SHOP_STORAGE_KEY));
    if (Number.isFinite(storedShopId)) {
      const rememberedShop = shops.find((ownedShop) => ownedShop.id === storedShopId);
      if (rememberedShop) {
        return rememberedShop;
      }
    }

    if (shop?.id) {
      const currentShop = shops.find((ownedShop) => ownedShop.id === shop.id);
      if (currentShop) {
        return currentShop;
      }
    }

    return shops[0];
  }, [shop?.id]);

  // Fetch shop by slug
  const fetchShopBySlug = useCallback(async (slug: string): Promise<Shop | null> => {
    try {
      setLoading(true);
      setError(null);

      console.log("[ShopContext] Fetching shop by slug:", slug);
      // Use /shops/s/{slug} endpoint which returns shop with queues and is confirmed to work
      const response = await api.get(`/shops/s/${slug}`);
      const shopData = response.data;
      console.log("[ShopContext] Shop fetched by slug:", shopData.name, shopData.slug);
      applySelectedShop(shopData);
      return shopData;
    } catch (err: any) {
      if (err.response && err.response.status === 404) {
        console.log(`[ShopContext] Shop not found for slug: ${slug} (this is normal if the shop doesn't exist)`);
        // Don't set global error for 404, just return null
        applySelectedShop(null);
        return null;
      }

      const errorMsg = err instanceof Error ? err.message : 'Failed to fetch shop';
      console.log("[ShopContext] Slug fetch failed:", errorMsg);
      setError(errorMsg);
      applySelectedShop(null);
      return null;
    } finally {
      setLoading(false);
    }
  }, [applySelectedShop]);

  // Fetch user's shop (for authenticated users)
  const fetchMyShop = useCallback(async (): Promise<Shop | null> => {
    try {
      setLoading(true);

      console.log("[ShopContext] Fetching user's shop");
      const response = await api.get(`/shops/my-shops`);

      const shops = Array.isArray(response.data) ? response.data : [];
      setOwnedShops(shops);

      if (shops.length > 0) {
        const myShop = resolvePreferredOwnedShop(shops);
        if (!myShop) {
          applySelectedShop(null);
          return null;
        }
        console.log("[ShopContext] User's shop fetched:", myShop.name, "slug:", myShop.slug);
        applySelectedShop(myShop);
        return myShop;
      }
      applySelectedShop(null);
      return null;
    } catch (err) {
      // Silently fail - user might not have a shop
      console.log("[ShopContext] My shop fetch failed:", err instanceof Error ? err.message : 'Unknown error');
      return null;
    } finally {
      setLoading(false);
    }
  }, [applySelectedShop, resolvePreferredOwnedShop]);

  const refreshOwnedShops = useCallback(async (): Promise<Shop[]> => {
    try {
      setShopsLoading(true);
      setError(null);

      const response = await api.get(`/shops/my-shops`);
      const shops = Array.isArray(response.data) ? response.data : [];
      setOwnedShops(shops);

      const preferredShop = resolvePreferredOwnedShop(shops);
      if (preferredShop) {
        applySelectedShop(preferredShop);
      } else if (shops.length === 0) {
        applySelectedShop(null);
      }

      return shops;
    } catch (err: any) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to load shops';
      setError(errorMsg);
      return [];
    } finally {
      setShopsLoading(false);
    }
  }, [applySelectedShop, resolvePreferredOwnedShop]);

  const selectOwnedShop = (shopId: number) => {
    const selectedShop = ownedShops.find((ownedShop) => ownedShop.id === shopId);
    if (!selectedShop) return;
    applySelectedShop(selectedShop);
  };

  useEffect(() => {
    const initializeShop = async () => {
      const subdomain = getSubdomainFromHost();
      console.log("[ShopContext] Subdomain detected:", subdomain);

      if (subdomain && subdomain !== '192' && subdomain !== '168') {
        // This is a shop subdomain, fetch the shop data
        console.log("[ShopContext] Fetching shop by subdomain:", subdomain);
        const result = await fetchShopBySlug(subdomain);
        if (!result) {
          console.log("[ShopContext] Subdomain fetch failed, trying user's shop");
          await fetchMyShop();
        }
      } else {
        // Regular domain, try to fetch user's shop if authenticated
        console.log("[ShopContext] Regular domain, fetching user's shop");
        await fetchMyShop();
      }
    };

    initializeShop();
  }, [fetchMyShop, fetchShopBySlug]);

  useEffect(() => {
    if (authLoading) return;

    const subdomain = getSubdomainFromHost();
    if (subdomain) return;

    if (!isAuthenticated || user?.role !== 'shop_owner') {
      if (!isAuthenticated) {
        setOwnedShops([]);
        applySelectedShop(null);
      }
      return;
    }

    if (!shop || ownedShops.length === 0) {
      void refreshOwnedShops();
    }
  }, [authLoading, isAuthenticated, user?.role, shop, ownedShops.length, refreshOwnedShops, applySelectedShop]);

  const value: ShopContextType = {
    shop,
    shopSlug,
    loading,
    shopsLoading,
    error,
    ownedShops,
    setShop: applySelectedShop,
    fetchShopBySlug,
    refreshOwnedShops,
    selectOwnedShop,
  };

  return (
    <ShopContext.Provider value={value}>
      {children}
    </ShopContext.Provider>
  );
};

export const useShop = (): ShopContextType => {
  const context = useContext(ShopContext);
  if (!context) {
    throw new Error('useShop must be used within ShopProvider');
  }
  return context;
};
