"use client";

import dynamic from "next/dynamic";
import { distanceKm, formatDistance } from "@/lib/geo";
import { useMapStore } from "@/stores/map-store";
import type { LatLng } from "@/types/api";

// Leaflet touches `window` on import, so it must never render on the server.
const MiniMap = dynamic(() => import("./MiniMap"), {
  ssr: false,
  loading: () => <div className="h-full w-full animate-pulse bg-gray-100" />,
});

/** Mini map, distance from the user (when the map already knows their location) and directions. */
export function ServiceLocation({
  position,
  color,
}: {
  position: LatLng;
  color: string;
}) {
  const userLocation = useMapStore((s) => s.userLocation);
  const directionsUrl = `https://www.google.com/maps/dir/?api=1&destination=${position.lat},${position.lng}`;

  return (
    <section className="space-y-3">
      <div className="h-64 overflow-hidden rounded-lg border border-gray-200">
        <MiniMap position={position} color={color} />
      </div>
      <div className="flex flex-wrap items-center gap-4 text-sm">
        {userLocation && (
          <span>{formatDistance(distanceKm(userLocation, position))} away</span>
        )}
        <a
          href={directionsUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="rounded bg-blue-600 px-3 py-1.5 font-medium text-white hover:bg-blue-700"
        >
          Get directions
        </a>
      </div>
    </section>
  );
}
