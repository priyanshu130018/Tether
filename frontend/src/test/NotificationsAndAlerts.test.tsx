import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import { NotificationChannelsPage } from '../pages/NotificationChannelsPage';
import { AlertsPage } from '../pages/AlertsPage';
import * as notifApi from '../api/notifications';
import * as alertsApi from '../api/alerts';
import * as targetsApi from '../api/targets';

import { AuthProvider } from '../context/AuthContext';
import * as authApi from '../api/auth';

vi.mock('../api/auth');
vi.mock('../api/notifications');
vi.mock('../api/alerts');
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

describe('NotificationChannelsPage & AlertsPage', () => {
  it('renders notification channels and triggers test notification', async () => {
    vi.mocked(notifApi.getNotificationChannels).mockResolvedValue([
      {
        id: 1,
        name: 'DevOps Slack',
        type: 'SLACK',
        enabled: true,
        configuration: { webhook_url: 'https://hooks.slack.com/services/***' },
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    ]);

    vi.mocked(notifApi.testNotificationChannel).mockResolvedValue({
      success: true,
      message: 'Test notification delivered successfully',
    });

    renderWithProviders(<NotificationChannelsPage />);

    expect(screen.getByText('Notification Channels')).toBeInTheDocument();
    expect(await screen.findByText('DevOps Slack')).toBeInTheDocument();
    expect(screen.getByText('https://hooks.slack.com/services/***')).toBeInTheDocument();

    const testBtn = screen.getByRole('button', { name: /test/i });
    fireEvent.click(testBtn);

    await waitFor(() => {
      expect(screen.getByText(/Test notification delivered successfully/i)).toBeInTheDocument();
    });
  });

  it('renders alerts history and active outages', async () => {
    vi.mocked(targetsApi.getTargets).mockResolvedValue([
      {
        id: 1,
        name: 'Critical API',
        hostname: 'api.example.com',
        port: 443,
        protocol: 'https',
        interval_seconds: 60,
        timeout_seconds: 5,
        retry_count: 0,
        enabled: true,
        status: 'DOWN',
        consecutive_failures: 3,
        consecutive_successes: 0,
        created_at: new Date().toISOString(),
      },
    ]);

    vi.mocked(alertsApi.getAlerts).mockResolvedValue([
      {
        id: 101,
        target_id: 1,
        event_type: 'OUTAGE',
        status: 'SENT',
        message: 'Target is DOWN. 3 consecutive failures.',
        deduplication_key: 'outage:1:123',
        created_at: new Date().toISOString(),
      },
    ]);

    renderWithProviders(<AlertsPage />);

    expect(screen.getByText('Alerts & Incidents')).toBeInTheDocument();
    const alertElements = await screen.findAllByText(/Target is DOWN\. 3 consecutive failures\./i);
    expect(alertElements.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Active Outage Incidents (1)')).toBeInTheDocument();
  });
});
