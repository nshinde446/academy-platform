import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PUBLIC_PATHS = ["/login"];

// Read a JWT's `exp` (seconds since epoch) without verifying its signature —
// the proxy only needs to know whether a token is still within its lifetime.
// Runtime-safe: prefers atob (edge) and falls back to Buffer (node).
function jwtExp(token: string | undefined): number | null {
  if (!token) return null;
  try {
    const part = token.split(".")[1];
    if (!part) return null;
    const b64 = part.replace(/-/g, "+").replace(/_/g, "/");
    const json =
      typeof atob === "function"
        ? atob(b64)
        : Buffer.from(b64, "base64").toString("binary");
    const payload = JSON.parse(json) as { exp?: number };
    return typeof payload.exp === "number" ? payload.exp : null;
  } catch {
    return null;
  }
}

// A token counts as live if it has no readable exp (fail-open: don't lock users
// out over a decode quirk) or its exp is in the future. An EXPIRED token does
// not — so a stale refresh cookie no longer masquerades as a session.
function tokenLive(token: string | undefined): boolean {
  const exp = jwtExp(token);
  return exp === null ? Boolean(token) : exp * 1000 > Date.now();
}

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  // A live session = a still-valid access token OR a still-valid refresh token.
  // The access token expires hourly; the api-client mints a fresh one on the
  // next API call via the refresh token, so gating on access_token alone would
  // bounce authenticated users the instant it expired. But an EXPIRED refresh
  // token must NOT count — otherwise the dashboard shell loads on a dead
  // session, every query 401s, and the user is stuck (had to hand-delete the
  // cookie). Checking exp here sends them straight to /login instead.
  const hasSession =
    tokenLive(request.cookies.get("access_token")?.value) ||
    tokenLive(request.cookies.get("refresh_token")?.value);

  const isPublic = PUBLIC_PATHS.some((p) => pathname.startsWith(p));

  if (!hasSession && !isPublic) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("redirect", pathname);
    return NextResponse.redirect(loginUrl);
  }

  if (hasSession && pathname === "/login") {
    return NextResponse.redirect(new URL("/home", request.url));
  }

  return NextResponse.next();
}

export const config = {
  // `iclock` is excluded alongside `api`: biometric devices push to /iclock/*
  // and authenticate by device serial at the backend, not a web session — the
  // proxy must NOT bounce them to /login (it runs before next.config rewrites).
  matcher: [
    "/((?!api|iclock|_next/static|_next/image|favicon.ico|sitemap.xml|robots.txt).*)",
  ],
};
