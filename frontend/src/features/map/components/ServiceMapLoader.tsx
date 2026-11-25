"use client";

import dynamic from "next/dynamic";

// Leaflet touches `window` on import, so it must never render on the server.
const ServiceMap = dynamic(() => import("./ServiceMap"), {
  ssr: false,
  loading: () => <div className="h-full w-full animate-pulse bg-gray-100" />,
});

export function ServiceMapLoader() {
  return <ServiceMap />;
}
