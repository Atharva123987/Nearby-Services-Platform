/// <reference types="leaflet.markercluster" />
"use client";

import "leaflet/dist/leaflet.css";
import "react-leaflet-cluster/dist/assets/MarkerCluster.css";
import MarkerClusterGroup from "react-leaflet-cluster";
import L from "leaflet";
import { BaseMapTiles } from "@/components/ui/BaseMapTiles";
import { useCallback, useEffect, useRef } from "react";
import {
  Circle,
  CircleMarker,
  MapContainer,
  useMap,
  useMapEvents,
} from "react-leaflet";
import { NEARBY_PAGE_SIZE } from "@/features/services/api";
import { config } from "@/lib/config";
import { useMapStore } from "@/stores/map-store";
import type { LatLng, NearbyMarker } from "@/types/api";
import { longitudeInView, ServiceMarker } from "./ServiceMarker";

interface NearbyMapProps {
  center: LatLng | null;
  radiusKm: number;
  /** Debounced radius, so the map only re-zooms once the slider settles. */
  fitRadiusKm: number;
  services: NearbyMarker[];
  onPick?: (center: LatLng) => void;
  /** A new object per list click, so clicking the same item again re-opens it. */
  focus: { id: string } | null;
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

function SearchViewport({
  center,
  radiusKm,
}: {
  center: LatLng | null;
  radiusKm: number;
}) {
  const map = useMap();
  useEffect(() => {
    const search = JSON.stringify([center, radiusKm]);
    const saved = useMapStore.getState().viewport;
    if (saved?.search === search)
      map.setView(saved.center, saved.zoom, { animate: false });
    else if (center)
      map.fitBounds(L.latLng(center).toBounds(radiusKm * 2000), {
        animate: false,
      });
    function remember() {
      const { lat, lng } = map.getCenter();
      useMapStore.setState({
        viewport: { search, center: { lat, lng }, zoom: map.getZoom() },
      });
    }
    remember();
    map.on("moveend", remember);
    return () => {
      map.off("moveend", remember);
    };
  }, [map, center, radiusKm]);
  return null;
}

export default function NearbyMap({
  center,
  radiusKm,
  fitRadiusKm,
  services,
  onPick,
  focus,
}: NearbyMapProps) {
  const markers = useRef(new Map<string, L.Marker>());
  const registerMarker = useCallback((id: string, marker: L.Marker | null) => {
    if (marker) markers.current.set(id, marker);
    else markers.current.delete(id);
  }, []);
  const clusters = useRef<L.MarkerClusterGroup>(null);
  useEffect(() => {
    const marker = focus && markers.current.get(focus.id);
    let active = true;
    if (marker)
      clusters.current?.zoomToShowLayer(marker, () => {
        if (active) marker.openPopup();
      });
    return () => {
      active = false;
    };
  }, [focus]);
  const userLocation = useMapStore((s) => s.userLocation);
  const start = center ?? userLocation ?? config.defaultCenter;

  return (
    <MapContainer
      maxZoom={20}
      center={[start.lat, start.lng]}
      zoom={config.defaultZoom}
      className={onPick ? "h-full w-full !cursor-crosshair" : "h-full w-full"}
    >
      <BaseMapTiles />
      {onPick && <ClickToPick onPick={onPick} />}
      <SearchViewport center={center} radiusKm={fitRadiusKm} />
      {center && (
        <>
          <Circle
            center={center}
            radius={radiusKm * 1000}
            interactive={false}
            pathOptions={{ color: "#0f766e", fillOpacity: 0.08 }}
          />
          <CircleMarker
            center={center}
            radius={7}
            interactive={false}
            pathOptions={{
              color: "#fff",
              fillColor: "#0f766e",
              fillOpacity: 1,
            }}
          />
        </>
      )}
      <MarkerClusterGroup
        ref={clusters}
        maxClusterRadius={(zoom) => (zoom <= 12 ? 20 : 42)}
        showCoverageOnHover={false}
        iconCreateFunction={(cluster) => {
          const count = cluster.getChildCount();
          return L.divIcon({
            className: "service-cluster",
            html: `<span aria-label="${count} services">${count > NEARBY_PAGE_SIZE ? `${NEARBY_PAGE_SIZE}+` : count}</span>`,
            iconSize: [29, 24],
            iconAnchor: [14, 27],
          });
        }}
      >
        {services.map((service) => (
          <ServiceMarker
            key={service.id}
            service={service}
            longitude={longitudeInView(
              service.longitude,
              center?.lng ?? start.lng,
            )}
            userLocation={userLocation}
            onRef={registerMarker}
          />
        ))}
      </MarkerClusterGroup>
    </MapContainer>
  );
}
