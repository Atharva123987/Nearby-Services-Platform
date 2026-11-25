import { apiFetch } from "@/lib/api/client";
import type { ServiceCategory, ServicePage } from "@/types/api";

export interface ServiceListParams {
  /** "minLng,minLat,maxLng,maxLat", as the backend expects. */
  bbox: string;
  category: ServiceCategory | null;
}

export const serviceKeys = {
  all: ["services"] as const,
  list: (params: ServiceListParams) =>
    [...serviceKeys.all, "list", params] as const,
};

/** Services inside the map viewport (the backend caps a page at 200). */
export function fetchServicesInView({ bbox, category }: ServiceListParams) {
  const query = new URLSearchParams({ bbox, page_size: "200" });
  if (category) query.set("category", category);
  return apiFetch<ServicePage>(`/api/v1/services?${query}`);
}
