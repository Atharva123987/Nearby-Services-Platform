import { ApiError, apiFetch } from "@/lib/api/client";
import { loginUrl } from "@/lib/auth/return-url";
import type { Admin, Service, ServiceCategory, ServicePage } from "@/types/api";

export interface LoginInput {
  email: string;
  password: string;
}

export interface AdminServiceParams {
  page: number;
  pageSize: number;
  search: string;
  category: ServiceCategory | null;
}

// Mirrors ServiceUpdate (backend/app/schemas/service.py); only sent fields change.
export type ServiceUpdate = Partial<
  Pick<Service, "name" | "category" | "latitude" | "longitude" | "rating">
>;

export const adminKeys = {
  all: ["admin"] as const,
  me: () => [...adminKeys.all, "me"] as const,
  services: () => [...adminKeys.all, "services"] as const,
  serviceList: (params: AdminServiceParams) =>
    [...adminKeys.services(), "list", params] as const,
  categoryCounts: () => [...adminKeys.services(), "category-counts"] as const,
  recent: () => [...adminKeys.services(), "recent"] as const,
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

/** Newest first (the backend's list order). */
export function fetchAdminServices({
  page,
  pageSize,
  search,
  category,
}: AdminServiceParams) {
  const query = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  if (search) query.set("search", search);
  if (category) query.set("category", category);
  return adminFetch<ServicePage>(`/admin/services?${query}`);
}

/** Totals per category. There is no stats endpoint, so each is a one-row page's `total`. */
export async function fetchCategoryCounts(
  categories: readonly ServiceCategory[],
): Promise<Record<ServiceCategory, number>> {
  const pages = await Promise.all(
    categories.map((category) =>
      fetchAdminServices({ page: 1, pageSize: 1, search: "", category }),
    ),
  );
  return Object.fromEntries(
    categories.map((category, i) => [category, pages[i].total]),
  ) as Record<ServiceCategory, number>;
}

export function updateService(id: string, body: ServiceUpdate) {
  return adminFetch<Service>(`/admin/services/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function deleteService(id: string) {
  return adminFetch<null>(`/admin/services/${id}`, { method: "DELETE" });
}
