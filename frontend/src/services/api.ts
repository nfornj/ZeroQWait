import axios from 'axios';

// Centralized API client with auth interceptor
const api = axios.create({
  baseURL: process.env.REACT_APP_API_URL || '/api',
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      // Only redirect to /login from protected pages — never from public pages
      // like the landing page (/) which would cause the root-URL jitter.
      const publicPaths = ['/', '/login', '/signup', '/forgot-password', '/reset-password'];
      const isPublic = publicPaths.some(
        (p) =>
          window.location.pathname === p ||
          window.location.pathname.startsWith('/shop-ai') ||
          window.location.pathname.startsWith('/queue/')
      );
      if (!isPublic) {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export default api;

// Types
export interface HaircutService {
  id: number;
  name: string;
  address: string;
  city: string;
  state: string;
  zip_code: string;
  phone: string;
  website?: string;
  latitude: number;
  longitude: number;
  rating: number;
  price_range?: string;
  hours?: string;
}

export interface SearchParams {
  latitude: number;
  longitude: number;
  radius?: number;
}

// API functions
export const getHaircuts = async (): Promise<HaircutService[]> => {
  const response = await axios.get('/api/haircuts');
  return response.data;
};

export const getHaircutById = async (id: number): Promise<HaircutService> => {
  const response = await axios.get(`/api/haircuts/${id}`);
  return response.data;
};

export const searchHaircuts = async (params: SearchParams): Promise<HaircutService[]> => {
  const response = await axios.post('/api/haircuts/search', params);
  return response.data;
};

export const getFavorites = async (): Promise<HaircutService[]> => {
  const response = await axios.get('/api/users/favorites');
  return response.data;
};

export const addFavorite = async (haircutId: number): Promise<void> => {
  await axios.post(`/api/users/favorites/${haircutId}`);
};

export const removeFavorite = async (haircutId: number): Promise<void> => {
  await axios.delete(`/api/users/favorites/${haircutId}`);
};

// ── Inventory API ─────────────────────────────────────────────────────────────

export interface InventoryItem {
  id: number;
  shop_id: number;
  name: string;
  sku: string | null;
  unit: string;
  category: string | null;
  current_stock: number;
  reorder_threshold: number;
  cost_per_unit: number | null;
  retail_price_cents: number | null;
  supplier: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface InventoryMovement {
  id: number;
  item_id: number;
  movement_type: string;
  quantity: number;
  unit_cost: number | null;
  notes: string | null;
  created_at: string;
  item_name?: string;
}

export interface AddItemPayload {
  name: string;
  unit?: string;
  category?: string;
  sku?: string;
  initial_stock?: number;
  reorder_threshold?: number;
  cost_per_unit?: number;
  retail_price_cents?: number;
  supplier?: string;
}

export const getInventoryItems = (shopId: number, includeInactive = false) =>
  api.get<{ items: InventoryItem[] }>(`/v1/inventory/shop/${shopId}`, {
    params: { include_inactive: includeInactive },
  });

export const getLowStockAlerts = (shopId: number) =>
  api.get<{ alerts: InventoryItem[]; count: number }>(`/v1/inventory/shop/${shopId}/alerts`);

export const addInventoryItem = (shopId: number, data: AddItemPayload) =>
  api.post<InventoryItem>(`/v1/inventory/shop/${shopId}`, data);

export const restockItem = (shopId: number, itemId: number, quantity: number, notes?: string, unitCost?: number) =>
  api.post(`/v1/inventory/shop/${shopId}/${itemId}/restock`, { quantity, notes, unit_cost: unitCost });

export const recordUsage = (shopId: number, itemId: number, quantity: number, notes?: string) =>
  api.post(`/v1/inventory/shop/${shopId}/${itemId}/usage`, { quantity, notes });

export const adjustInventory = (shopId: number, itemId: number, quantity: number, notes?: string) =>
  api.post(`/v1/inventory/shop/${shopId}/${itemId}/adjust`, { quantity, notes });

export const getItemMovementHistory = (shopId: number, itemId: number) =>
  api.get<{ movements: InventoryMovement[] }>(`/v1/inventory/shop/${shopId}/${itemId}/history`);