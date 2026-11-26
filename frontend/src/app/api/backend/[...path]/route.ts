// Authenticated pass-through: /api/backend/<path> -> API /api/v1/<path> with the access token
// from the httpOnly cookie as a Bearer header. On a 401 it refreshes once and retries.
import { NextResponse, type NextRequest } from "next/server";
import {
  ACCESS_COOKIE,
  REFRESH_COOKIE,
  backendUrl,
  clearAuthCookies,
  refreshTokens,
  setAuthCookies,
  type TokenResponse,
} from "@/lib/auth/session";

type Context = { params: Promise<{ path: string[] }> };

async function forward(request: NextRequest, { params }: Context) {
  const { path } = await params;
  const url = `${backendUrl}/api/v1/${path.join("/")}${request.nextUrl.search}`;
  const body = ["GET", "HEAD"].includes(request.method)
    ? undefined
    : await request.arrayBuffer();

  const send = (token: string | undefined) => {
    const headers = new Headers({ Accept: "application/json" });
    const contentType = request.headers.get("content-type");
    if (contentType) headers.set("Content-Type", contentType);
    if (token) headers.set("Authorization", `Bearer ${token}`);
    return fetch(url, {
      method: request.method,
      headers,
      body,
      cache: "no-store",
    });
  };

  let refreshed: TokenResponse | null = null;
  let upstream = await send(request.cookies.get(ACCESS_COOKIE)?.value);
  if (upstream.status === 401) {
    const refreshToken = request.cookies.get(REFRESH_COOKIE)?.value;
    refreshed = refreshToken ? await refreshTokens(refreshToken) : null;
    if (refreshed) upstream = await send(refreshed.access_token);
  }

  const headers = new Headers();
  for (const name of [
    "Content-Type",
    "Content-Disposition",
    "Retry-After",
    "X-Request-ID",
  ]) {
    const value = upstream.headers.get(name);
    if (value) headers.set(name, value);
  }
  const response = new NextResponse(upstream.body, {
    status: upstream.status,
    headers,
  });
  if (refreshed) setAuthCookies(response, refreshed);
  else if (upstream.status === 401) clearAuthCookies(response);
  return response;
}

export {
  forward as GET,
  forward as POST,
  forward as PUT,
  forward as PATCH,
  forward as DELETE,
};
