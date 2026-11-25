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
import { useEffect, useState } from "react";
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
import { distanceKm } from "@/lib/geo";
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

function toBBox(bounds: L.LatLngBounds): string {
  return [
    bounds.getWest(),
    bounds.getSouth(),
    bounds.getEast(),
    bounds.getNorth(),
  ]
    .map((n) => n.toFixed(5))
    .join(",");
}

/** Keeps the store's viewport and the fetched bbox in sync with the map. */
function ViewportTracker({ onBBox }: { onBBox: (bbox: string) => void }) {
  const setViewport = useMapStore((s) => s.setViewport);
  const map = useMapEvents({
    moveend: () => {
      const { lat, lng } = map.getCenter();
      setViewport({ lat, lng, zoom: map.getZoom() });
      onBBox(toBBox(map.getBounds()));
    },
  });
  useEffect(() => onBBox(toBBox(map.getBounds())), [map, onBBox]);
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
          {distanceKm(userLocation, position).toFixed(1)} km away
        </p>
      )}
      <Link href={`/services/${service.id}`} className="text-xs">
        View details
      </Link>
    </div>
  );
}

export default function ServiceMap() {
  const viewport = useMapStore((s) => s.viewport);
  const userLocation = useMapStore((s) => s.userLocation);
  const category = useMapStore((s) => s.selectedCategory);
  const [bbox, setBBox] = useState<string | null>(null);

  const { data } = useQuery({
    queryKey: serviceKeys.list({ bbox: bbox ?? "", category }),
    queryFn: () => fetchServicesInView({ bbox: bbox ?? "", category }),
    enabled: bbox !== null,
    placeholderData: keepPreviousData,
  });

  return (
    <MapContainer
      center={[viewport.lat, viewport.lng]}
      zoom={viewport.zoom}
      className="h-full w-full"
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <ViewportTracker onBBox={setBBox} />
      <RecenterOnUser />
      {userLocation && (
        <CircleMarker
          center={userLocation}
          radius={8}
          pathOptions={{ color: "#fff", fillColor: "#2563eb", fillOpacity: 1 }}
        />
      )}
      <MarkerClusterGroup chunkedLoading>
        {data?.items.map((service) => (
          <Marker
            key={service.id}
            position={[service.latitude, service.longitude]}
            icon={categoryIcons[service.category]}
          >
            <Popup>
              <ServicePopup service={service} userLocation={userLocation} />
            </Popup>
          </Marker>
        ))}
      </MarkerClusterGroup>
    </MapContainer>
  );
}
