import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Layers, RefreshCw, ExternalLink } from 'lucide-react';
import { getJobs } from '../api/jobs';
import { getTargets } from '../api/targets';
import { JobStatus } from '../types';
import { StatusBadge } from '../components/StatusBadge';
import { LoadingSkeleton } from '../components/LoadingSkeleton';
import { ErrorState } from '../components/ErrorState';
import { EmptyState } from '../components/EmptyState';
import { formatDate, formatRelativeTime } from '../utils/formatters';

export const JobsPage: React.FC = () => {
  const [selectedTarget, setSelectedTarget] = useState<number | undefined>(undefined);
  const [selectedStatus, setSelectedStatus] = useState<string>('ALL');

  const { data: targets } = useQuery({
    queryKey: ['targets'],
    queryFn: () => getTargets(),
  });

  const {
    data: jobs,
    isLoading,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ['jobs', selectedTarget, selectedStatus],
    queryFn: () =>
      getJobs({
        target_id: selectedTarget,
        status: selectedStatus !== 'ALL' ? (selectedStatus.toLowerCase() as JobStatus) : undefined,
        limit: 100,
      }),
    refetchInterval: 5000,
  });

  if (error) {
    return <ErrorState message="Failed to load background monitoring jobs." onRetry={refetch} />;
  }

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-100">Background Jobs</h1>
          <p className="text-sm text-slate-400 mt-1">
            Real-time execution queue, Celery task workers, timings, and error outputs.
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

      {/* Filters Bar */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 p-4 rounded-xl border border-slate-800 bg-slate-900/60 backdrop-blur-sm text-xs font-mono">
        <div>
          <label className="block text-slate-400 mb-1 font-medium">Filter by Target</label>
          <select
            value={selectedTarget ?? ''}
            onChange={(e) => setSelectedTarget(e.target.value ? Number(e.target.value) : undefined)}
            className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500"
          >
            <option value="">All Targets</option>
            {targets?.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name} ({t.protocol.toUpperCase()}://{t.hostname}:{t.port})
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-slate-400 mb-1 font-medium">Job Status</label>
          <select
            value={selectedStatus}
            onChange={(e) => setSelectedStatus(e.target.value)}
            className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500"
          >
            <option value="ALL">All Statuses</option>
            <option value="QUEUED">QUEUED</option>
            <option value="RUNNING">RUNNING</option>
            <option value="SUCCESSFUL">SUCCESSFUL</option>
            <option value="FAILED">FAILED</option>
            <option value="TIMED_OUT">TIMED_OUT</option>
          </select>
        </div>
      </div>

      {/* Jobs Table */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/70 overflow-hidden backdrop-blur-sm">
        {isLoading ? (
          <div className="p-6">
            <LoadingSkeleton rows={6} />
          </div>
        ) : !jobs || jobs.length === 0 ? (
          <div className="p-8">
            <EmptyState
              title="No monitoring jobs found"
              description="Jobs will appear here as Celery Beat schedules checks or when manual checks are triggered."
              icon={Layers}
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-slate-950/60 text-slate-400 uppercase tracking-wider border-b border-slate-800 text-[11px]">
                <tr>
                  <th className="py-3.5 px-4 font-semibold">Job ID</th>
                  <th className="py-3.5 px-4 font-semibold">Target</th>
                  <th className="py-3.5 px-4 font-semibold">Task Type</th>
                  <th className="py-3.5 px-4 font-semibold">Status</th>
                  <th className="py-3.5 px-4 font-semibold">Duration</th>
                  <th className="py-3.5 px-4 font-semibold">Created / Started</th>
                  <th className="py-3.5 px-4 font-semibold">Worker Node</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {jobs.map((j) => (
                  <tr key={j.id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="py-3 px-4 font-bold text-slate-300">#{j.id}</td>
                    <td className="py-3 px-4">
                      <Link
                        to={`/targets/${j.target_id}`}
                        className="font-semibold text-emerald-400 hover:underline inline-flex items-center gap-1"
                      >
                        <span>Target #{j.target_id}</span>
                        <ExternalLink className="w-3 h-3" />
                      </Link>
                    </td>
                    <td className="py-3 px-4 text-slate-300 font-semibold">{j.task_type}</td>
                    <td className="py-3 px-4">
                      <StatusBadge status={j.status} size="sm" />
                    </td>
                    <td className="py-3 px-4 text-slate-300">
                      {j.duration_ms !== undefined && j.duration_ms !== null ? (
                        <span className="font-bold text-emerald-400">{j.duration_ms.toFixed(1)}ms</span>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td className="py-3 px-4 text-slate-400">
                      <div>{formatRelativeTime(j.created_at)}</div>
                      <div className="text-[10px] text-slate-600">{formatDate(j.created_at)}</div>
                    </td>
                    <td className="py-3 px-4 text-slate-400 max-w-xs truncate" title={j.worker_id || ''}>
                      {j.worker_id || 'unassigned'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
