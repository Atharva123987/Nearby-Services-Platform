"use client";

import "leaflet/dist/leaflet.css";
import "react-leaflet-cluster/dist/assets/MarkerCluster.css";
import "react-leaflet-cluster/dist/assets/MarkerCluster.Default.css";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import L from "leaflet";
import markerIcon2x from "leaflet/dist/images/marker-icon-2x.png";
import markerIcon from "leaflet/dist/images/marker-icon.png";
import markerShadow from "leaflet/dist/images/marker-shadow.png";
import Link from "next/link";
import { memo, useEffect, useMemo, useState } from "react";
import {
  CircleMarker,
  MapContainer,
  Marker,
  Popup,
  TileLayer,
  useMap,
  useMapEvents,
} from "react-leaflet";
import MarkerClusterGroup from "react-leaflet-cluster";
import { fetchServicesInView, serviceKeys } from "@/features/services/api";
import { CATEGORY_STYLES, formatRating } from "@/features/services/categories";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { distanceKm, formatDistance } from "@/lib/geo";
import { useMapStore } from "@/stores/map-store";
import type { LatLng, Service, ServiceCategory } from "@/types/api";

// Bundlers rewrite Leaflet's default icon paths; point them at the real assets.
L.Icon.Default.mergeOptions({
  iconUrl: markerIcon.src,
  iconRetinaUrl: markerIcon2x.src,
  shadowUrl: markerShadow.src,
});

const categoryIcons = Object.fromEntries(
  Object.entries(CATEGORY_STYLES).map(([category, { color, glyph }]) => [
    category,
    L.divIcon({
      className: "",
      html: `<div style="background:${color}" class="flex size-7 items-center justify-center rounded-full border-2 border-white text-xs font-bold text-white shadow">${glyph}</div>`,
      iconSize: [28, 28],
      iconAnchor: [14, 14],
      popupAnchor: [0, -14],
    }),
  ]),
) as Record<ServiceCategory, L.DivIcon>;

function toBBoxes(bounds: L.LatLngBounds): string[] {
  const south = Math.max(-90, bounds.getSouth());
  const north = Math.min(90, bounds.getNorth());
  const format = (west: number, east: number) =>
    [west, south, east, north].map((n) => n.toFixed(5)).join(",");

  const width = bounds.getEast() - bounds.getWest();
  if (width >= 360) return [format(-180, 180)];

  const west = L.Util.wrapNum(bounds.getWest(), [-180, 180]);
  const east = west + width;
  // The API accepts ordered bounds inside the canonical longitude range.
  return east > 180
    ? [format(west, 180), format(-180, east - 360)]
    : [format(west, east)];
}

export function longitudeInView(longitude: number, center: number): number {
  return longitude + 360 * Math.round((center - longitude) / 360);
}

/** Keeps the store's viewport and the fetched bbox in sync with the map. */
function ViewportTracker({
  onBoundsChange,
}: {
  onBoundsChange: (bboxes: string[]) => void;
}) {
  const setViewport = useMapStore((s) => s.setViewport);
  const map = useMapEvents({
    moveend: () => {
      const { lat, lng } = map.getCenter();
      setViewport({ lat, lng, zoom: map.getZoom() });
      onBoundsChange(toBBoxes(map.getBounds()));
    },
  });
  useEffect(
    () => onBoundsChange(toBBoxes(map.getBounds())),
    [map, onBoundsChange],
  );
  return null;
}

function RecenterOnUser() {
  const map = useMap();
  const userLocation = useMapStore((s) => s.userLocation);
  useEffect(() => {
    if (userLocation) map.setView(userLocation, map.getZoom());
  }, [map, userLocation]);
  return null;
}

function ServicePopup({
  service,
  userLocation,
}: {
  service: Service;
  userLocation: LatLng | null;
}) {
  const style = CATEGORY_STYLES[service.category];
  const position = { lat: service.latitude, lng: service.longitude };
  return (
    <div className="space-y-1">
      <p className="!m-0 text-sm font-semibold">{service.name}</p>
      <p className="!m-0 text-xs" style={{ color: style.color }}>
        {style.label}
      </p>
      <p className="!m-0 text-xs">{formatRating(service.rating)}</p>
      {userLocation && (
        <p className="!m-0 text-xs">
          {formatDistance(distanceKm(userLocation, position))} away
        </p>
      )}
      <Link href={`/services/${service.id}`} className="text-xs">
        View details
      </Link>
    </div>
  );
}

