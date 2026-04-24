import type { UserRole } from "../types";

export function getToken(): string | null {
  return localStorage.getItem("token");
}

export function setToken(token: string): void {
  localStorage.setItem("token", token);
}

export function clearToken(): void {
  localStorage.removeItem("token");
}

export function getUserRoleFromToken(): UserRole | null {
  const token = getToken();
  if (!token) return null;
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    const payload = JSON.parse(atob(parts[1]));
    return (payload.role as UserRole) ?? null;
  } catch {
    return null;
  }
}

export function isAuthenticated(): boolean {
  const token = getToken();
  if (!token) return false;
  try {
    const parts = token.split(".");
    const payload = JSON.parse(atob(parts[1]));
    return payload.exp * 1000 > Date.now();
  } catch {
    return false;
  }
}
