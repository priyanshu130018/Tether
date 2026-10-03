import { request } from './client';
import { Job, LatencyPoint, MonitoringResult, Protocol, Target, TargetCreate, TargetUpdate } from '../types';

export function getTargets(params?: { enabled?: boolean; protocol?: Protocol }): Promise<Target[]> {
  const searchParams = new URLSearchParams();
  if (params?.enabled !== undefined) {
    searchParams.append('enabled', String(params.enabled));
  }
  if (params?.protocol) {
    searchParams.append('protocol', params.protocol);
  }
  const query = searchParams.toString();
  return request<Target[]>(`/targets${query ? `?${query}` : ''}`);
}

export function getTarget(id: number | string): Promise<Target> {
  return request<Target>(`/targets/${id}`);
}

export function createTarget(data: TargetCreate): Promise<Target> {
  return request<Target>('/targets', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function updateTarget(id: number | string, data: TargetUpdate): Promise<Target> {
  return request<Target>(`/targets/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export function deleteTarget(id: number | string): Promise<void> {
  return request<void>(`/targets/${id}`, {
    method: 'DELETE',
  });
}

export function enableTarget(id: number | string): Promise<Target> {
  return request<Target>(`/targets/${id}/enable`, {
    method: 'POST',
  });
}

export function disableTarget(id: number | string): Promise<Target> {
  return request<Target>(`/targets/${id}/disable`, {
    method: 'POST',
  });
}

export function runManualCheck(id: number | string): Promise<Job> {
  return request<Job>(`/targets/${id}/check`, {
    method: 'POST',
  });
}

export function getTargetResults(id: number | string, limit = 50, offset = 0): Promise<MonitoringResult[]> {
  return request<MonitoringResult[]>(`/targets/${id}/results?limit=${limit}&offset=${offset}`);
}

export function getTargetLatency(id: number | string, range = '24h'): Promise<LatencyPoint[]> {
  return request<LatencyPoint[]>(`/targets/${id}/latency?range=${range}`);
}
