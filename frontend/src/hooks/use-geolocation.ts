"use client";

import { useEffect } from "react";
import { useMapStore } from "@/stores/map-store";

/** Asks the browser for the user's position once; on failure the map keeps the default centre. */
export function useGeolocation() {
  const setUserLocation = useMapStore((s) => s.setUserLocation);
  const setLocationFailed = useMapStore((s) => s.setLocationFailed);

  useEffect(() => {
    if (!("geolocation" in navigator)) {
      setLocationFailed("unavailable");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      ({ coords }) =>
        setUserLocation({ lat: coords.latitude, lng: coords.longitude }),
      (error) =>
        setLocationFailed(
          error.code === error.PERMISSION_DENIED
            ? "denied"
            : error.code === error.TIMEOUT
              ? "timeout"
              : "unavailable",
        ),
      { timeout: 10_000, maximumAge: 5 * 60_000 },
    );
  }, [setUserLocation, setLocationFailed]);
}
