"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";

// First-segment slug → display label. Sub-segments (e.g.
// /teachers/abc-123) just show the slug — the detail page can render
// its own breadcrumb if needed.
const PATH_LABELS: Record<string, string> = {
  home: "Home",
  today: "Today",
  students: "Students",
  teachers: "Teachers",
  lectures: "Lectures",
  insights: "Insights",
  "question-bank": "Question Bank",
  materials: "Materials",
  courses: "Courses",
  batches: "Batches",
  classrooms: "Classrooms",
  "academic-years": "Academic Years",
  syllabus: "Syllabus",
};

export function Header() {
  const pathname = usePathname() ?? "";
  const segments = pathname.split("/").filter(Boolean);
  const crumbs =
    segments.length === 0 ? ["Home"] : segments.map((s) => PATH_LABELS[s] ?? s);

  // Render the date only after mount. Locale-aware formatting can't
  // be reproduced on the server (it doesn't know the browser's
  // locale), so SSR'd HTML mismatches the client paint and React
  // regenerates the subtree. Empty string until hydration → no
  // mismatch, tiny single-frame delay.
  const [todayDate, setTodayDate] = useState("");
  useEffect(() => {
    // Deliberate hydration-deferral: server doesn't know the browser locale,
    // so we render "" on the server and fill in after mount. Disable the
    // set-state-in-effect lint — this *is* the pattern.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setTodayDate(
      new Date().toLocaleDateString(undefined, {
        weekday: "long",
        month: "short",
        day: "numeric",
        year: "numeric",
      }),
    );
  }, []);

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b bg-background px-6">
      <div className="flex items-center gap-2 text-[15px] font-semibold">
        {crumbs.map((c, i) => (
          <span key={i} className="flex items-center gap-2">
            {i > 0 && <span className="text-muted-foreground/60">/</span>}
            <span
              className={
                i === crumbs.length - 1
                  ? ""
                  : "font-normal text-muted-foreground"
              }
            >
              {c}
            </span>
          </span>
        ))}
      </div>
      <div className="flex items-center gap-3 text-[12.5px] text-muted-foreground">
        <span>{todayDate}</span>
        <span className="h-4 w-px bg-border" />
        <kbd className="rounded border border-border bg-muted px-1.5 py-0.5 text-[11px] font-medium">
          ⌘K
        </kbd>
      </div>
    </header>
  );
}
