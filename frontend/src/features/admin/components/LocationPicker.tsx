"use client";

import "leaflet/dist/leaflet.css";

import L from "leaflet";
import markerIcon2x from "leaflet/dist/images/marker-icon-2x.png";
import markerIcon from "leaflet/dist/images/marker-icon.png";
import markerShadow from "leaflet/dist/images/marker-shadow.png";
import { BaseMapTiles } from "@/components/ui/BaseMapTiles";
import { MapContainer, Marker, useMapEvents } from "react-leaflet";
import { config } from "@/lib/config";
import type { LatLng } from "@/types/api";

// Bundlers rewrite Leaflet's default icon paths; point them at the real assets.
L.Icon.Default.mergeOptions({
  iconUrl: markerIcon.src,
  iconRetinaUrl: markerIcon2x.src,
  shadowUrl: markerShadow.src,
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
      maxZoom={20}
      center={value ?? config.defaultCenter}
      zoom={value ? 15 : config.defaultZoom}
      className="h-64 w-full rounded border border-gray-300"
    >
      <BaseMapTiles />
      <ClickToPick onPick={onPick} />
      {value && <Marker position={value} />}
    </MapContainer>
  );
}
