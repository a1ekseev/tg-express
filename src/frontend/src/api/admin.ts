import axios from 'axios';
import { router } from '@/router';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token');
      router.push('/login');
    }
    return Promise.reject(error);
  },
);

// --- Auth ---

export async function login(username: string, password: string): Promise<string> {
  const { data } = await api.post<{ access_token: string }>('/api/admin/login', {
    username,
    password,
  });
  localStorage.setItem('access_token', data.access_token);
  return data.access_token;
}

export function logout(): void {
  localStorage.removeItem('access_token');
  router.push('/login');
}

export function isAuthenticated(): boolean {
  return !!localStorage.getItem('access_token');
}

// --- Channel Pairs ---

export interface ChannelPair {
  id: string;
  tg_chat_id: number;
  express_chat_id: string | null;
  is_approved: boolean;
  name: string | null;
}

export async function listChannelPairs(): Promise<ChannelPair[]> {
  const { data } = await api.get<ChannelPair[]>('/api/admin/channel-pairs');
  return data;
}

export async function approveChannelPair(pairId: string): Promise<void> {
  await api.post(`/api/admin/channel-pairs/${pairId}/approve`);
}

// --- Employees ---

export interface Employee {
  id: string;
  tg_user_id: number | null;
  express_huid: string | null;
  full_name: string | null;
  position: string | null;
  tg_name: string | null;
  express_name: string | null;
}

export async function listEmployees(): Promise<Employee[]> {
  const { data } = await api.get<Employee[]>('/api/admin/employees');
  return data;
}

export async function updateEmployee(
  id: string,
  payload: { full_name?: string | null; position?: string | null },
): Promise<void> {
  await api.put(`/api/admin/employees/${id}`, payload);
}

export async function deleteEmployee(id: string): Promise<void> {
  await api.delete(`/api/admin/employees/${id}`);
}
