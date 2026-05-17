import { describe, it, expect, vi, beforeEach } from "vitest";
import { useAuthStore } from "@/store/auth-store";

const mockGet = vi.fn();
const mockPost = vi.fn();

vi.mock("@/services/api-client", () => ({
  default: { get: (...args: any[]) => mockGet(...args), post: (...args: any[]) => mockPost(...args) },
}));

describe("useAuthStore", () => {
  beforeEach(() => {
    useAuthStore.setState({ isAuthenticated: false, isLoading: true });
    vi.clearAllMocks();
  });

  it("has correct initial state", () => {
    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(false);
    expect(state.isLoading).toBe(true);
  });

  it("setAuthenticated updates state", () => {
    useAuthStore.getState().setAuthenticated(true);
    expect(useAuthStore.getState().isAuthenticated).toBe(true);

    useAuthStore.getState().setAuthenticated(false);
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });

  it("setLoading updates state", () => {
    useAuthStore.getState().setLoading(false);
    expect(useAuthStore.getState().isLoading).toBe(false);
  });

  it("checkAuth sets authenticated on success", async () => {
    mockGet.mockResolvedValueOnce({ data: { id: "1", email: "test@test.com" } });

    await useAuthStore.getState().checkAuth();

    expect(mockGet).toHaveBeenCalledWith("/api/v1/auth/me");
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
    expect(useAuthStore.getState().isLoading).toBe(false);
  });

  it("checkAuth sets unauthenticated on failure", async () => {
    mockGet.mockRejectedValueOnce(new Error("Unauthorized"));

    await useAuthStore.getState().checkAuth();

    expect(useAuthStore.getState().isAuthenticated).toBe(false);
    expect(useAuthStore.getState().isLoading).toBe(false);
  });

  it("logout calls API and resets state", async () => {
    useAuthStore.setState({ isAuthenticated: true });
    mockPost.mockResolvedValueOnce({});

    delete (window as any).location;
    (window as any).location = { href: "" };

    await useAuthStore.getState().logout();

    expect(mockPost).toHaveBeenCalledWith("/api/v1/auth/logout");
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
    expect(window.location.href).toBe("/login");
  });

  it("logout resets state even if API fails", async () => {
    useAuthStore.setState({ isAuthenticated: true });
    mockPost.mockRejectedValueOnce(new Error("Network error"));

    delete (window as any).location;
    (window as any).location = { href: "" };

    await useAuthStore.getState().logout();

    expect(useAuthStore.getState().isAuthenticated).toBe(false);
    expect(window.location.href).toBe("/login");
  });
});
