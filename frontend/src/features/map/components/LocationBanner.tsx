"use client";

import { useGeolocation } from "@/hooks/use-geolocation";
import { useMapStore } from "@/stores/map-store";

const MESSAGES = {
  denied: "Location access was denied.",
  unavailable: "Your location is unavailable.",
  timeout: "Finding your location took too long.",
} as const;

/** Requests the user's location and, if that fails, says we're showing the default city. */
export function LocationBanner() {
  useGeolocation();
  const status = useMapStore((s) => s.locationStatus);

  if (status === "pending" || status === "granted") return null;
  return (
    <div
      role="status"
      className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-900"
    >
      {MESSAGES[status]} Showing services around the city centre instead.
    </div>
  );
}
