import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import { TargetsListPage } from '../pages/TargetsListPage';
import { AuthProvider } from '../context/AuthContext';
import { ToastProvider } from '../components/ui/Toast';
import * as targetsApi from '../api/targets';
import * as authApi from '../api/auth';

vi.mock('../api/auth');
vi.mock('../api/targets');

const renderWithProviders = () => {
  vi.mocked(authApi.getMe).mockResolvedValue({
    user: { id: 1, email: 'admin@tether.local', full_name: 'Admin', is_active: true, is_verified: true, created_at: '' },
    active_tenant: { id: 1, name: 'Default Org', slug: 'default-org', created_at: '' },
    role: 'OWNER',
    memberships: [],
  });

  vi.mocked(targetsApi.getTargets).mockResolvedValue([
    {
      id: 1,
      name: 'Alpha API',
      hostname: 'alpha.example.com',
      port: 443,
      protocol: 'https',
      interval_seconds: 60,
      timeout_seconds: 5,
      retry_count: 2,
      enabled: true,
      status: 'UP',
      consecutive_failures: 0,
      consecutive_successes: 20,
      created_at: new Date().toISOString(),
    },
    {
      id: 2,
      name: 'Beta DB',
      hostname: 'beta.example.com',
      port: 5432,
      protocol: 'tcp',
      interval_seconds: 120,
      timeout_seconds: 5,
      retry_count: 2,
      enabled: true,
      status: 'DOWN',
      consecutive_failures: 4,
      consecutive_successes: 0,
      created_at: new Date().toISOString(),
    },
  ]);

  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ToastProvider>
          <BrowserRouter>
            <TargetsListPage />
          </BrowserRouter>
        </ToastProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
};

describe('TargetsListPage', () => {
  it('renders target cards and filters by search text', async () => {
    renderWithProviders();

    expect(screen.getByText('Monitored Targets')).toBeInTheDocument();
    expect(await screen.findByText('Alpha API')).toBeInTheDocument();
    expect(screen.getByText('Beta DB')).toBeInTheDocument();

    const searchInput = screen.getByPlaceholderText(/Search by name/i);
    fireEvent.change(searchInput, { target: { value: 'Alpha' } });

    expect(screen.getByText('Alpha API')).toBeInTheDocument();
    expect(screen.queryByText('Beta DB')).not.toBeInTheDocument();
  });

  it('filters by status dropdown', async () => {
    renderWithProviders();

    expect(await screen.findByText('Alpha API')).toBeInTheDocument();

    const statusSelect = screen.getByDisplayValue('All Statuses');
    fireEvent.change(statusSelect, { target: { value: 'DOWN' } });

    expect(screen.queryByText('Alpha API')).not.toBeInTheDocument();
    expect(screen.getByText('Beta DB')).toBeInTheDocument();
  });
});
