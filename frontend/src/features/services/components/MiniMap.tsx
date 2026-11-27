"use client";

import "leaflet/dist/leaflet.css";

import { BaseMapTiles } from "@/components/ui/BaseMapTiles";
import { CircleMarker, MapContainer } from "react-leaflet";
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
      maxZoom={20}
      center={position}
      zoom={16}
      scrollWheelZoom={false}
      className="h-full w-full"
    >
      <BaseMapTiles />
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
