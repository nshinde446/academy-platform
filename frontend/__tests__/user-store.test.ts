import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook } from "@testing-library/react";
import { useUserStore, useBranchId } from "@/store/user-store";

const mockGet = vi.fn();

vi.mock("@/services/api-client", () => ({
  default: { get: (...args: any[]) => mockGet(...args) },
}));

const mockUser = {
  id: "user-1",
  email: "admin@test.com",
  first_name: "Admin",
  last_name: "User",
  status: "active",
  roles: ["super_admin"],
  permissions: ["manage_users"],
  branch_roles: [
    { branch_id: "b1", branch_name: "Main", branch_code: "MAIN", role_name: "branch_admin" },
  ],
};

describe("useUserStore", () => {
  beforeEach(() => {
    useUserStore.setState({ user: null, status: "loading" });
    vi.clearAllMocks();
  });

  it("has null user initially", () => {
    expect(useUserStore.getState().user).toBeNull();
  });

  it("fetchUser sets user + ready status on success", async () => {
    mockGet.mockResolvedValueOnce({ data: mockUser });

    await useUserStore.getState().fetchUser();

    expect(mockGet).toHaveBeenCalledWith("/api/v1/auth/me");
    expect(useUserStore.getState().user).toEqual(mockUser);
    expect(useUserStore.getState().status).toBe("ready");
  });

  it("fetchUser sets null + error status on failure", async () => {
    useUserStore.setState({ user: mockUser });
    mockGet.mockRejectedValueOnce(new Error("Unauthorized"));

    await useUserStore.getState().fetchUser();

    expect(useUserStore.getState().user).toBeNull();
    expect(useUserStore.getState().status).toBe("error");
  });

  it("setUser updates user", () => {
    useUserStore.getState().setUser(mockUser);
    expect(useUserStore.getState().user).toEqual(mockUser);
  });

  it("clearUser resets to null", () => {
    useUserStore.setState({ user: mockUser });
    useUserStore.getState().clearUser();
    expect(useUserStore.getState().user).toBeNull();
  });
});

describe("useBranchId", () => {
  beforeEach(() => {
    useUserStore.setState({ user: null, status: "loading" });
  });

  it("is resolving with no branch on first paint (status loading)", () => {
    const { result } = renderHook(() => useBranchId());
    expect(result.current.isResolving).toBe(true);
    expect(result.current.branchId).toBeUndefined();
  });

  it("resolves the first branch role once the user is ready", () => {
    useUserStore.setState({ user: mockUser, status: "ready" });
    const { result } = renderHook(() => useBranchId());
    expect(result.current.isResolving).toBe(false);
    expect(result.current.branchId).toBe("b1");
  });

  it("is not resolving but has no branch when the user genuinely lacks one", () => {
    useUserStore.setState({
      user: { ...mockUser, branch_roles: [] },
      status: "ready",
    });
    const { result } = renderHook(() => useBranchId());
    expect(result.current.isResolving).toBe(false);
    expect(result.current.branchId).toBeUndefined();
  });
});
