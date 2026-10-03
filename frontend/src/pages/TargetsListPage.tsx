import React, { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  Search,
  Filter,
  PlusCircle,
  Play,
  Trash2,
  Power,
  RefreshCw,
  ExternalLink,
} from 'lucide-react';
import { getTargets, enableTarget, disableTarget, deleteTarget, runManualCheck } from '../api/targets';
import { StatusBadge } from '../components/StatusBadge';
import { ProtocolBadge } from '../components/ProtocolBadge';
import { LoadingSkeleton } from '../components/LoadingSkeleton';
import { ErrorState } from '../components/ErrorState';
import { EmptyState } from '../components/EmptyState';
import { Modal } from '../components/Modal';
import { formatRelativeTime } from '../utils/formatters';
import { useAuth } from '../context/AuthContext';

export const TargetsListPage: React.FC = () => {
  const queryClient = useQueryClient();
  const { role, activeTenant } = useAuth();

  const [search, setSearch] = useState('');
  const [selectedProtocol, setSelectedProtocol] = useState<string>('ALL');
  const [selectedStatus, setSelectedStatus] = useState<string>('ALL');
  const [targetToDelete, setTargetToDelete] = useState<number | null>(null);

  const canCreate = role !== 'VIEWER';
  const canDelete = role === 'OWNER' || role === 'ADMIN';
  const canToggle = role !== 'VIEWER';

  const {
    data: targets,
    isLoading,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ['targets', activeTenant?.id],
    queryFn: () => getTargets(),
    refetchInterval: 5000,
  });

  const enableMutation = useMutation({
    mutationFn: (id: number) => enableTarget(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['targets'] }),
  });

  const disableMutation = useMutation({
    mutationFn: (id: number) => disableTarget(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['targets'] }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteTarget(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['targets'] });
      setTargetToDelete(null);
    },
  });

  const checkMutation = useMutation({
    mutationFn: (id: number) => runManualCheck(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['targets'] }),
  });

  const filteredTargets = useMemo(() => {
    if (!targets) return [];
    return targets.filter((t) => {
      const matchSearch =
        t.name.toLowerCase().includes(search.toLowerCase()) ||
        t.hostname.toLowerCase().includes(search.toLowerCase()) ||
        String(t.port).includes(search);
      const matchProtocol = selectedProtocol === 'ALL' || t.protocol.toUpperCase() === selectedProtocol;
      const matchStatus = selectedStatus === 'ALL' || t.status === selectedStatus;
      return matchSearch && matchProtocol && matchStatus;
    });
  }, [targets, search, selectedProtocol, selectedStatus]);

  if (error) {
    return <ErrorState message="Failed to load targets fleet." onRetry={refetch} />;
  }

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-100">Monitored Targets</h1>
          <p className="text-sm text-slate-400 mt-1 font-mono">
            Manage your network fleet endpoints, protocols, intervals, and check policies.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => refetch()}
            type="button"
            className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border border-slate-800 bg-slate-900 text-xs font-mono text-slate-300 hover:text-white transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
          {canCreate && (
            <Link
              to="/targets/new"
              className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-md transition-colors"
            >
              <PlusCircle className="w-4 h-4" />
              <span>Create Target</span>
            </Link>
          )}
        </div>
      </div>

      {/* Filters Bar */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 p-4 rounded-xl border border-slate-800 bg-slate-900/60 backdrop-blur-sm">
        {/* Search */}
        <div className="relative">
          <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search by name, host, or port..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-3 py-2 text-xs font-mono text-slate-200 placeholder-slate-500 focus:outline-none focus:border-emerald-500"
          />
        </div>

        {/* Protocol Filter */}
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-slate-500 shrink-0" />
          <select
            value={selectedProtocol}
            onChange={(e) => setSelectedProtocol(e.target.value)}
            className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs font-mono text-slate-200 focus:outline-none focus:border-emerald-500"
          >
            <option value="ALL">All Protocols</option>
            <option value="TCP">TCP</option>
            <option value="HTTP">HTTP</option>
            <option value="HTTPS">HTTPS</option>
            <option value="DNS">DNS</option>
          </select>
        </div>

        {/* Status Filter */}
        <div>
          <select
            value={selectedStatus}
            onChange={(e) => setSelectedStatus(e.target.value)}
            className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs font-mono text-slate-200 focus:outline-none focus:border-emerald-500"
          >
            <option value="ALL">All Statuses</option>
            <option value="UP">UP</option>
            <option value="DOWN">DOWN</option>
            <option value="UNKNOWN">UNKNOWN</option>
          </select>
        </div>
      </div>

      {/* Targets Table */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/70 overflow-hidden backdrop-blur-sm">
        {isLoading ? (
          <div className="p-6">
            <LoadingSkeleton rows={6} />
          </div>
        ) : filteredTargets.length === 0 ? (
          <div className="p-8">
            <EmptyState
              title="No targets match your filter criteria"
              description="Try adjusting your search terms or filters above, or create a new monitoring target."
              actionText={canCreate ? 'Add New Target' : undefined}
              onAction={canCreate ? () => (window.location.href = '/targets/new') : undefined}
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-slate-950/60 text-slate-400 uppercase tracking-wider border-b border-slate-800 text-[11px]">
                <tr>
                  <th className="py-3.5 px-4 font-semibold">Name & Endpoint</th>
                  <th className="py-3.5 px-4 font-semibold">Protocol</th>
                  <th className="py-3.5 px-4 font-semibold">Status</th>
                  <th className="py-3.5 px-4 font-semibold">Interval</th>
                  <th className="py-3.5 px-4 font-semibold">Last Checked</th>
                  <th className="py-3.5 px-4 font-semibold">Next Check</th>
                  <th className="py-3.5 px-4 font-semibold">Monitoring</th>
                  <th className="py-3.5 px-4 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {filteredTargets.map((t) => (
                  <tr key={t.id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="py-3 px-4">
                      <Link
                        to={`/targets/${t.id}`}
                        className="font-bold text-slate-100 hover:text-emerald-400 transition-colors inline-flex items-center gap-1.5"
                      >
                        <span>{t.name}</span>
                        <ExternalLink className="w-3 h-3 text-slate-500" />
                      </Link>
                      <div className="text-[11px] text-slate-400 mt-0.5">
                        {t.hostname}:{t.port}
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <ProtocolBadge protocol={t.protocol} />
                    </td>
                    <td className="py-3 px-4">
                      <StatusBadge status={t.status} size="sm" />
                      {t.consecutive_failures > 0 && (
                        <span className="ml-2 text-[10px] text-rose-400 font-semibold">
                          ({t.consecutive_failures} fail)
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-slate-300">{t.interval_seconds}s</td>
                    <td className="py-3 px-4 text-slate-400">
                      {formatRelativeTime(t.last_checked_at)}
                    </td>
                    <td className="py-3 px-4 text-slate-400">
                      {t.enabled ? (
                        formatRelativeTime(t.next_check_at)
                      ) : (
                        <span className="text-slate-600">Paused</span>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <button
                        onClick={() =>
                          canToggle && (t.enabled ? disableMutation.mutate(t.id) : enableMutation.mutate(t.id))
                        }
                        disabled={!canToggle}
                        type="button"
                        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-semibold border transition-colors ${
                          !canToggle
                            ? 'opacity-60 cursor-not-allowed bg-slate-900 border-slate-800 text-slate-500'
                            : t.enabled
                            ? 'bg-emerald-950/40 text-emerald-400 border-emerald-800/60 hover:bg-emerald-900/60'
                            : 'bg-slate-800 text-slate-400 border-slate-700 hover:bg-slate-700'
                        }`}
                      >
                        <Power className="w-3 h-3" />
                        <span>{t.enabled ? 'Enabled' : 'Disabled'}</span>
                      </button>
                    </td>
                    <td className="py-3 px-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        {canToggle && (
                          <button
                            onClick={() => checkMutation.mutate(t.id)}
                            disabled={checkMutation.isPending}
                            type="button"
                            className="p-1.5 rounded bg-slate-800 hover:bg-slate-700 text-emerald-400 border border-slate-700 transition-colors"
                            title="Run check immediately"
                          >
                            <Play className="w-3.5 h-3.5" />
                          </button>
                        )}
                        {canDelete && (
                          <button
                            onClick={() => setTargetToDelete(t.id)}
                            type="button"
                            className="p-1.5 rounded bg-slate-800 hover:bg-rose-900/60 text-slate-400 hover:text-rose-300 border border-slate-700 transition-colors"
                            title="Delete target"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={targetToDelete !== null}
        onClose={() => setTargetToDelete(null)}
        title="Confirm Target Deletion"
        maxWidth="sm"
      >
        <div className="space-y-4 text-xs font-mono">
          <p className="text-slate-300">
            Are you sure you want to delete this target? All associated monitoring results, job history, and alert rules will be permanently deleted.
          </p>
          <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
            <button
              onClick={() => setTargetToDelete(null)}
              type="button"
              className="px-3.5 py-1.5 rounded-lg border border-slate-700 text-slate-300 hover:bg-slate-800 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={() => targetToDelete && deleteMutation.mutate(targetToDelete)}
              disabled={deleteMutation.isPending}
              type="button"
              className="px-3.5 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white font-semibold transition-colors"
            >
              {deleteMutation.isPending ? 'Deleting...' : 'Delete Target'}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
