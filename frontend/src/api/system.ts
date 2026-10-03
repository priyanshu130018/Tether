import { request } from './client';
import { SystemHealth } from '../types';

export const getSystemHealth = async (): Promise<SystemHealth> => {
  return request<SystemHealth>('/health');
};
