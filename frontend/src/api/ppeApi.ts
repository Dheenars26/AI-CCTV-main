import { axiosClient } from './axiosClient';
import { PPEProfile, PPEViolation, Incident, SafetyStatistics } from '../types/ppe';

export const ppeApi = {
  getProfiles: async (): Promise<PPEProfile[]> => {
    const res = await axiosClient.get('/ppe/profiles');
    return res.data?.data || res.data;
  },

  createProfile: async (data: Partial<PPEProfile>): Promise<PPEProfile> => {
    const res = await axiosClient.post('/ppe/profiles', data);
    return res.data?.data || res.data;
  },

  updateProfile: async (id: number, data: Partial<PPEProfile>): Promise<PPEProfile> => {
    const res = await axiosClient.patch(`/ppe/profiles/${id}`, data);
    return res.data?.data || res.data;
  },

  deleteProfile: async (id: number): Promise<void> => {
    await axiosClient.delete(`/ppe/profiles/${id}`);
  },

  getViolations: async (params?: Record<string, any>): Promise<{ items: PPEViolation[]; total: number }> => {
    const res = await axiosClient.get('/ppe/violations', { params });
    return res.data?.data || res.data;
  },

  getIncidents: async (params?: Record<string, any>): Promise<{ items: Incident[]; total: number }> => {
    const res = await axiosClient.get('/incidents', { params });
    return res.data?.data || res.data;
  },

  getSafetyStatistics: async (): Promise<SafetyStatistics> => {
    const res = await axiosClient.get('/safety/statistics');
    return res.data?.data || res.data;
  }
};

export default ppeApi;
