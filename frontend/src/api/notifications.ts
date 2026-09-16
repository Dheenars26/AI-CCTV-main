import { axiosClient } from './axiosClient';
import { ApiResponse } from '../types/api';

export interface NotificationSettings {
  recipient_emails: string[];
  email_alerts_enabled: boolean;
  cooldown_seconds: number;
  smtp_host?: string;
  smtp_port?: number;
  smtp_username?: string;
  smtp_sender_email?: string;
  smtp_sender_name?: string;
  smtp_use_tls?: boolean;
  has_smtp_password?: boolean;
  smtp_status?: string;
  smtp_last_error?: string | null;
}

export interface NotificationSettingsPayload {
  recipient_emails: string[];
  email_alerts_enabled?: boolean;
  cooldown_seconds?: number;
  smtp_host?: string;
  smtp_port?: number;
  smtp_username?: string;
  smtp_password?: string;
  smtp_sender_email?: string;
  smtp_sender_name?: string;
  smtp_use_tls?: boolean;
}

export interface NotificationAuditLog {
  id: string;
  alert_id: string;
  channel: string;
  recipient: string;
  status: string;
  error_message?: string | null;
  sent_at: string;
}

export const notificationsApi = {
  getSettings: async (): Promise<ApiResponse<NotificationSettings>> => {
    const res = await axiosClient.get<ApiResponse<NotificationSettings>>('/notifications/settings');
    return res.data;
  },

  updateSettings: async (payload: NotificationSettingsPayload): Promise<ApiResponse<NotificationSettings>> => {
    const res = await axiosClient.put<ApiResponse<NotificationSettings>>('/notifications/settings', payload);
    return res.data;
  },

  testSmtp: async (): Promise<ApiResponse<{ success: boolean; message: string }>> => {
    const res = await axiosClient.post<ApiResponse<{ success: boolean; message: string }>>('/notifications/test-smtp');
    return res.data;
  },

  sendTestEmail: async (recipientEmail?: string): Promise<ApiResponse<{ success: boolean; recipient: string; snapshot_attached: boolean }>> => {
    const res = await axiosClient.post<ApiResponse<{ success: boolean; recipient: string; snapshot_attached: boolean }>>(
      '/notifications/test-email',
      null,
      { params: { recipient_email: recipientEmail } }
    );
    return res.data;
  },

  getAuditLogs: async (limit: number = 20): Promise<ApiResponse<NotificationAuditLog[]>> => {
    const res = await axiosClient.get<ApiResponse<NotificationAuditLog[]>>('/notifications', {
      params: { limit }
    });
    return res.data;
  }
};
