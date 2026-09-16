import { axiosClient } from './axiosClient';
import { ApiResponse, SystemStatus, SystemStats, VerificationSettings } from '../types/api';

export const systemApi = {
  getStatus: async (): Promise<ApiResponse<SystemStatus>> => {
    const res = await axiosClient.get<ApiResponse<SystemStatus>>('/system/status');
    return res.data;
  },

  getStats: async (): Promise<ApiResponse<SystemStats>> => {
    const res = await axiosClient.get<ApiResponse<SystemStats>>('/system/stats');
    return res.data;
  },

  getLogs: async (): Promise<ApiResponse<string[]>> => {
    const res = await axiosClient.get<ApiResponse<string[]>>('/system/logs');
    return res.data;
  },

  getVerificationSettings: async (): Promise<ApiResponse<VerificationSettings>> => {
    const res = await axiosClient.get<ApiResponse<VerificationSettings>>('/system/verification');
    return res.data;
  },

  updateVerificationSettings: async (payload: Partial<VerificationSettings>): Promise<ApiResponse<VerificationSettings>> => {
    const res = await axiosClient.put<ApiResponse<VerificationSettings>>('/system/verification', payload);
    return res.data;
  }
};
