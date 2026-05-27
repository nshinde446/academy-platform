"use client";

// Right preview pane in the Question Bank three-pane layout. Renders
// the full question (content + options + explanation + provenance)
// with primary actions inline. Reuses MathText for LaTeX.

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { MathText } from "./math-text";
import type { QuestionResponse, ReviewStatus } from "../_schemas/question";

interface QBPreviewPaneProps {
  question: QuestionResponse | null;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
  onEdit: (q: QuestionResponse) => void;
  pending: boolean;
}

const STATUS_LABEL: Record<ReviewStatus, string> = {
  pending_review: "Pending",
  approved: "Approved",
  rejected: "Rejected",
};

const STATUS_VARIANT: Record<
  ReviewStatus,
  "default" | "secondary" | "success" | "destructive"
> = {
  pending_review: "default",
  approved: "success",
  rejected: "destructive",
};

export function QBPreviewPane({
  question: q,
  onApprove,
  onReject,
  onEdit,
  pending,
}: QBPreviewPaneProps) {
  if (!q) {
    return (
      <aside className="flex h-full min-h-[300px] flex-col items-center justify-center rounded-xl border bg-card p-6 text-center text-sm text-muted-foreground">
        Pick a question on the left to preview, edit, or approve it here.
      </aside>
    );
  }

  const optionEntries = q.options ? Object.entries(q.options) : [];
  const tags = (q.concept_tags ?? []).filter(Boolean);

  return (
    <aside className="flex flex-col gap-4 rounded-xl border bg-card p-4">
      {/* Header: status + actions */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={STATUS_VARIANT[q.review_status]}>
            {STATUS_LABEL[q.review_status]}
          </Badge>
          <Badge variant="secondary">{q.difficulty}</Badge>
          <Badge variant="secondary">{q.blooms_taxonomy}</Badge>
        </div>
        <div className="flex gap-1">
          <Button
            size="sm"
            variant="outline"
            onClick={() => onEdit(q)}
            disabled={pending}
          >
            Edit
          </Button>
          {q.review_status !== "rejected" && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => onReject(q.id)}
              disabled={pending}
            >
              Reject
            </Button>
          )}
          {q.review_status !== "approved" && (
            <Button
              size="sm"
              onClick={() => onApprove(q.id)}
              disabled={pending}
            >
              Approve
            </Button>
          )}
        </div>
      </div>

      {/* Question body */}
      <div className="text-sm leading-relaxed">
        <MathText text={q.content} />
      </div>

      {/* Options */}
      {optionEntries.length > 0 && (
        <ol className="grid grid-cols-1 gap-1.5 text-sm">
          {optionEntries.map(([key, val]) => {
            const isCorrect =
              q.correct_answer &&
              key.toUpperCase() === q.correct_answer.toUpperCase();
            return (
              <li
                key={key}
                className={`flex gap-2 rounded-md border px-2.5 py-1.5 ${
                  isCorrect
                    ? "border-emerald-500/40 bg-emerald-500/5"
                    : "border-foreground/10"
                }`}
              >
                <span className="font-medium">{key}.</span>
                <span className="flex-1">
                  <MathText text={val} />
                </span>
                {isCorrect && (
                  <Badge variant="success" className="text-[10px]">
                    ✓
                  </Badge>
                )}
              </li>
            );
          })}
        </ol>
      )}

      {!q.correct_answer && (
        <p className="text-xs text-amber-600 dark:text-amber-400">
          ⚠ No correct answer set — fix via Edit before approving.
        </p>
      )}

      {q.explanation && (
        <details className="text-xs">
          <summary className="cursor-pointer text-muted-foreground">
            Explanation
          </summary>
          <div className="mt-1 pl-4 text-sm">
            <MathText text={q.explanation} />
          </div>
        </details>
      )}

      {/* Provenance */}
      <div className="flex flex-col gap-1 border-t pt-3 text-[11px] text-muted-foreground">
        {q.source && (
          <p>
            <span className="font-medium">Source:</span> {q.source}
          </p>
        )}
        {q.source_ref && (
          <p className="break-all">
            <span className="font-medium">Ref:</span> {q.source_ref}
          </p>
        )}
        {tags.length > 0 && (
          <p>
            <span className="font-medium">Tags:</span> {tags.join(" · ")}
          </p>
        )}
        <p className="tabular-nums">ID: {q.id.slice(0, 8)}…</p>
      </div>
    </aside>
  );
}
