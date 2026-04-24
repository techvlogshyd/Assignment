import client from "./client";

export interface LoginPayload {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export async function login(payload: LoginPayload): Promise<LoginResponse> {
  const { data } = await client.post<LoginResponse>("/auth/login", payload);
  return data;
}

export async function register(payload: {
  email: string;
  password: string;
  role?: string;
}): Promise<void> {
  await client.post("/auth/register", payload);
}
