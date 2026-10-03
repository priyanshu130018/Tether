const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

let currentAccessToken: string | null = null;
let currentTenantId: number | null = null;
let onAuthFailedCallback: (() => void) | null = null;
let isRefreshing = false;
let pendingQueue: Array<(token: string | null) => void> = [];

export function setAuthToken(token: string | null): void {
  currentAccessToken = token;
}

export function getAuthToken(): string | null {
  return currentAccessToken;
}

export function setActiveTenantHeader(tenantId: number | null): void {
  currentTenantId = tenantId;
}

export function setOnAuthFailed(callback: () => void): void {
  onAuthFailedCallback = callback;
}

export class ApiError extends Error {
  status: number;
  data: any;

  constructor(message: string, status: number, data?: any) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

async function tryRefreshToken(): Promise<string | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({}),
    });
    if (!res.ok) {
      return null;
    }
    const data = await res.json();
    if (data.access_token) {
      setAuthToken(data.access_token);
      return data.access_token;
    }
    return null;
  } catch {
    return null;
  }
}

export async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;

  const headers = new Headers(options.headers || {});
  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  // Inject Authorization Bearer token if available
  if (currentAccessToken && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${currentAccessToken}`);
  }

  // Inject Active Tenant header if available
  if (currentTenantId && !headers.has('X-Tenant-ID')) {
    headers.set('X-Tenant-ID', String(currentTenantId));
  }

  const response = await fetch(url, {
    ...options,
    headers,
    credentials: 'include',
  });

  // Handle 401 Unauthorized for non-auth endpoints with transparent refresh retry
  if (response.status === 401 && !endpoint.includes('/auth/login') && !endpoint.includes('/auth/register') && !endpoint.includes('/auth/refresh')) {
    if (!isRefreshing) {
      isRefreshing = true;
      const newToken = await tryRefreshToken();
      isRefreshing = false;

      pendingQueue.forEach((cb) => cb(newToken));
      pendingQueue = [];

      if (newToken) {
        headers.set('Authorization', `Bearer ${newToken}`);
        const retryRes = await fetch(url, {
          ...options,
          headers,
          credentials: 'include',
        });
        return handleResponse<T>(retryRes);
      } else {
        if (onAuthFailedCallback) {
          onAuthFailedCallback();
        }
      }
    } else {
      // Wait for the active refresh
      return new Promise((resolve, reject) => {
        pendingQueue.push(async (token) => {
          if (!token) {
            reject(new ApiError('Session expired. Please log in again.', 401));
            return;
          }
          headers.set('Authorization', `Bearer ${token}`);
          try {
            const retryRes = await fetch(url, {
              ...options,
              headers,
              credentials: 'include',
            });
            resolve(await handleResponse<T>(retryRes));
          } catch (err) {
            reject(err);
          }
        });
      });
    }
  }

  return handleResponse<T>(response);
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (response.status === 204) {
    return {} as T;
  }

  let data: any;
  const contentType = response.headers.get('content-type');
  if (contentType && contentType.includes('application/json')) {
    data = await response.json();
  } else {
    data = await response.text();
  }

  if (!response.ok) {
    const errorMsg = data?.detail || data?.message || response.statusText || 'An unexpected error occurred';
    throw new ApiError(errorMsg, response.status, data);
  }

  return data as T;
}
