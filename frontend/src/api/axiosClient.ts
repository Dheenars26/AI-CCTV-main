import axios from 'axios';
import { API_BASE_URL } from '../config/apiConfig';

// Helper to extract CSRF token from document cookies if present
function getCsrfTokenFromCookie(): string | null {
  const match = document.cookie.match(new RegExp('(^| )csrf_token=([^;]+)'));
  return match ? decodeURIComponent(match[2]) : null;
}

export const axiosClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 20000, // 20 seconds request timeout for reliable responses under AI inference loads
  withCredentials: true, // Send HttpOnly refresh_token and csrf_token cookies
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  },
});

// Request Interceptor: Inject Authorization Bearer Header & CSRF Header
axiosClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token && config.headers) {
    config.headers['Authorization'] = `Bearer ${token}`;
  }

  const csrfToken = getCsrfTokenFromCookie();
  if (csrfToken && config.headers) {
    config.headers['X-CSRF-Token'] = csrfToken;
  }

  return config;
}, (error) => Promise.reject(error));

// Response Interceptor: Auto Refresh Token Handling on 401 + Auto Retry on 502 (backend restart)
axiosClient.interceptors.response.use(
  (response) => {
    // If backend returns a new CSRF token in custom header, store it
    const newCsrf = response.headers['x-csrf-token'];
    if (newCsrf) {
      document.cookie = `csrf_token=${newCsrf}; path=/; SameSite=Lax`;
    }
    return response;
  },
  async (error) => {
    const originalRequest = error.config;

    // Auto-retry on 502 Bad Gateway / 503 Service Unavailable / ECONNABORTED (backend temporarily unavailable during restart)
    // MAX_RETRIES=4 and RETRY_DELAY_MS=2000 handle the ~4-5 second backend cold-start window
    // (all ONNX models load sequentially before uvicorn accepts requests)
    const MAX_RETRIES = 4;
    const RETRY_DELAY_MS = 2000;
    const isTimeoutOrUnavailable = error.code === 'ECONNABORTED' || error.response?.status === 502 || error.response?.status === 503;
    if (isTimeoutOrUnavailable && (originalRequest.__retryCount || 0) < MAX_RETRIES) {
      originalRequest.__retryCount = (originalRequest.__retryCount || 0) + 1;
      const delay = RETRY_DELAY_MS * originalRequest.__retryCount; // exponential-ish: 2s, 4s, 6s, 8s
      await new Promise((resolve) => setTimeout(resolve, delay));
      return axiosClient(originalRequest);
    }

    const isAuthPath = originalRequest.url?.includes('/auth/login') || 
                       originalRequest.url?.includes('/auth/refresh');
    if (error.response?.status === 401 && !originalRequest._retry && !isAuthPath) {
      originalRequest._retry = true;
      try {
        const csrfToken = getCsrfTokenFromCookie();
        const headers: Record<string, string> = {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        };
        if (csrfToken) {
          headers['X-CSRF-Token'] = csrfToken;
        }

        // Attempt refresh using HttpOnly cookie & CSRF header
        const refreshResp = await axios.post(`${API_BASE_URL}/auth/refresh`, {}, {
          withCredentials: true,
          headers,
        });

        const newAccessToken = refreshResp.data?.data?.access_token;
        if (newAccessToken) {
          localStorage.setItem('access_token', newAccessToken);

          if (originalRequest.headers) {
            originalRequest.headers['Authorization'] = `Bearer ${newAccessToken}`;
          }
          return axiosClient(originalRequest);
        }
      } catch (refreshErr) {
        localStorage.removeItem('access_token');
        window.dispatchEvent(new Event('auth_logout'));
        return Promise.reject(refreshErr);
      }
    }
    return Promise.reject(error);
  }
);

export default axiosClient;
