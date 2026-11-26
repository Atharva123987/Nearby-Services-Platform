"use client";

import { skipToken, useInfiniteQuery } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { fetchNearby, serviceKeys } from "@/features/services/api";
import { CATEGORY_STYLES } from "@/features/services/categories";
import { CategoryChips } from "@/features/services/components/CategoryChips";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { ApiError } from "@/lib/api/client";
import { formatDistance } from "@/lib/geo";
import { useMapStore } from "@/stores/map-store";
import type { LatLng } from "@/types/api";

// Leaflet touches `window` on import, so it must never render on the server.
const NearbyMap = dynamic(() => import("./NearbyMap"), {
  ssr: false,
  loading: () => <div className="h-full w-full animate-pulse bg-gray-100" />,
});

const MIN_RADIUS_KM = 1;
const MAX_RADIUS_KM = 50;
const DEFAULT_RADIUS_KM = 5;

/** Invalid or missing `?radius=` falls back to the default. */
function parseRadius(value: string | null): number {
  const n = value ? Number(value) : NaN;
  return n >= MIN_RADIUS_KM && n <= MAX_RADIUS_KM ? n : DEFAULT_RADIUS_KM;
}

/** Invalid or missing `?lat=&lng=` means no centre yet. */
function parseCenter(lat: string | null, lng: string | null): LatLng | null {
  const la = lat ? Number(lat) : NaN;
  const ln = lng ? Number(lng) : NaN;
  return Math.abs(la) <= 90 && Math.abs(ln) <= 180
    ? { lat: la, lng: ln }
    : null;
}

/** 429 notice that counts down the server's Retry-After before allowing a retry. */
function RateLimitNotice({
  seconds,
  onRetry,
}: {
  seconds: number;
  onRetry: () => void;
}) {
  const [left, setLeft] = useState(seconds);
  useEffect(() => {
    if (left <= 0) return;
    const id = setTimeout(() => setLeft(left - 1), 1000);
    return () => clearTimeout(id);
  }, [left]);

  return (
    <p role="alert" className="flex items-center gap-2 text-amber-800">
      {left > 0
        ? `Too many searches. Try again in ${left}s.`
        : "Too many searches."}
      <button
        type="button"
        onClick={onRetry}
        disabled={left > 0}
        className="font-medium underline disabled:opacity-50"
      >
        Retry
      </button>
    </p>
  );
}

