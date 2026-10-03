import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  Bell,
  RefreshCw,
  ExternalLink,
  Flame,
} from 'lucide-react';
import { getAlerts } from '../api/alerts';
import { getTargets } from '../api/targets';
import { AlertEvent, AlertEventStatus, AlertEventType } from '../types';
import { StatusBadge } from '../components/StatusBadge';
import { LoadingSkeleton } from '../components/LoadingSkeleton';
import { ErrorState } from '../components/ErrorState';
import { EmptyState } from '../components/EmptyState';
import { Modal } from '../components/Modal';
import { Button } from '../components/ui/Button';
import { formatDate, formatRelativeTime } from '../utils/formatters';

export const AlertsPage: React.FC = () => {
  const [selectedTarget, setSelectedTarget] = useState<number | undefined>(undefined);
  const [selectedEventType, setSelectedEventType] = useState<string>('ALL');
  const [selectedStatus, setSelectedStatus] = useState<string>('ALL');
  const [inspectEvent, setInspectEvent] = useState<AlertEvent | null>(null);

  const { data: targets } = useQuery({
    queryKey: ['targets'],
    queryFn: () => getTargets(),
  });

  const {
    data: alerts,
    isLoading,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ['alerts', selectedTarget, selectedEventType, selectedStatus],
    queryFn: () =>
      getAlerts({
        target_id: selectedTarget,
        event_type: selectedEventType !== 'ALL' ? (selectedEventType as AlertEventType) : undefined,
        status: selectedStatus !== 'ALL' ? (selectedStatus as AlertEventStatus) : undefined,
        limit: 100,
      }),
    refetchInterval: 10000,
  });

  if (error) {
    return <ErrorState message="Failed to load alert history." onRetry={refetch} />;
  }

  const activeOutages = (alerts || []).filter(
    (a) => a.event_type === 'OUTAGE' && !a.resolved_at
  );

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-100">Alerts & Incidents</h1>
          <p className="text-xs text-slate-400 mt-1">
            Outage detections, state transitions, cooldown suppression, and multi-channel delivery logs.
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => refetch()}
          isLoading={isFetching}
          leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
        >
          Refresh
        </Button>
      </div>

      {/* Active Outage Banner */}
      {activeOutages.length > 0 && (
        <div className="rounded-xl border border-rose-900/60 bg-rose-950/20 p-4">
          <div className="flex items-center gap-2.5 text-rose-400 font-semibold mb-3 text-sm">
            <Flame className="w-4 h-4 text-rose-400" />
            <span>Active Outage Incidents ({activeOutages.length})</span>
          </div>
          <div className="space-y-2">
            {activeOutages.slice(0, 3).map((outage) => (
              <div
                key={outage.id}
                className="flex flex-col sm:flex-row sm:items-center justify-between p-3 rounded-lg bg-rose-950/40 border border-rose-800/40 text-xs font-mono gap-2"
              >
                <div>
                  <span className="font-bold text-rose-200 mr-2">Target #{outage.target_id}</span>
                  <span className="text-slate-300">{outage.message}</span>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <span className="text-slate-400">{formatRelativeTime(outage.created_at)}</span>
                  <Button
                    variant="danger"
                    size="xs"
                    onClick={() => setInspectEvent(outage)}
                  >
                    Inspect
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Filter Toolbar */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 p-3 rounded-xl border border-slate-800 bg-slate-900 text-xs">
        <div>
          <label className="block text-slate-400 mb-1 font-medium">Filter by Target</label>
          <select
            value={selectedTarget ?? ''}
            onChange={(e) => setSelectedTarget(e.target.value ? Number(e.target.value) : undefined)}
            className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500 font-mono text-xs"
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
          <label className="block text-slate-400 mb-1 font-medium">Event Type</label>
          <select
            value={selectedEventType}
            onChange={(e) => setSelectedEventType(e.target.value)}
            className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500 font-mono text-xs"
          >
            <option value="ALL">All Event Types</option>
            <option value="OUTAGE">OUTAGE</option>
            <option value="RECOVERY">RECOVERY</option>
          </select>
        </div>

        <div>
          <label className="block text-slate-400 mb-1 font-medium">Delivery Status</label>
          <select
            value={selectedStatus}
            onChange={(e) => setSelectedStatus(e.target.value)}
            className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500 font-mono text-xs"
          >
            <option value="ALL">All Statuses</option>
            <option value="PENDING">PENDING</option>
            <option value="PROCESSING">PROCESSING</option>
            <option value="SENT">SENT</option>
            <option value="FAILED">FAILED</option>
            <option value="SUPPRESSED">SUPPRESSED</option>
          </select>
        </div>
      </div>

      {/* Alert Events Table */}
      <div className="rounded-xl border border-slate-800 bg-slate-900 overflow-hidden">
        {isLoading ? (
          <div className="p-6">
            <LoadingSkeleton rows={6} />
          </div>
        ) : !alerts || alerts.length === 0 ? (
          <div className="p-8">
            <EmptyState
              title="No alert events recorded"
              description="Alert events will automatically appear here when targets experience state transitions or threshold failures."
              icon={Bell}
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-slate-950 text-slate-400 border-b border-slate-800 text-[11px]">
                <tr>
                  <th className="py-2.5 px-4 font-semibold">Time</th>
                  <th className="py-2.5 px-4 font-semibold">Target ID</th>
                  <th className="py-2.5 px-4 font-semibold">Event</th>
                  <th className="py-2.5 px-4 font-semibold">Status</th>
                  <th className="py-2.5 px-4 font-semibold">Message & Reason</th>
                  <th className="py-2.5 px-4 font-semibold">Resolved</th>
                  <th className="py-2.5 px-4 font-semibold text-right">Deliveries</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {alerts.map((a) => (
                  <tr key={a.id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="py-2.5 px-4 text-slate-300">{formatDate(a.created_at)}</td>
                    <td className="py-2.5 px-4">
                      <Link
                        to={`/targets/${a.target_id}`}
                        className="font-bold text-emerald-400 hover:underline inline-flex items-center gap-1"
                      >
                        <span>Target #{a.target_id}</span>
                        <ExternalLink className="w-3 h-3" />
                      </Link>
                    </td>
                    <td className="py-2.5 px-4">
                      <StatusBadge status={a.event_type} size="sm" />
                    </td>
                    <td className="py-2.5 px-4">
                      <StatusBadge status={a.status} size="sm" />
                    </td>
                    <td className="py-2.5 px-4 text-slate-300 max-w-sm truncate" title={a.message}>
                      {a.message}
                    </td>
                    <td className="py-2.5 px-4 text-slate-400">
                      {a.resolved_at ? (
                        <span className="text-emerald-400 font-bold">{formatRelativeTime(a.resolved_at)}</span>
                      ) : (
                        <span className="text-rose-400 font-semibold">Active</span>
                      )}
                    </td>
                    <td className="py-2.5 px-4 text-right">
                      <Button
                        variant="secondary"
                        size="xs"
                        onClick={() => setInspectEvent(a)}
                      >
                        Inspect
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Inspect Event Modal */}
      <Modal
        isOpen={inspectEvent !== null}
        onClose={() => setInspectEvent(null)}
        title={`Alert Event #${inspectEvent?.id} Details`}
        maxWidth="lg"
      >
        {inspectEvent && (
          <div className="space-y-4 text-xs font-mono">
            <div className="grid grid-cols-2 gap-3 p-3 rounded-lg bg-slate-950 border border-slate-800">
              <div>
                <span className="text-slate-500">Event Type:</span>
                <div className="mt-1">
                  <StatusBadge status={inspectEvent.event_type} size="sm" />
                </div>
              </div>
              <div>
                <span className="text-slate-500">Status:</span>
                <div className="mt-1">
                  <StatusBadge status={inspectEvent.status} size="sm" />
                </div>
              </div>
              <div>
                <span className="text-slate-500">Created:</span>
                <div className="text-slate-200 mt-1">{formatDate(inspectEvent.created_at)}</div>
              </div>
              <div>
                <span className="text-slate-500">Resolved:</span>
                <div className="text-slate-200 mt-1">{formatDate(inspectEvent.resolved_at)}</div>
              </div>
            </div>

            <div>
              <span className="text-slate-400 font-semibold">Message:</span>
              <p className="mt-1 p-3 rounded bg-slate-950 border border-slate-800 text-slate-200">
                {inspectEvent.message}
              </p>
            </div>

            {inspectEvent.deduplication_key && (
              <div>
                <span className="text-slate-400 font-semibold">Deduplication Key:</span>
                <div className="mt-1 p-2 rounded bg-slate-950 border border-slate-800 text-slate-400 break-all text-[11px]">
                  {inspectEvent.deduplication_key}
                </div>
              </div>
            )}

            {/* Notification Deliveries */}
            <div>
              <span className="text-slate-400 font-semibold">Channel Deliveries:</span>
              {!inspectEvent.deliveries || inspectEvent.deliveries.length === 0 ? (
                <p className="text-slate-500 mt-1">No delivery logs recorded for this event.</p>
              ) : (
                <div className="mt-2 space-y-2">
                  {inspectEvent.deliveries.map((del) => (
                    <div
                      key={del.id}
                      className="p-3 rounded bg-slate-950 border border-slate-800 flex items-center justify-between"
                    >
                      <div>
                        <span className="font-bold text-slate-200">Channel #{del.channel_id}</span>
                        <div className="text-slate-500 text-[11px] mt-0.5">
                          Attempts: {del.attempt_count} | Last Attempt: {formatDate(del.last_attempt_at)}
                        </div>
                        {del.last_error && (
                          <div className="text-rose-400 text-[11px] mt-1">{del.last_error}</div>
                        )}
                      </div>
                      <StatusBadge status={del.status} size="sm" />
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
};
