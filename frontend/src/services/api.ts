import axios from 'axios';

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