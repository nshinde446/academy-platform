import { describe, it, expect, vi, beforeEach } from "vitest";
import { useUserStore } from "@/store/user-store";

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
    useUserStore.setState({ user: null });
    vi.clearAllMocks();
  });

  it("has null user initially", () => {
    expect(useUserStore.getState().user).toBeNull();
  });

  it("fetchUser sets user on success", async () => {
    mockGet.mockResolvedValueOnce({ data: mockUser });

    await useUserStore.getState().fetchUser();

    expect(mockGet).toHaveBeenCalledWith("/api/v1/auth/me");
    expect(useUserStore.getState().user).toEqual(mockUser);
  });

  it("fetchUser sets null on failure", async () => {
    useUserStore.setState({ user: mockUser });
    mockGet.mockRejectedValueOnce(new Error("Unauthorized"));

    await useUserStore.getState().fetchUser();

    expect(useUserStore.getState().user).toBeNull();
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
