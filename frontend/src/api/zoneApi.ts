import { axiosClient } from './axiosClient';
import { SafetyZone } from '../types/ppe';

export const zoneApi = {
  getZones: async (cameraId?: number): Promise<SafetyZone[]> => {
    const res = await axiosClient.get('/zones', { params: { camera_id: cameraId } });
    return res.data?.data || res.data;
  },

  createZone: async (data: Partial<SafetyZone>): Promise<SafetyZone> => {
    const res = await axiosClient.post('/zones', data);
    return res.data?.data || res.data;
  },

  updateZone: async (id: number, data: Partial<SafetyZone>): Promise<SafetyZone> => {
    const res = await axiosClient.patch(`/zones/${id}`, data);
    return res.data?.data || res.data;
  },

  deleteZone: async (id: number): Promise<void> => {
    await axiosClient.delete(`/zones/${id}`);
  }
};

export default zoneApi;
