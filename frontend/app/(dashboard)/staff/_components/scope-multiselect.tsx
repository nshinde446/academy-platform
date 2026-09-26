"use client";

import { useMemo, useState } from "react";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

export interface ScopeOption {
  id: string;
  label: string;
  /** Secondary text shown muted after the label (e.g. emp code, department). */
  sublabel?: string;
}

interface ScopeMultiSelectProps {
  /** Field label above the control. */
  label: string;
  /** Text for the "select everything" row (e.g. "All departments"). An empty
   *  selection means "all", mirroring the backend which omits the filter. */
  allLabel: string;
  options: ScopeOption[];
  /** Currently-selected ids. Empty set = "all". */
  selected: Set<string>;
  onChange: (next: Set<string>) => void;
  /** Show a search box above the list (for long lists like staff). */
  searchable?: boolean;
  /** Greys the control out and shows `disabledNote` in place of the list. */
  disabled?: boolean;
  disabledNote?: string;
  /** Shown when there are no options to choose from. */
  emptyNote?: string;
}

/**
 * A labelled "All / a chosen few" checkbox picker. An empty selection is the
 * "All" state, matching how the staff-report API treats an omitted
 * `department_ids` / `staff_ids` filter. Ticking "All" clears the selection;
 * ticking any row narrows to the chosen set.
 */
export function ScopeMultiSelect({
  label,
  allLabel,
  options,
  selected,
  onChange,
  searchable = false,
  disabled = false,
  disabledNote,
  emptyNote = "Nothing to choose from.",
}: ScopeMultiSelectProps) {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    if (!searchable || !query.trim()) return options;
    const q = query.trim().toLowerCase();
    return options.filter(
      (o) =>
        o.label.toLowerCase().includes(q) ||
        (o.sublabel?.toLowerCase().includes(q) ?? false),
    );
  }, [options, query, searchable]);

  const allChecked = selected.size === 0;

  function toggle(id: string) {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    onChange(next);
  }

  return (
    <div className="flex flex-col gap-1.5">
      <Label>
        {label}
        {selected.size > 0 && (
          <span className="ml-2 text-xs font-normal text-muted-foreground">
            {selected.size} selected
          </span>
        )}
      </Label>
      <div
        className={cn(
          "rounded-md border border-input bg-background",
          disabled && "opacity-60",
        )}
      >
        {disabled ? (
          <p className="px-3 py-2 text-xs text-muted-foreground">
            {disabledNote}
          </p>
        ) : (
          <>
            {searchable && options.length > 8 && (
              <div className="border-b p-1.5">
                <Input
                  type="search"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search…"
                  className="h-8 text-sm"
                  aria-label={`Search ${label.toLowerCase()}`}
                />
              </div>
            )}
            <div className="max-h-44 overflow-y-auto p-1.5 text-sm">
              <label className="flex cursor-pointer items-center gap-2 rounded px-2 py-1 hover:bg-muted">
                <input
                  type="checkbox"
                  checked={allChecked}
                  onChange={() => onChange(new Set())}
                />
                <span className="font-medium">{allLabel}</span>
              </label>
              {options.length === 0 ? (
                <p className="px-2 py-1 text-xs text-muted-foreground">
                  {emptyNote}
                </p>
              ) : filtered.length === 0 ? (
                <p className="px-2 py-1 text-xs text-muted-foreground">
                  No matches.
                </p>
              ) : (
                filtered.map((o) => (
                  <label
                    key={o.id}
                    className="flex cursor-pointer items-center gap-2 rounded px-2 py-1 hover:bg-muted"
                  >
                    <input
                      type="checkbox"
                      checked={selected.has(o.id)}
                      onChange={() => toggle(o.id)}
                    />
                    <span>{o.label}</span>
                    {o.sublabel && (
                      <span className="text-xs text-muted-foreground">
                        {o.sublabel}
                      </span>
                    )}
                  </label>
                ))
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
