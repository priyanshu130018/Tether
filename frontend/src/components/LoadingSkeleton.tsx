import React from 'react';

export const LoadingSkeleton: React.FC<{ rows?: number }> = ({ rows = 5 }) => {
  return (
    <div className="w-full space-y-3 animate-pulse" role="status" aria-label="Loading content">
      <div className="h-10 bg-slate-800/60 rounded-lg w-full mb-4"></div>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-12 bg-slate-800/40 rounded-lg w-full flex items-center px-4 gap-4">
          <div className="h-4 bg-slate-700/50 rounded w-1/4"></div>
          <div className="h-4 bg-slate-700/50 rounded w-1/6"></div>
          <div className="h-4 bg-slate-700/50 rounded w-1/6"></div>
          <div className="h-4 bg-slate-700/50 rounded w-1/4"></div>
        </div>
      ))}
      <span className="sr-only">Loading...</span>
    </div>
  );
};
