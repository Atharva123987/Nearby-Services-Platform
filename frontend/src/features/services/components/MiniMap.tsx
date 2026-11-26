"use client";

import "leaflet/dist/leaflet.css";

import { CircleMarker, MapContainer, TileLayer } from "react-leaflet";
import type { LatLng } from "@/types/api";

/** Small static map centred on one service. */
export default function MiniMap({
  position,
  color,
}: {
  position: LatLng;
  color: string;
}) {
  return (
    <MapContainer
      center={position}
      zoom={16}
      scrollWheelZoom={false}
      className="h-full w-full"
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <CircleMarker
        center={position}
        radius={10}
        pathOptions={{
          color: "#fff",
          weight: 2,
          fillColor: color,
          fillOpacity: 1,
        }}
      />
    </MapContainer>
  );
}
