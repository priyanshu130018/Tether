import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Cpu, RefreshCw, Clock } from 'lucide-react';
import { getWorkers } from '../api/workers';
import { StatusBadge } from '../components/StatusBadge';
import { LoadingSkeleton } from '../components/LoadingSkeleton';
import { ErrorState } from '../components/ErrorState';
import { EmptyState } from '../components/EmptyState';
import { formatRelativeTime } from '../utils/formatters';

export const WorkersPage: React.FC = () => {
  const {
    data: workers,
    isLoading,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ['workers'],
    queryFn: () => getWorkers(),
    refetchInterval: 5000,
  });

  if (error) {
    return <ErrorState message="Failed to retrieve Celery worker nodes." onRetry={refetch} />;
  }

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-100">Worker Fleet</h1>
          <p className="text-sm text-slate-400 mt-1">
            Active Celery distributed monitoring workers, capacity, processed checks, and heartbeats.
          </p>
        </div>
        <button
          onClick={() => refetch()}
          type="button"
          className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border border-slate-800 bg-slate-900 text-xs font-mono text-slate-300 hover:text-white transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Workers Cards */}
      {isLoading ? (
        <LoadingSkeleton rows={4} />
      ) : !workers || workers.length === 0 ? (
        <EmptyState
          title="No worker nodes detected"
          description="Ensure Celery workers are running and connected to Redis."
          icon={Cpu}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {workers.map((w) => (
            <div
              key={w.worker_id}
              className="rounded-xl border border-slate-800 bg-slate-900/70 p-5 backdrop-blur-sm space-y-4"
            >
              <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                <div className="flex items-center gap-2.5">
                  <div className="p-2 rounded-lg bg-slate-800 text-emerald-400 border border-slate-700">
                    <Cpu className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold font-mono text-slate-100 truncate max-w-[180px]">
                      {w.worker_id}
                    </h3>
                    <div className="text-[10px] text-slate-500 font-mono">Celery Node</div>
                  </div>
                </div>
                <StatusBadge status={w.status} size="sm" />
              </div>

              <div className="grid grid-cols-3 gap-2 text-center font-mono">
                <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800">
                  <span className="text-[10px] uppercase text-slate-500 block">Active</span>
                  <span className="text-base font-bold text-sky-400">{w.active_jobs}</span>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800">
                  <span className="text-[10px] uppercase text-slate-500 block">Passed</span>
                  <span className="text-base font-bold text-emerald-400">{w.processed_jobs}</span>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800">
                  <span className="text-[10px] uppercase text-slate-500 block">Failed</span>
                  <span className="text-base font-bold text-rose-400">{w.failed_jobs}</span>
                </div>
              </div>

              <div className="flex items-center justify-between pt-2 text-[11px] font-mono text-slate-400 border-t border-slate-800/80">
                <span className="flex items-center gap-1 text-slate-500">
                  <Clock className="w-3 h-3" /> Last Active:
                </span>
                <span className="text-slate-200 font-bold">{formatRelativeTime(w.last_seen)}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
