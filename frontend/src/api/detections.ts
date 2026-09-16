import { axiosClient } from './axiosClient';
import { ApiResponse, Detection } from '../types/api';

export interface DetectionQueryParams {
  limit?: number;
  offset?: number;
  camera_id?: number;
  class_name?: string;
  min_confidence?: number;
}

export const detectionsApi = {
  list: async (params?: DetectionQueryParams): Promise<ApiResponse<Detection[]>> => {
    const res = await axiosClient.get<ApiResponse<Detection[]>>('/detections', { params });
    return res.data;
  }
};
