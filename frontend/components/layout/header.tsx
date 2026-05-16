"use client";

import { useUserStore } from "@/store/user-store";

export function Header() {
  const user = useUserStore((s) => s.user);

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b bg-background px-6">
      <h1 className="text-lg font-semibold">Academy Platform</h1>
      <div className="flex items-center gap-4">
        {user ? (
          <span className="text-sm text-muted-foreground">
            {user.first_name} {user.last_name} ({user.roles.join(", ")})
          </span>
        ) : (
          <span className="text-sm text-muted-foreground">Not signed in</span>
        )}
      </div>
    </header>
  );
}
