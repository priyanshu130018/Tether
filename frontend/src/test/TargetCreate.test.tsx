import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import { TargetCreatePage } from '../pages/TargetCreatePage';

import { AuthProvider } from '../context/AuthContext';
import { ToastProvider } from '../components/ui/Toast';
import * as authApi from '../api/auth';

vi.mock('../api/auth');

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
        <ToastProvider>
          <BrowserRouter>{ui}</BrowserRouter>
        </ToastProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
};

describe('TargetCreatePage', () => {
  it('renders target creation form and toggles protocol fields', () => {
    renderWithProviders(<TargetCreatePage />);

    expect(screen.getByText('Add Monitoring Target')).toBeInTheDocument();
    expect(screen.getByLabelText(/Target Name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Host \/ IP \/ Domain/i)).toBeInTheDocument();

    const protocolSelect = screen.getByLabelText(/Protocol \*/i);
    expect(protocolSelect).toBeInTheDocument();

    // Select HTTP -> HTTP fields appear
    fireEvent.change(protocolSelect, { target: { value: 'http' } });
    expect(screen.getByText('HTTP / HTTPS Configuration')).toBeInTheDocument();
    expect(screen.getByLabelText(/HTTP Method/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Request Path/i)).toBeInTheDocument();

    // Select DNS -> DNS fields appear
    fireEvent.change(protocolSelect, { target: { value: 'dns' } });
    expect(screen.getByText('DNS Configuration')).toBeInTheDocument();
    expect(screen.getByLabelText(/Record Type/i)).toBeInTheDocument();
  });
});
