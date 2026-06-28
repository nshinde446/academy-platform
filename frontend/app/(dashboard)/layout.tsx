"use client";

import { useEffect } from "react";
import { Header } from "@/components/layout/header";
import { Sidebar } from "@/components/layout/sidebar";
import { Toast, Toaster } from "@/components/ui/toast";
import { useUserStore } from "@/store/user-store";
import type { ReactNode } from "react";

export default function DashboardLayout({ children }: { children: ReactNode }) {
  const user = useUserStore((s) => s.user);
  const fetchUser = useUserStore((s) => s.fetchUser);

  useEffect(() => {
    if (!user) fetchUser();
  }, [user, fetchUser]);

  return (
    <Toast.Provider>
      <div className="flex h-screen">
        {/* Sidebar runs the full height on the left, brand mark up top. */}
        <Sidebar />
        {/* Right column: header on top of scrollable main. */}
        <div className="flex min-w-0 flex-1 flex-col">
          <Header />
          <main className="flex-1 overflow-y-auto px-8 py-6">{children}</main>
        </div>
      </div>
      <Toaster />
    </Toast.Provider>
  );
}
