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
  RefreshCw,
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
import { Button } from '../components/ui/Button';
import { IconButton } from '../components/ui/IconButton';
import { useToast } from '../components/ui/Toast';
import { formatDate, formatLatency, formatRelativeTime } from '../utils/formatters';

export const TargetDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();
  const targetId = Number(id);

  const [latencyRange, setLatencyRange] = useState('24h');
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [activeJobId, setActiveJobId] = useState<number | null>(null);

  // Queries
  const {
    data: target,
    isLoading: isTargetLoading,
    isFetching: isTargetFetching,
    error: targetError,
    refetch: refetchTarget,
  } = useQuery({
    queryKey: ['target', targetId],
    queryFn: () => getTarget(targetId),
    refetchInterval: 5000,
  });

  const { data: results, isLoading: isResultsLoading, refetch: refetchResults } = useQuery({
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
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['target', targetId] });
      toast.success('Monitoring resumed for target.');
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail || 'Failed to enable target.');
    },
  });

  const disableMutation = useMutation({
    mutationFn: () => disableTarget(targetId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['target', targetId] });
      toast.info('Monitoring paused for target.');
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail || 'Failed to pause target.');
    },
  });

  const checkMutation = useMutation({
    mutationFn: () => runManualCheck(targetId),
    onSuccess: (job) => {
      setActiveJobId(job.id);
      toast.success(`Check job #${job.id} queued successfully.`);
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ['target', targetId] });
        queryClient.invalidateQueries({ queryKey: ['targetResults', targetId] });
        queryClient.invalidateQueries({ queryKey: ['targetLatency', targetId, latencyRange] });
        setActiveJobId(null);
      }, 2500);
    },
    onError: (err: any) => {
      const msg = err?.response?.data?.detail || 'Failed to dispatch manual check.';
      toast.error(msg);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteTarget(targetId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['targets'] });
      toast.success('Target deleted successfully.');
      navigate('/targets');
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail || 'Failed to delete target.');
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
      toast.success('Alert rule saved successfully.');
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail || 'Failed to save alert rule.');
    },
  });

  const handleRefreshAll = () => {
    refetchTarget();
    refetchResults();
    queryClient.invalidateQueries({ queryKey: ['targetLatency', targetId, latencyRange] });
  };

  if (isTargetLoading) {
    return <LoadingSkeleton rows={8} />;
  }

  if (targetError || !target) {
    return <ErrorState message="Target not found or failed to load." onRetry={refetchTarget} />;
  }

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-3">
          <Link
            to="/targets"
            className="p-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors"
            title="Back to targets"
          >
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-xl font-bold text-slate-100">{target.name}</h1>
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
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefreshAll}
            isLoading={isTargetFetching}
            leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
          >
            Refresh
          </Button>

          <Button
            variant={target.enabled ? 'secondary' : 'outline'}
            size="sm"
            onClick={() =>
              target.enabled ? disableMutation.mutate() : enableMutation.mutate()
            }
            isLoading={enableMutation.isPending || disableMutation.isPending}
            leftIcon={<Power className="w-3.5 h-3.5" />}
          >
            {target.enabled ? 'Pause' : 'Resume'}
          </Button>

          <Button
            variant="primary"
            size="sm"
            onClick={() => checkMutation.mutate()}
            isLoading={checkMutation.isPending || activeJobId !== null}
            leftIcon={<Play className="w-3.5 h-3.5" />}
          >
            {activeJobId !== null ? 'Checking...' : 'Run Check'}
          </Button>

          <IconButton
            variant="danger"
            size="sm"
            onClick={() => setDeleteModalOpen(true)}
            icon={<Trash2 className="w-4 h-4" />}
            aria-label="Delete target"
            title="Delete target"
          />
        </div>
      </div>

      {/* Target Health & Metadata Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="rounded-xl border border-slate-800 bg-slate-900 p-4 font-mono">
          <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
            <Clock className="w-3.5 h-3.5" />
            <span>Interval & Timeout</span>
          </div>
          <div className="text-base font-bold text-slate-100">
            {target.interval_seconds}s <span className="text-xs text-slate-500 font-normal">({target.timeout_seconds}s timeout)</span>
          </div>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900 p-4 font-mono">
          <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
            <span>Success Streak</span>
          </div>
          <div className="text-base font-bold text-emerald-400">{target.consecutive_successes}</div>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900 p-4 font-mono">
          <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
            <XCircle className="w-3.5 h-3.5 text-rose-400" />
            <span>Failure Streak</span>
          </div>
          <div className="text-base font-bold text-rose-400">{target.consecutive_failures}</div>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900 p-4 font-mono">
          <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
            <Activity className="w-3.5 h-3.5 text-sky-400" />
            <span>Next Check</span>
          </div>
          <div className="text-base font-bold text-slate-100">
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
      <div className="rounded-xl border border-slate-800 bg-slate-900 p-5 space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <div>
            <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
              <Bell className="w-4 h-4 text-emerald-400" />
              <span>Target Alert Rule & Notification Channels</span>
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Define failure thresholds, cooldown suppression, and notification routing for this target.
            </p>
          </div>
          <Button
            variant="primary"
            size="sm"
            onClick={() => saveRuleMutation.mutate()}
            isLoading={saveRuleMutation.isPending}
          >
            Save Alert Rule
          </Button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
          <div>
            <label className="block text-slate-300 mb-1.5 font-medium">Failure Threshold</label>
            <input
              type="number"
              min={1}
              value={failureThreshold}
              onChange={(e) => setFailureThreshold(parseInt(e.target.value, 10) || 1)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500 font-mono text-xs"
            />
            <span className="text-[11px] text-slate-500 mt-1 block">Trigger alert after N consecutive failures</span>
          </div>

          <div>
            <label className="block text-slate-300 mb-1.5 font-medium">Cooldown (Seconds)</label>
            <input
              type="number"
              min={0}
              value={cooldownSeconds}
              onChange={(e) => setCooldownSeconds(parseInt(e.target.value, 10) || 0)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500 font-mono text-xs"
            />
            <span className="text-[11px] text-slate-500 mt-1 block">Cooldown suppression window before repeating outage alert</span>
          </div>

          <div className="flex flex-col justify-center space-y-2 pt-2">
            <label className="flex items-center gap-2 text-slate-300 cursor-pointer text-xs">
              <input
                type="checkbox"
                checked={ruleEnabled}
                onChange={(e) => setRuleEnabled(e.target.checked)}
                className="rounded bg-slate-950 border-slate-800 text-emerald-500 focus:ring-0"
              />
              <span>Enable Alert Rule</span>
            </label>

            <label className="flex items-center gap-2 text-slate-300 cursor-pointer text-xs">
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
          <label className="block text-xs font-semibold text-slate-300 mb-2">
            Dispatch Notifications To:
          </label>
          {!channels || channels.length === 0 ? (
            <p className="text-xs text-slate-500">
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
                    className={`flex items-center gap-3 p-3 rounded-lg border text-xs cursor-pointer transition-colors ${
                      isSelected
                        ? 'bg-emerald-950/30 border-emerald-800 text-emerald-300'
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
                      <div className="font-semibold text-slate-200">{chan.name}</div>
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
      <div className="rounded-xl border border-slate-800 bg-slate-900 overflow-hidden">
        <div className="p-4 border-b border-slate-800 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-slate-200">
              Recent Monitoring Results
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Historical check responses, HTTP codes, and error traces
            </p>
          </div>
        </div>

        {isResultsLoading ? (
          <div className="p-6">
            <LoadingSkeleton rows={5} />
          </div>
        ) : !results || results.length === 0 ? (
          <div className="p-8 text-center text-slate-500 text-xs">
            No monitoring check results recorded yet. Click <strong>Run Check</strong> above to trigger an immediate check.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-slate-950 text-slate-400 border-b border-slate-800 text-[11px]">
                <tr>
                  <th className="py-2.5 px-4 font-semibold">Timestamp</th>
                  <th className="py-2.5 px-4 font-semibold">Status</th>
                  <th className="py-2.5 px-4 font-semibold">Latency</th>
                  <th className="py-2.5 px-4 font-semibold">Status Code / Type</th>
                  <th className="py-2.5 px-4 font-semibold">Error / Details</th>
                  <th className="py-2.5 px-4 font-semibold">Worker</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {results.map((r) => (
                  <tr key={r.id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="py-2.5 px-4 text-slate-300">{formatDate(r.timestamp)}</td>
                    <td className="py-2.5 px-4">
                      <StatusBadge status={r.status} size="sm" />
                    </td>
                    <td className="py-2.5 px-4 text-emerald-400 font-bold">
                      {formatLatency(r.latency_ms)}
                    </td>
                    <td className="py-2.5 px-4 text-slate-300">
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
                    <td className="py-2.5 px-4 text-slate-400 max-w-xs truncate" title={r.error_message || ''}>
                      {r.error_message || '—'}
                    </td>
                    <td className="py-2.5 px-4 text-slate-500 text-[11px]">{r.worker_id || 'default'}</td>
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
        <div className="space-y-4 text-xs">
          <p className="text-slate-300">
            Are you sure you want to delete target <strong>{target.name}</strong>? This action cannot be undone.
          </p>
          <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-800">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setDeleteModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              variant="danger"
              size="sm"
              onClick={() => deleteMutation.mutate()}
              isLoading={deleteMutation.isPending}
            >
              Confirm Delete
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
