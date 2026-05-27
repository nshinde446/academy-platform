"use client";

// Compact list row used in the middle pane of the Question Bank
// three-pane layout. Clicking the body selects the row for the
// preview pane; the checkbox is separate for bulk approve/reject.

import { Badge } from "@/components/ui/badge";
import type { QuestionResponse, ReviewStatus } from "../_schemas/question";

interface QBListRowProps {
  question: QuestionResponse;
  selected: boolean; // open in the preview pane
  bulkChecked: boolean;
  onSelect: (id: string) => void;
  onToggleBulk: (id: string) => void;
  isLast: boolean;
}

const STATUS_DOT: Record<ReviewStatus, string> = {
  pending_review: "bg-amber-500",
  approved: "bg-[var(--success)]",
  rejected: "bg-destructive",
};

const DIFFICULTY_TONE: Record<string, string> = {
  EASY: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  MEDIUM: "bg-amber-500/10 text-amber-700 dark:text-amber-300",
  HARD: "bg-rose-500/10 text-rose-700 dark:text-rose-300",
};

export function QBListRow({
  question: q,
  selected,
  bulkChecked,
  onSelect,
  onToggleBulk,
  isLast,
}: QBListRowProps) {
  const preview = q.content
    .replace(/\$([^$]+)\$/g, "$1") // strip $...$ delimiters for snippet
    .slice(0, 180);
  const tail = q.content.length > 180 ? "…" : "";

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => onSelect(q.id)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect(q.id);
        }
      }}
      className={`cursor-pointer border-l-2 px-3 py-2.5 transition-colors ${
        isLast ? "" : "border-b"
      } ${
        selected
          ? "border-l-primary bg-primary/5"
          : "border-l-transparent hover:bg-muted/40"
      }`}
    >
      <div className="flex items-center gap-2 text-xs">
        <input
          type="checkbox"
          checked={bulkChecked}
          onChange={() => onToggleBulk(q.id)}
          onClick={(e) => e.stopPropagation()}
          aria-label={`Select ${q.id} for bulk action`}
          className="cursor-pointer"
        />
        <span
          aria-label={q.review_status}
          className={`inline-block h-1.5 w-1.5 rounded-full ${
            STATUS_DOT[q.review_status]
          }`}
        />
        <span
          className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${
            DIFFICULTY_TONE[q.difficulty] ?? "bg-muted text-muted-foreground"
          }`}
        >
          {q.difficulty}
        </span>
        <Badge variant="secondary" className="text-[10px]">
          {q.blooms_taxonomy}
        </Badge>
        {q.source?.startsWith("studymat:") && (
          <span className="text-muted-foreground text-[10px]">📄 studymat</span>
        )}
        {q.source?.startsWith("AI-") && (
          <Badge variant="secondary" className="text-[10px]">✦ AI</Badge>
        )}
      </div>

      <p className="mt-1.5 line-clamp-2 text-sm text-foreground">
        {preview}
        {tail}
      </p>

      {q.source_ref && (
        <p className="mt-1 truncate text-[10px] text-muted-foreground">
          {q.source_ref}
        </p>
      )}
    </div>
  );
}
