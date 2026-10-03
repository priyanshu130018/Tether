import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { listMembers, inviteMember, updateMemberRole, removeMember } from '../api/tenants';
import { Role } from '../types';
import { useAuth } from '../context/AuthContext';
import { Users, UserPlus, Shield, Trash2, RefreshCw, AlertCircle } from 'lucide-react';
import { LoadingSkeleton } from '../components/LoadingSkeleton';
import { ErrorState } from '../components/ErrorState';
import { Modal } from '../components/Modal';
import { formatRelativeTime } from '../utils/formatters';

export const TeamManagementPage: React.FC = () => {
  const queryClient = useQueryClient();
  const { activeTenant, role: currentUserRole, user: currentUser } = useAuth();

  const [isInviteOpen, setIsInviteOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteName, setInviteName] = useState('');
  const [inviteRole, setInviteRole] = useState<Role>('MEMBER');
  const [memberToRemove, setMemberToRemove] = useState<number | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const canManageTeam = currentUserRole === 'OWNER' || currentUserRole === 'ADMIN';

  const {
    data: members,
    isLoading,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ['team-members', activeTenant?.id],
    queryFn: () => listMembers(),
  });

  const inviteMutation = useMutation({
    mutationFn: () => inviteMember({ email: inviteEmail, role: inviteRole, full_name: inviteName || undefined }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['team-members'] });
      setIsInviteOpen(false);
      setInviteEmail('');
      setInviteName('');
      setInviteRole('MEMBER');
      setErrorMsg(null);
    },
    onError: (err: any) => {
      setErrorMsg(err?.message || 'Failed to invite member');
    },
  });

  const roleMutation = useMutation({
    mutationFn: ({ id, role }: { id: number; role: Role }) => updateMemberRole(id, role),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['team-members'] });
    },
    onError: (err: any) => {
      setErrorMsg(err?.message || 'Failed to update member role');
    },
  });

  const removeMutation = useMutation({
    mutationFn: (id: number) => removeMember(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['team-members'] });
      setMemberToRemove(null);
    },
    onError: (err: any) => {
      setErrorMsg(err?.message || 'Failed to remove member');
    },
  });

  if (error) {
    return <ErrorState message="Failed to load organization members." onRetry={refetch} />;
  }

  const getRoleBadgeClass = (r: Role) => {
    switch (r) {
      case 'OWNER':
        return 'bg-purple-950/60 text-purple-300 border-purple-800/80';
      case 'ADMIN':
        return 'bg-amber-950/60 text-amber-300 border-amber-800/80';
      case 'MEMBER':
        return 'bg-emerald-950/60 text-emerald-300 border-emerald-800/80';
      case 'VIEWER':
      default:
        return 'bg-slate-800 text-slate-300 border-slate-700';
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-100 flex items-center gap-2.5">
            <Users className="w-6 h-6 text-emerald-400" />
            <span>Team & Access Control</span>
          </h1>
          <p className="text-sm text-slate-400 mt-1 font-mono">
            Manage organization members and role permissions for <strong className="text-slate-200">{activeTenant?.name}</strong>.
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
          {canManageTeam && (
            <button
              onClick={() => setIsInviteOpen(true)}
              type="button"
              className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-md transition-colors"
            >
              <UserPlus className="w-4 h-4" />
              <span>Invite Member</span>
            </button>
          )}
        </div>
      </div>

      {errorMsg && (
        <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs font-mono flex items-start gap-2.5">
          <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Members Table */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/70 overflow-hidden backdrop-blur-sm">
        {isLoading ? (
          <div className="p-6">
            <LoadingSkeleton rows={4} />
          </div>
        ) : !members || members.length === 0 ? (
          <div className="p-8 text-center text-xs font-mono text-slate-400">
            No team members found for this organization.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-slate-950/60 text-slate-400 uppercase tracking-wider border-b border-slate-800 text-[11px]">
                <tr>
                  <th className="py-3.5 px-4 font-semibold">User</th>
                  <th className="py-3.5 px-4 font-semibold">Email</th>
                  <th className="py-3.5 px-4 font-semibold">Role</th>
                  <th className="py-3.5 px-4 font-semibold">Joined</th>
                  {canManageTeam && <th className="py-3.5 px-4 font-semibold text-right">Actions</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {members.map((m) => {
                  const isMe = m.user_id === currentUser?.id;
                  const isOwner = m.role === 'OWNER';
                  return (
                    <tr key={m.id} className="hover:bg-slate-800/30 transition-colors">
                      <td className="py-3.5 px-4">
                        <div className="font-bold text-slate-100 flex items-center gap-2">
                          <span>{m.user?.full_name || 'Member'}</span>
                          {isMe && (
                            <span className="px-1.5 py-0.5 rounded text-[10px] bg-slate-800 text-emerald-400 font-normal">
                              You
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="py-3.5 px-4 text-slate-300">{m.user?.email}</td>
                      <td className="py-3.5 px-4">
                        {canManageTeam && !isOwner ? (
                          <select
                            value={m.role}
                            onChange={(e) => roleMutation.mutate({ id: m.id, role: e.target.value as Role })}
                            className={`px-2 py-1 rounded text-xs font-mono font-semibold border ${getRoleBadgeClass(m.role)} bg-slate-950 focus:outline-none focus:border-emerald-500`}
                          >
                            <option value="VIEWER">VIEWER</option>
                            <option value="MEMBER">MEMBER</option>
                            <option value="ADMIN">ADMIN</option>
                            {currentUserRole === 'OWNER' && <option value="OWNER">OWNER</option>}
                          </select>
                        ) : (
                          <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold border ${getRoleBadgeClass(m.role)}`}>
                            <Shield className="w-3 h-3" />
                            <span>{m.role}</span>
                          </span>
                        )}
                      </td>
                      <td className="py-3.5 px-4 text-slate-400">{formatRelativeTime(m.created_at)}</td>
                      {canManageTeam && (
                        <td className="py-3.5 px-4 text-right">
                          {!isMe && !isOwner && (
                            <button
                              onClick={() => setMemberToRemove(m.id)}
                              type="button"
                              className="p-1.5 rounded bg-slate-800 hover:bg-rose-900/60 text-slate-400 hover:text-rose-300 border border-slate-700 transition-colors"
                              title="Remove member"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          )}
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Invite Member Modal */}
      <Modal
        isOpen={isInviteOpen}
        onClose={() => {
          setIsInviteOpen(false);
          setErrorMsg(null);
        }}
        title="Invite New Team Member"
        maxWidth="md"
      >
        <div className="space-y-4 text-xs font-mono">
          <p className="text-slate-400">
            Invite a colleague to collaborate in <strong className="text-slate-200">{activeTenant?.name}</strong>.
          </p>

          <div>
            <label htmlFor="invEmail" className="block font-medium text-slate-300 mb-1">
              Colleague Email Address
            </label>
            <input
              id="invEmail"
              type="email"
              required
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              placeholder="colleague@example.com"
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 placeholder-slate-600 focus:outline-none focus:border-emerald-500"
            />
          </div>

          <div>
            <label htmlFor="invName" className="block font-medium text-slate-300 mb-1">
              Full Name (Optional)
            </label>
            <input
              id="invName"
              type="text"
              value={inviteName}
              onChange={(e) => setInviteName(e.target.value)}
              placeholder="Alex Smith"
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 placeholder-slate-600 focus:outline-none focus:border-emerald-500"
            />
          </div>

          <div>
            <label htmlFor="invRole" className="block font-medium text-slate-300 mb-1">
              Role & Permissions
            </label>
            <select
              id="invRole"
              value={inviteRole}
              onChange={(e) => setInviteRole(e.target.value as Role)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500"
            >
              <option value="VIEWER">VIEWER (Read-only observability)</option>
              <option value="MEMBER">MEMBER (Manage targets, run checks)</option>
              <option value="ADMIN">ADMIN (Manage targets, channels, alert rules, team)</option>
              {currentUserRole === 'OWNER' && <option value="OWNER">OWNER (Full organization control)</option>}
            </select>
          </div>

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
            <button
              onClick={() => setIsInviteOpen(false)}
              type="button"
              className="px-3.5 py-1.5 rounded-lg border border-slate-700 text-slate-300 hover:bg-slate-800 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={() => inviteMutation.mutate()}
              disabled={!inviteEmail || inviteMutation.isPending}
              type="button"
              className="px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold transition-colors disabled:opacity-50"
            >
              {inviteMutation.isPending ? 'Sending Invitation...' : 'Send Invitation'}
            </button>
          </div>
        </div>
      </Modal>

      {/* Remove Member Confirmation Modal */}
      <Modal
        isOpen={memberToRemove !== null}
        onClose={() => setMemberToRemove(null)}
        title="Remove Member from Organization"
        maxWidth="sm"
      >
        <div className="space-y-4 text-xs font-mono">
          <p className="text-slate-300">
            Are you sure you want to remove this member? They will immediately lose access to all targets, alerts, and telemetry for this organization.
          </p>
          <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
            <button
              onClick={() => setMemberToRemove(null)}
              type="button"
              className="px-3.5 py-1.5 rounded-lg border border-slate-700 text-slate-300 hover:bg-slate-800 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={() => memberToRemove && removeMutation.mutate(memberToRemove)}
              disabled={removeMutation.isPending}
              type="button"
              className="px-3.5 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white font-semibold transition-colors"
            >
              {removeMutation.isPending ? 'Removing...' : 'Remove Member'}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
