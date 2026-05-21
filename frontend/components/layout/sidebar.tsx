"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

interface NavItem {
  label: string;
  href: string;
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

const TOP_LEVEL: NavItem[] = [
  { label: "Home", href: "/home" },
  { label: "Students", href: "/students" },
  { label: "Teachers", href: "/teachers" },
  { label: "Lectures", href: "/lectures" },
];

const ACADEMICS: NavGroup = {
  label: "Academics",
  items: [
    { label: "Courses", href: "/courses" },
    { label: "Batches", href: "/batches" },
    { label: "Academic Years", href: "/academic-years" },
    { label: "Syllabus", href: "/syllabus" },
  ],
};

function NavLink({ item, active }: { item: NavItem; active: boolean }) {
  return (
    <Link
      href={item.href}
      className={`block rounded-md px-3 py-2 text-sm transition-colors ${
        active
          ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium"
          : "text-sidebar-foreground hover:bg-sidebar-accent/50"
      }`}
    >
      {item.label}
    </Link>
  );
}

function AcademicsGroup({ pathname }: { pathname: string }) {
  const hasActiveChild = ACADEMICS.items.some((i) => pathname === i.href);
  const [open, setOpen] = useState(hasActiveChild);
  // Keep parent expanded whenever a child is active, regardless of user toggles
  // — re-renders with a new pathname re-evaluate this state on click.
  const isOpen = open || hasActiveChild;

  return (
    <div className="flex flex-col">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={isOpen}
        aria-controls="sidebar-academics"
        className={`flex w-full items-center justify-between rounded-md px-3 py-2 text-sm transition-colors ${
          hasActiveChild
            ? "bg-sidebar-accent/60 text-sidebar-accent-foreground font-medium"
            : "text-sidebar-foreground hover:bg-sidebar-accent/50"
        }`}
      >
        <span>{ACADEMICS.label}</span>
        <span
          aria-hidden
          className={`inline-block text-xs transition-transform ${
            isOpen ? "rotate-90" : ""
          }`}
        >
          ▶
        </span>
      </button>
      {isOpen && (
        <div id="sidebar-academics" className="ml-3 mt-1 flex flex-col gap-1 border-l pl-2">
          {ACADEMICS.items.map((item) => (
            <NavLink
              key={item.href}
              item={item}
              active={pathname === item.href}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex w-60 shrink-0 flex-col border-r bg-sidebar">
      <div className="flex h-14 items-center border-b px-4">
        <span className="text-sm font-semibold text-sidebar-foreground">
          Navigation
        </span>
      </div>
      <nav className="flex flex-col gap-1 p-2">
        {TOP_LEVEL.map((item) => (
          <NavLink
            key={item.href}
            item={item}
            active={pathname === item.href}
          />
        ))}
        <AcademicsGroup pathname={pathname ?? ""} />
      </nav>
    </aside>
  );
}
