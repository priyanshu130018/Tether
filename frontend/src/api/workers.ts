import { request } from './client';
import { WorkerStatus } from '../types';

export function getWorkers(): Promise<WorkerStatus[]> {
  return request<WorkerStatus[]>('/workers');
}
