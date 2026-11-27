"use client";

import { skipToken, useQuery } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import { useSearchParams } from "next/navigation";
import { type CSSProperties, useEffect, useRef, useState } from "react";
import {
  fetchNearbyMarkers,
  NEARBY_PAGE_SIZE,
  serviceKeys,
} from "@/features/services/api";
import { CATEGORY_STYLES, parseCategory } from "@/features/services/categories";
import { CategoryChips } from "@/features/services/components/CategoryChips";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { ApiError } from "@/lib/api/client";
import { config } from "@/lib/config";
import { formatDistance } from "@/lib/geo";
import { useMapStore } from "@/stores/map-store";
import type { LatLng } from "@/types/api";

// Leaflet touches `window` on import, so it must never render on the server.
const NearbyMap = dynamic(() => import("./NearbyMap"), {
  ssr: false,
  loading: () => <div className="h-full w-full animate-pulse bg-gray-100" />,
});

const CITY_CENTERS = {
  Mumbai: { lat: 19.076, lng: 72.8777 },
  Nashik: config.defaultCenter,
};

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

/** Nearby search: pick a centre (my location or a map click) and a radius; lists services inside it. */
export function NearbyView() {
  const searchParams = useSearchParams();
  // A shared URL takes precedence. A bare Explore link resumes this tab's search.
  const [initial] = useState(() => {
    const saved = useMapStore.getState();
    const shared = ["lat", "lng", "radius", "category"].some((key) =>
      searchParams.has(key),
    );
    return shared
      ? {
          center:
            parseCenter(searchParams.get("lat"), searchParams.get("lng")) ??
            CITY_CENTERS.Nashik,
          allDistances: searchParams.get("radius") === "all",
          radius: parseRadius(searchParams.get("radius")),
          category: parseCategory(searchParams.get("category")),
        }
      : {
          center: saved.searchCenter ?? CITY_CENTERS.Nashik,
          allDistances: saved.allDistances,
          radius: saved.radiusKm,
          category: saved.selectedCategory,
        };
  });
  const [center, setCenter] = useState(initial.center);
  const [allDistances, setAllDistances] = useState(initial.allDistances);
  const [radiusKm, setRadiusKm] = useState(initial.radius);
  const [picking, setPicking] = useState(false);
  const [locating, setLocating] = useState(false);
  const mapFrame = useRef<HTMLDivElement>(null);
  const locationRequest = useRef(0);
  const [locationError, setLocationError] = useState<string | null>(null);
  const [focus, setFocus] = useState<{ id: string } | null>(null);
  const [category, setCategory] = useState(initial.category);
  const setUserLocation = useMapStore((s) => s.setUserLocation);
  // Dragging the slider fires one request once it settles; React Query aborts stale ones.
  const debouncedRadius = useDebouncedValue(radiusKm, 300);

  // Keep the URL shareable without a navigation per slider tick.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    params.set("radius", allDistances ? "all" : String(radiusKm));
    if (category) params.set("category", category);
    else params.delete("category");
    useMapStore.setState({
      searchCenter: center,
      allDistances,
      radiusKm,
      selectedCategory: category,
    });
    if (center) {
      params.set("lat", center.lat.toFixed(5));
      params.set("lng", center.lng.toFixed(5));
    }
    window.history.replaceState(null, "", `?${params}`);
  }, [center, radiusKm, category, allDistances]);

  const searchRadius = allDistances ? ("all" as const) : debouncedRadius;
  const params = center ? { center, radiusKm: searchRadius, category } : null;
  const { data, error, errorUpdatedAt, isError, isFetching, refetch } =
    useQuery({
      queryKey: serviceKeys.markers(params),
      queryFn: params
        ? ({ signal }) => fetchNearbyMarkers(params, signal)
        : skipToken,
    });
  const items = data?.items ?? [];
  const total = data?.items.length;
  const search = JSON.stringify(params);
  const expandedList = useMapStore((state) => state.expandedList);
  const listLimit =
    expandedList?.search === search ? expandedList.limit : NEARBY_PAGE_SIZE;
  const retryAfter =
    error instanceof ApiError && error.status === 429
      ? ((error.details as { retryAfter: number | null }).retryAfter ?? 0)
      : null;

  function pick(next: LatLng) {
    setAllDistances(false);
    locationRequest.current += 1;
    setLocating(false);
    setPicking(false);
    setCenter({
      lat: Number(next.lat.toFixed(5)),
      lng: Number(next.lng.toFixed(5)),
    });
    setLocationError(null);
  }

  useEffect(() => {
    if (!locating) return;
    const request = locationRequest.current;
    const deadline = window.setTimeout(() => {
      if (request !== locationRequest.current) return;
      locationRequest.current++;
      setLocating(false);
      setLocationError(
        "Location timed out. Try again or choose a point on the map.",
      );
    }, 35000);
    return () => {
      clearTimeout(deadline);
      locationRequest.current++;
    };
  }, [locating]);

  function locateMe() {
    if (!navigator.geolocation) {
      setLocationError(
        "Location is unavailable in this browser. Use HTTPS or choose a point on the map.",
      );
      return;
    }
    setPicking(false);
    setLocating(true);
    setLocationError(null);
    const request = ++locationRequest.current;
    function attempt(precise: boolean) {
      navigator.geolocation.getCurrentPosition(
        ({ coords }) => {
          if (request !== locationRequest.current) return;
          const location = { lat: coords.latitude, lng: coords.longitude };
          setUserLocation(location);
          pick(location);
        },
        (error) => {
          if (request !== locationRequest.current) return;
          if (error.code !== 1 && !precise) {
            attempt(true);
            return;
          }
          setLocating(false);
          setLocationError(
            error.code === 1
              ? "Location access was denied. Allow location for this site or choose a point on the map."
              : error.code === 3
                ? "Location timed out. Try again or choose a point on the map."
                : "Your device could not determine its location. Check device location services or choose a point on the map.",
          );
        },
        {
          enableHighAccuracy: precise,
          timeout: precise ? 20000 : 10000,
          maximumAge: precise ? 0 : 300000,
        },
      );
    }
    attempt(false);
  }

  let status = "";
  if (allDistances && total !== undefined) {
    status = total
      ? `${total} services, nearest first`
      : "No matching services.";
  } else if (center && total === 0) {
    const suggestion =
      debouncedRadius < MAX_RADIUS_KM
        ? "Try increasing the radius."
        : category
          ? "Try another category or search location."
          : "Try another search location.";
    status = `No services within ${debouncedRadius} km. ${suggestion}`;
  } else if (center && total !== undefined) {
    status = `${total} services within ${debouncedRadius} km, nearest first`;
  } else if (center) {
    status = isError ? "" : "Loading…";
  }

  return (
    <div className="search-layout">
      <div
        ref={mapFrame}
        className="map-frame"
        style={
          {
            "--cluster-fill": category
              ? CATEGORY_STYLES[category].color
              : "var(--fieldguide-lime)",
            "--cluster-ink":
              !category || category === "atm" ? "#10251c" : "white",
          } as CSSProperties
        }
      >
        <NearbyMap
          category={category}
          center={center}
          allDistances={allDistances}
          radiusKm={radiusKm}
          fitRadiusKm={debouncedRadius}
          services={items}
          onPick={picking ? pick : undefined}
          focus={focus}
        />
      </div>
      <section className="search-panel">
        <h1>Find nearby services</h1>
        <p className="mt-1 text-sm text-slate-600">
          {picking
            ? "Click the map to set your search location."
            : "Use your location or choose a search location on the map."}
        </p>
        <div className="mt-5 space-y-4 text-sm">
          <div className="rounded-lg bg-teal-50 px-3 py-2.5">
            <p className="text-xs text-teal-950">
              Service coverage is currently limited to Mumbai and Nashik.
            </p>
            <div
              className="mt-2 flex gap-2"
              role="group"
              aria-label="Search by city"
            >
              {Object.entries(CITY_CENTERS).map(([city, point]) => (
                <button
                  key={city}
                  aria-pressed={
                    center?.lat === point.lat && center?.lng === point.lng
                  }
                  type="button"
                  onClick={() => pick(point)}
                  className="rounded-md border border-teal-200 bg-white px-3 py-1.5 font-medium text-teal-900 hover:bg-teal-100 aria-pressed:bg-teal-800 aria-pressed:text-white"
                >
                  {city}
                </button>
              ))}
            </div>
          </div>
          <button
            type="button"
            onClick={locateMe}
            disabled={locating}
            className="w-full rounded-lg bg-teal-800 px-4 py-2.5 font-medium text-white hover:bg-teal-900 disabled:opacity-50"
          >
            {locating ? "Locating…" : "Use my location"}
          </button>
          <button
            type="button"
            aria-pressed={picking}
            className="w-full rounded-lg border border-teal-800 px-4 py-2 font-medium text-teal-800"
            onClick={() => {
              locationRequest.current++;
              setLocating(false);
              setLocationError(null);
              setPicking(!picking);
              if (!picking)
                mapFrame.current?.scrollIntoView({ block: "nearest" });
            }}
          >
            {picking ? "Cancel map selection" : "Choose location on map"}
          </button>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={!allDistances}
              onChange={(event) => setAllDistances(!event.target.checked)}
            />
            Limit search by radius
          </label>
          {!allDistances && (
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
          )}
          <CategoryChips selected={category} onSelect={setCategory} />
          {locationError && (
            <p role="alert" className="text-amber-800">
              {locationError}
            </p>
          )}
          <p role="status" className="text-gray-600">
            {status}
          </p>
          {items.length > 0 && (
            <ul className="divide-y divide-slate-200">
              {items.slice(0, listLimit).map((service) => {
                const style = CATEGORY_STYLES[service.category];
                return (
                  <li key={service.id}>
                    <button
                      type="button"
                      onClick={() => {
                        setFocus({ id: service.id });
                        mapFrame.current?.scrollIntoView({ block: "nearest" });
                      }}
                      className="flex w-full items-center justify-between gap-3 px-1 py-2 text-left hover:bg-gray-50"
                    >
                      <span
                        className="grid size-8 shrink-0 place-items-center rounded-full"
                        style={{
                          color: style.color,
                          backgroundColor: style.color + "12",
                        }}
                      >
                        <svg
                          aria-hidden="true"
                          width="18"
                          height="18"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2.4"
                          strokeLinejoin="round"
                          strokeLinecap="round"
                        >
                          <path d={style.iconPath} />
                        </svg>
                      </span>
                      <span className="min-w-0 flex-1">
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
              {listLimit < items.length && (
                <li className="py-2 text-center">
                  <button
                    type="button"
                    onClick={() =>
                      useMapStore.setState({
                        expandedList: {
                          search,
                          limit: listLimit + NEARBY_PAGE_SIZE,
                        },
                      })
                    }
                    className="font-medium text-blue-700 hover:underline disabled:opacity-50"
                  >
                    Load more
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
                onRetry={() => refetch()}
              />
            ) : (
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
            ))}
        </div>
      </section>
    </div>
  );
}
