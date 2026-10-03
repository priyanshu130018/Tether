import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { TargetDetailPage } from '../pages/TargetDetailPage';
import { AuthProvider } from '../context/AuthContext';
import { ToastProvider } from '../components/ui/Toast';
import * as targetsApi from '../api/targets';
import * as authApi from '../api/auth';

vi.mock('../api/auth');
vi.mock('../api/targets');

const renderWithProviders = (targetId: number = 1) => {
  vi.mocked(authApi.getMe).mockResolvedValue({
    user: { id: 1, email: 'admin@tether.local', full_name: 'Admin', is_active: true, is_verified: true, created_at: '' },
    active_tenant: { id: 1, name: 'Default Org', slug: 'default-org', created_at: '' },
    role: 'OWNER',
    memberships: [],
  });

  vi.mocked(targetsApi.getTarget).mockResolvedValue({
    id: targetId,
    name: 'Production Gateway',
    hostname: 'gateway.example.com',
    port: 443,
    protocol: 'https',
    interval_seconds: 60,
    timeout_seconds: 5,
    retry_count: 2,
    enabled: true,
    status: 'UP',
    consecutive_failures: 0,
    consecutive_successes: 25,
    created_at: '2026-10-01T00:00:00Z',
  });

  vi.mocked(targetsApi.getTargetLatency).mockResolvedValue([
    { timestamp: '2026-10-03T12:00:00Z', latency_ms: 45, status: 'up' },
    { timestamp: '2026-10-03T12:15:00Z', latency_ms: 55, status: 'up' },
    { timestamp: '2026-10-03T12:30:00Z', latency_ms: 50, status: 'up' },
  ]);

  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ToastProvider>
          <MemoryRouter initialEntries={[`/targets/${targetId}`]}>
            <Routes>
              <Route path="/targets/:id" element={<TargetDetailPage />} />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
};

describe('TargetDetailPage', () => {
  it('renders target metadata and latency metrics summary', async () => {
    renderWithProviders(1);

    expect(await screen.findByText('Production Gateway')).toBeInTheDocument();
    expect(screen.getByText(/gateway\.example\.com:443/i)).toBeInTheDocument();

    // Check time range controls
    expect(screen.getByRole('button', { name: '1h' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '6h' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '24h' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '7d' })).toBeInTheDocument();
  });

  it('triggers manual check with feedback', async () => {
    vi.mocked(targetsApi.runManualCheck).mockResolvedValue({
      id: 99,
      task_type: 'check_target',
      status: 'queued',
      target_id: 1,
      created_at: new Date().toISOString(),
    });

    renderWithProviders(1);

    const runCheckBtn = await screen.findByRole('button', { name: /run check/i });
    fireEvent.click(runCheckBtn);

    await waitFor(() => {
      expect(targetsApi.runManualCheck).toHaveBeenCalledWith(1);
    });
  });

  it('opens delete modal and can cancel', async () => {
    renderWithProviders(1);

    const deleteBtn = await screen.findByRole('button', { name: /delete target/i });
    fireEvent.click(deleteBtn);

    expect(await screen.findByText('Delete Target Confirmation')).toBeInTheDocument();
    expect(screen.getByText(/Are you sure you want to delete target/i)).toBeInTheDocument();

    const cancelBtn = screen.getByRole('button', { name: /cancel/i });
    fireEvent.click(cancelBtn);

    await waitFor(() => {
      expect(screen.queryByText('Delete Target Confirmation')).not.toBeInTheDocument();
    });
  });
});
