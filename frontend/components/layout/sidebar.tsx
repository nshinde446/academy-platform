"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

interface NavItem {
  label: string;
  href: string;
  isNew?: boolean;
}

interface NavSection {
  // Empty string means no label — used for the top, primary section.
  label: string;
  items: NavItem[];
}

// MSA_Design grouping. Top is unlabeled (primary surfaces), then
// Content (creation tools), Academics (configuration), and Admin
// (rolls in when /branch-settings ships in Tier 14).
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
      { label: "Question Bank", href: "/question-bank", isNew: true },
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
      className={`flex items-center justify-between rounded-md px-3 py-2 text-sm transition-colors ${
        active
          ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium"
          : "text-sidebar-foreground hover:bg-sidebar-accent/50"
      }`}
    >
      <span className="truncate">{item.label}</span>
      {item.isNew && (
        <span className="ml-2 rounded border border-current/30 px-1.5 py-px text-[9.5px] font-medium tracking-wide text-muted-foreground">
          NEW
        </span>
      )}
    </Link>
  );
}

export function Sidebar() {
  const pathname = usePathname() ?? "";

  return (
    <aside className="flex w-60 shrink-0 flex-col border-r bg-sidebar">
      <div className="flex h-14 items-center border-b px-4">
        <span className="text-sm font-semibold text-sidebar-foreground">
          Navigation
        </span>
      </div>
      <nav className="flex flex-col gap-4 p-2">
        {SECTIONS.map((section) => (
          <div key={section.label || "top"} className="flex flex-col gap-1">
            {section.label ? (
              <div className="px-3 pt-1 pb-0.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                {section.label}
              </div>
            ) : null}
            {section.items.map((item) => (
              <NavLink
                key={item.href}
                item={item}
                active={pathname === item.href || pathname.startsWith(item.href + "/")}
              />
            ))}
          </div>
        ))}
      </nav>
    </aside>
  );
}
