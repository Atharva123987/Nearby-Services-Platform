// Next 16's `proxy` (formerly `middleware.ts`): guards /admin/*.
import { NextResponse, type NextRequest } from "next/server";
import { ADMIN_LOGIN, loginUrl, safeReturnUrl } from "@/lib/auth/return-url";
import {
  ACCESS_COOKIE,
  REFRESH_COOKIE,
  clearAuthCookies,
  refreshTokens,
  setAuthCookies,
} from "@/lib/auth/session";

export async function proxy(request: NextRequest) {
  const { pathname, search, searchParams } = request.nextUrl;
  const onLogin = pathname === ADMIN_LOGIN;
  // Signed-in users visiting the login page go where they were headed.
  const signedIn = () =>
    onLogin
      ? NextResponse.redirect(
          new URL(safeReturnUrl(searchParams.get("next")), request.url),
        )
      : NextResponse.next();

  // The access cookie expires with its token, so its presence means "probably valid";
  // the API still verifies every request.
  if (request.cookies.has(ACCESS_COOKIE)) return signedIn();

  // Access token expired mid-session: refresh silently.
  const refreshToken = request.cookies.get(REFRESH_COOKIE)?.value;
  const tokens = refreshToken ? await refreshTokens(refreshToken) : null;
  if (tokens) {
    const response = signedIn();
    setAuthCookies(response, tokens);
    return response;
  }

  const response = onLogin
    ? NextResponse.next()
    : NextResponse.redirect(new URL(loginUrl(pathname + search), request.url));
  if (refreshToken) clearAuthCookies(response);
  return response;
}

export const config = {
  matcher: ["/admin", "/admin/:path*"],
};
