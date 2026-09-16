import { axiosClient } from './axiosClient';
import { ApiResponse, EvidenceItem } from '../types/api';

export interface EvidenceQueryParams {
  limit?: number;
  offset?: number;
  alert_id?: string;
  camera_id?: number;
}

export const evidenceApi = {
  list: async (params?: EvidenceQueryParams): Promise<ApiResponse<EvidenceItem[]>> => {
    const res = await axiosClient.get<ApiResponse<EvidenceItem[]>>('/evidence', { params });
    return res.data;
  },

  get: async (id: string): Promise<ApiResponse<EvidenceItem>> => {
    const res = await axiosClient.get<ApiResponse<EvidenceItem>>(`/evidence/${id}`);
    return res.data;
  },

  purge: async (id: string): Promise<ApiResponse<boolean>> => {
    const res = await axiosClient.delete<ApiResponse<boolean>>(`/evidence/${id}`);
    return res.data;
  },

  purgeAll: async (): Promise<ApiResponse<any>> => {
    const res = await axiosClient.delete<ApiResponse<any>>('/evidence');
    return res.data;
  }
};
