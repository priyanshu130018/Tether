import { request } from './client';
import { AuditLog, MemberInvite, MemberRoleUpdate, Role, Tenant, TenantMembership } from '../types';

export async function listTenants(): Promise<Tenant[]> {
  return request<Tenant[]>('/tenants');
}

export async function createTenant(payload: { name: string; slug?: string }): Promise<Tenant> {
  return request<Tenant>('/tenants', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function listMembers(): Promise<TenantMembership[]> {
  return request<TenantMembership[]>('/tenants/members');
}

export async function inviteMember(payload: MemberInvite): Promise<TenantMembership> {
  return request<TenantMembership>('/tenants/members', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateMemberRole(membershipId: number, role: Role): Promise<TenantMembership> {
  const payload: MemberRoleUpdate = { role };
  return request<TenantMembership>(`/tenants/members/${membershipId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function removeMember(membershipId: number): Promise<void> {
  return request<void>(`/tenants/members/${membershipId}`, {
    method: 'DELETE',
  });
}

export async function listAuditLogs(params: {
  limit?: number;
  offset?: number;
  action?: string;
} = {}): Promise<AuditLog[]> {
  const query = new URLSearchParams();
  if (params.limit) query.append('limit', String(params.limit));
  if (params.offset) query.append('offset', String(params.offset));
  if (params.action) query.append('action', params.action);

  const qs = query.toString();
  return request<AuditLog[]>(`/audit-logs${qs ? `?${qs}` : ''}`);
}
