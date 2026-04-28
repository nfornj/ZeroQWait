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