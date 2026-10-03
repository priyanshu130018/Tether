import React from 'react';
import { LucideIcon, Inbox } from 'lucide-react';

interface EmptyStateProps {
  title: string;
  description: string;
  icon?: LucideIcon;
  actionText?: string;
  onAction?: () => void;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  description,
  icon: Icon = Inbox,
  actionText,
  onAction,
}) => {
  return (
    <div className="rounded-xl border border-dashed border-slate-800 bg-slate-900/30 p-12 text-center">
      <div className="inline-flex p-3.5 rounded-xl bg-slate-800/80 text-slate-400 mb-4 border border-slate-700">
        <Icon className="w-6 h-6" />
      </div>
      <h3 className="text-base font-semibold text-slate-200">{title}</h3>
      <p className="mt-1.5 text-sm text-slate-400 max-w-sm mx-auto">{description}</p>
      {actionText && onAction && (
        <button
          onClick={onAction}
          type="button"
          className="mt-5 inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg bg-emerald-600 text-white hover:bg-emerald-500 transition-colors shadow-lg shadow-emerald-950/40"
        >
          {actionText}
        </button>
      )}
    </div>
  );
};
