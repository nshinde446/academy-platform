"use client";

import { useEffect, useRef, useState } from "react";

export interface MultiSelectOption {
  value: string;
  label: string;
}

interface MultiSelectProps {
  label: string;
  options: MultiSelectOption[];
  selected: string[];
  onChange: (values: string[]) => void;
  disabled?: boolean;
}

// Compact checkbox dropdown filter — the app has no combobox primitive, so this
// is a small self-contained one (button + absolutely-positioned panel, closes on
// outside click). Multi-select, matching the filter pattern the report needs.
export function MultiSelect({
  label,
  options,
  selected,
  onChange,
  disabled,
}: MultiSelectProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onDoc(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  const selectedSet = new Set(selected);
  const summary =
    selected.length === 0
      ? "All"
      : selected.length === 1
        ? (options.find((o) => o.value === selected[0])?.label ?? "1 selected")
        : `${selected.length} selected`;

  function toggle(value: string) {
    const next = new Set(selectedSet);
    if (next.has(value)) next.delete(value);
    else next.add(value);
    onChange([...next]);
  }

  return (
    <div className="relative flex flex-col gap-1" ref={ref}>
      <span className="text-xs text-muted-foreground">{label}</span>
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((v) => !v)}
        className="flex h-9 min-w-40 items-center justify-between gap-2 rounded-lg border border-input bg-background px-3 text-sm disabled:opacity-50"
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span className="truncate">{summary}</span>
        <span className="text-muted-foreground">▾</span>
      </button>
      {open && (
        <div className="absolute top-full z-20 mt-1 max-h-64 w-64 overflow-auto rounded-lg border bg-background p-1 shadow-lg ring-1 ring-foreground/10">
          {selected.length > 0 && (
            <button
              type="button"
              onClick={() => onChange([])}
              className="mb-1 w-full rounded px-2 py-1 text-left text-xs text-muted-foreground hover:bg-muted"
            >
              Clear selection
            </button>
          )}
          {options.length === 0 ? (
            <p className="px-2 py-1 text-xs text-muted-foreground">No options</p>
          ) : (
            options.map((o) => (
              <label
                key={o.value}
                className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-muted"
              >
                <input
                  type="checkbox"
                  checked={selectedSet.has(o.value)}
                  onChange={() => toggle(o.value)}
                />
                <span className="truncate">{o.label}</span>
              </label>
            ))
          )}
        </div>
      )}
    </div>
  );
}
