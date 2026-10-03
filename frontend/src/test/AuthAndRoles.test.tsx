import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import { LoginPage } from '../pages/LoginPage';
import { RegisterPage } from '../pages/RegisterPage';
import { TeamManagementPage } from '../pages/TeamManagementPage';
import { AuthProvider } from '../context/AuthContext';
import { ToastProvider } from '../components/ui/Toast';
import * as authApi from '../api/auth';
import * as tenantsApi from '../api/tenants';

vi.mock('../api/auth');
vi.mock('../api/tenants');

const renderWithAuth = (ui: React.ReactElement) => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ToastProvider>
          <BrowserRouter>{ui}</BrowserRouter>
        </ToastProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
};

describe('Phase 6: Frontend Authentication & RBAC UI', () => {
  it('renders LoginPage and handles submit', async () => {
    vi.mocked(authApi.getMe).mockRejectedValue(new Error('Unauthenticated'));
    vi.mocked(authApi.login).mockResolvedValue({
      access_token: 'fake-jwt-token',
      token_type: 'bearer',
      user: {
        id: 1,
        email: 'admin@tether.local',
        full_name: 'Admin User',
        is_active: true,
        is_verified: true,
        created_at: new Date().toISOString(),
      },
      active_tenant: {
        id: 1,
        name: 'Default Org',
        slug: 'default-org',
        created_at: new Date().toISOString(),
      },
      role: 'OWNER',
    });

    renderWithAuth(<LoginPage />);

    expect(screen.getByText('Sign in to your organization')).toBeInTheDocument();
    const emailInput = screen.getByLabelText(/work email address/i);
    const passwordInput = screen.getByLabelText(/password/i);

    fireEvent.change(emailInput, { target: { value: 'admin@tether.local' } });
    fireEvent.change(passwordInput, { target: { value: 'password123' } });

    const submitBtn = screen.getByRole('button', { name: /sign in/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(authApi.login).toHaveBeenCalledWith({
        email: 'admin@tether.local',
        password: 'password123',
      });
    });
  });

  it('renders RegisterPage and performs validation', async () => {
    vi.mocked(authApi.getMe).mockRejectedValue(new Error('Unauthenticated'));
    vi.mocked(authApi.register).mockResolvedValue({
      access_token: 'fake-jwt-token-2',
      token_type: 'bearer',
      user: {
        id: 2,
        email: 'alice@acme.local',
        full_name: 'Alice Wonder',
        is_active: true,
        is_verified: true,
        created_at: new Date().toISOString(),
      },
      active_tenant: {
        id: 2,
        name: 'Acme Corp',
        slug: 'acme-corp',
        created_at: new Date().toISOString(),
      },
      role: 'OWNER',
    });

    renderWithAuth(<RegisterPage />);

    expect(screen.getByText('Create your monitoring tenant')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/full name/i), { target: { value: 'Alice Wonder' } });
    fireEvent.change(screen.getByLabelText(/work email address/i), { target: { value: 'alice@acme.local' } });
    fireEvent.change(screen.getByLabelText(/password \(min\. 8 characters\)/i), { target: { value: 'password123' } });
    fireEvent.change(screen.getByLabelText(/confirm password/i), { target: { value: 'password123' } });

    const submitBtn = screen.getByRole('button', { name: /create account/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(authApi.register).toHaveBeenCalled();
    });
  });

  it('renders TeamManagementPage with member list and invite button', async () => {
    vi.mocked(authApi.getMe).mockResolvedValue({
      user: {
        id: 1,
        email: 'owner@acme.local',
        full_name: 'Org Owner',
        is_active: true,
        is_verified: true,
        created_at: new Date().toISOString(),
      },
      active_tenant: {
        id: 1,
        name: 'Acme Corp',
        slug: 'acme-corp',
        created_at: new Date().toISOString(),
      },
      role: 'OWNER',
      memberships: [],
    });

    vi.mocked(tenantsApi.listMembers).mockResolvedValue([
      {
        id: 10,
        user_id: 1,
        tenant_id: 1,
        role: 'OWNER',
        user: {
          id: 1,
          email: 'owner@acme.local',
          full_name: 'Org Owner',
          is_active: true,
          is_verified: true,
          created_at: new Date().toISOString(),
        },
        created_at: new Date().toISOString(),
      },
      {
        id: 11,
        user_id: 2,
        tenant_id: 1,
        role: 'MEMBER',
        user: {
          id: 2,
          email: 'dev@acme.local',
          full_name: 'Dev Member',
          is_active: true,
          is_verified: true,
          created_at: new Date().toISOString(),
        },
        created_at: new Date().toISOString(),
      },
    ]);

    renderWithAuth(<TeamManagementPage />);

    expect(screen.getByText('Team & Access Control')).toBeInTheDocument();
    expect(await screen.findByText('Org Owner')).toBeInTheDocument();
    expect(screen.getByText('Dev Member')).toBeInTheDocument();
    expect(screen.getByText('Invite Member')).toBeInTheDocument();
  });
});
