/**
 * Application API and WebSocket Configuration
 * Supports local development, Render static site deployments, and Vercel deployments.
 */

// Reads VITE_API_URL or VITE_API_BASE_URL (set in Vercel or Render environment)
const rawApiUrl = ((import.meta as any).env?.VITE_API_URL || (import.meta as any).env?.VITE_API_BASE_URL || '').trim();

function normalizeApiBase(rawUrl: string): string {
  if (!rawUrl) return '';
  let url = rawUrl;
  // If protocol is missing (common with Render's host property), add https://
  if (!url.startsWith('http://') && !url.startsWith('https://')) {
    url = `https://${url}`;
  }
  // Remove trailing slashes
  return url.replace(/\/+$/, '');
}

export const API_HOST_URL = normalizeApiBase(rawApiUrl);

// REST API Base URL (e.g. "https://backend.onrender.com/api/v1" or "/api/v1" for relative/proxy)
export const API_BASE_URL = API_HOST_URL ? `${API_HOST_URL}/api/v1` : '/api/v1';

// WebSocket Base URL
export function getWebSocketUrl(ticketOrToken?: string): string {
  let wsOrigin = '';
  if (API_HOST_URL) {
    wsOrigin = API_HOST_URL.replace(/^http:/, 'ws:').replace(/^https:/, 'wss:');
  } else {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    wsOrigin = `${protocol}//${window.location.host}`;
  }
  const endpoint = `${wsOrigin}/api/v1/ws`;
  if (!ticketOrToken) return endpoint;

  if (ticketOrToken.startsWith('wst_')) {
    return `${endpoint}?ticket=${encodeURIComponent(ticketOrToken)}`;
  }
  return `${endpoint}?token=${encodeURIComponent(ticketOrToken)}`;
}

// Stream Base URL for MJPEG camera streams
export function getCameraStreamBaseUrl(): string {
  if (API_HOST_URL) {
    return API_HOST_URL;
  }
  const isDev = (import.meta as any).env?.DEV ?? true;
  return isDev ? `${window.location.protocol}//${window.location.hostname}:8000` : '';
}

// Media/Snapshot URL resolver (resolves relative backend paths like /api/v1/evidence/...)
export function resolveApiUrl(path?: string): string {
  if (!path) return '';
  if (path.startsWith('http://') || path.startsWith('https://') || path.startsWith('data:') || path.startsWith('blob:')) {
    return path;
  }
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  return API_HOST_URL ? `${API_HOST_URL}${cleanPath}` : cleanPath;
}
