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
import { Button } from '../components/ui/Button';
import { IconButton } from '../components/ui/IconButton';
import { useToast } from '../components/ui/Toast';
import { formatRelativeTime } from '../utils/formatters';
import { useAuth } from '../context/AuthContext';

export const TargetsListPage: React.FC = () => {
  const queryClient = useQueryClient();
  const toast = useToast();
  const { role, activeTenant } = useAuth();

  const [search, setSearch] = useState('');
  const [selectedProtocol, setSelectedProtocol] = useState<string>('ALL');
  const [selectedStatus, setSelectedStatus] = useState<string>('ALL');
  const [targetToDelete, setTargetToDelete] = useState<number | null>(null);
  const [checkingTargetId, setCheckingTargetId] = useState<number | null>(null);

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
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['targets'] });
      toast.success('Monitoring enabled.');
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail || 'Failed to enable target.');
    },
  });

  const disableMutation = useMutation({
    mutationFn: (id: number) => disableTarget(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['targets'] });
      toast.info('Monitoring disabled.');
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail || 'Failed to disable target.');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteTarget(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['targets'] });
      setTargetToDelete(null);
      toast.success('Target deleted successfully.');
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail || 'Failed to delete target.');
    },
  });

  const checkMutation = useMutation({
    mutationFn: (id: number) => runManualCheck(id),
    onSuccess: (job, id) => {
      setCheckingTargetId(id);
      toast.success(`Check job #${job.id} dispatched.`);
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ['targets'] });
        setCheckingTargetId(null);
      }, 2500);
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail || 'Check dispatch failed.');
    },
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
          <h1 className="text-xl font-bold text-slate-100">Monitored Targets</h1>
          <p className="text-xs text-slate-400 mt-1">
            Manage your network fleet endpoints, protocols, intervals, and check policies.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => refetch()}
            isLoading={isFetching}
            leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
          >
            Refresh
          </Button>
          {canCreate && (
            <Link to="/targets/new">
              <Button
                variant="primary"
                size="sm"
                leftIcon={<PlusCircle className="w-3.5 h-3.5" />}
              >
                Create Target
              </Button>
            </Link>
          )}
        </div>
      </div>

      {/* Filters Bar */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 p-3 rounded-xl border border-slate-800 bg-slate-900">
        {/* Search */}
        <div className="relative">
          <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search by name, host, or port..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-emerald-500"
          />
        </div>

        {/* Protocol Filter */}
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-slate-500 shrink-0" />
          <select
            value={selectedProtocol}
            onChange={(e) => setSelectedProtocol(e.target.value)}
            className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-emerald-500"
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
            className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-emerald-500"
          >
            <option value="ALL">All Statuses</option>
            <option value="UP">UP</option>
            <option value="DOWN">DOWN</option>
            <option value="UNKNOWN">UNKNOWN</option>
          </select>
        </div>
      </div>

      {/* Targets Table */}
      <div className="rounded-xl border border-slate-800 bg-slate-900 overflow-hidden">
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
              <thead className="bg-slate-950 text-slate-400 border-b border-slate-800 text-[11px]">
                <tr>
                  <th className="py-2.5 px-4 font-semibold">Name & Endpoint</th>
                  <th className="py-2.5 px-4 font-semibold">Protocol</th>
                  <th className="py-2.5 px-4 font-semibold">Status</th>
                  <th className="py-2.5 px-4 font-semibold">Interval</th>
                  <th className="py-2.5 px-4 font-semibold">Last Checked</th>
                  <th className="py-2.5 px-4 font-semibold">Next Check</th>
                  <th className="py-2.5 px-4 font-semibold">Monitoring</th>
                  <th className="py-2.5 px-4 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {filteredTargets.map((t) => (
                  <tr key={t.id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="py-2.5 px-4 font-sans">
                      <Link
                        to={`/targets/${t.id}`}
                        className="font-semibold text-slate-100 hover:text-emerald-400 transition-colors inline-flex items-center gap-1.5"
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
                    <td className="py-2.5 px-4 text-slate-300">{t.interval_seconds}s</td>
                    <td className="py-2.5 px-4 text-slate-400">
                      {formatRelativeTime(t.last_checked_at)}
                    </td>
                    <td className="py-2.5 px-4 text-slate-400">
                      {t.enabled ? (
                        formatRelativeTime(t.next_check_at)
                      ) : (
                        <span className="text-slate-600">Paused</span>
                      )}
                    </td>
                    <td className="py-2.5 px-4">
                      <button
                        onClick={() =>
                          canToggle && (t.enabled ? disableMutation.mutate(t.id) : enableMutation.mutate(t.id))
                        }
                        disabled={!canToggle || enableMutation.isPending || disableMutation.isPending}
                        type="button"
                        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-semibold border transition-all active:scale-[0.98] ${
                          !canToggle
                            ? 'opacity-50 cursor-not-allowed bg-slate-900 border-slate-800 text-slate-500'
                            : t.enabled
                            ? 'bg-emerald-950/40 text-emerald-400 border-emerald-800 hover:bg-emerald-900/60'
                            : 'bg-slate-800 text-slate-400 border-slate-700 hover:bg-slate-700'
                        }`}
                      >
                        <Power className="w-3 h-3" />
                        <span>{t.enabled ? 'Enabled' : 'Disabled'}</span>
                      </button>
                    </td>
                    <td className="py-2.5 px-4 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        {canToggle && (
                          <IconButton
                            variant="secondary"
                            size="sm"
                            onClick={() => checkMutation.mutate(t.id)}
                            isLoading={checkingTargetId === t.id}
                            icon={<Play className="w-3.5 h-3.5 text-emerald-400" />}
                            aria-label="Run check immediately"
                            title="Run check immediately"
                          />
                        )}
                        {canDelete && (
                          <IconButton
                            variant="danger"
                            size="sm"
                            onClick={() => setTargetToDelete(t.id)}
                            icon={<Trash2 className="w-3.5 h-3.5" />}
                            aria-label="Delete target"
                            title="Delete target"
                          />
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
        <div className="space-y-4 text-xs">
          <p className="text-slate-300">
            Are you sure you want to delete this target? All associated monitoring results, job history, and alert rules will be permanently deleted.
          </p>
          <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-800">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setTargetToDelete(null)}
            >
              Cancel
            </Button>
            <Button
              variant="danger"
              size="sm"
              onClick={() => targetToDelete && deleteMutation.mutate(targetToDelete)}
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
