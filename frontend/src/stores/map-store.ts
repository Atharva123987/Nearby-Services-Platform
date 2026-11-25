import { create } from "zustand";
import { config } from "@/lib/config";
import type { LatLng, ServiceCategory } from "@/types/api";

export type LocationStatus =
  "pending" | "granted" | "denied" | "unavailable" | "timeout";

interface Viewport extends LatLng {
  zoom: number;
}

interface MapState {
  viewport: Viewport;
  selectedCategory: ServiceCategory | null;
  userLocation: LatLng | null;
  locationStatus: LocationStatus;
  setViewport: (viewport: Viewport) => void;
  setSelectedCategory: (category: ServiceCategory | null) => void;
  setUserLocation: (location: LatLng) => void;
  setLocationFailed: (
    status: Exclude<LocationStatus, "pending" | "granted">,
  ) => void;
}

export const useMapStore = create<MapState>()((set) => ({
  viewport: { ...config.defaultCenter, zoom: config.defaultZoom },
  selectedCategory: null,
  userLocation: null,
  locationStatus: "pending",
  setViewport: (viewport) => set({ viewport }),
  setSelectedCategory: (selectedCategory) => set({ selectedCategory }),
  // A fresh fix also recentres the map on the user.
  setUserLocation: (location) =>
    set((state) => ({
      userLocation: location,
      locationStatus: "granted",
      viewport: { ...location, zoom: state.viewport.zoom },
    })),
  // The viewport stays on the default centre.
  setLocationFailed: (locationStatus) => set({ locationStatus }),
}));
