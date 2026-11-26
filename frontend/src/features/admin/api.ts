import { ApiError, apiFetch } from "@/lib/api/client";
import { loginUrl } from "@/lib/auth/return-url";
import type { Admin } from "@/types/api";

export interface LoginInput {
  email: string;
  password: string;
}

export const adminKeys = {
  all: ["admin"] as const,
  me: () => [...adminKeys.all, "me"] as const,
};

/**
 * Authenticated API call via the Next route handler that attaches the cookie token
 * (`/api/backend/x` -> `/api/v1/x`). If the session is gone even after a refresh,
 * go to login and come back here afterwards.
 */
export async function adminFetch<T>(path: string, init?: RequestInit) {
  try {
    return await apiFetch<T>(`/api/backend${path}`, init, "");
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      window.location.assign(
        loginUrl(window.location.pathname + window.location.search),
      );
    }
    throw error;
  }
}

export function login(input: LoginInput) {
  return apiFetch<{ ok: true }>(
    "/api/auth/login",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    },
    "",
  );
}

export function logout() {
  return apiFetch<{ ok: true }>("/api/auth/logout", { method: "POST" }, "");
}

export function fetchMe() {
  return adminFetch<Admin>("/auth/me");
}
