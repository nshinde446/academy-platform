"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { STANDARDS, TARGET_EXAMS } from "../_schemas/student";
import {
  type RosterFilters,
  type SavedView,
  EMPTY_FILTERS,
  hasActiveFilters,
  loadSavedViews,
  upsertSavedView,
  deleteSavedView,
} from "../_lib/saved-views";

const FEES_OPTIONS = ["paid", "due", "overdue", "partial"] as const;
const SELECT =
  "h-9 rounded-md border border-input bg-background px-2 text-sm";

interface RosterFiltersBarProps {
  branchId: string;
  filters: RosterFilters;
  onChange: (filters: RosterFilters) => void;
  batches: { id: string; code: string }[];
}

export function RosterFiltersBar({
  branchId,
  filters,
  onChange,
  batches,
}: RosterFiltersBarProps) {
  const [views, setViews] = useState<SavedView[]>([]);
  const [viewName, setViewName] = useState("");

  // localStorage is client-only, so load after mount (keyed by branch).
  useEffect(() => {
    setViews(loadSavedViews(branchId));
  }, [branchId]);

  const active = hasActiveFilters(filters);

  function set<K extends keyof RosterFilters>(key: K, value: string) {
    onChange({ ...filters, [key]: value });
  }

  function handleSaveView() {
    const name = viewName.trim();
    if (!name) return;
    setViews(upsertSavedView(branchId, { name, filters }));
    setViewName("");
  }

  function handleDeleteView(name: string) {
    setViews(deleteSavedView(branchId, name));
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <select
          aria-label="Filter by class"
          className={SELECT}
          value={filters.standard}
          onChange={(e) => set("standard", e.target.value)}
        >
          <option value="">All classes</option>
          {STANDARDS.map((s) => (
            <option key={s} value={s}>
              {s === "Dropper" ? "Dropper" : `Class ${s}`}
            </option>
          ))}
        </select>

        <select
          aria-label="Filter by target"
          className={SELECT}
          value={filters.targetExam}
          onChange={(e) => set("targetExam", e.target.value)}
        >
          <option value="">All targets</option>
          {TARGET_EXAMS.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>

        <select
          aria-label="Filter by fees"
          className={SELECT}
          value={filters.feesStatus}
          onChange={(e) => set("feesStatus", e.target.value)}
        >
          <option value="">All fees</option>
          {FEES_OPTIONS.map((f) => (
            <option key={f} value={f}>
              {f[0].toUpperCase() + f.slice(1)}
            </option>
          ))}
        </select>

        <select
          aria-label="Filter by batch"
          className={SELECT}
          value={filters.batchId}
          onChange={(e) => set("batchId", e.target.value)}
        >
          <option value="">All batches</option>
          {batches.map((b) => (
            <option key={b.id} value={b.id}>
              {b.code}
            </option>
          ))}
        </select>

        {active && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onChange({ ...EMPTY_FILTERS })}
          >
            Clear filters
          </Button>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {views.map((v) => (
          <span
            key={v.name}
            className="inline-flex items-center gap-1 rounded-full border border-border bg-muted px-2 py-0.5 text-xs"
          >
            <button
              type="button"
              className="hover:underline"
              onClick={() => onChange({ ...v.filters })}
            >
              {v.name}
            </button>
            <button
              type="button"
              aria-label={`Delete view ${v.name}`}
              className="text-muted-foreground hover:text-destructive"
              onClick={() => handleDeleteView(v.name)}
            >
              ×
            </button>
          </span>
        ))}
        {active && (
          <span className="flex items-center gap-1">
            <Input
              aria-label="Save view name"
              placeholder="Save view as…"
              value={viewName}
              onChange={(e) => setViewName(e.target.value)}
              className="h-8 w-36 text-xs"
            />
            <Button
              variant="outline"
              size="sm"
              onClick={handleSaveView}
              disabled={!viewName.trim()}
            >
              Save view
            </Button>
          </span>
        )}
      </div>
    </div>
  );
}
