import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Cpu, RefreshCw, Clock, Activity, AlertTriangle } from 'lucide-react';
import { getWorkers } from '../api/workers';
import { StatusBadge } from '../components/StatusBadge';
import { LoadingSkeleton } from '../components/LoadingSkeleton';
import { ErrorState } from '../components/ErrorState';
import { EmptyState } from '../components/EmptyState';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { useToast } from '../components/ui/Toast';
import { formatRelativeTime } from '../utils/formatters';

export const WorkersPage: React.FC = () => {
  const { showToast } = useToast();
  const {
    data: workers,
    isLoading,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ['workers'],
    queryFn: async () => {
      try {
        return await getWorkers();
      } catch (err: any) {
        showToast('error', err?.message || 'Failed to retrieve Celery worker nodes');
        throw err;
      }
    },
    refetchInterval: 5000,
  });

  if (error) {
    return <ErrorState message="Failed to retrieve Celery worker nodes." onRetry={refetch} />;
  }

  const totalWorkers = workers?.length || 0;
  const activeWorkers = workers?.filter((w) => w.status === 'HEALTHY' || w.status === 'ONLINE').length || 0;
  const totalActiveJobs = workers?.reduce((sum, w) => sum + (w.active_jobs || 0), 0) || 0;

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-100 flex items-center gap-2.5">
            <Cpu className="w-6 h-6 text-emerald-400" />
            <span>Worker Fleet</span>
          </h1>
          <p className="text-sm text-slate-400 mt-1 font-mono">
            Active Celery distributed monitoring workers, execution load, processed tasks, and health heartbeats.
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => refetch()}
          loading={isFetching}
          icon={<RefreshCw className="w-3.5 h-3.5" />}
        >
          Refresh
        </Button>
      </div>

      {/* Summary Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 font-mono">
        <Card className="p-4 flex items-center justify-between">
          <div>
            <div className="text-[11px] uppercase text-slate-500 font-semibold">Registered Workers</div>
            <div className="text-2xl font-bold text-slate-100 mt-1">{totalWorkers}</div>
          </div>
          <div className="p-2.5 rounded-xl bg-slate-800 text-slate-400 border border-slate-700">
            <Cpu className="w-5 h-5" />
          </div>
        </Card>
        <Card className="p-4 flex items-center justify-between">
          <div>
            <div className="text-[11px] uppercase text-slate-500 font-semibold">Healthy Nodes</div>
            <div className="text-2xl font-bold text-emerald-400 mt-1">{activeWorkers}</div>
          </div>
          <div className="p-2.5 rounded-xl bg-emerald-950/40 text-emerald-400 border border-emerald-800/60">
            <Activity className="w-5 h-5" />
          </div>
        </Card>
        <Card className="p-4 flex items-center justify-between">
          <div>
            <div className="text-[11px] uppercase text-slate-500 font-semibold">Executing Jobs</div>
            <div className="text-2xl font-bold text-sky-400 mt-1">{totalActiveJobs}</div>
          </div>
          <div className="p-2.5 rounded-xl bg-sky-950/40 text-sky-400 border border-sky-800/60">
            <AlertTriangle className="w-5 h-5" />
          </div>
        </Card>
      </div>

      {/* Workers Cards */}
      {isLoading ? (
        <LoadingSkeleton rows={4} />
      ) : !workers || workers.length === 0 ? (
        <EmptyState
          title="No worker nodes detected"
          description="Ensure Celery distributed worker processes are running and connected to Redis."
          icon={Cpu}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {workers.map((w) => (
            <Card
              key={w.worker_id}
              className="p-5 space-y-4 hover:border-slate-700 transition-colors"
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
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};
