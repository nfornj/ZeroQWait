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

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

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
      
      const response = await axios.get(`${API_URL}/shops/by-slug/${slug}`);
      const shopData = response.data;
      setShop(shopData);
      setShopSlug(slug);
      return shopData;
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to fetch shop';
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
      if (!token) return null;

      const response = await axios.get(`${API_URL}/shops/my-shops`, {
        headers: { Authorization: `Bearer ${token}` }
      });

      if (response.data.length > 0) {
        setShop(response.data[0]);
        setShopSlug(response.data[0].slug);
        return response.data[0];
      }
      return null;
    } catch (err) {
      // Silently fail - user might not have a shop
      return null;
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const subdomain = getSubdomainFromHost();
    
    if (subdomain && subdomain !== '192' && subdomain !== '168') {
      // This is a shop subdomain, fetch the shop data
      fetchShopBySlug(subdomain);
    } else {
      // Regular domain, try to fetch user's shop if authenticated
      fetchMyShop();
    }
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
