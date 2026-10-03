import React from 'react';
import { CheckCircle2, XCircle, HelpCircle, Clock, AlertTriangle, Play, Flame, ShieldCheck } from 'lucide-react';

interface StatusBadgeProps {
  status: string;
  size?: 'sm' | 'md' | 'lg';
  showIcon?: boolean;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, size = 'md', showIcon = true }) => {
  const norm = (status || '').toUpperCase();

  let bgClass = 'bg-slate-800/80 text-slate-300 border-slate-700';
  let Icon = HelpCircle;
  let iconClass = 'text-slate-400';

  if (norm === 'UP' || norm === 'SUCCESSFUL' || norm === 'SENT' || norm === 'ACTIVE') {
    bgClass = 'bg-emerald-950/40 text-emerald-400 border-emerald-800/50';
    Icon = CheckCircle2;
    iconClass = 'text-emerald-400';
  } else if (norm === 'DOWN' || norm === 'FAILED' || norm === 'OUTAGE') {
    bgClass = 'bg-rose-950/40 text-rose-400 border-rose-800/50';
    Icon = norm === 'OUTAGE' ? Flame : XCircle;
    iconClass = 'text-rose-400';
  } else if (norm === 'RECOVERY') {
    bgClass = 'bg-teal-950/40 text-teal-300 border-teal-800/50';
    Icon = ShieldCheck;
    iconClass = 'text-teal-400';
  } else if (norm === 'RUNNING' || norm === 'PROCESSING') {
    bgClass = 'bg-sky-950/40 text-sky-400 border-sky-800/50 animate-pulse';
    Icon = Play;
    iconClass = 'text-sky-400';
  } else if (norm === 'QUEUED' || norm === 'SCHEDULED' || norm === 'PENDING') {
    bgClass = 'bg-amber-950/40 text-amber-400 border-amber-800/50';
    Icon = Clock;
    iconClass = 'text-amber-400';
  } else if (norm === 'TIMED_OUT' || norm === 'SUPPRESSED') {
    bgClass = 'bg-zinc-800/80 text-zinc-400 border-zinc-700';
    Icon = AlertTriangle;
    iconClass = 'text-zinc-400';
  }

  const sizeClasses = {
    sm: 'px-1.5 py-0.5 text-xs gap-1',
    md: 'px-2.5 py-1 text-xs font-medium gap-1.5',
    lg: 'px-3 py-1.5 text-sm font-semibold gap-2',
  };

  const iconSizes = {
    sm: 'w-3 h-3',
    md: 'w-3.5 h-3.5',
    lg: 'w-4 h-4',
  };

  return (
    <span
      className={`inline-flex items-center rounded-md border tracking-wide font-mono ${bgClass} ${sizeClasses[size]}`}
    >
      {showIcon && <Icon className={`${iconSizes[size]} ${iconClass} shrink-0`} />}
      <span>{norm}</span>
    </span>
  );
};
