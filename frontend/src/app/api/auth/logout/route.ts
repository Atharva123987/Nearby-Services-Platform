import { NextResponse } from "next/server";
import { clearAuthCookies } from "@/lib/auth/session";

// Tokens are stateless JWTs (no server-side revocation), so logout = drop the cookies.
export function POST() {
  const response = NextResponse.json({ ok: true });
  clearAuthCookies(response);
  return response;
}
