import { axiosClient } from './axiosClient';
import { ApiResponse, Alert } from '../types/api';

export interface AlertQueryParams {
  limit?: number;
  offset?: number;
  status?: string;
  state?: string;
  class_name?: string;
  camera_id?: number;
}

export const alertsApi = {
  list: async (params?: AlertQueryParams): Promise<ApiResponse<Alert[]>> => {
    const queryParams: Record<string, any> = { ...params };
    if (params?.status && !params?.state) {
      queryParams.state = params.status;
    }
    const res = await axiosClient.get<ApiResponse<Alert[]>>('/alerts', { params: queryParams });
    return res.data;
  },

  get: async (id: string | number): Promise<ApiResponse<Alert>> => {
    const res = await axiosClient.get<ApiResponse<Alert>>(`/alerts/${id}`);
    return res.data;
  },

  acknowledge: async (id: string | number): Promise<ApiResponse<Alert>> => {
    const res = await axiosClient.patch<ApiResponse<Alert>>(`/alerts/${id}`, { state: 'ACKNOWLEDGED' });
    return res.data;
  },

  resolve: async (
    id: string | number,
    remedyData?: { remedial_action?: string; remedy_notes?: string; resolved_by?: string }
  ): Promise<ApiResponse<Alert>> => {
    const res = await axiosClient.patch<ApiResponse<Alert>>(`/alerts/${id}`, {
      state: 'RESOLVED',
      ...remedyData,
    });
    return res.data;
  },

  resolveAll: async (): Promise<ApiResponse<{ resolved_count: number }>> => {
    const res = await axiosClient.post<ApiResponse<{ resolved_count: number }>>('/alerts/resolve-all');
    return res.data;
  }
};
