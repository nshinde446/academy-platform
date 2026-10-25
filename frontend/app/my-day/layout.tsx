"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Menu, X } from "lucide-react";
import type { ReactNode } from "react";
import { PortalSidebar } from "@/components/layout/portal-sidebar";
import { Toast, Toaster } from "@/components/ui/toast";
import { useUserStore } from "@/store/user-store";

// The teacher self-service portal shell. Desktop/laptop gets a fixed left
// sidebar + a wide content column; narrow screens collapse the sidebar into a
// slide-in drawer behind a top bar — responsive, not mobile-only.
export default function PortalLayout({ children }: { children: ReactNode }) {
  const user = useUserStore((s) => s.user);
  const fetchUser = useUserStore((s) => s.fetchUser);
  const router = useRouter();
  const [drawerOpen, setDrawerOpen] = useState(false);

  useEffect(() => {
    if (!user) fetchUser();
  }, [user, fetchUser]);

  // A pending forced password change wins over everything.
  useEffect(() => {
    if (user?.must_change_password) router.replace("/change-password");
  }, [user, router]);

  if (user?.must_change_password) return null; // redirecting

  return (
    <Toast.Provider>
      <div className="flex h-screen bg-background">
        {/* Desktop sidebar — fixed left column, full height. */}
        <div className="hidden md:block">
          <PortalSidebar />
        </div>

        {/* Mobile drawer + scrim. */}
        {drawerOpen && (
          <div className="fixed inset-0 z-40 md:hidden">
            <button
              aria-label="Close menu"
              className="absolute inset-0 bg-black/40"
              onClick={() => setDrawerOpen(false)}
            />
            <div className="absolute left-0 top-0 h-full">
              <PortalSidebar onNavigate={() => setDrawerOpen(false)} />
            </div>
          </div>
        )}

        {/* Right column */}
        <div className="flex min-w-0 flex-1 flex-col">
          {/* Mobile top bar — only below md, where the sidebar is hidden. */}
          <div className="flex h-14 shrink-0 items-center gap-3 border-b px-4 md:hidden">
            <button
              aria-label="Open menu"
              onClick={() => setDrawerOpen(true)}
              className="grid h-9 w-9 place-items-center rounded-md border border-border hover:bg-muted"
            >
              {drawerOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
            </button>
            <span className="text-[13px] font-semibold">Teacher Portal</span>
          </div>

          <main className="flex-1 overflow-y-auto px-4 py-6 md:px-8">
            {/* Content is capped so a wide monitor doesn't stretch cards edge to
                edge, while still using the laptop/desktop real estate. */}
            <div className="mx-auto w-full max-w-5xl">{children}</div>
          </main>
        </div>
      </div>
      <Toaster />
    </Toast.Provider>
  );
}
