"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useUserStore } from "@/store/user-store";
import { useAuthStore } from "@/store/auth-store";

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
      { label: "Insights", href: "/insights" },
    ],
  },
  {
    label: "Content",
    items: [
      { label: "Materials", href: "/materials", isNew: true },
      { label: "Question Bank", href: "/question-bank" },
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

export function Sidebar() {
  const pathname = usePathname() ?? "";
  const user = useUserStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);

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
      {/* Brand */}
      <div className="flex h-14 items-center gap-2.5 border-b px-4">
        <div
          className="grid h-7 w-7 place-items-center rounded-md bg-primary text-[12px] font-bold tracking-wider text-primary-foreground"
          aria-hidden
        >
          A
        </div>
        <div className="flex min-w-0 flex-col leading-tight">
          <span className="truncate text-[13.5px] font-semibold">Academy</span>
          <span className="text-[10.5px] uppercase tracking-[0.06em] text-muted-foreground">
            Platform
          </span>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto p-2">
        {SECTIONS.map((section) => (
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
      <div className="flex items-center gap-2.5 border-t px-3 py-2.5">
        <div className="grid h-7 w-7 shrink-0 place-items-center rounded-full border bg-muted text-[11px] font-semibold text-foreground">
          {initials}
        </div>
        <div className="flex min-w-0 flex-1 flex-col leading-tight">
          <span className="truncate text-[12.5px] font-medium">{fullName}</span>
          <span className="truncate text-[11px] text-muted-foreground">
            {roleLabel}
          </span>
        </div>
        {user && (
          <button
            onClick={logout}
            className="text-[11px] text-muted-foreground transition-colors hover:text-foreground"
            title="Sign out"
            aria-label="Sign out"
          >
            ⏻
          </button>
        )}
      </div>
    </aside>
  );
}
