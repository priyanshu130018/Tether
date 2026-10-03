import { request, setAuthToken } from './client';
import { AuthResponse, TokenRefreshResponse, UserProfileResponse } from '../types';

export async function register(payload: {
  email: string;
  password: string;
  full_name: string;
  tenant_name?: string;
}): Promise<AuthResponse> {
  const res = await request<AuthResponse>('/auth/register', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  if (res.access_token) {
    setAuthToken(res.access_token);
  }
  return res;
}

export async function login(payload: {
  email: string;
  password: string;
  tenant_id?: number;
}): Promise<AuthResponse> {
  const res = await request<AuthResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  if (res.access_token) {
    setAuthToken(res.access_token);
  }
  return res;
}

export async function refreshToken(): Promise<TokenRefreshResponse> {
  const res = await request<TokenRefreshResponse>('/auth/refresh', {
    method: 'POST',
    body: JSON.stringify({}),
  });
  if (res.access_token) {
    setAuthToken(res.access_token);
  }
  return res;
}

export async function logout(): Promise<{ status: string }> {
  try {
    const res = await request<{ status: string }>('/auth/logout', {
      method: 'POST',
      body: JSON.stringify({}),
    });
    setAuthToken(null);
    return res;
  } catch {
    setAuthToken(null);
    return { status: 'logged_out' };
  }
}

export async function getMe(): Promise<UserProfileResponse> {
  return request<UserProfileResponse>('/auth/me');
}
