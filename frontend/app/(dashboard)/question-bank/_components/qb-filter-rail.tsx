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
  class_label: "" | "9" | "10" | "11" | "12" | "drop";
  subject_id: string;
  exam_type: "" | "neet" | "jee_main" | "jee_advanced" | "boards" | "cet";
}

const EXAM_TYPE_OPTIONS: { value: QBFilters["exam_type"]; label: string }[] = [
  { value: "neet", label: "NEET" },
  { value: "jee_main", label: "JEE Main" },
  { value: "jee_advanced", label: "JEE Adv" },
  { value: "boards", label: "Boards" },
  { value: "cet", label: "CET" },
];

interface QBFilterRailProps {
  filters: QBFilters;
  onChange: (next: QBFilters) => void;
  counts: { pending: number; approved: number; rejected: number };
  subjects: { id: string; name: string }[];
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
  subjects,
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
  function setClass(v: QBFilters["class_label"]) {
    onChange({ ...filters, class_label: filters.class_label === v ? "" : v });
  }
  function setExam(v: QBFilters["exam_type"]) {
    onChange({ ...filters, exam_type: filters.exam_type === v ? "" : v });
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
            onClick={() => setClass(c)}
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
              onClick={() =>
                onChange({
                  ...filters,
                  subject_id: filters.subject_id === s.id ? "" : s.id,
                })
              }
            />
          ))}
        </section>
      )}

      <section className="flex flex-col gap-1.5">
        <h3 className="px-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          Exam type
        </h3>
        {EXAM_TYPE_OPTIONS.map((e) => (
          <RailItem
            key={e.value}
            label={e.label}
            active={filters.exam_type === e.value}
            onClick={() => setExam(e.value)}
          />
        ))}
      </section>
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
