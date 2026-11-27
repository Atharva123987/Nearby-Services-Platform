import { maplibreGL } from "@maplibre/maplibre-gl-leaflet";
import { setWorkerUrl } from "maplibre-gl";
import L from "leaflet";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect } from "react";
import { useMap } from "react-leaflet";

const attribution =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>';
const key = process.env.NEXT_PUBLIC_CARTO_BASEMAP_KEY ?? "";
const geography = new Set([
  "boundaries",
  "buildings",
  "landuse",
  "places",
  "roads",
  "water",
]);

export function BaseMapTiles() {
  const map = useMap();
  useEffect(() => {
    const context = document.createElement("canvas").getContext("webgl2");
    if (!context) {
      const raster = L.tileLayer(
        `https://{s}.basemaps.cartocdn.com/rastertiles/voyager_nolabels/{z}/{x}/{y}{r}.png?key=${encodeURIComponent(key)}`,
        { attribution, maxZoom: 20 },
      ).addTo(map);
      return () => {
        raster.remove();
      };
    }
    context.getExtension("WEBGL_lose_context")?.loseContext();
    setWorkerUrl("/maplibre/maplibre-gl-worker.mjs");
    const layer = maplibreGL({
      style: "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
      attributionControl: { customAttribution: attribution },
      transformStyle: (_, style) => ({
        ...style,
        layers: style.layers.filter(
          (layer) =>
            layer.type === "background" ||
            ("source-layer" in layer &&
              geography.has(layer["source-layer"] ?? "")),
        ),
      }),
      transformRequest: (url) => {
        const resource = new URL(url);
        if (
          resource.protocol === "https:" &&
          resource.hostname.endsWith(".cartocdn.com")
        ) {
          resource.searchParams.set("key", key);
        }
        return { url: resource.href };
      },
    }).addTo(map);
    return () => {
      layer.remove();
    };
  }, [map]);
  return null;
}
