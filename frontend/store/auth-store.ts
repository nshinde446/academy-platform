import { create } from "zustand";
import apiClient from "@/services/api-client";

interface AuthState {
  isAuthenticated: boolean;
  isLoading: boolean;
  setAuthenticated: (value: boolean) => void;
  setLoading: (value: boolean) => void;
  checkAuth: () => Promise<void>;
  logout: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  isAuthenticated: false,
  isLoading: true,
  setAuthenticated: (value) => set({ isAuthenticated: value }),
  setLoading: (value) => set({ isLoading: value }),
  checkAuth: async () => {
    try {
      await apiClient.get("/api/v1/auth/me");
      set({ isAuthenticated: true, isLoading: false });
    } catch {
      set({ isAuthenticated: false, isLoading: false });
    }
  },
  logout: async () => {
    try {
      await apiClient.post("/api/v1/auth/logout");
    } catch {
      // proceed with local logout regardless
    }
    set({ isAuthenticated: false });
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
  },
}));
