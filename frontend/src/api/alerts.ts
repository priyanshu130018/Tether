import { request } from './client';
import { AlertEvent, AlertEventStatus, AlertEventType, AlertRule, AlertRuleCreate, AlertRuleUpdate } from '../types';

export function getAlertRules(targetId?: number): Promise<AlertRule[]> {
  const query = targetId ? `?target_id=${targetId}` : '';
  return request<AlertRule[]>(`/alert-rules${query}`);
}

export function getAlertRule(id: number | string): Promise<AlertRule> {
  return request<AlertRule>(`/alert-rules/${id}`);
}

export function createAlertRule(data: AlertRuleCreate): Promise<AlertRule> {
  return request<AlertRule>('/alert-rules', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function updateAlertRule(id: number | string, data: AlertRuleUpdate): Promise<AlertRule> {
  return request<AlertRule>(`/alert-rules/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export function deleteAlertRule(id: number | string): Promise<void> {
  return request<void>(`/alert-rules/${id}`, {
    method: 'DELETE',
  });
}

export function getAlerts(params?: {
  target_id?: number;
  event_type?: AlertEventType;
  status?: AlertEventStatus;
  limit?: number;
  offset?: number;
}): Promise<AlertEvent[]> {
  const searchParams = new URLSearchParams();
  if (params?.target_id) searchParams.append('target_id', String(params.target_id));
  if (params?.event_type) searchParams.append('event_type', params.event_type);
  if (params?.status) searchParams.append('status', params.status);
  if (params?.limit) searchParams.append('limit', String(params.limit));
  if (params?.offset) searchParams.append('offset', String(params.offset));

  const query = searchParams.toString();
  return request<AlertEvent[]>(`/alerts${query ? `?${query}` : ''}`);
}

export function getAlert(id: number | string): Promise<AlertEvent> {
  return request<AlertEvent>(`/alerts/${id}`);
}
