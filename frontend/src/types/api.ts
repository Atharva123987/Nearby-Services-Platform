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
