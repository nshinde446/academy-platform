"use client";

import { CATEGORY_LABEL, EXAM_TYPE_LABEL } from "../_schemas/material";
import type {
  MaterialCategory,
  ExamType,
} from "../_schemas/material";
import type { MaterialFacetCounts } from "../_schemas/material";

export interface MaterialFilters {
  academic_year_id: string;
  class_label: "" | "9" | "10" | "11" | "12" | "drop";
  subject_id: string;
  category: MaterialCategory | "";
  exam_type: ExamType | "";
  batch_id: string;
}

interface RailProps {
  filters: MaterialFilters;
  onChange: (next: MaterialFilters) => void;
  facets: MaterialFacetCounts | undefined;
  subjects: { id: string; name: string }[];
  batches: { id: string; name: string }[];
}

function RailItem({
  label,
  active,
  count,
  onClick,
}: {
  label: string;
  active: boolean;
  count?: number;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`flex w-full items-center justify-between rounded-md px-2.5 py-1.5 text-sm transition-colors ${
        active
          ? "bg-primary/10 text-foreground font-medium"
          : "text-muted-foreground hover:bg-muted"
      }`}
    >
      <span className="truncate">{label}</span>
      {typeof count === "number" ? (
        <span className="text-xs tabular-nums">{count}</span>
      ) : null}
    </button>
  );
}

function countOf(buckets: { value: string; count: number }[] | undefined, key: string) {
  return buckets?.find((b) => b.value === key)?.count ?? 0;
}

export function MaterialFilterRail({
  filters,
  onChange,
  facets,
  subjects,
  batches,
}: RailProps) {
  function toggle<K extends keyof MaterialFilters>(
    key: K,
    value: MaterialFilters[K],
  ) {
    onChange({
      ...filters,
      [key]: filters[key] === value ? ("" as MaterialFilters[K]) : value,
    });
  }

  return (
    <aside className="flex flex-col gap-5 rounded-xl border bg-card p-3">
      <section className="flex flex-col gap-1.5">
        <h3 className="px-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          Class
        </h3>
        {(["9", "10", "11", "12", "drop"] as const).map((c) => (
          <RailItem
            key={c}
            label={c === "drop" ? "Drop year" : `Class ${c}`}
            active={filters.class_label === c}
            count={countOf(facets?.classes, c)}
            onClick={() => toggle("class_label", c)}
          />
        ))}
      </section>

      {subjects.length > 0 && (
        <section className="flex flex-col gap-1.5">
          <h3 className="px-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Subject
          </h3>
          {subjects.map((s) => (
            <RailItem
              key={s.id}
              label={s.name}
              active={filters.subject_id === s.id}
              count={countOf(facets?.subjects, s.id)}
              onClick={() => toggle("subject_id", s.id)}
            />
          ))}
        </section>
      )}

      <section className="flex flex-col gap-1.5">
        <h3 className="px-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          Category
        </h3>
        {(Object.keys(CATEGORY_LABEL) as MaterialCategory[]).map((c) => (
          <RailItem
            key={c}
            label={CATEGORY_LABEL[c]}
            active={filters.category === c}
            count={countOf(facets?.categories, c)}
            onClick={() => toggle("category", c)}
          />
        ))}
      </section>

      <section className="flex flex-col gap-1.5">
        <h3 className="px-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          Exam type
        </h3>
        {(Object.keys(EXAM_TYPE_LABEL) as ExamType[]).map((e) => (
          <RailItem
            key={e}
            label={EXAM_TYPE_LABEL[e]}
            active={filters.exam_type === e}
            count={countOf(facets?.exam_types, e)}
            onClick={() => toggle("exam_type", e)}
          />
        ))}
      </section>

      {batches.length > 0 && (
        <section className="flex flex-col gap-1.5">
          <h3 className="px-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Batch
          </h3>
          {batches.map((b) => (
            <RailItem
              key={b.id}
              label={b.name}
              active={filters.batch_id === b.id}
              count={countOf(facets?.batches, b.id)}
              onClick={() => toggle("batch_id", b.id)}
            />
          ))}
        </section>
      )}
    </aside>
  );
}
