"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { KeyRound, LogIn, LogOut } from "lucide-react";
import { useUserStore } from "@/store/user-store";
import { useAuthStore } from "@/store/auth-store";
import { ChangePasswordDialog } from "@/components/layout/change-password-dialog";

interface NavItem {
  label: string;
  href: string;
  isNew?: boolean;
  badge?: number;
}

interface NavSection {
  // Empty string means no label — used for the top, primary section.
  label: string;
  items: NavItem[];
}

const SECTIONS: NavSection[] = [
  {
    label: "",
    items: [
      { label: "Home", href: "/home" },
      { label: "Today", href: "/today" },
      { label: "Students", href: "/students" },
      { label: "Teachers", href: "/teachers" },
      { label: "Lectures", href: "/lectures" },
      { label: "Attendance", href: "/attendance" },
      { label: "Insights", href: "/insights" },
    ],
  },
  {
    label: "Content",
    items: [
      { label: "Materials", href: "/materials" },
      { label: "Question Bank", href: "/question-bank" },
      { label: "Papers", href: "/papers", isNew: true },
    ],
  },
  {
    label: "Academics",
    items: [
      { label: "Courses", href: "/courses" },
      { label: "Batches", href: "/batches" },
      { label: "Classrooms", href: "/classrooms" },
      { label: "Academic Years", href: "/academic-years" },
      { label: "Syllabus", href: "/syllabus" },
    ],
  },
];

function NavLink({ item, active }: { item: NavItem; active: boolean }) {
  return (
    <Link
      href={item.href}
      className={`relative flex items-center justify-between gap-2 rounded-md px-2.5 py-1.5 text-[13px] transition-colors ${
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
      <span className="truncate">{item.label}</span>
      {item.isNew && (
        <span className="rounded border border-border px-1.5 text-[9.5px] font-medium uppercase tracking-wide text-muted-foreground">
          NEW
        </span>
      )}
      {item.badge != null && (
        <span className="min-w-[18px] rounded-full bg-primary px-1.5 text-center text-[10px] font-semibold leading-[1.4] text-primary-foreground">
          {item.badge}
        </span>
      )}
    </Link>
  );
}

const ADMIN_ROLES = ["super_admin", "branch_admin"];

// Only branch/super admins manage staff accounts.
const ADMIN_SECTION: NavSection = {
  label: "Administration",
  items: [
    { label: "Users", href: "/users" },
    { label: "Access Control", href: "/access-control" },
    { label: "Accounts", href: "/accounts" },
    { label: "Audit Log", href: "/audit-log" },
    { label: "WhatsApp Log", href: "/whatsapp-log" },
    { label: "Settings", href: "/settings" },
  ],
};

export function Sidebar() {
  const pathname = usePathname() ?? "";
  const user = useUserStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const [changePwOpen, setChangePwOpen] = useState(false);

  const isAdmin = (user?.roles ?? []).some((r) => ADMIN_ROLES.includes(r));
  const sections = isAdmin ? [...SECTIONS, ADMIN_SECTION] : SECTIONS;

  const initials =
    user?.first_name && user?.last_name
      ? `${user.first_name[0]}${user.last_name[0]}`.toUpperCase()
      : "AP";
  const fullName = user
    ? `${user.first_name ?? ""} ${user.last_name ?? ""}`.trim() || "Signed in"
    : "Not signed in";
  const roleLabel = user?.roles?.join(", ") ?? "—";

  return (
    <aside className="flex w-60 shrink-0 flex-col border-r bg-sidebar">
      {/* Brand — Matrix Science Academy */}
      <div className="flex h-14 items-center gap-2.5 border-b px-4">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/logo.svg" alt="" className="h-7 w-7 shrink-0" aria-hidden />
        <div className="flex min-w-0 flex-col leading-tight">
          <span className="truncate text-[13px] font-semibold">
            Matrix Science Academy
          </span>
          <span className="truncate text-[9.5px] font-semibold uppercase tracking-[0.06em] text-brand-gold">
            JEE · NEET · MHT-CET
          </span>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto p-2">
        {sections.map((section) => (
          <div key={section.label || "top"} className="flex flex-col gap-0.5">
            {section.label ? (
              <div className="px-3 pb-1 pt-3.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                {section.label}
              </div>
            ) : null}
            {section.items.map((item) => (
              <NavLink
                key={item.href}
                item={item}
                active={
                  pathname === item.href ||
                  pathname.startsWith(item.href + "/")
                }
              />
            ))}
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div className="flex flex-col gap-2 border-t px-3 py-2.5">
        <div className="flex items-center gap-2.5">
          <div className="grid h-7 w-7 shrink-0 place-items-center rounded-full border bg-muted text-[11px] font-semibold text-foreground">
            {initials}
          </div>
          <div className="flex min-w-0 flex-1 flex-col leading-tight">
            <span className="truncate text-[12.5px] font-medium">{fullName}</span>
            <span className="truncate text-[11px] text-muted-foreground">
              {roleLabel}
            </span>
          </div>
        </div>
        {user ? (
          <div className="flex gap-1.5">
            <button
              onClick={() => setChangePwOpen(true)}
              className="flex flex-1 items-center justify-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-[12.5px] font-medium text-foreground transition-colors hover:bg-muted"
              title="Change password"
            >
              <KeyRound className="h-3.5 w-3.5" aria-hidden />
              Password
            </button>
            <button
              onClick={logout}
              className="flex flex-1 items-center justify-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-[12.5px] font-medium text-foreground transition-colors hover:bg-muted"
              title="Sign out"
            >
              <LogOut className="h-3.5 w-3.5" aria-hidden />
              Sign out
            </button>
          </div>
        ) : (
          <Link
            href="/login"
            className="flex items-center justify-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-[12.5px] font-medium text-foreground transition-colors hover:bg-muted"
          >
            <LogIn className="h-3.5 w-3.5" aria-hidden />
            Sign in
          </Link>
        )}
      </div>
      <ChangePasswordDialog open={changePwOpen} onOpenChange={setChangePwOpen} />
    </aside>
  );
}
