import React from 'react';

interface ProtocolBadgeProps {
  protocol: string;
}

export const ProtocolBadge: React.FC<ProtocolBadgeProps> = ({ protocol }) => {
  const norm = (protocol || '').toUpperCase();

  let colors = 'bg-slate-800 text-slate-300 border-slate-700';
  if (norm === 'HTTP') {
    colors = 'bg-blue-950/50 text-blue-400 border-blue-800/60';
  } else if (norm === 'HTTPS') {
    colors = 'bg-cyan-950/50 text-cyan-300 border-cyan-800/60';
  } else if (norm === 'DNS') {
    colors = 'bg-purple-950/50 text-purple-300 border-purple-800/60';
  } else if (norm === 'TCP') {
    colors = 'bg-emerald-950/50 text-emerald-300 border-emerald-800/60';
  }

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-medium border ${colors}`}
    >
      {norm}
    </span>
  );
};
