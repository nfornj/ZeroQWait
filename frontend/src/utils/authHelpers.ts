/**
 * Authentication helper utilities
 */

/**
 * Check if an error is due to authentication failure
 */
export const isAuthError = (error: any): boolean => {
  return error?.response?.status === 401;
};

/**
 * Get user-friendly error message for authentication errors
 */
export const getAuthErrorMessage = (error: any): string => {
  if (isAuthError(error)) {
    return 'Your session has expired. Please log in again.';
  }
  return error?.response?.data?.detail || error?.message || 'An error occurred';
};

/**
 * Check if token exists in localStorage
 */
export const hasToken = (): boolean => {
  return !!localStorage.getItem('token');
};

/**
 * Decode JWT token to check expiration (without verifying signature)
 * Returns null if token is invalid
 */
export const getTokenExpiration = (token: string): Date | null => {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    if (payload.exp) {
      return new Date(payload.exp * 1000);
    }
  } catch (e) {
    console.error('Failed to decode token:', e);
  }
  return null;
};

/**
 * Check if token is expired
 */
export const isTokenExpired = (token: string): boolean => {
  const expiration = getTokenExpiration(token);
  if (!expiration) return true;
  return expiration < new Date();
};

/**
 * Check if token will expire soon (within 5 minutes)
 */
export const isTokenExpiringSoon = (token: string, minutesThreshold: number = 5): boolean => {
  const expiration = getTokenExpiration(token);
  if (!expiration) return true;
  const thresholdMs = minutesThreshold * 60 * 1000;
  return (expiration.getTime() - Date.now()) < thresholdMs;
};
