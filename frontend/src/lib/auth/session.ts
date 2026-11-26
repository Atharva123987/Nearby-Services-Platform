// Server-only: auth cookies for the admin area. Used by route handlers and src/proxy.ts.
// Tokens live in httpOnly cookies so page JavaScript (and any XSS) can never read them.
import type { NextResponse } from "next/server";
import { config } from "@/lib/config";

export const ACCESS_COOKIE = "fg_access";
export const REFRESH_COOKIE = "fg_refresh";
// Matches the backend default JWT_REFRESH_TOKEN_EXPIRE_DAYS; the backend still enforces the real expiry.
const REFRESH_MAX_AGE_SECONDS = 7 * 24 * 60 * 60;

// Mirrors TokenResponse (backend/app/schemas/auth.py).
export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
  expires_in: number;
}

// Server-to-server base URL. In Docker the browser's URL (localhost) is not the api container.
export const backendUrl = (
  process.env.API_INTERNAL_URL ?? config.apiUrl
).replace(/\/+$/, "");

export function setAuthCookies(response: NextResponse, tokens: TokenResponse) {
  const options = {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
  } as const;
  // Expire the cookie a little before the token so we never send an expired one.
  response.cookies.set(ACCESS_COOKIE, tokens.access_token, {
    ...options,
    maxAge: Math.max(tokens.expires_in - 30, 1),
  });
  response.cookies.set(REFRESH_COOKIE, tokens.refresh_token, {
    ...options,
    maxAge: REFRESH_MAX_AGE_SECONDS,
  });
}

export function clearAuthCookies(response: NextResponse) {
  response.cookies.delete(ACCESS_COOKIE);
  response.cookies.delete(REFRESH_COOKIE);
}

/** New token pair for a refresh token, or null if it is invalid/expired or the API is down. */
export async function refreshTokens(
  refreshToken: string,
): Promise<TokenResponse | null> {
  try {
    const response = await fetch(`${backendUrl}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
      cache: "no-store",
    });
    return response.ok ? ((await response.json()) as TokenResponse) : null;
  } catch {
    return null;
  }
}
