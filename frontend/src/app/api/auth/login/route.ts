import { NextResponse, type NextRequest } from "next/server";
import {
  backendUrl,
  setAuthCookies,
  type TokenResponse,
} from "@/lib/auth/session";

// Headers worth passing back to the browser (429 lockout timing, request correlation).
const PASSTHROUGH_HEADERS = ["Retry-After", "X-Request-ID"];

export async function POST(request: NextRequest) {
  let upstream: Response;
  try {
    upstream = await fetch(`${backendUrl}/api/v1/auth/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        // Honoured by the backend only if this server is in TRUSTED_PROXIES.
        ...(request.headers.has("x-forwarded-for") && {
          "X-Forwarded-For": request.headers.get("x-forwarded-for")!,
        }),
      },
      body: await request.text(),
      cache: "no-store",
    });
  } catch {
    return NextResponse.json(
      {
        error: {
          code: "bad_gateway",
          message: "Could not reach the API",
          details: null,
          request_id: null,
        },
      },
      { status: 502 },
    );
  }

  const body: unknown = await upstream.json().catch(() => null);
  if (!upstream.ok) {
    const headers = new Headers();
    for (const name of PASSTHROUGH_HEADERS) {
      const value = upstream.headers.get(name);
      if (value) headers.set(name, value);
    }
    return NextResponse.json(body, { status: upstream.status, headers });
  }

  const response = NextResponse.json({ ok: true });
  setAuthCookies(response, body as TokenResponse);
  return response;
}
