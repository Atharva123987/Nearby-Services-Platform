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
