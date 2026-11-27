"use client";

import "leaflet/dist/leaflet.css";

import L from "leaflet";
import { BaseMapTiles } from "@/components/ui/BaseMapTiles";
import { MapContainer, Marker, useMapEvents } from "react-leaflet";
import { config } from "@/lib/config";
import type { LatLng } from "@/types/api";

const locationIcon = L.divIcon({
  className: "service-pin",
  html: '<span style="background:#0f766e"><svg aria-hidden="true" width="12" height="12" viewBox="0 0 12 12"><circle cx="6" cy="6" r="3" fill="white"/></svg></span>',
  iconSize: [28, 28],
  iconAnchor: [14, 33],
});

const round6 = (n: number) => Math.round(n * 1e6) / 1e6;

function ClickToPick({ onPick }: { onPick: (point: LatLng) => void }) {
  useMapEvents({
    click: (e) =>
      onPick({ lat: round6(e.latlng.lat), lng: round6(e.latlng.lng) }),
  });
  return null;
}

/** Click the map to set a point. Load via next/dynamic with `ssr: false` (Leaflet needs `window`). */
export default function LocationPicker({
  value,
  onPick,
}: {
  value: LatLng | null;
  onPick: (point: LatLng) => void;
}) {
  return (
    <MapContainer
      scrollWheelZoom={false}
      maxZoom={20}
      center={value ?? config.defaultCenter}
      zoom={value ? 15 : config.defaultZoom}
      className="h-64 w-full rounded border border-gray-300"
    >
      <BaseMapTiles />
      <ClickToPick onPick={onPick} />
      {value && (
        <Marker position={value} icon={locationIcon} title="Service location" />
      )}
    </MapContainer>
  );
}
