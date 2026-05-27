"use client";

// Left filter rail. Mirrors the MSA_Design checkbox groups, but our
// backend supports a single value per filter (review_status,
// difficulty, source_prefix), so each group renders as a radio-style
// list — clicking again on the active row clears it.

import type { ReviewStatus } from "../_schemas/question";

export interface QBFilters {
  review_status: ReviewStatus | "";
  difficulty: "" | "EASY" | "MEDIUM" | "HARD";
  source_prefix: "" | "studymat:" | "HUMAN" | "AI-";
}

interface QBFilterRailProps {
  filters: QBFilters;
  onChange: (next: QBFilters) => void;
  counts: { pending: number; approved: number; rejected: number };
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
      <span>{label}</span>
      {typeof count === "number" ? (
        <span className="text-xs tabular-nums">{count}</span>
      ) : null}
    </button>
  );
}

export function QBFilterRail({
  filters,
  onChange,
  counts,
}: QBFilterRailProps) {
  function setStatus(v: QBFilters["review_status"]) {
    onChange({ ...filters, review_status: filters.review_status === v ? "" : v });
  }
  function setDifficulty(v: QBFilters["difficulty"]) {
    onChange({ ...filters, difficulty: filters.difficulty === v ? "" : v });
  }
  function setSource(v: QBFilters["source_prefix"]) {
    onChange({ ...filters, source_prefix: filters.source_prefix === v ? "" : v });
  }

  return (
    <aside className="flex flex-col gap-5 rounded-xl border bg-card p-3">
      <section className="flex flex-col gap-1.5">
        <h3 className="px-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          Status
        </h3>
        <RailItem
          label="Pending review"
          active={filters.review_status === "pending_review"}
          count={counts.pending}
          onClick={() => setStatus("pending_review")}
        />
        <RailItem
          label="Approved"
          active={filters.review_status === "approved"}
          count={counts.approved}
          onClick={() => setStatus("approved")}
        />
        <RailItem
          label="Rejected"
          active={filters.review_status === "rejected"}
          count={counts.rejected}
          onClick={() => setStatus("rejected")}
        />
      </section>

      <section className="flex flex-col gap-1.5">
        <h3 className="px-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          Difficulty
        </h3>
        <RailItem
          label="Easy"
          active={filters.difficulty === "EASY"}
          onClick={() => setDifficulty("EASY")}
        />
        <RailItem
          label="Medium"
          active={filters.difficulty === "MEDIUM"}
          onClick={() => setDifficulty("MEDIUM")}
        />
        <RailItem
          label="Hard"
          active={filters.difficulty === "HARD"}
          onClick={() => setDifficulty("HARD")}
        />
      </section>

      <section className="flex flex-col gap-1.5">
        <h3 className="px-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          Source
        </h3>
        <RailItem
          label="Study material"
          active={filters.source_prefix === "studymat:"}
          onClick={() => setSource("studymat:")}
        />
        <RailItem
          label="Manual / seed"
          active={filters.source_prefix === "HUMAN"}
          onClick={() => setSource("HUMAN")}
        />
        <RailItem
          label="AI generated"
          active={filters.source_prefix === "AI-"}
          onClick={() => setSource("AI-")}
        />
      </section>
    </aside>
  );
}
