"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  CalendarDays,
  CalendarOff,
  KeyRound,
  LayoutDashboard,
  LogOut,
  UserRound,
} from "lucide-react";
import type { ComponentType } from "react";
import { useUserStore } from "@/store/user-store";
import { useAuthStore } from "@/store/auth-store";

interface PortalNavItem {
  label: string;
  href: string;
  icon: ComponentType<{ className?: string }>;
}

// The teacher self-service sections. Overview is today's attendance + lectures;
// the rest land in later slices (placeholders for now) but the nav is stable so
// the shell reads as a complete portal.
const NAV: PortalNavItem[] = [
  { label: "Overview", href: "/my-day", icon: LayoutDashboard },
  { label: "Attendance", href: "/my-day/attendance", icon: CalendarDays },
  { label: "Productivity", href: "/my-day/productivity", icon: BarChart3 },
  { label: "Leave", href: "/my-day/leave", icon: CalendarOff },
  { label: "Profile", href: "/my-day/profile", icon: UserRound },
];

function isActive(pathname: string, href: string): boolean {
  if (href === "/my-day") return pathname === "/my-day";
  return pathname === href || pathname.startsWith(href + "/");
}

export function PortalSidebar({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname() ?? "";
  const user = useUserStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);

  const initials =
    user?.first_name && user?.last_name
      ? `${user.first_name[0]}${user.last_name[0]}`.toUpperCase()
      : "T";
  const fullName = user
    ? `${user.first_name ?? ""} ${user.last_name ?? ""}`.trim() || "Teacher"
    : "Teacher";

  return (
    <aside className="flex h-full w-60 shrink-0 flex-col border-r bg-sidebar">
      {/* Brand */}
      <div className="flex h-14 items-center gap-2.5 border-b px-4">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/logo.svg" alt="" className="h-7 w-7 shrink-0" aria-hidden />
        <div className="flex min-w-0 flex-col leading-tight">
          <span className="truncate text-[13px] font-semibold">
            Matrix Science Academy
          </span>
          <span className="truncate text-[9.5px] font-semibold uppercase tracking-[0.06em] text-brand-gold">
            Teacher Portal
          </span>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex flex-1 flex-col gap-0.5 overflow-y-auto p-2">
        {NAV.map((item) => {
          const active = isActive(pathname, item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onNavigate}
              className={`relative flex items-center gap-2.5 rounded-md px-2.5 py-2 text-[13px] transition-colors ${
                active
                  ? "bg-muted font-medium text-foreground"
                  : "text-foreground hover:bg-muted"
              }`}
            >
              {active && (
                <span
                  aria-hidden
                  className="absolute -left-1 top-1/2 h-3.5 w-[2px] -translate-y-1/2 rounded-sm bg-primary"
                />
              )}
              <Icon className="h-4 w-4 shrink-0 text-muted-foreground" />
              <span className="truncate">{item.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Footer: who + account actions */}
      <div className="flex flex-col gap-2 border-t px-3 py-2.5">
        <div className="flex items-center gap-2.5">
          <div className="grid h-7 w-7 shrink-0 place-items-center rounded-full border bg-muted text-[11px] font-semibold text-foreground">
            {initials}
          </div>
          <div className="flex min-w-0 flex-1 flex-col leading-tight">
            <span className="truncate text-[12.5px] font-medium">{fullName}</span>
            <span className="truncate text-[11px] text-muted-foreground">
              {user?.roles?.includes("teacher_portal") ? "Teacher" : "Signed in"}
            </span>
          </div>
        </div>
        <div className="flex gap-1.5">
          <Link
            href="/change-password"
            onClick={onNavigate}
            className="flex flex-1 items-center justify-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-[12.5px] font-medium text-foreground transition-colors hover:bg-muted"
            title="Change password"
          >
            <KeyRound className="h-3.5 w-3.5" aria-hidden />
            Password
          </Link>
          <button
            onClick={logout}
            className="flex flex-1 items-center justify-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-[12.5px] font-medium text-foreground transition-colors hover:bg-muted"
            title="Sign out"
          >
            <LogOut className="h-3.5 w-3.5" aria-hidden />
            Sign out
          </button>
        </div>
      </div>
    </aside>
  );
}
