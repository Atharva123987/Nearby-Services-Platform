// Mirrors the backend error envelope (backend/app/core/errors.py).
export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details: unknown;
    request_id: string | null;
  };
}
