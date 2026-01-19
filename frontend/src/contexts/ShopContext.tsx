import React, { createContext, useContext, useEffect, useState } from 'react';
import axios from 'axios';

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
  error: string | null;
  setShop: (shop: Shop | null) => void;
  fetchShopBySlug: (slug: string) => Promise<Shop | null>;
}

const ShopContext = createContext<ShopContextType | undefined>(undefined);

export const ShopProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [shop, setShop] = useState<Shop | null>(null);
  const [shopSlug, setShopSlug] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

  // Fetch shop by slug
  const fetchShopBySlug = async (slug: string): Promise<Shop | null> => {
    try {
      setLoading(true);
      setError(null);
      
      console.log("[ShopContext] Fetching shop by slug:", slug);
      const response = await axios.get(`/shops/by-slug/${slug}`);
      const shopData = response.data;
      console.log("[ShopContext] Shop fetched by slug:", shopData.name, shopData.slug);
      setShop(shopData);
      setShopSlug(slug);
      return shopData;
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to fetch shop';
      console.log("[ShopContext] Slug fetch failed:", errorMsg);
      setError(errorMsg);
      setShop(null);
      return null;
    } finally {
      setLoading(false);
    }
  };

  // Fetch user's shop (for authenticated users)
  const fetchMyShop = async (): Promise<Shop | null> => {
    try {
      setLoading(true);
      const token = localStorage.getItem('token');
      if (!token) {
        console.log("[ShopContext] No token, skipping shop fetch");
        return null;
      }

      console.log("[ShopContext] Fetching user's shop");
      const response = await axios.get(`/shops/my-shops`, {
        headers: { Authorization: `Bearer ${token}` }
      });

      if (response.data.length > 0) {
        const myShop = response.data[0];
        console.log("[ShopContext] User's shop fetched:", myShop.name, "slug:", myShop.slug);
        setShop(myShop);
        setShopSlug(myShop.slug);
        return myShop;
      }
      return null;
    } catch (err) {
      // Silently fail - user might not have a shop
      console.log("[ShopContext] My shop fetch failed:", err instanceof Error ? err.message : 'Unknown error');
      return null;
    } finally {
      setLoading(false);
    }
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
  }, []);

  const value: ShopContextType = {
    shop,
    shopSlug,
    loading,
    error,
    setShop,
    fetchShopBySlug,
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
