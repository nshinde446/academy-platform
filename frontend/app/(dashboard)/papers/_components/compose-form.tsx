"use client";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import type { Difficulty } from "@/app/(dashboard)/question-bank/_schemas/question";
import {
  CLASS_LABELS,
  DIFFICULTY_ORDER,
  EXAM_TYPES,
  EXAM_TYPE_LABEL,
  PAPER_TYPES,
  PAPER_TYPE_HINT,
  PAPER_TYPE_LABEL,
  type ClassLabel,
  type DifficultyMix,
  type ExamType,
  type PaperType,
} from "../_schemas/paper";
import type { SubjectOption, BatchOption } from "../_hooks/use-papers";

const DIFFICULTY_LABEL: Record<Difficulty, string> = {
  EASY: "Easy",
  MEDIUM: "Medium",
  HARD: "Hard",
};

interface ComposeFormProps {
  paperType: PaperType;
  onPaperType: (t: PaperType) => void;
  batches: BatchOption[];
  batchId: string;
  onBatchId: (id: string) => void;
  subjects: SubjectOption[];
  subjectId: string;
  onSubjectId: (id: string) => void;
  classLabel: ClassLabel | "";
  onClassLabel: (c: ClassLabel | "") => void;
  examType: ExamType | "";
  onExamType: (e: ExamType | "") => void;
  mix: DifficultyMix;
  onMix: (d: Difficulty, value: number) => void;
  availableByDifficulty: Record<Difficulty, number | undefined>;
  onAutoPick: () => void;
  picking: boolean;
}

const SELECT = "rounded-md border bg-background px-2 py-1.5 text-sm";

export function ComposeForm({
  paperType,
  onPaperType,
  batches,
  batchId,
  onBatchId,
  subjects,
  subjectId,
  onSubjectId,
  classLabel,
  onClassLabel,
  examType,
  onExamType,
  mix,
  onMix,
  availableByDifficulty,
  onAutoPick,
  picking,
}: ComposeFormProps) {
  const total = DIFFICULTY_ORDER.reduce((s, d) => s + (mix[d] || 0), 0);
  const ready = Boolean(batchId && subjectId && total > 0);

  return (
    <aside className="flex flex-col gap-5 rounded-xl border bg-card p-4">
      {/* Paper type */}
      <section className="flex flex-col gap-1.5">
        <Label>Paper type</Label>
        <div className="flex gap-1.5">
          {PAPER_TYPES.map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => onPaperType(t)}
              title={PAPER_TYPE_HINT[t]}
              aria-pressed={paperType === t}
              className={`flex-1 rounded-md border px-2 py-1.5 text-sm transition-colors ${
                paperType === t
                  ? "border-primary bg-primary/10 font-medium"
                  : "border-border text-muted-foreground hover:bg-muted"
              }`}
            >
              {PAPER_TYPE_LABEL[t]}
            </button>
          ))}
        </div>
        <p className="text-[11px] text-muted-foreground">
          {PAPER_TYPE_HINT[paperType]}
        </p>
      </section>

      {/* Batch */}
      <section className="flex flex-col gap-1.5">
        <Label>Batch</Label>
        <select
          className={SELECT}
          value={batchId}
          onChange={(e) => onBatchId(e.target.value)}
        >
          <option value="">— select —</option>
          {batches.map((b) => (
            <option key={b.id} value={b.id}>
              {b.name}
            </option>
          ))}
        </select>
      </section>

      {/* Subject */}
      <section className="flex flex-col gap-1.5">
        <Label>Subject</Label>
        <select
          className={SELECT}
          value={subjectId}
          onChange={(e) => onSubjectId(e.target.value)}
        >
          <option value="">— select —</option>
          {subjects.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
      </section>

      {/* Class (optional) */}
      <section className="flex flex-col gap-1.5">
        <Label>Class (optional)</Label>
        <div className="flex flex-wrap gap-1.5">
          {CLASS_LABELS.map((c) => (
            <button
              key={c}
              type="button"
              onClick={() => onClassLabel(classLabel === c ? "" : c)}
              aria-pressed={classLabel === c}
              className={`rounded-full border px-2 py-0.5 text-[12px] transition-colors ${
                classLabel === c
                  ? "border-primary bg-primary/10"
                  : "border-border text-muted-foreground hover:bg-muted"
              }`}
            >
              {c === "drop" ? "Drop" : c}
            </button>
          ))}
        </div>
      </section>

      {/* Exam type (optional) */}
      <section className="flex flex-col gap-1.5">
        <Label>Exam type (optional)</Label>
        <div className="flex flex-wrap gap-1.5">
          {EXAM_TYPES.map((e) => (
            <button
              key={e}
              type="button"
              onClick={() => onExamType(examType === e ? "" : e)}
              aria-pressed={examType === e}
              className={`rounded-full border px-2 py-0.5 text-[12px] transition-colors ${
                examType === e
                  ? "border-primary bg-primary/10"
                  : "border-border text-muted-foreground hover:bg-muted"
              }`}
            >
              {EXAM_TYPE_LABEL[e]}
            </button>
          ))}
        </div>
      </section>

      {/* Difficulty mix */}
      <section className="flex flex-col gap-2">
        <Label>Question mix</Label>
        {DIFFICULTY_ORDER.map((d) => {
          const avail = availableByDifficulty[d];
          const want = mix[d] || 0;
          const short = avail != null && want > avail;
          return (
            <div key={d} className="flex items-center gap-2">
              <span className="w-16 text-sm">{DIFFICULTY_LABEL[d]}</span>
              <input
                type="number"
                min={0}
                value={want}
                onChange={(e) =>
                  onMix(d, Math.max(0, Number(e.target.value) || 0))
                }
                className="w-16 rounded-md border bg-background px-2 py-1 text-sm"
                aria-label={`${DIFFICULTY_LABEL[d]} count`}
              />
              <span
                className={`text-[11px] ${short ? "text-destructive" : "text-muted-foreground"}`}
              >
                {avail == null ? "…" : `${avail} available`}
              </span>
            </div>
          );
        })}
        <div className="flex items-center justify-between pt-1 text-sm">
          <span className="text-muted-foreground">Total</span>
          <span className="font-medium tabular-nums">{total}</span>
        </div>
      </section>

      <Button type="button" onClick={onAutoPick} disabled={!ready || picking}>
        {picking ? "Picking…" : "Auto-pick"}
      </Button>
    </aside>
  );
}
