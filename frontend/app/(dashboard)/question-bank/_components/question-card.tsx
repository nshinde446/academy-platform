"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { MathText } from "./math-text";
import type { QuestionResponse, ReviewStatus } from "../_schemas/question";

interface QuestionCardProps {
  question: QuestionResponse;
  selected: boolean;
  onToggleSelected: (id: string) => void;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
  onEdit: (q: QuestionResponse) => void;
  pending: boolean;
}

const STATUS_TONE: Record<
  ReviewStatus,
  "default" | "secondary" | "success" | "destructive"
> = {
  pending_review: "default",
  approved: "success",
  rejected: "destructive",
};

const DIFFICULTY_TONE: Record<
  string,
  "default" | "secondary" | "success" | "destructive"
> = {
  EASY: "success",
  MEDIUM: "default",
  HARD: "destructive",
};

export function QuestionCard({
  question: q,
  selected,
  onToggleSelected,
  onApprove,
  onReject,
  onEdit,
  pending,
}: QuestionCardProps) {
  const tags = q.concept_tags ?? [];
  const optionEntries = q.options ? Object.entries(q.options) : [];
  const sourceShort = q.source ? q.source.replace(/^studymat:/, "📄 ") : null;

  return (
    <Card className="ring-1 ring-foreground/10">
      <CardContent className="flex flex-col gap-3">
        {/* Top row: select + meta + actions */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <input
            type="checkbox"
            checked={selected}
            onChange={() => onToggleSelected(q.id)}
            aria-label={`Select question ${q.id}`}
            className="cursor-pointer"
          />
          <Badge variant={STATUS_TONE[q.review_status]}>
            {q.review_status.replace("_", " ")}
          </Badge>
          <Badge variant={DIFFICULTY_TONE[q.difficulty] ?? "default"}>
            {q.difficulty}
          </Badge>
          <Badge variant="secondary">{q.blooms_taxonomy}</Badge>
          {sourceShort && (
            <span className="text-muted-foreground">{sourceShort}</span>
          )}
          {tags.length > 0 && (
            <span className="text-muted-foreground">
              · {tags.filter(Boolean).join(" · ")}
            </span>
          )}
          <div className="ml-auto flex gap-1">
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

        {/* Question content */}
        <div className="text-sm">
          <MathText text={q.content} />
        </div>

        {/* Options */}
        {optionEntries.length > 0 && (
          <ol className="grid grid-cols-1 gap-1.5 sm:grid-cols-2 text-sm">
            {optionEntries.map(([key, val]) => {
              const isCorrect =
                q.correct_answer &&
                key.toUpperCase() === q.correct_answer.toUpperCase();
              return (
                <li
                  key={key}
                  className={`flex gap-2 rounded-md border px-2 py-1.5 ${
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
          <details className="text-xs text-muted-foreground">
            <summary className="cursor-pointer">Explanation</summary>
            <div className="mt-1 pl-4">
              <MathText text={q.explanation} />
            </div>
          </details>
        )}

        {q.source_ref && (
          <p className="text-[10px] text-muted-foreground truncate">
            {q.source_ref}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
