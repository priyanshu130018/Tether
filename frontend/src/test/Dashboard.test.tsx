import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import { DashboardPage } from '../pages/DashboardPage';
import * as dashboardApi from '../api/dashboard';
import * as targetsApi from '../api/targets';

import { AuthProvider } from '../context/AuthContext';
import * as authApi from '../api/auth';

vi.mock('../api/auth');
vi.mock('../api/dashboard');
vi.mock('../api/targets');

const renderWithProviders = (ui: React.ReactElement) => {
  vi.mocked(authApi.getMe).mockResolvedValue({
    user: { id: 1, email: 'admin@tether.local', full_name: 'Admin', is_active: true, is_verified: true, created_at: '' },
    active_tenant: { id: 1, name: 'Default Org', slug: 'default-org', created_at: '' },
    role: 'OWNER',
    memberships: [],
  });

  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>{ui}</BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
};

describe('DashboardPage', () => {
  it('renders dashboard with summary cards and targets list', async () => {
    vi.mocked(dashboardApi.getDashboardSummary).mockResolvedValue({
      targets: 5,
      up: 4,
      down: 1,
      unknown: 0,
      active_alerts: 1,
      running_jobs: 0,
      total_jobs: 25,
      active_workers: 1,
    });

    vi.mocked(targetsApi.getTargets).mockResolvedValue([
      {
        id: 1,
        name: 'Production Web App',
        hostname: 'app.example.com',
        port: 443,
        protocol: 'https',
        interval_seconds: 60,
        timeout_seconds: 5,
        retry_count: 2,
        enabled: true,
        status: 'UP',
        consecutive_failures: 0,
        consecutive_successes: 10,
        created_at: new Date().toISOString(),
      },
      {
        id: 2,
        name: 'Failed Database',
        hostname: 'db.example.com',
        port: 5432,
        protocol: 'tcp',
        interval_seconds: 60,
        timeout_seconds: 5,
        retry_count: 2,
        enabled: true,
        status: 'DOWN',
        consecutive_failures: 3,
        consecutive_successes: 0,
        created_at: new Date().toISOString(),
      },
    ]);

    renderWithProviders(<DashboardPage />);

    expect(screen.getByText('Operations Dashboard')).toBeInTheDocument();
    expect(await screen.findByText('Production Web App')).toBeInTheDocument();
    expect(screen.getAllByText('Failed Database').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Active Outages (1)')).toBeInTheDocument();
  });
});
