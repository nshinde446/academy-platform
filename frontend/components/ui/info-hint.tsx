"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

// A tiny "ⓘ" button that reveals helper text in a popover on click. Lets a page
// keep its explanatory copy available without spending vertical space on a
// paragraph every visit (progressive disclosure). Closes on outside-click/Escape.
export function InfoHint({
  text,
  label = "What is this?",
}: {
  text: ReactNode;
  label?: string;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onDoc(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={ref} className="relative inline-flex">
      <button
        type="button"
        aria-label={label}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="grid h-[18px] w-[18px] place-items-center rounded-full border border-border text-[11px] font-medium leading-none text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
      >
        i
      </button>
      {open && (
        <div
          role="tooltip"
          className="absolute left-0 top-[26px] z-30 w-72 rounded-lg border bg-card p-3 text-xs leading-relaxed text-muted-foreground shadow-lg ring-1 ring-foreground/10"
        >
          {text}
        </div>
      )}
    </div>
  );
}
