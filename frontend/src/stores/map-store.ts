import { create } from "zustand";
import type { LatLng, ServiceCategory } from "@/types/api";

interface MapState {
  searchCenter: LatLng | null;
  radiusKm: number;
  expandedList: { search: string; limit: number } | null;
  viewport: { search: string; center: LatLng; zoom: number } | null;
  selectedCategory: ServiceCategory | null;
  userLocation: LatLng | null;
  setUserLocation: (location: LatLng) => void;
}

export const useMapStore = create<MapState>()((set) => ({
  selectedCategory: null,
  searchCenter: null,
  radiusKm: 5,
  viewport: null,
  expandedList: null,
  userLocation: null,
  setUserLocation: (userLocation) => set({ userLocation }),
}));
