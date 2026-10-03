import { request } from './client';
import { DashboardSummary } from '../types';

export function getDashboardSummary(): Promise<DashboardSummary> {
  return request<DashboardSummary>('/dashboard/summary');
}
