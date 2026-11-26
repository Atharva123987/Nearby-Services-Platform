"use client";

import { keepPreviousData, skipToken, useQuery } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { fetchNearby, serviceKeys } from "@/features/services/api";
import { CategoryChips } from "@/features/services/components/CategoryChips";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
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

/** /nearby: pick a centre (my location or a map click) and a radius; shows services inside it. */
export function NearbyView() {
  const searchParams = useSearchParams();
  const [center, setCenter] = useState(() =>
    parseCenter(searchParams.get("lat"), searchParams.get("lng")),
  );
  const [radiusKm, setRadiusKm] = useState(() =>
    parseRadius(searchParams.get("radius")),
  );
  const [locating, setLocating] = useState(false);
  const [locationError, setLocationError] = useState<string | null>(null);
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
  const { data, isError, isFetching, refetch } = useQuery({
    queryKey: serviceKeys.nearby(params),
    queryFn: params ? ({ signal }) => fetchNearby(params, signal) : skipToken,
    placeholderData: keepPreviousData,
  });

  function pick(next: LatLng) {
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
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        const location = { lat: coords.latitude, lng: coords.longitude };
        setLocating(false);
        setUserLocation(location);
        pick(location);
      },
      (error) => {
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
  if (center && data) {
    status = `${data.total} services within ${debouncedRadius} km`;
    if (data.items.length < data.total) {
      status += ` (showing nearest ${data.items.length})`;
    }
  } else if (center) {
    status = "Loading…";
  }

  return (
    <div className="relative h-full w-full">
      <NearbyMap
        center={center}
        radiusKm={radiusKm}
        fitRadiusKm={debouncedRadius}
        services={data?.items ?? []}
        onPick={pick}
      />
      {/* Inset so the panel never covers the top-left zoom controls. */}
      <div className="pointer-events-none absolute inset-x-14 top-3 z-[1000] flex flex-col items-center gap-2">
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
          {isError ? (
            <p role="alert" className="flex items-center gap-2 text-red-700">
              Couldn&apos;t load services.
              <button
                type="button"
                onClick={() => refetch()}
                disabled={isFetching}
                className="font-medium underline disabled:opacity-50"
              >
                {isFetching ? "Retrying…" : "Retry"}
              </button>
            </p>
          ) : (
            <p role="status" className="text-gray-600">
              {status}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
