import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { StatusBadge } from '../components/StatusBadge';
import { ProtocolBadge } from '../components/ProtocolBadge';
import { SummaryCard } from '../components/SummaryCard';
import { Server } from 'lucide-react';

describe('UI Component rendering', () => {
  it('renders StatusBadge with accessible label and icons', () => {
    const { rerender } = render(<StatusBadge status="UP" />);
    expect(screen.getByText('UP')).toBeInTheDocument();

    rerender(<StatusBadge status="DOWN" />);
    expect(screen.getByText('DOWN')).toBeInTheDocument();

    rerender(<StatusBadge status="OUTAGE" />);
    expect(screen.getByText('OUTAGE')).toBeInTheDocument();

    rerender(<StatusBadge status="RECOVERY" />);
    expect(screen.getByText('RECOVERY')).toBeInTheDocument();
  });

  it('renders ProtocolBadge with protocol names', () => {
    const { rerender } = render(<ProtocolBadge protocol="http" />);
    expect(screen.getByText('HTTP')).toBeInTheDocument();

    rerender(<ProtocolBadge protocol="https" />);
    expect(screen.getByText('HTTPS')).toBeInTheDocument();

    rerender(<ProtocolBadge protocol="dns" />);
    expect(screen.getByText('DNS')).toBeInTheDocument();

    rerender(<ProtocolBadge protocol="tcp" />);
    expect(screen.getByText('TCP')).toBeInTheDocument();
  });

  it('renders SummaryCard with title and numeric value', () => {
    render(
      <SummaryCard
        title="Active Targets"
        value={42}
        icon={Server}
        variant="success"
        subtitle="Healthy fleet"
      />
    );
    expect(screen.getByText('Active Targets')).toBeInTheDocument();
    expect(screen.getByText('42')).toBeInTheDocument();
    expect(screen.getByText('Healthy fleet')).toBeInTheDocument();
  });
});
