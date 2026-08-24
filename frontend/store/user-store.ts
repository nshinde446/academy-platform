import { create } from "zustand";
import apiClient from "@/services/api-client";

interface BranchRole {
  branch_id: string;
  branch_name: string;
  branch_code: string;
  role_name: string;
}

interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  status: string;
  roles: string[];
  permissions: string[];
  branch_roles: BranchRole[];
}

// Whether the current user (and therefore the active branch) is known yet.
// Starts "loading" so branch-gated pages treat the very first paint as
// "still resolving" rather than "no branch" — see useBranchId below.
type UserStatus = "loading" | "ready" | "error";

interface UserState {
  user: User | null;
  status: UserStatus;
  fetchUser: () => Promise<void>;
  setUser: (user: User | null) => void;
  clearUser: () => void;
}

export const useUserStore = create<UserState>((set) => ({
  user: null,
  status: "loading",
  fetchUser: async () => {
    set({ status: "loading" });
    try {
      const res = await apiClient.get("/api/v1/auth/me");
      set({ user: res.data, status: "ready" });
    } catch {
      set({ user: null, status: "error" });
    }
  },
  setUser: (user) => set({ user, status: "ready" }),
  clearUser: () => set({ user: null, status: "ready" }),
}));

// Shared active-branch resolution. Every branch-scoped page derives its
// branch from the user's first branch role; `isResolving` stays true until
// /auth/me has settled so those pages can render a loading state instead of
// flashing an empty "No branch selected" / 0-0 console on first paint — the
// window before the user is known.
export function useBranchId(): {
  branchId: string | undefined;
  isResolving: boolean;
} {
  const user = useUserStore((s) => s.user);
  const status = useUserStore((s) => s.status);
  return {
    branchId: user?.branch_roles?.[0]?.branch_id,
    isResolving: status === "loading",
  };
}

// Manager = the full-access roles (super_admin / branch_admin). Used to gate
// Manager-only UI controls (Delete, manual attendance mark) so non-Managers
// don't hit dead-end 403s. The server remains the source of truth.
const MANAGER_ROLES = ["super_admin", "branch_admin"];

export function useRoles(): {
  roles: string[];
  hasRole: (role: string) => boolean;
  isManager: boolean;
} {
  const user = useUserStore((s) => s.user);
  const roles = user?.roles ?? [];
  return {
    roles,
    hasRole: (role: string) => roles.includes(role),
    isManager: roles.some((r) => MANAGER_ROLES.includes(r)),
  };
}
