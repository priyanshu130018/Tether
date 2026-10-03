import React, { useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft,
  Play,
  Power,
  Trash2,
  Bell,
  Clock,
  CheckCircle2,
  XCircle,
  Activity,
} from 'lucide-react';
import {
  getTarget,
  getTargetResults,
  getTargetLatency,
  enableTarget,
  disableTarget,
  deleteTarget,
  runManualCheck,
} from '../api/targets';
import { getAlertRules, createAlertRule, updateAlertRule } from '../api/alerts';
import { getNotificationChannels } from '../api/notifications';
import { StatusBadge } from '../components/StatusBadge';
import { ProtocolBadge } from '../components/ProtocolBadge';
import { LatencyChart } from '../components/LatencyChart';
import { LoadingSkeleton } from '../components/LoadingSkeleton';
import { ErrorState } from '../components/ErrorState';
import { Modal } from '../components/Modal';
import { formatDate, formatLatency, formatRelativeTime } from '../utils/formatters';

export const TargetDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const targetId = Number(id);

  const [latencyRange, setLatencyRange] = useState('24h');
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [activeJobId, setActiveJobId] = useState<number | null>(null);

  // Queries
  const {
    data: target,
    isLoading: isTargetLoading,
    error: targetError,
    refetch: refetchTarget,
  } = useQuery({
    queryKey: ['target', targetId],
    queryFn: () => getTarget(targetId),
    refetchInterval: 5000,
  });

  const { data: results, isLoading: isResultsLoading } = useQuery({
    queryKey: ['targetResults', targetId],
    queryFn: () => getTargetResults(targetId, 30),
    refetchInterval: 5000,
  });

  const { data: latencyData, isLoading: isLatencyLoading } = useQuery({
    queryKey: ['targetLatency', targetId, latencyRange],
    queryFn: () => getTargetLatency(targetId, latencyRange),
    refetchInterval: 5000,
  });

  const { data: alertRules } = useQuery({
    queryKey: ['alertRules', targetId],
    queryFn: () => getAlertRules(targetId),
  });

  const { data: channels } = useQuery({
    queryKey: ['notificationChannels'],
    queryFn: () => getNotificationChannels(),
  });

  // Alert Rule Form State
  const existingRule = alertRules && alertRules.length > 0 ? alertRules[0] : null;
  const [ruleEnabled, setRuleEnabled] = useState(true);
  const [failureThreshold, setFailureThreshold] = useState(3);
  const [recoveryEnabled, setRecoveryEnabled] = useState(true);
  const [cooldownSeconds, setCooldownSeconds] = useState(1800);
  const [selectedChannels, setSelectedChannels] = useState<number[]>([]);
  const [ruleInitialized, setRuleInitialized] = useState(false);

  if (existingRule && !ruleInitialized) {
    setRuleEnabled(existingRule.enabled);
    setFailureThreshold(existingRule.failure_threshold);
    setRecoveryEnabled(existingRule.recovery_enabled);
    setCooldownSeconds(existingRule.cooldown_seconds);
    setSelectedChannels(existingRule.channel_ids || []);
    setRuleInitialized(true);
  }

  // Mutations
  const enableMutation = useMutation({
    mutationFn: () => enableTarget(targetId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['target', targetId] }),
  });

  const disableMutation = useMutation({
    mutationFn: () => disableTarget(targetId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['target', targetId] }),
  });

  const checkMutation = useMutation({
    mutationFn: () => runManualCheck(targetId),
    onSuccess: (job) => {
      setActiveJobId(job.id);
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ['target', targetId] });
        queryClient.invalidateQueries({ queryKey: ['targetResults', targetId] });
        queryClient.invalidateQueries({ queryKey: ['targetLatency', targetId, latencyRange] });
        setActiveJobId(null);
      }, 3000);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteTarget(targetId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['targets'] });
      navigate('/targets');
    },
  });

  const saveRuleMutation = useMutation({
    mutationFn: () => {
      if (existingRule) {
        return updateAlertRule(existingRule.id, {
          enabled: ruleEnabled,
          failure_threshold: failureThreshold,
          recovery_enabled: recoveryEnabled,
          cooldown_seconds: cooldownSeconds,
          channel_ids: selectedChannels,
        });
      } else {
        return createAlertRule({
          target_id: targetId,
          enabled: ruleEnabled,
          failure_threshold: failureThreshold,
          recovery_enabled: recoveryEnabled,
          cooldown_seconds: cooldownSeconds,
          channel_ids: selectedChannels,
        });
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alertRules', targetId] });
      alert('Alert rule saved successfully!');
    },
  });

  if (isTargetLoading) {
    return <LoadingSkeleton rows={8} />;
  }

  if (targetError || !target) {
    return <ErrorState message="Target not found or failed to load." onRetry={refetchTarget} />;
  }

  return (
    <div className="space-y-8">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-3">
          <Link
            to="/targets"
            className="p-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold tracking-tight text-slate-100">{target.name}</h1>
              <StatusBadge status={target.status} size="md" />
              <ProtocolBadge protocol={target.protocol} />
            </div>
            <p className="text-xs font-mono text-slate-400 mt-1">
              {target.protocol.toUpperCase()}://{target.hostname}:{target.port}
            </p>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2">
          <button
            onClick={() =>
              target.enabled ? disableMutation.mutate() : enableMutation.mutate()
            }
            type="button"
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-semibold border transition-colors ${
              target.enabled
                ? 'bg-slate-800 hover:bg-slate-700 text-slate-300 border-slate-700'
                : 'bg-emerald-950/40 text-emerald-400 border-emerald-800/60 hover:bg-emerald-900/60'
            }`}
          >
            <Power className="w-3.5 h-3.5" />
            <span>{target.enabled ? 'Pause Monitoring' : 'Resume Monitoring'}</span>
          </button>

          <button
            onClick={() => checkMutation.mutate()}
            disabled={checkMutation.isPending || activeJobId !== null}
            type="button"
            className="inline-flex items-center gap-2 px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-mono font-bold shadow-md shadow-emerald-950/40 transition-colors disabled:opacity-60"
          >
            <Play className={`w-3.5 h-3.5 ${activeJobId !== null ? 'animate-spin' : ''}`} />
            <span>{activeJobId !== null ? 'Checking...' : 'Run Check'}</span>
          </button>

          <button
            onClick={() => setDeleteModalOpen(true)}
            type="button"
            className="p-2 rounded-lg bg-slate-900 hover:bg-rose-950/60 text-slate-400 hover:text-rose-400 border border-slate-800 transition-colors"
            title="Delete target"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Target Health & Metadata Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-4 font-mono">
          <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
            <Clock className="w-3.5 h-3.5" />
            <span>Interval & Timeout</span>
          </div>
          <div className="text-lg font-bold text-slate-100">
            {target.interval_seconds}s <span className="text-xs text-slate-500">({target.timeout_seconds}s timeout)</span>
          </div>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-4 font-mono">
          <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
            <span>Consecutive Successes</span>
          </div>
          <div className="text-lg font-bold text-emerald-400">{target.consecutive_successes}</div>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-4 font-mono">
          <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
            <XCircle className="w-3.5 h-3.5 text-rose-400" />
            <span>Consecutive Failures</span>
          </div>
          <div className="text-lg font-bold text-rose-400">{target.consecutive_failures}</div>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-4 font-mono">
          <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
            <Activity className="w-3.5 h-3.5 text-sky-400" />
            <span>Next Check</span>
          </div>
          <div className="text-lg font-bold text-slate-100">
            {target.enabled ? formatRelativeTime(target.next_check_at) : 'Paused'}
          </div>
        </div>
      </div>

      {/* Latency & Performance Time-Series Chart */}
      <LatencyChart
        data={latencyData || []}
        isLoading={isLatencyLoading}
        selectedRange={latencyRange}
        onRangeChange={(r) => setLatencyRange(r)}
      />

      {/* Alert Rule Configuration & Notification Routing */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-6 space-y-5 backdrop-blur-sm">
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <div>
            <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-200 flex items-center gap-2">
              <Bell className="w-4 h-4 text-emerald-400" />
              <span>Target Alert Rule & Notification Channels</span>
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Define failure thresholds, cooldown suppression, and notification routing for this target.
            </p>
          </div>
          <button
            onClick={() => saveRuleMutation.mutate()}
            disabled={saveRuleMutation.isPending}
            type="button"
            className="px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-mono font-bold transition-colors"
          >
            {saveRuleMutation.isPending ? 'Saving...' : 'Save Alert Rule'}
          </button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs font-mono">
          <div>
            <label className="block text-slate-300 mb-1.5 font-medium">Failure Threshold</label>
            <input
              type="number"
              min={1}
              value={failureThreshold}
              onChange={(e) => setFailureThreshold(parseInt(e.target.value, 10))}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500"
            />
            <span className="text-[10px] text-slate-500">Alert triggers after N consecutive failures</span>
          </div>

          <div>
            <label className="block text-slate-300 mb-1.5 font-medium">Cooldown (Seconds)</label>
            <input
              type="number"
              min={0}
              value={cooldownSeconds}
              onChange={(e) => setCooldownSeconds(parseInt(e.target.value, 10))}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500"
            />
            <span className="text-[10px] text-slate-500">Cooldown window before repeating outage alert</span>
          </div>

          <div className="flex flex-col justify-center space-y-2 pt-2">
            <label className="flex items-center gap-2 text-slate-300 cursor-pointer">
              <input
                type="checkbox"
                checked={ruleEnabled}
                onChange={(e) => setRuleEnabled(e.target.checked)}
                className="rounded bg-slate-950 border-slate-800 text-emerald-500 focus:ring-0"
              />
              <span>Enable Alert Rule</span>
            </label>

            <label className="flex items-center gap-2 text-slate-300 cursor-pointer">
              <input
                type="checkbox"
                checked={recoveryEnabled}
                onChange={(e) => setRecoveryEnabled(e.target.checked)}
                className="rounded bg-slate-950 border-slate-800 text-emerald-500 focus:ring-0"
              />
              <span>Send Recovery Notification</span>
            </label>
          </div>
        </div>

        {/* Channel Selection */}
        <div className="pt-2">
          <label className="block text-xs font-mono font-semibold text-slate-300 mb-2">
            Dispatch Notifications To:
          </label>
          {!channels || channels.length === 0 ? (
            <p className="text-xs text-slate-500 font-mono">
              No notification channels configured yet.{' '}
              <Link to="/notifications" className="text-emerald-400 hover:underline">
                Create a channel
              </Link>
              .
            </p>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
              {channels.map((chan) => {
                const isSelected = selectedChannels.includes(chan.id);
                return (
                  <label
                    key={chan.id}
                    className={`flex items-center gap-3 p-3 rounded-xl border text-xs font-mono cursor-pointer transition-colors ${
                      isSelected
                        ? 'bg-emerald-950/30 border-emerald-800/60 text-emerald-300'
                        : 'bg-slate-950/60 border-slate-800 text-slate-400 hover:border-slate-700'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setSelectedChannels([...selectedChannels, chan.id]);
                        } else {
                          setSelectedChannels(selectedChannels.filter((cid) => cid !== chan.id));
                        }
                      }}
                      className="rounded bg-slate-950 border-slate-800 text-emerald-500 focus:ring-0"
                    />
                    <div>
                      <div className="font-bold text-slate-200">{chan.name}</div>
                      <div className="text-[10px] text-slate-500">{chan.type}</div>
                    </div>
                  </label>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Recent Check Results History Table */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/70 overflow-hidden backdrop-blur-sm">
        <div className="p-5 border-b border-slate-800 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-200">
              Recent Monitoring Results
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Historical check responses, HTTP codes, and error traces.
            </p>
          </div>
        </div>

        {isResultsLoading ? (
          <div className="p-6">
            <LoadingSkeleton rows={5} />
          </div>
        ) : !results || results.length === 0 ? (
          <div className="p-8 text-center text-slate-500 font-mono text-xs">
            No monitoring check results recorded yet. Click <strong>Run Check</strong> above to trigger an immediate check.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-slate-950/60 text-slate-400 uppercase tracking-wider border-b border-slate-800 text-[11px]">
                <tr>
                  <th className="py-3 px-4 font-semibold">Timestamp</th>
                  <th className="py-3 px-4 font-semibold">Status</th>
                  <th className="py-3 px-4 font-semibold">Latency</th>
                  <th className="py-3 px-4 font-semibold">Status Code / Type</th>
                  <th className="py-3 px-4 font-semibold">Error / Details</th>
                  <th className="py-3 px-4 font-semibold">Worker Node</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {results.map((r) => (
                  <tr key={r.id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="py-3 px-4 text-slate-300">{formatDate(r.timestamp)}</td>
                    <td className="py-3 px-4">
                      <StatusBadge status={r.status} size="sm" />
                    </td>
                    <td className="py-3 px-4 text-emerald-400 font-bold">
                      {formatLatency(r.latency_ms)}
                    </td>
                    <td className="py-3 px-4 text-slate-300">
                      {r.status_code ? (
                        <span className="px-2 py-0.5 rounded bg-slate-800 border border-slate-700 font-bold">
                          HTTP {r.status_code}
                        </span>
                      ) : r.error_type ? (
                        <span className="text-rose-400 font-semibold">{r.error_type}</span>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td className="py-3 px-4 text-slate-400 max-w-xs truncate" title={r.error_message || ''}>
                      {r.error_message || '—'}
                    </td>
                    <td className="py-3 px-4 text-slate-500 text-[11px]">{r.worker_id || 'default'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={deleteModalOpen}
        onClose={() => setDeleteModalOpen(false)}
        title="Delete Target Confirmation"
        maxWidth="sm"
      >
        <div className="space-y-4 text-xs font-mono">
          <p className="text-slate-300">
            Are you sure you want to delete target <strong>{target.name}</strong>? This action cannot be undone.
          </p>
          <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
            <button
              onClick={() => setDeleteModalOpen(false)}
              type="button"
              className="px-3.5 py-1.5 rounded-lg border border-slate-700 text-slate-300 hover:bg-slate-800 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={() => deleteMutation.mutate()}
              disabled={deleteMutation.isPending}
              type="button"
              className="px-3.5 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white font-semibold transition-colors"
            >
              {deleteMutation.isPending ? 'Deleting...' : 'Confirm Delete'}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
