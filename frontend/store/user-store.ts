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

interface UserState {
  user: User | null;
  fetchUser: () => Promise<void>;
  setUser: (user: User | null) => void;
  clearUser: () => void;
}

export const useUserStore = create<UserState>((set) => ({
  user: null,
  fetchUser: async () => {
    try {
      const res = await apiClient.get("/api/v1/auth/me");
      set({ user: res.data });
    } catch {
      set({ user: null });
    }
  },
  setUser: (user) => set({ user }),
  clearUser: () => set({ user: null }),
}));
