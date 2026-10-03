import { request } from './client';
import { NotificationChannel, NotificationChannelCreate } from '../types';

export function getNotificationChannels(enabledOnly = false): Promise<NotificationChannel[]> {
  const query = enabledOnly ? '?enabled_only=true' : '';
  return request<NotificationChannel[]>(`/notification-channels${query}`);
}

export function getNotificationChannel(id: number | string): Promise<NotificationChannel> {
  return request<NotificationChannel>(`/notification-channels/${id}`);
}

export function createNotificationChannel(data: NotificationChannelCreate): Promise<NotificationChannel> {
  return request<NotificationChannel>('/notification-channels', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function updateNotificationChannel(
  id: number | string,
  data: Partial<NotificationChannelCreate>
): Promise<NotificationChannel> {
  return request<NotificationChannel>(`/notification-channels/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export function deleteNotificationChannel(id: number | string): Promise<void> {
  return request<void>(`/notification-channels/${id}`, {
    method: 'DELETE',
  });
}

export function testNotificationChannel(id: number | string): Promise<{ success: boolean; message: string; error?: string }> {
  return request<{ success: boolean; message: string; error?: string }>(`/notification-channels/${id}/test`, {
    method: 'POST',
  });
}
