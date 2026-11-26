"use client";

import L from "leaflet";
import Link from "next/link";
import { memo, useMemo } from "react";
import { Marker, Popup } from "react-leaflet";
import { CATEGORY_STYLES, formatRating } from "@/features/services/categories";
import { distanceKm, formatDistance } from "@/lib/geo";
import type { LatLng, NearbyMarker, ServiceCategory } from "@/types/api";

const categoryIcons = Object.fromEntries(
  Object.entries(CATEGORY_STYLES).map(([category, { color, iconPath }]) => [
    category,
    L.divIcon({
      className: "service-pin",
      html: `<span style="background:${color}"><svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round"><path d="${iconPath}"/></svg></span>`,
      iconSize: [28, 28],
      iconAnchor: [14, 33],
      popupAnchor: [0, -30],
    }),
  ]),
) as Record<ServiceCategory, L.DivIcon>;

export function longitudeInView(longitude: number, center: number): number {
  return longitude + 360 * Math.round((center - longitude) / 360);
}

function ServicePopup({
  service,
  userLocation,
}: {
  service: NearbyMarker;
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
  service: NearbyMarker;
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
