import client from './client';

export interface LoginRequest {
  username: string;
  password: string;
}

export interface RegisterRequest {
  username: string;
  password: string;
  email?: string;
}

export interface UserInfo {
  id: string;  // uuid hex from BE
  username: string;
  email: string | null;
  role: 'admin' | 'editor' | 'viewer';
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: UserInfo;
}

export async function login(data: LoginRequest): Promise<AuthResponse> {
  return client.post('/auth/login', data);
}

export async function register(data: RegisterRequest): Promise<AuthResponse> {
  return client.post('/auth/register', data);
}

export async function getMe(): Promise<UserInfo> {
  return client.get('/users/me');
}
