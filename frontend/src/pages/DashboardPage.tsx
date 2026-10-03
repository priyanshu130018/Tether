import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  Server,
  CheckCircle2,
  XCircle,
  HelpCircle,
  AlertTriangle,
  Play,
  ArrowRight,
  RefreshCw,
  ExternalLink,
} from 'lucide-react';
import { getDashboardSummary } from '../api/dashboard';
import { getTargets, runManualCheck } from '../api/targets';
import { SummaryCard } from '../components/SummaryCard';
import { StatusBadge } from '../components/StatusBadge';
import { ProtocolBadge } from '../components/ProtocolBadge';
import { LoadingSkeleton } from '../components/LoadingSkeleton';
import { ErrorState } from '../components/ErrorState';
import { Button } from '../components/ui/Button';
import { IconButton } from '../components/ui/IconButton';
import { useToast } from '../components/ui/Toast';
import { formatRelativeTime } from '../utils/formatters';

export const DashboardPage: React.FC = () => {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [checkingTargetId, setCheckingTargetId] = useState<number | null>(null);

  const {
    data: summary,
    isLoading: isSummaryLoading,
    isFetching: isSummaryFetching,
    error: summaryError,
    refetch: refetchSummary,
  } = useQuery({
    queryKey: ['dashboardSummary'],
    queryFn: getDashboardSummary,
    refetchInterval: 5000,
  });

  const {
    data: targets,
    isLoading: isTargetsLoading,
    isFetching: isTargetsFetching,
    error: targetsError,
    refetch: refetchTargets,
  } = useQuery({
    queryKey: ['targets'],
    queryFn: () => getTargets(),
    refetchInterval: 5000,
  });

  const checkMutation = useMutation({
    mutationFn: (targetId: number) => runManualCheck(targetId),
    onMutate: (id) => setCheckingTargetId(id),
    onSuccess: (job) => {
      toast.success(`Check job #${job.id} dispatched.`);
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ['targets'] });
        queryClient.invalidateQueries({ queryKey: ['dashboardSummary'] });
        queryClient.invalidateQueries({ queryKey: ['jobs'] });
        setCheckingTargetId(null);
      }, 2500);
    },
    onError: (err: any) => {
      setCheckingTargetId(null);
      toast.error(err?.response?.data?.detail || 'Failed to dispatch manual check.');
    },
  });

  if (summaryError || targetsError) {
    return (
      <ErrorState
        title="Failed to load dashboard overview"
        message="Could not connect to Tether monitoring backend."
        onRetry={() => {
          refetchSummary();
          refetchTargets();
        }}
      />
    );
  }

  const downTargets = (targets || []).filter((t) => t.status === 'DOWN');

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-100">Operations Dashboard</h1>
          <p className="text-xs text-slate-400 mt-1">
            Real-time multi-protocol network health, active alerts, and scheduler status.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              refetchSummary();
              refetchTargets();
            }}
            isLoading={isSummaryFetching || isTargetsFetching}
            leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
          >
            Refresh
          </Button>
        </div>
      </div>

      {/* Summary Metric Cards */}
      {isSummaryLoading ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-24 rounded-xl bg-slate-900 border border-slate-800 animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          <SummaryCard
            title="Targets"
            value={summary?.targets ?? 0}
            icon={Server}
            variant="default"
          />
          <SummaryCard
            title="UP"
            value={summary?.up ?? 0}
            icon={CheckCircle2}
            variant="success"
          />
          <SummaryCard
            title="DOWN"
            value={summary?.down ?? 0}
            icon={XCircle}
            variant="danger"
          />
          <SummaryCard
            title="UNKNOWN"
            value={summary?.unknown ?? 0}
            icon={HelpCircle}
            variant="default"
          />
          <SummaryCard
            title="Active Alerts"
            value={summary?.active_alerts ?? 0}
            icon={AlertTriangle}
            variant={summary?.active_alerts ? 'danger' : 'default'}
          />
          <SummaryCard
            title="In-Progress"
            value={summary?.running_jobs ?? 0}
            icon={Play}
            variant="info"
          />
        </div>
      )}

      {/* Active Outage Alert Banner */}
      {downTargets.length > 0 && (
        <div className="rounded-xl border border-rose-900/60 bg-rose-950/20 p-4">
          <div className="flex items-center gap-2 text-rose-400 font-semibold mb-3 text-sm">
            <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>Active Outages ({downTargets.length})</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {downTargets.map((t) => (
              <div
                key={t.id}
                className="flex items-center justify-between p-3 rounded-lg bg-rose-950/40 border border-rose-800/40 text-xs font-mono"
              >
                <div>
                  <Link to={`/targets/${t.id}`} className="font-semibold text-rose-200 hover:underline">
                    {t.name}
                  </Link>
                  <div className="text-slate-400 text-[11px] mt-0.5">
                    {t.protocol.toUpperCase()}://{t.hostname}:{t.port}
                  </div>
                </div>
                <div className="text-right">
                  <span className="px-2 py-0.5 rounded bg-rose-900/60 text-rose-300 font-bold border border-rose-700/50">
                    {t.consecutive_failures} fail
                  </span>
                  <div className="text-[10px] text-slate-400 mt-1">
                    {formatRelativeTime(t.last_failed_check_at)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Target Health Overview Table */}
      <div className="rounded-xl border border-slate-800 bg-slate-900 overflow-hidden">
        <div className="flex items-center justify-between p-4 border-b border-slate-800">
          <div>
            <h2 className="text-sm font-semibold text-slate-200">
              Monitored Target Fleet
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Live status, last check latency, and next execution schedule.
            </p>
          </div>
          <Link
            to="/targets"
            className="inline-flex items-center gap-1.5 text-xs font-medium text-emerald-400 hover:text-emerald-300 transition-colors"
          >
            <span>View All Targets</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        {isTargetsLoading ? (
          <div className="p-6">
            <LoadingSkeleton rows={5} />
          </div>
        ) : !targets || targets.length === 0 ? (
          <div className="p-8 text-center text-slate-500 text-xs font-mono">
            No targets configured yet.{' '}
            <Link to="/targets/new" className="text-emerald-400 hover:underline">
              Add your first target
            </Link>
            .
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-slate-950 text-slate-400 border-b border-slate-800 text-[11px]">
                <tr>
                  <th className="py-2.5 px-4 font-semibold">Target</th>
                  <th className="py-2.5 px-4 font-semibold">Protocol</th>
                  <th className="py-2.5 px-4 font-semibold">Status</th>
                  <th className="py-2.5 px-4 font-semibold">Interval</th>
                  <th className="py-2.5 px-4 font-semibold">Last Checked</th>
                  <th className="py-2.5 px-4 font-semibold">Next Check</th>
                  <th className="py-2.5 px-4 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {targets.slice(0, 10).map((t) => (
                  <tr key={t.id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="py-2.5 px-4 font-sans">
                      <Link
                        to={`/targets/${t.id}`}
                        className="font-semibold text-slate-200 hover:text-emerald-400 transition-colors inline-flex items-center gap-1.5"
                      >
                        <span>{t.name}</span>
                        <ExternalLink className="w-3 h-3 text-slate-500" />
                      </Link>
                      <div className="text-[11px] text-slate-400 font-mono mt-0.5">
                        {t.hostname}:{t.port}
                      </div>
                    </td>
                    <td className="py-2.5 px-4">
                      <ProtocolBadge protocol={t.protocol} />
                    </td>
                    <td className="py-2.5 px-4">
                      <StatusBadge status={t.status} size="sm" />
                      {t.consecutive_failures > 0 && (
                        <span className="ml-2 text-[10px] text-rose-400 font-semibold">
                          ({t.consecutive_failures} fail)
                        </span>
                      )}
                    </td>
                    <td className="py-2.5 px-4 text-slate-300">
                      {t.interval_seconds}s
                    </td>
                    <td className="py-2.5 px-4 text-slate-400">
                      {formatRelativeTime(t.last_checked_at)}
                    </td>
                    <td className="py-2.5 px-4 text-slate-400">
                      {t.enabled ? formatRelativeTime(t.next_check_at) : <span className="text-slate-600">Disabled</span>}
                    </td>
                    <td className="py-2.5 px-4 text-right">
                      <IconButton
                        variant="secondary"
                        size="xs"
                        onClick={() => checkMutation.mutate(t.id)}
                        isLoading={checkingTargetId === t.id}
                        icon={<Play className="w-3.5 h-3.5 text-emerald-400" />}
                        aria-label="Run check"
                        title="Run check immediately"
                      />
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