export const ServiceMarker = memo(function ServiceMarker({
  service,
  longitude,
  userLocation,
  onRef,
}: {
  service: Service;
  longitude: number;
  userLocation: LatLng | null;
  /** Lets a parent open this marker's popup (e.g. from a results list). */
  onRef?: (id: string, marker: L.Marker | null) => void;
}) {
  // Keep the position stable so the cluster does not remove an unchanged marker
  // while its popup is open.
  const position = useMemo<L.LatLngTuple>(
    () => [service.latitude, longitude],
    [service.latitude, longitude],
  );

  return (
    <Marker
      ref={onRef && ((marker) => onRef(service.id, marker))}
      position={position}
      icon={categoryIcons[service.category]}
      // Screen readers announce the marker by name instead of its glyph.
      title={service.name}
      alt={`${service.name} (${CATEGORY_STYLES[service.category].label})`}
    >
      <Popup>
        <ServicePopup service={service} userLocation={userLocation} />
      </Popup>
    </Marker>
  );
});

export default function ServiceMap() {
  const viewport = useMapStore((s) => s.viewport);
  const userLocation = useMapStore((s) => s.userLocation);
  const category = useMapStore((s) => s.selectedCategory);
  const [liveBBoxes, setBBoxes] = useState<string[] | null>(null);
  // Rapid pans/zooms collapse into one request once the map settles.
  const bboxes = useDebouncedValue(liveBBoxes, 300);
  const listParams = { bboxes: bboxes ?? [], category };

  const { data, isError, isFetching, refetch } = useQuery({
    queryKey: serviceKeys.list(listParams),
    queryFn: () => fetchServicesInView(listParams),
    enabled: bboxes !== null,
    placeholderData: keepPreviousData,
  });

  return (
    <div className="relative h-full w-full">
      {/* Inset past the zoom controls and below the category chips. */}
      <div className="pointer-events-none absolute inset-x-14 top-14 z-[1000] flex justify-center">
        {isError ? (
          <div
            role="alert"
            className="pointer-events-auto flex items-center gap-3 rounded-md bg-red-600 px-3 py-2 text-sm text-white shadow"
          >
            Couldn&apos;t load services.
            <button
              type="button"
              onClick={() => refetch()}
              disabled={isFetching}
              className="rounded bg-white/20 px-2 py-0.5 font-medium hover:bg-white/30 disabled:opacity-50"
            >
              {isFetching ? "Retrying…" : "Retry"}
            </button>
          </div>
        ) : (
          data?.total === 0 &&
          !isFetching && (
            <div
              role="status"
              className="rounded-md bg-white/90 px-3 py-2 text-sm text-gray-700 shadow"
            >
              No services in this area. Try zooming out or moving the map.
            </div>
          )
        )}
      </div>
      {/* Keyboard alternative to the markers: hidden until a Tab focuses it. */}
      <nav
        aria-label="Services in view"
        className="sr-only z-[1001] focus-within:not-sr-only focus-within:absolute focus-within:bottom-3 focus-within:left-3 focus-within:max-h-[50vh] focus-within:w-72 focus-within:overflow-y-auto focus-within:rounded-md focus-within:bg-white focus-within:p-3 focus-within:text-sm focus-within:shadow"
      >
        <p className="font-medium">
          {data?.items.length ?? 0} services in view
        </p>
        <ul className="mt-2 divide-y">
          {data?.items.map((service) => (
            <li key={service.id} className="py-1">
              <Link
                href={`/services/${service.id}`}
                className="text-blue-700 hover:underline"
              >
                {service.name}
              </Link>{" "}
              <span className="text-xs text-gray-600">
                {CATEGORY_STYLES[service.category].label}
              </span>
            </li>
          ))}
        </ul>
      </nav>
      <MapContainer
        center={[viewport.lat, viewport.lng]}
        zoom={viewport.zoom}
        className="h-full w-full"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <ViewportTracker onBoundsChange={setBBoxes} />
        <RecenterOnUser />
        {userLocation && (
          <CircleMarker
            center={[
              userLocation.lat,
              longitudeInView(userLocation.lng, viewport.lng),
            ]}
            radius={8}
            pathOptions={{
              color: "#fff",
              fillColor: "#2563eb",
              fillOpacity: 1,
            }}
          />
        )}
        <MarkerClusterGroup chunkedLoading>
          {data?.items.map((service) => (
            <ServiceMarker
              key={service.id}
              service={service}
              longitude={longitudeInView(service.longitude, viewport.lng)}
              userLocation={userLocation}
            />
          ))}
        </MarkerClusterGroup>
      </MapContainer>
    </div>
  );
}