/** /nearby: pick a centre (my location or a map click) and a radius; lists services inside it. */
export function NearbyView() {
  const searchParams = useSearchParams();
  const [center, setCenter] = useState(() =>
    parseCenter(searchParams.get("lat"), searchParams.get("lng")),
  );
  const [radiusKm, setRadiusKm] = useState(() =>
    parseRadius(searchParams.get("radius")),
  );
  const [locating, setLocating] = useState(false);
  const locationRequest = useRef(0);
  const [locationError, setLocationError] = useState<string | null>(null);
  const [focus, setFocus] = useState<{ id: string } | null>(null);
  const controls = useRef<HTMLDivElement>(null);
  const category = useMapStore((s) => s.selectedCategory);
  const setUserLocation = useMapStore((s) => s.setUserLocation);
  // Dragging the slider fires one request once it settles; React Query aborts stale ones.
  const debouncedRadius = useDebouncedValue(radiusKm, 300);

  // Keep the URL shareable without a navigation per slider tick.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    params.set("radius", String(debouncedRadius));
    if (center) {
      params.set("lat", center.lat.toFixed(5));
      params.set("lng", center.lng.toFixed(5));
    }
    window.history.replaceState(null, "", `?${params}`);
  }, [center, debouncedRadius]);

  const params = center
    ? { center, radiusKm: debouncedRadius, category }
    : null;
  const {
    data,
    error,
    errorUpdatedAt,
    isError,
    isFetching,
    isFetchNextPageError,
    hasNextPage,
    isFetchingNextPage,
    fetchNextPage,
    refetch,
  } = useInfiniteQuery({
    queryKey: serviceKeys.nearby(params),
    queryFn: params
      ? ({ pageParam, signal }) => fetchNearby(params, pageParam, signal)
      : skipToken,
    initialPageParam: 0,
    getNextPageParam: (last, pages) => {
      const loaded = pages.reduce((n, page) => n + page.items.length, 0);
      return loaded < last.total ? loaded : undefined;
    },
  });
  const items = data?.pages.flatMap((page) => page.items) ?? [];
  const total = data?.pages[0]?.total;
  const retry = () => (isFetchNextPageError ? fetchNextPage() : refetch());
  const retryAfter =
    error instanceof ApiError && error.status === 429
      ? ((error.details as { retryAfter: number | null }).retryAfter ?? 0)
      : null;

  function pick(next: LatLng) {
    locationRequest.current += 1;
    setLocating(false);
    setCenter(next);
    setLocationError(null);
  }

  function locateMe() {
    if (!("geolocation" in navigator)) {
      setLocationError("Your location is unavailable.");
      return;
    }
    setLocating(true);
    setLocationError(null);
    const request = ++locationRequest.current;
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        if (request !== locationRequest.current) return;
        const location = { lat: coords.latitude, lng: coords.longitude };
        setUserLocation(location);
        pick(location);
      },
      (error) => {
        if (request !== locationRequest.current) return;
        setLocating(false);
        setLocationError(
          error.code === error.PERMISSION_DENIED
            ? "Location access was denied."
            : "Couldn't get your location.",
        );
      },
      { timeout: 10_000, maximumAge: 5 * 60_000 },
    );
  }

  let status = "Use your location or click the map to set the centre.";
  if (center && total === 0) {
    status = `No services within ${debouncedRadius} km. Try increasing the radius.`;
  } else if (center && total !== undefined) {
    status = `${total} services within ${debouncedRadius} km, nearest first`;
  } else if (center) {
    status = isError ? "" : "Loading…";
  }

  return (
    <div className="relative h-full w-full">
      <NearbyMap
        center={center}
        radiusKm={radiusKm}
        fitRadiusKm={debouncedRadius}
        services={items}
        onPick={pick}
        focus={focus}
        controls={controls}
      />
      {/* Inset so the panel never covers the top-left zoom controls. */}
      <div
        ref={controls}
        className="pointer-events-none absolute inset-x-14 top-3 z-[1000] flex flex-col items-center gap-2"
      >
        <div className="pointer-events-auto">
          <CategoryChips />
        </div>
        <div className="pointer-events-auto w-full max-w-md space-y-2 rounded-md bg-white/95 p-3 text-sm shadow">
          <button
            type="button"
            onClick={locateMe}
            disabled={locating}
            className="rounded bg-blue-600 px-3 py-1 font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {locating ? "Locating…" : "Use my location"}
          </button>
          <label className="flex items-center gap-3">
            <span className="w-28 shrink-0">Radius: {radiusKm} km</span>
            <input
              type="range"
              min={MIN_RADIUS_KM}
              max={MAX_RADIUS_KM}
              step={1}
              value={radiusKm}
              onChange={(e) => setRadiusKm(Number(e.target.value))}
              className="w-full"
            />
          </label>
          {locationError && (
            <p role="alert" className="text-amber-800">
              {locationError} Click on the map to choose a centre instead.
            </p>
          )}
          <p role="status" className="text-gray-600">
            {status}
          </p>
          {items.length > 0 && (
            <ul className="max-h-[40vh] divide-y overflow-y-auto">
              {items.map((service) => {
                const style = CATEGORY_STYLES[service.category];
                return (
                  <li key={service.id}>
                    <button
                      type="button"
                      onClick={() => setFocus({ id: service.id })}
                      className="flex w-full items-center justify-between gap-3 px-1 py-2 text-left hover:bg-gray-50"
                    >
                      <span className="min-w-0">
                        <span className="block truncate font-medium">
                          {service.name}
                        </span>
                        <span
                          className="text-xs"
                          style={{ color: style.color }}
                        >
                          {style.label}
                        </span>
                      </span>
                      <span className="shrink-0 text-gray-600">
                        {formatDistance(service.distance_km)}
                      </span>
                    </button>
                  </li>
                );
              })}
              {hasNextPage && !isFetchNextPageError && (
                <li className="py-2 text-center">
                  <button
                    type="button"
                    onClick={() => fetchNextPage()}
                    disabled={isFetchingNextPage}
                    className="font-medium text-blue-700 hover:underline disabled:opacity-50"
                  >
                    {isFetchingNextPage ? "Loading…" : "Load more"}
                  </button>
                </li>
              )}
            </ul>
          )}
          {isError &&
            (retryAfter !== null ? (
              <RateLimitNotice
                key={errorUpdatedAt}
                seconds={retryAfter}
                onRetry={retry}
              />
            ) : (
              <p role="alert" className="flex items-center gap-2 text-red-700">
                Couldn&apos;t load services.
                <button
                  type="button"
                  onClick={retry}
                  disabled={isFetching}
                  className="font-medium underline disabled:opacity-50"
                >
                  {isFetching ? "Retrying…" : "Retry"}
                </button>
              </p>
            ))}
        </div>
      </div>
    </div>
  );
}
