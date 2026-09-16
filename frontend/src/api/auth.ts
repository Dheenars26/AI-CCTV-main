import { axiosClient } from './axiosClient';
import { ApiResponse, User } from '../types/api';

export interface LoginPayload {
  username: string;
  password: string;
}

export interface LoginResponseData {
  access_token: string;
  token_type: string;
  csrf_token: string;
  user: User;
}

export interface WSTicketData {
  ticket: string;
  expires_in_seconds: number;
}

export const authApi = {
  login: async (payload: LoginPayload): Promise<ApiResponse<LoginResponseData>> => {
    const res = await axiosClient.post<ApiResponse<LoginResponseData>>('/auth/login', payload);
    return res.data;
  },

  logout: async (): Promise<void> => {
    await axiosClient.post('/auth/logout');
  },

  getMe: async (): Promise<ApiResponse<User>> => {
    const res = await axiosClient.get<ApiResponse<User>>('/auth/me');
    return res.data;
  },

  updateMe: async (payload: { email?: string; full_name?: string }): Promise<ApiResponse<User>> => {
    const res = await axiosClient.put<ApiResponse<User>>('/auth/me', payload);
    return res.data;
  },

  getWSTicket: async (): Promise<string> => {
    const res = await axiosClient.post<ApiResponse<WSTicketData>>('/auth/ws-ticket');
    return res.data.data.ticket;
  }
};
