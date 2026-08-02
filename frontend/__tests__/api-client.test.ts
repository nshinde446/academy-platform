import { describe, it, expect, vi, beforeEach } from "vitest";
import axios from "axios";

vi.mock("axios", async () => {
  const interceptors = {
    request: { use: vi.fn() },
    response: { use: vi.fn() },
  };
  const instance = {
    get: vi.fn(),
    post: vi.fn(),
    interceptors,
  };
  return {
    default: {
      create: vi.fn(() => instance),
    },
  };
});

// jsdom's window.location is read-only; swap in a stub without an `any` cast.
function stubLocation(pathname: string) {
  delete (window as unknown as { location?: unknown }).location;
  (
    window as unknown as {
      location: { href: string; pathname: string; search: string };
    }
  ).location = { href: "", pathname, search: "" };
}

describe("apiClient", () => {
  let apiClient: any;
  let mockInstance: any;
  let responseInterceptorError: any;

  beforeEach(async () => {
    vi.clearAllMocks();
    vi.resetModules();

    const axiosMod = await import("axios");
    mockInstance = (axiosMod.default.create as any)();

    await import("@/services/api-client");

    const responseUseCalls = mockInstance.interceptors.response.use.mock.calls;
    if (responseUseCalls.length > 0) {
      responseInterceptorError = responseUseCalls[0][1];
    }
  });

  it("creates axios instance with correct config", async () => {
    const axiosMod = await import("axios");
    expect(axiosMod.default.create).toHaveBeenCalledWith({
      baseURL: "",
      withCredentials: true,
      headers: { "Content-Type": "application/json" },
    });
  });

  it("registers a response interceptor", () => {
    expect(mockInstance.interceptors.response.use).toHaveBeenCalled();
  });

  it("interceptor attempts refresh on 401", async () => {
    if (!responseInterceptorError) return;

    const originalRequest = { _retry: false, url: "/api/v1/some-endpoint" };
    const error = { response: { status: 401 }, config: originalRequest };

    mockInstance.post.mockResolvedValueOnce({});
    mockInstance.mockImplementation?.(() => Promise.resolve({ data: "retried" }));

    try {
      await responseInterceptorError(error);
    } catch {
      // may throw if mock instance isn't callable
    }

    expect(mockInstance.post).toHaveBeenCalledWith("/api/v1/auth/refresh");
    expect(originalRequest._retry).toBe(true);
  });

  it("interceptor redirects to login if refresh fails", async () => {
    if (!responseInterceptorError) return;

    delete (window as any).location;
    (window as any).location = { href: "", pathname: "/attendance", search: "" };

    const originalRequest = { _retry: false, url: "/api/v1/some-endpoint" };
    const error = { response: { status: 401 }, config: originalRequest };

    mockInstance.post.mockRejectedValueOnce(new Error("refresh failed"));

    try {
      await responseInterceptorError(error);
    } catch {
      // expected
    }

    // Redirects to /login and preserves where the user was.
    expect(window.location.href).toContain("/login");
    expect(window.location.href).toContain("redirect=");
  });

  it("does NOT recurse when the refresh endpoint itself 401s", async () => {
    if (!responseInterceptorError) return;

    stubLocation("/attendance");

    // A 401 whose own request is /auth/refresh must go straight to login,
    // never trigger another POST /auth/refresh (the infinite-loop bug).
    const error = {
      response: { status: 401 },
      config: { url: "/api/v1/auth/refresh" },
    };

    await expect(responseInterceptorError(error)).rejects.toEqual(error);
    expect(mockInstance.post).not.toHaveBeenCalledWith("/api/v1/auth/refresh");
    expect(window.location.href).toContain("/login");
  });

  it("does NOT redirect when already on the login page", async () => {
    if (!responseInterceptorError) return;

    stubLocation("/login");

    // A bad-password login 401 shouldn't bounce the login page to itself.
    const error = {
      response: { status: 401 },
      config: { url: "/api/v1/auth/login" },
    };

    await expect(responseInterceptorError(error)).rejects.toEqual(error);
    expect(window.location.href).toBe("");
  });

  it("interceptor rejects non-401 errors", async () => {
    if (!responseInterceptorError) return;

    const error = { response: { status: 500 }, config: {} };

    await expect(responseInterceptorError(error)).rejects.toEqual(error);
  });
});
