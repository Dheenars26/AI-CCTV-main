import { axiosClient } from './axiosClient';
import { ApiResponse, Camera, CameraCreatePayload, CameraRuntimeState } from '../types/api';

export interface StreamConfigData {
  camera_id: number;
  stream_token: string;
  mjpeg_url: string;
  hls_url: string;
  supported_protocols: string[];
}

export const camerasApi = {
  list: async (): Promise<ApiResponse<Camera[]>> => {
    const res = await axiosClient.get<ApiResponse<Camera[]>>('/cameras');
    return res.data;
  },

  get: async (id: number): Promise<ApiResponse<Camera>> => {
    const res = await axiosClient.get<ApiResponse<Camera>>(`/cameras/${id}`);
    return res.data;
  },

  create: async (payload: CameraCreatePayload): Promise<ApiResponse<Camera>> => {
    const res = await axiosClient.post<ApiResponse<Camera>>('/cameras', payload);
    return res.data;
  },

  update: async (id: number, payload: Partial<CameraCreatePayload>): Promise<ApiResponse<Camera>> => {
    const res = await axiosClient.patch<ApiResponse<Camera>>(`/cameras/${id}`, payload);
    return res.data;
  },

  delete: async (id: number): Promise<ApiResponse<boolean>> => {
    const res = await axiosClient.delete<ApiResponse<boolean>>(`/cameras/${id}`);
    return res.data;
  },

  deleteAll: async (): Promise<ApiResponse<number>> => {
    const res = await axiosClient.delete<ApiResponse<number>>('/cameras');
    return res.data;
  },

  getStatus: async (id: number): Promise<ApiResponse<CameraRuntimeState>> => {
    const res = await axiosClient.get<ApiResponse<CameraRuntimeState>>(`/cameras/${id}/status`);
    return res.data;
  },

  start: async (id: number): Promise<ApiResponse<CameraRuntimeState>> => {
    const res = await axiosClient.post<ApiResponse<CameraRuntimeState>>(`/cameras/${id}/start`);
    return res.data;
  },

  stop: async (id: number): Promise<ApiResponse<CameraRuntimeState>> => {
    const res = await axiosClient.post<ApiResponse<CameraRuntimeState>>(`/cameras/${id}/stop`);
    return res.data;
  },

  getStreamConfig: async (id: number): Promise<ApiResponse<StreamConfigData>> => {
    const res = await axiosClient.get<ApiResponse<StreamConfigData>>(`/cameras/${id}/stream/config`);
    return res.data;
  }
};
