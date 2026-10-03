import React from 'react';
import { LucideIcon } from 'lucide-react';

interface SummaryCardProps {
  title: string;
  value: number | string;
  icon: LucideIcon;
  variant?: 'default' | 'success' | 'danger' | 'warning' | 'info';
  subtitle?: string;
  onClick?: () => void;
}

export const SummaryCard: React.FC<SummaryCardProps> = ({
  title,
  value,
  icon: Icon,
  variant = 'default',
  subtitle,
  onClick,
}) => {
  const variantStyles = {
    default: {
      border: 'border-slate-800 hover:border-slate-700',
      iconBg: 'bg-slate-800/80 text-slate-300',
      valueColor: 'text-slate-100',
    },
    success: {
      border: 'border-emerald-900/40 hover:border-emerald-700/60 bg-emerald-950/10',
      iconBg: 'bg-emerald-950/60 text-emerald-400 border border-emerald-800/40',
      valueColor: 'text-emerald-400',
    },
    danger: {
      border: 'border-rose-900/40 hover:border-rose-700/60 bg-rose-950/10',
      iconBg: 'bg-rose-950/60 text-rose-400 border border-rose-800/40',
      valueColor: 'text-rose-400',
    },
    warning: {
      border: 'border-amber-900/40 hover:border-amber-700/60 bg-amber-950/10',
      iconBg: 'bg-amber-950/60 text-amber-400 border border-amber-800/40',
      valueColor: 'text-amber-400',
    },
    info: {
      border: 'border-sky-900/40 hover:border-sky-700/60 bg-sky-950/10',
      iconBg: 'bg-sky-950/60 text-sky-400 border border-sky-800/40',
      valueColor: 'text-sky-400',
    },
  };

  const style = variantStyles[variant];

  return (
    <div
      onClick={onClick}
      className={`rounded-xl border bg-slate-900/70 p-5 transition-all duration-200 backdrop-blur-sm ${
        style.border
      } ${onClick ? 'cursor-pointer hover:scale-[1.01]' : ''}`}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">{title}</span>
        <div className={`p-2.5 rounded-lg ${style.iconBg}`}>
          <Icon className="w-5 h-5" />
        </div>
      </div>
      <div className="mt-3 flex items-baseline gap-2">
        <span className={`text-3xl font-bold font-mono tracking-tight ${style.valueColor}`}>{value}</span>
        {subtitle && <span className="text-xs text-slate-500 font-medium">{subtitle}</span>}
      </div>
    </div>
  );
};
