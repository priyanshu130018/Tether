import { request } from './client';
import { Job, JobStatus } from '../types';

export function getJobs(params?: {
  target_id?: number;
  status?: JobStatus;
  task_type?: string;
  limit?: number;
  offset?: number;
}): Promise<Job[]> {
  const searchParams = new URLSearchParams();
  if (params?.target_id) searchParams.append('target_id', String(params.target_id));
  if (params?.status) searchParams.append('status', params.status);
  if (params?.task_type) searchParams.append('task_type', params.task_type);
  if (params?.limit) searchParams.append('limit', String(params.limit));
  if (params?.offset) searchParams.append('offset', String(params.offset));

  const query = searchParams.toString();
  return request<Job[]>(`/jobs${query ? `?${query}` : ''}`);
}

export function getJob(id: number | string): Promise<Job> {
  return request<Job>(`/jobs/${id}`);
}
