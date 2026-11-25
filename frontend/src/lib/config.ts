// NEXT_PUBLIC_* values are inlined at build time.
export const config = {
  apiUrl: (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(
    /\/+$/,
    "",
  ),
  // Fallback map centre when the user's location is unknown (Nashik, where the sample data lives).
  defaultCenter: { lat: 20.0059, lng: 73.7897 },
  defaultZoom: 13,
} as const;
