"use client";

import L from "leaflet";
import { useEffect } from "react";
import {
  Circle,
  CircleMarker,
  MapContainer,
  TileLayer,
  useMap,
  useMapEvents,
} from "react-leaflet";
import { config } from "@/lib/config";
import { useMapStore } from "@/stores/map-store";
import type { LatLng, Service } from "@/types/api";
import { longitudeInView, ServiceMarker } from "./ServiceMap";

interface NearbyMapProps {
  center: LatLng | null;
  radiusKm: number;
  /** Debounced radius, so the map only re-zooms once the slider settles. */
  fitRadiusKm: number;
  services: Service[];
  onPick: (center: LatLng) => void;
}

function ClickToPick({ onPick }: { onPick: (center: LatLng) => void }) {
  useMapEvents({
    click: (e) => {
      const { lat, lng } = e.latlng.wrap();
      onPick({ lat, lng });
    },
  });
  return null;
}

function FitToCircle({
  center,
  radiusKm,
}: {
  center: LatLng;
  radiusKm: number;
}) {
  const map = useMap();
  useEffect(() => {
    map.fitBounds(L.latLng(center).toBounds(radiusKm * 2000));
  }, [map, center, radiusKm]);
  return null;
}

export default function NearbyMap({
  center,
  radiusKm,
  fitRadiusKm,
  services,
  onPick,
}: NearbyMapProps) {
  const userLocation = useMapStore((s) => s.userLocation);
  const start = center ?? userLocation ?? config.defaultCenter;

  return (
    <MapContainer
      center={[start.lat, start.lng]}
      zoom={config.defaultZoom}
      className="h-full w-full cursor-crosshair"
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <ClickToPick onPick={onPick} />
      {center && (
        <>
          <FitToCircle center={center} radiusKm={fitRadiusKm} />
          <Circle
            center={center}
            radius={radiusKm * 1000}
            interactive={false}
            pathOptions={{ color: "#2563eb", fillOpacity: 0.08 }}
          />
          <CircleMarker
            center={center}
            radius={7}
            interactive={false}
            pathOptions={{
              color: "#fff",
              fillColor: "#2563eb",
              fillOpacity: 1,
            }}
          />
        </>
      )}
      {services.map((service) => (
        <ServiceMarker
          key={service.id}
          service={service}
          longitude={longitudeInView(
            service.longitude,
            center?.lng ?? start.lng,
          )}
          userLocation={userLocation}
        />
      ))}
    </MapContainer>
  );
}
