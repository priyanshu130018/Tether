import React from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';

interface ErrorStateProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  title = 'Failed to load data',
  message = 'Unable to connect to the Tether monitoring API.',
  onRetry,
}) => {
  return (
    <div className="rounded-xl border border-rose-900/50 bg-rose-950/20 p-6 text-center max-w-lg mx-auto my-8">
      <div className="inline-flex p-3 rounded-full bg-rose-900/40 text-rose-400 mb-3 border border-rose-800/60">
        <AlertCircle className="w-6 h-6" />
      </div>
      <h3 className="text-base font-semibold text-rose-200">{title}</h3>
      <p className="mt-1 text-sm text-rose-300/80 font-mono">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          type="button"
          className="mt-4 inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg bg-rose-900/60 text-rose-200 hover:bg-rose-800/80 transition-colors border border-rose-700/60"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Retry Request</span>
        </button>
      )}
    </div>
  );
};
