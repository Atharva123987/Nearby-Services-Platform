import { apiFetch } from "@/lib/api/client";
import type {
  LatLng,
  NearbyMarkers,
  Service,
  ServiceCategory,
} from "@/types/api";

export interface NearbyParams {
  center: LatLng;
  radiusKm: number | "all";
  category: ServiceCategory | null;
}

export const serviceKeys = {
  all: ["services"] as const,
  markers: (params: NearbyParams | null) =>
    [...serviceKeys.all, "nearby", "markers", params] as const,
};

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
export function fetchNearbyMarkers(
  { center, radiusKm, category }: NearbyParams,
  signal?: AbortSignal,
): Promise<NearbyMarkers> {
  const query = new URLSearchParams({
    lat: String(center.lat),
    lng: String(center.lng),
    radius_km: String(radiusKm),
  });
  if (category) query.set("category", category);
  return apiFetch<NearbyMarkers>(`/api/v1/services/nearby/markers?${query}`, {
    signal,
  });
}
