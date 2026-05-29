"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { QuestionResponse } from "@/app/(dashboard)/question-bank/_schemas/question";

interface PaperPreviewProps {
  questions: QuestionResponse[];
  name: string;
  onName: (v: string) => void;
  onRemove: (id: string) => void;
  onSwap: (q: QuestionResponse) => void;
  onReshuffle: () => void;
  onSave: () => void;
  swappingId: string | null;
  reshuffling: boolean;
  saving: boolean;
}

const DIFF_TONE: Record<string, string> = {
  EASY: "text-success",
  MEDIUM: "text-foreground",
  HARD: "text-destructive",
};

export function PaperPreview({
  questions,
  name,
  onName,
  onRemove,
  onSwap,
  onReshuffle,
  onSave,
  swappingId,
  reshuffling,
  saving,
}: PaperPreviewProps) {
  const canSave = questions.length > 0 && name.trim().length > 0 && !saving;

  if (questions.length === 0) {
    return (
      <div className="grid min-h-[300px] place-items-center rounded-xl border bg-card p-6 text-center">
        <p className="max-w-xs text-sm text-muted-foreground">
          Choose a batch, subject and a question mix on the left, then{" "}
          <span className="font-medium text-foreground">Auto-pick</span> to fill
          the paper. You can swap or remove any question before saving.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3 rounded-xl border bg-card p-4">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium">
          {questions.length} question{questions.length !== 1 ? "s" : ""}
        </span>
        <div className="ml-auto flex gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={onReshuffle}
            disabled={reshuffling || saving}
          >
            {reshuffling ? "Reshuffling…" : "Reshuffle"}
          </Button>
        </div>
      </div>

      {/* Name + save */}
      <div className="flex flex-col gap-1.5 rounded-md border bg-muted/30 p-2.5">
        <Label htmlFor="paper-name">Paper name</Label>
        <div className="flex gap-2">
          <Input
            id="paper-name"
            value={name}
            onChange={(e) => onName(e.target.value)}
            placeholder="e.g. Physics — Mechanics DPP"
          />
          <Button onClick={onSave} disabled={!canSave}>
            {saving ? "Saving…" : "Save draft"}
          </Button>
        </div>
      </div>

      {/* Question list */}
      <ol className="flex flex-col gap-2">
        {questions.map((q, i) => (
          <li
            key={q.id}
            className="flex gap-2 rounded-lg border bg-background p-2.5 text-sm"
          >
            <span className="shrink-0 text-xs font-medium text-muted-foreground tabular-nums">
              {i + 1}.
            </span>
            <div className="min-w-0 flex-1">
              <p className="line-clamp-3 whitespace-pre-wrap">{q.content}</p>
              <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
                <span className={DIFF_TONE[q.difficulty] ?? ""}>
                  {q.difficulty}
                </span>
                {q.correct_answer && <span>· Ans {q.correct_answer}</span>}
              </div>
            </div>
            <div className="flex shrink-0 flex-col gap-1">
              <button
                type="button"
                onClick={() => onSwap(q)}
                disabled={swappingId === q.id}
                className="rounded px-1.5 py-0.5 text-[11px] text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-50"
                title="Swap with another question of the same difficulty"
              >
                {swappingId === q.id ? "…" : "Swap"}
              </button>
              <button
                type="button"
                onClick={() => onRemove(q.id)}
                className="rounded px-1.5 py-0.5 text-[11px] text-muted-foreground transition-colors hover:bg-muted hover:text-destructive"
                title="Remove"
              >
                Remove
              </button>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
