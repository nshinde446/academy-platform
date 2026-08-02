import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";

const apiClient = axios.create({
  baseURL: "",
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
});

// A 401 from these endpoints is terminal, not "access token expired" — never
// try to refresh-and-retry them, or a stale refresh token makes the interceptor
// call /refresh in an endless recursion (the original request never settles,
// the page hangs on its error boundary, and the bad cookie is never cleared).
const AUTH_PATHS = ["/api/v1/auth/refresh", "/api/v1/auth/login"];

function isAuthPath(url?: string): boolean {
  return !!url && AUTH_PATHS.some((p) => url.includes(p));
}

// Single-flight: when the access token expires, every in-flight query 401s at
// once. Without this they'd all stampede /refresh; instead they await one.
let refreshPromise: Promise<void> | null = null;

function refreshSession(): Promise<void> {
  if (!refreshPromise) {
    refreshPromise = apiClient
      .post("/api/v1/auth/refresh")
      .then(() => undefined)
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

function redirectToLogin(): void {
  if (typeof window === "undefined") return;
  const pathname = window.location.pathname || "/";
  if (pathname.startsWith("/login")) return; // already there — don't loop
  const target = encodeURIComponent(pathname + (window.location.search || ""));
  window.location.href = `/login?redirect=${target}`;
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as
      | (InternalAxiosRequestConfig & { _retry?: boolean })
      | undefined;

    if (error.response?.status === 401) {
      // Session is genuinely gone (refresh/login itself failed): sign out
      // cleanly to /login instead of recursing into another refresh.
      if (isAuthPath(original?.url)) {
        redirectToLogin();
        return Promise.reject(error);
      }
      // Access token expired: refresh once, then replay the original request.
      if (original && !original._retry) {
        original._retry = true;
        try {
          await refreshSession();
          return apiClient(original);
        } catch {
          redirectToLogin();
        }
      }
    }

    return Promise.reject(error);
  },
);

export default apiClient;
