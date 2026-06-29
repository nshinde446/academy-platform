import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PUBLIC_PATHS = ["/login"];

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  // A live session = either a valid access token OR a refresh token.
  // The access token expires hourly; the api-client mints a fresh one
  // on the next API call. Gating on access_token alone bounced
  // authenticated users to /login the instant it expired, even though
  // their session was still valid via the refresh token.
  const hasSession = Boolean(
    request.cookies.get("access_token")?.value ||
      request.cookies.get("refresh_token")?.value,
  );

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
