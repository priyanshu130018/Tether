import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import { SystemStatusPage } from '../pages/SystemStatusPage';
import { AuthProvider } from '../context/AuthContext';
import * as systemApi from '../api/system';
import * as workersApi from '../api/workers';
import * as authApi from '../api/auth';

vi.mock('../api/system');
vi.mock('../api/workers');
vi.mock('../api/auth');

const renderWithProviders = (ui: React.ReactElement) => {
  vi.mocked(authApi.getMe).mockResolvedValue({
    user: { id: 1, email: 'admin@tether.local', full_name: 'Admin', is_active: true, is_verified: true, created_at: '' },
    active_tenant: { id: 1, name: 'Default Org', slug: 'default-org', created_at: '' },
    role: 'OWNER',
    memberships: [],
  });

  vi.mocked(systemApi.getSystemHealth).mockResolvedValue({
    status: 'healthy',
    app_name: 'Tether',
    version: '1.0.0',
    environment: 'production',
    uptime_seconds: 3665,
    database: 'healthy',
    redis: 'healthy',
    timestamp: '2026-10-03T00:00:00Z',
  });

  vi.mocked(workersApi.getWorkers).mockResolvedValue([
    {
      worker_id: 'celery@worker-1',
      status: 'online',
      active_jobs: 0,
      processed_jobs: 142,
      failed_jobs: 2,
      last_seen: '2026-10-03T00:00:00Z',
    },
  ]);

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

describe('Phase 7: System Observability & Infrastructure UI', () => {
  it('renders SystemStatusPage with live health cards and environment metadata', async () => {
    renderWithProviders(<SystemStatusPage />);

    expect(screen.getByText(/System Observability & Infrastructure/i)).toBeInTheDocument();
    expect(await screen.findByText(/All Core Systems Operational/i)).toBeInTheDocument();
    expect(screen.getByText(/FastAPI Service/i)).toBeInTheDocument();
    expect(screen.getAllByText(/PostgreSQL/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Redis Broker/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/1 Active Nodes/i)).toBeInTheDocument();
    expect(screen.getByText(/Environment: production/i)).toBeInTheDocument();
  });
});
