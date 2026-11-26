// Mirrors the backend error envelope (backend/app/core/errors.py).
export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details: unknown;
    request_id: string | null;
  };
}

// Mirrors ServiceCategory (backend/app/models/service.py).
export type ServiceCategory = "hospital" | "atm" | "shop" | "other";

export interface LatLng {
  lat: number;
  lng: number;
}

// Mirrors ServiceRead / ServicePage (backend/app/schemas/service.py).
export interface Service {
  id: string;
  name: string;
  category: ServiceCategory;
  latitude: number;
  longitude: number;
  rating: string | null; // Decimal, serialised as a string
  metadata: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface ServicePage {
  items: Service[];
  page: number;
  page_size: number;
  total: number;
}

// Mirrors NearbyMarker / NearbyMarkers (backend/app/schemas/service.py).
export interface NearbyMarker extends Pick<
  Service,
  "id" | "name" | "category" | "rating" | "latitude" | "longitude"
> {
  distance_km: number;
}

export interface NearbyMarkers {
  items: NearbyMarker[];
}

// Mirrors AdminRead (backend/app/schemas/admin.py).
export interface Admin {
  id: string;
  email: string;
  is_active: boolean;
  created_at: string;
}

// Mirrors BulkUploadResult (backend/app/schemas/service.py).
export interface BulkUploadResult {
  total: number;
  inserted: number;
  failed: number;
  errors: { row: number; field: string | null; message: string }[];
}
