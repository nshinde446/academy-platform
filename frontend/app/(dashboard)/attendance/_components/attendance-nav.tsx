"use client";

import type { ReactNode } from "react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export type AttendanceView =
  | "overview"
  | "defaulters"
  | "month"
  | "day"
  | "lecture";

const ICON_PROPS = {
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  className: "h-[18px] w-[18px]",
};

const ITEMS: {
  view: AttendanceView;
  name: string;
  desc: string;
  icon: ReactNode;
}[] = [
  {
    view: "overview",
    name: "Today at a glance",
    desc: "Whole-institute pulse — every batch's present % right now.",
    icon: (
      <svg {...ICON_PROPS}>
        <rect x="3" y="3" width="7" height="9" rx="1" />
        <rect x="14" y="3" width="7" height="5" rx="1" />
        <rect x="14" y="12" width="7" height="9" rx="1" />
        <rect x="3" y="16" width="7" height="5" rx="1" />
      </svg>
    ),
  },
  {
    view: "defaulters",
    name: "Defaulters",
    desc: "Eligibility watchlist, worst first — act before the cutoff.",
    icon: (
      <svg {...ICON_PROPS}>
        <path d="M12 9v4M12 17h.01" />
        <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
      </svg>
    ),
  },
  {
    view: "month",
    name: "Batch month grid",
    desc: "Every student × every day — spot the chronic pattern.",
    icon: (
      <svg {...ICON_PROPS}>
        <rect x="3" y="4" width="18" height="17" rx="2" />
        <path d="M3 9h18M8 2v4M16 2v4" />
      </svg>
    ),
  },
  {
    view: "day",
    name: "Day register",
    desc: "One day's campus in/out roster, with missed sign-offs.",
    icon: (
      <svg {...ICON_PROPS}>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5l3 2" />
      </svg>
    ),
  },
  {
    view: "lecture",
    name: "Mark a lecture",
    desc: "Take a single lecture's roster by hand or from punches.",
    icon: (
      <svg {...ICON_PROPS}>
        <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
        <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
      </svg>
    ),
  },
];

// Descriptive view rail — each target names itself (icon + purpose) and carries
// a live signal (the defaulter count) so the state reads before you click.
// Horizontal scroll strip on mobile, vertical rail on desktop.
export function AttendanceNav({
  view,
  onChange,
  defaultersCount,
}: {
  view: AttendanceView;
  onChange: (v: AttendanceView) => void;
  defaultersCount: number;
}) {
  return (
    <div
      role="tablist"
      aria-label="Attendance views"
      className="flex gap-2 overflow-x-auto pb-1 lg:flex-col lg:overflow-visible lg:pb-0"
    >
      {ITEMS.map((it) => {
        const active = view === it.view;
        return (
          <button
            key={it.view}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(it.view)}
            className={cn(
              "flex min-w-[210px] items-start gap-3 rounded-xl border bg-card p-3 text-left shadow-sm ring-1 ring-foreground/10 transition-colors lg:min-w-0",
              active ? "border-primary" : "hover:border-foreground/25",
            )}
          >
            <span
              className={cn(
                "grid h-8 w-8 shrink-0 place-items-center rounded-lg border",
                active
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-border bg-muted/40 text-muted-foreground",
              )}
            >
              {it.icon}
            </span>
            <span className="min-w-0">
              <span className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm font-semibold">
                {it.name}
                {it.view === "defaulters" && defaultersCount > 0 && (
                  <Badge variant="destructive" className="text-[10px]">
                    {defaultersCount} below 75%
                  </Badge>
                )}
              </span>
              <span className="mt-0.5 block text-xs leading-snug text-muted-foreground">
                {it.desc}
              </span>
            </span>
          </button>
        );
      })}
    </div>
  );
}
