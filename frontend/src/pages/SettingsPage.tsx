import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { createTenant, listAuditLogs } from '../api/tenants';
import { useAuth } from '../context/AuthContext';
import { Settings, Building, PlusCircle, Shield, History, RefreshCw, Lock } from 'lucide-react';
import { LoadingSkeleton } from '../components/LoadingSkeleton';
import { Modal } from '../components/Modal';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { FormField, Input } from '../components/ui/FormField';
import { useToast } from '../components/ui/Toast';
import { formatRelativeTime } from '../utils/formatters';

export const SettingsPage: React.FC = () => {
  const queryClient = useQueryClient();
  const { activeTenant, role, switchTenant, memberships, user } = useAuth();
  const { showToast } = useToast();

  const [isNewOrgOpen, setIsNewOrgOpen] = useState(false);
  const [newOrgName, setNewOrgName] = useState('');
  const [newOrgSlug, setNewOrgSlug] = useState('');

  const canViewAudit = role === 'OWNER' || role === 'ADMIN';

  const {
    data: auditLogs,
    isLoading: isAuditLoading,
    refetch: refetchAudit,
    isFetching: isAuditFetching,
  } = useQuery({
    queryKey: ['audit-logs', activeTenant?.id],
    queryFn: () => listAuditLogs({ limit: 50 }),
    enabled: canViewAudit,
  });

  const createOrgMutation = useMutation({
    mutationFn: () => createTenant({ name: newOrgName, slug: newOrgSlug || undefined }),
    onSuccess: async (tenant) => {
      queryClient.invalidateQueries({ queryKey: ['tenants'] });
      setIsNewOrgOpen(false);
      setNewOrgName('');
      setNewOrgSlug('');
      showToast('success', `Organization "${tenant.name}" created successfully`);
      await switchTenant(tenant.id);
    },
    onError: (err: any) => {
      showToast('error', err?.message || 'Failed to create organization');
    },
  });

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-100 flex items-center gap-2.5">
          <Settings className="w-6 h-6 text-emerald-400" />
          <span>Organization & Settings</span>
        </h1>
        <p className="text-sm text-slate-400 mt-1 font-mono">
          Manage tenant configuration, security policies, and audit logs.
        </p>
      </div>

      {/* Organization Overview Card */}
      <Card className="p-6 space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-5 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="p-3 rounded-xl bg-slate-800 text-emerald-400 border border-slate-700">
              <Building className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-100 font-mono">{activeTenant?.name}</h2>
              <div className="text-xs text-slate-400 font-mono mt-0.5">Slug: <code className="text-emerald-400">{activeTenant?.slug}</code></div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-950/60 text-emerald-300 border border-emerald-800/80 font-mono">
              <Shield className="w-3.5 h-3.5" />
              <span>Your Role: {role}</span>
            </span>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setIsNewOrgOpen(true)}
              icon={<PlusCircle className="w-3.5 h-3.5 text-emerald-400" />}
            >
              New Organization
            </Button>
          </div>
        </div>

        {/* User Account Info */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
            <span className="text-slate-500 uppercase block text-[10px]">Active User Profile</span>
            <div className="text-slate-200 font-bold">{user?.full_name}</div>
            <div className="text-slate-400">{user?.email}</div>
          </div>
          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
            <span className="text-slate-500 uppercase block text-[10px]">Your Tenant Memberships</span>
            <div className="flex flex-wrap gap-2 pt-1">
              {memberships.map((m) => (
                <button
                  key={m.id}
                  onClick={() => switchTenant(m.tenant_id)}
                  type="button"
                  className={`px-2.5 py-1 rounded text-xs border transition-colors ${
                    m.tenant_id === activeTenant?.id
                      ? 'bg-emerald-950 text-emerald-300 border-emerald-700'
                      : 'bg-slate-900 text-slate-400 border-slate-800 hover:text-white'
                  }`}
                >
                  Org #{m.tenant_id} ({m.role})
                </button>
              ))}
            </div>
          </div>
        </div>
      </Card>

      {/* Security & Audit Trail Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2 font-mono">
              <History className="w-5 h-5 text-emerald-400" />
              <span>Security & Audit Trail</span>
            </h2>
            <p className="text-xs text-slate-400 font-mono mt-0.5">
              Immutable security event logs for this organization.
            </p>
          </div>
          {canViewAudit && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => refetchAudit()}
              loading={isAuditFetching}
              icon={<RefreshCw className="w-3.5 h-3.5" />}
            >
              Refresh
            </Button>
          )}
        </div>

        {!canViewAudit ? (
          <div className="p-8 rounded-xl border border-slate-800 bg-slate-900/40 text-center text-xs font-mono text-slate-500 flex flex-col items-center justify-center space-y-2">
            <Lock className="w-6 h-6 text-slate-600" />
            <span>Audit logs require ADMIN or OWNER permissions.</span>
          </div>
        ) : isAuditLoading ? (
          <LoadingSkeleton rows={5} />
        ) : !auditLogs || auditLogs.length === 0 ? (
          <div className="p-8 rounded-xl border border-slate-800 bg-slate-900/40 text-center text-xs font-mono text-slate-500">
            No audit records found for this organization yet.
          </div>
        ) : (
          <Card className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead className="bg-slate-950/60 text-slate-400 uppercase tracking-wider border-b border-slate-800 text-[11px]">
                  <tr>
                    <th className="py-3 px-4 font-semibold">Action</th>
                    <th className="py-3 px-4 font-semibold">Resource</th>
                    <th className="py-3 px-4 font-semibold">Details</th>
                    <th className="py-3 px-4 font-semibold">Timestamp</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {auditLogs.map((log) => (
                    <tr key={log.id} className="hover:bg-slate-800/30 transition-colors">
                      <td className="py-3 px-4">
                        <span className="font-bold text-emerald-400">{log.action}</span>
                      </td>
                      <td className="py-3 px-4 text-slate-300">
                        {log.resource_type} {log.resource_id ? `#${log.resource_id}` : ''}
                      </td>
                      <td className="py-3 px-4 text-slate-400 max-w-xs truncate">
                        {log.metadata ? JSON.stringify(log.metadata) : '-'}
                      </td>
                      <td className="py-3 px-4 text-slate-400">{formatRelativeTime(log.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}
      </div>

      {/* New Organization Modal */}
      <Modal
        isOpen={isNewOrgOpen}
        onClose={() => setIsNewOrgOpen(false)}
        title="Create New Organization"
        maxWidth="md"
      >
        <div className="space-y-4 text-xs font-mono">
          <p className="text-slate-400">
            Create an isolated monitoring tenant. You will become the <strong>OWNER</strong> of the new tenant.
          </p>

          <FormField label="Organization Name" required>
            <Input
              type="text"
              required
              value={newOrgName}
              onChange={(e) => setNewOrgName(e.target.value)}
              placeholder="Production Fleet US-East"
            />
          </FormField>

          <FormField label="Custom Slug (Optional)">
            <Input
              type="text"
              value={newOrgSlug}
              onChange={(e) => setNewOrgSlug(e.target.value)}
              placeholder="prod-fleet-us-east"
            />
          </FormField>

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setIsNewOrgOpen(false)}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={() => createOrgMutation.mutate()}
              loading={createOrgMutation.isPending}
              disabled={!newOrgName}
            >
              Create Organization
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
