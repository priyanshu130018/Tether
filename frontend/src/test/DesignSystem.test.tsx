import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { Button } from '../components/ui/Button';
import { IconButton } from '../components/ui/IconButton';
import { Card, CardHeader } from '../components/ui/Card';
import { FormField, Input, Select } from '../components/ui/FormField';
import { ToastProvider, useToast } from '../components/ui/Toast';
import { Trash2 } from 'lucide-react';

const ToastTestConsumer: React.FC = () => {
  const { showToast } = useToast();
  return (
    <div>
      <button onClick={() => showToast('success', 'Operation succeeded')}>Show Success</button>
      <button onClick={() => showToast('error', 'Operation failed')}>Show Error</button>
    </div>
  );
};

describe('Design System UI Components', () => {
  it('renders Button with variants and loading spinner', () => {
    const { rerender } = render(<Button variant="primary">Click Me</Button>);
    expect(screen.getByRole('button', { name: 'Click Me' })).toBeInTheDocument();

    rerender(<Button isLoading={true}>Click Me</Button>);
    const button = screen.getByRole('button');
    expect(button).toBeDisabled();
  });

  it('renders IconButton with accessible attributes', () => {
    const handleClick = vi.fn();
    render(
      <IconButton
        icon={<Trash2 className="w-4 h-4" />}
        aria-label="Delete item"
        onClick={handleClick}
        variant="danger"
      />
    );

    const btn = screen.getByRole('button', { name: 'Delete item' });
    expect(btn).toBeInTheDocument();
    fireEvent.click(btn);
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('renders Card and CardHeader with custom title and action', () => {
    render(
      <Card>
        <CardHeader
          title="Telemetry Data"
          description="Detailed probe observations"
          action={<button>Export</button>}
        />
        <div data-testid="card-content">Content</div>
      </Card>
    );

    expect(screen.getByText('Telemetry Data')).toBeInTheDocument();
    expect(screen.getByText('Detailed probe observations')).toBeInTheDocument();
    expect(screen.getByText('Export')).toBeInTheDocument();
    expect(screen.getByTestId('card-content')).toBeInTheDocument();
  });

  it('renders FormField with Input, Select, error and hint', () => {
    render(
      <form>
        <FormField label="Target Port" htmlFor="portInput" error="Invalid port range" required>
          <Input id="portInput" defaultValue="80" />
        </FormField>
        <FormField label="Protocol" htmlFor="protocolSelect" hint="TCP or HTTP">
          <Select id="protocolSelect">
            <option value="http">HTTP</option>
          </Select>
        </FormField>
      </form>
    );

    expect(screen.getByLabelText(/Target Port/i)).toBeInTheDocument();
    expect(screen.getByText('Invalid port range')).toBeInTheDocument();
    expect(screen.getByText('TCP or HTTP')).toBeInTheDocument();
  });

  it('triggers and renders toast notifications through ToastProvider', () => {
    render(
      <ToastProvider>
        <ToastTestConsumer />
      </ToastProvider>
    );

    const successBtn = screen.getByText('Show Success');
    act(() => {
      fireEvent.click(successBtn);
    });
    expect(screen.getByText('Operation succeeded')).toBeInTheDocument();

    const errorBtn = screen.getByText('Show Error');
    act(() => {
      fireEvent.click(errorBtn);
    });
    expect(screen.getByText('Operation failed')).toBeInTheDocument();
  });
});
