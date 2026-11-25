import { config } from "@/lib/config";
import type { ApiErrorBody } from "@/types/api";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly details: unknown = null,
    readonly requestId: string | null = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function isErrorBody(value: unknown): value is ApiErrorBody {
  return (
    typeof value === "object" &&
    value !== null &&
    "error" in value &&
    typeof (value as ApiErrorBody).error?.code === "string"
  );
}

/** All HTTP to the backend goes through here; non-2xx responses become `ApiError`. */
export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${config.apiUrl}${path}`, {
      ...init,
      headers: { Accept: "application/json", ...init?.headers },
    });
  } catch (cause) {
    throw new ApiError(0, "network_error", "Could not reach the server", cause);
  }

  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const requestId = response.headers.get("X-Request-ID");
    if (isErrorBody(body)) {
      const { code, message, details, request_id } = body.error;
      throw new ApiError(
        response.status,
        code,
        message,
        details,
        request_id ?? requestId,
      );
    }
    throw new ApiError(
      response.status,
      "http_error",
      response.statusText,
      body,
      requestId,
    );
  }
  return body as T;
}
