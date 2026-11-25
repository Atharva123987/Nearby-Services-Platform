import { apiFetch } from "@/lib/api/client";
import type { ServiceCategory, ServicePage } from "@/types/api";

export interface ServiceListParams {
  /** Each box uses the backend's "minLng,minLat,maxLng,maxLat" format. */
  bboxes: readonly string[];
  category: ServiceCategory | null;
}

export const serviceKeys = {
  all: ["services"] as const,
  list: (params: ServiceListParams) =>
    [...serviceKeys.all, "list", params] as const,
};

/** Services inside the map viewport (the backend caps each box at 200). */
export async function fetchServicesInView({
  bboxes,
  category,
}: ServiceListParams): Promise<Pick<ServicePage, "items" | "total">> {
  const pages = await Promise.all(
    bboxes.map((bbox) => {
      const query = new URLSearchParams({ bbox, page_size: "200" });
      if (category) query.set("category", category);
      return apiFetch<ServicePage>(`/api/v1/services?${query}`);
    }),
  );
  return {
    items: pages.flatMap((page) => page.items),
    total: pages.reduce((total, page) => total + page.total, 0),
  };
}
