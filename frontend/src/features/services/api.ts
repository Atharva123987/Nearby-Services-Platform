import { apiFetch } from "@/lib/api/client";
import type {
  LatLng,
  NearbyPage,
  Service,
  ServiceCategory,
  ServicePage,
} from "@/types/api";

export interface ServiceListParams {
  /** Each box uses the backend's "minLng,minLat,maxLng,maxLat" format. */
  bboxes: readonly string[];
  category: ServiceCategory | null;
}

export interface NearbyParams {
  center: LatLng;
  radiusKm: number;
  category: ServiceCategory | null;
}

export const serviceKeys = {
  all: ["services"] as const,
  list: (params: ServiceListParams) =>
    [...serviceKeys.all, "list", params] as const,
  nearby: (params: NearbyParams | null) =>
    [...serviceKeys.all, "nearby", params] as const,
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

/** Next data-cache tag for one service's detail page; admin writes revalidate it. */
export const serviceTag = (id: string) => `service:${id}`;

/**
 * Server-only: one service for the /services/[id] page, cached by Next (ISR).
 * Admin edits revalidate the tag; the short `revalidate` is the fallback.
 */
export function fetchServiceDetail(id: string, baseUrl: string) {
  return apiFetch<Service>(
    `/api/v1/services/${encodeURIComponent(id)}`,
    { next: { revalidate: 60, tags: [serviceTag(id)] } },
    baseUrl,
  );
}

export const NEARBY_PAGE_SIZE = 20;

/** Services within `radiusKm` of `center`, nearest first. `signal` cancels stale requests. */
export function fetchNearby(
  { center, radiusKm, category }: NearbyParams,
  offset: number,
  signal?: AbortSignal,
): Promise<NearbyPage> {
  const query = new URLSearchParams({
    lat: String(center.lat),
    lng: String(center.lng),
    radius_km: String(radiusKm),
    limit: String(NEARBY_PAGE_SIZE),
    offset: String(offset),
  });
  if (category) query.set("category", category);
  return apiFetch<NearbyPage>(`/api/v1/services/nearby?${query}`, { signal });
}
