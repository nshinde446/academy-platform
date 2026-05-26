"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogPopup,
  DialogTitle,
  DialogDescription,
  DialogClose,
} from "@/components/ui/dialog";
import {
  BLOOMS,
  DIFFICULTIES,
  type Difficulty,
  type Blooms,
  type QuestionResponse,
  type QuestionUpdate,
} from "../_schemas/question";

interface EditQuestionDialogProps {
  question: QuestionResponse | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: QuestionUpdate) => Promise<void> | void;
  isPending: boolean;
}

const SELECT_CLASS =
  "flex h-9 w-full rounded-lg border border-input bg-background px-3 text-sm";

function buildForm(q: QuestionResponse | null) {
  return {
    content: q?.content ?? "",
    option_a: q?.options?.A ?? "",
    option_b: q?.options?.B ?? "",
    option_c: q?.options?.C ?? "",
    option_d: q?.options?.D ?? "",
    correct_answer: (q?.correct_answer ?? "").toUpperCase(),
    explanation: q?.explanation ?? "",
    difficulty: (q?.difficulty ?? "MEDIUM") as Difficulty,
    blooms_taxonomy: (q?.blooms_taxonomy ?? "APPLY") as Blooms,
  };
}

export function EditQuestionDialog({
  question,
  open,
  onOpenChange,
  onSubmit,
  isPending,
}: EditQuestionDialogProps) {
  const [form, setForm] = useState(() => buildForm(question));
  const [error, setError] = useState("");

  useEffect(() => {
    if (open) {
      setForm(buildForm(question));
      setError("");
    }
  }, [open, question]);

  async function handleSave(approve: boolean) {
    setError("");
    if (!form.content.trim()) {
      setError("Question text is required");
      return;
    }
    const correct = form.correct_answer.trim().toUpperCase();
    if (correct && !["A", "B", "C", "D"].includes(correct)) {
      setError("Correct answer must be A, B, C, or D (or empty)");
      return;
    }

    const data: QuestionUpdate = {
      content: form.content,
      options: {
        A: form.option_a,
        B: form.option_b,
        C: form.option_c,
        D: form.option_d,
      },
      correct_answer: correct,
      explanation: form.explanation || null,
      difficulty: form.difficulty,
      blooms_taxonomy: form.blooms_taxonomy,
    };
    if (approve) data.review_status = "approved";

    try {
      await onSubmit(data);
      onOpenChange(false);
    } catch (err: any) {
      setError(
        err?.response?.data?.error?.message ||
          err?.response?.data?.detail ||
          "Failed to save question",
      );
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogPopup className="max-w-3xl">
        <DialogTitle>Edit question</DialogTitle>
        <DialogDescription>
          LaTeX math goes inside $…$ (inline) or $$…$$ (display). The
          preview on the card shows what students will see. Click
          &quot;Save &amp; approve&quot; when the question is ready.
        </DialogDescription>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSave(false);
          }}
          className="mt-4 flex flex-col gap-4"
        >
          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="q_content">Question text *</Label>
            <textarea
              id="q_content"
              value={form.content}
              onChange={(e) =>
                setForm({ ...form, content: e.target.value })
              }
              rows={4}
              className="rounded-lg border border-input bg-background px-3 py-2 text-sm"
              required
            />
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {(["A", "B", "C", "D"] as const).map((key) => (
              <div key={key} className="flex flex-col gap-1.5">
                <Label htmlFor={`q_opt_${key}`}>Option {key}</Label>
                <Input
                  id={`q_opt_${key}`}
                  value={(form as any)[`option_${key.toLowerCase()}`]}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      [`option_${key.toLowerCase()}`]: e.target.value,
                    })
                  }
                />
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="q_correct">Correct answer</Label>
              <select
                id="q_correct"
                value={form.correct_answer}
                onChange={(e) =>
                  setForm({
                    ...form,
                    correct_answer: e.target.value.toUpperCase(),
                  })
                }
                className={SELECT_CLASS}
              >
                <option value="">— not set</option>
                {(["A", "B", "C", "D"] as const).map((k) => (
                  <option key={k} value={k}>
                    {k}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="q_difficulty">Difficulty</Label>
              <select
                id="q_difficulty"
                value={form.difficulty}
                onChange={(e) =>
                  setForm({
                    ...form,
                    difficulty: e.target.value as Difficulty,
                  })
                }
                className={SELECT_CLASS}
              >
                {DIFFICULTIES.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="q_blooms">Bloom&apos;s</Label>
              <select
                id="q_blooms"
                value={form.blooms_taxonomy}
                onChange={(e) =>
                  setForm({
                    ...form,
                    blooms_taxonomy: e.target.value as Blooms,
                  })
                }
                className={SELECT_CLASS}
              >
                {BLOOMS.map((b) => (
                  <option key={b} value={b}>
                    {b}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="q_explanation">Explanation</Label>
            <textarea
              id="q_explanation"
              value={form.explanation}
              onChange={(e) =>
                setForm({ ...form, explanation: e.target.value })
              }
              rows={3}
              className="rounded-lg border border-input bg-background px-3 py-2 text-sm"
            />
          </div>

          <div className="flex flex-wrap justify-end gap-2 pt-2">
            <DialogClose
              render={
                <Button variant="outline" type="button">
                  Cancel
                </Button>
              }
            />
            <Button
              type="button"
              variant="outline"
              onClick={() => handleSave(false)}
              disabled={isPending}
            >
              {isPending ? "Saving…" : "Save"}
            </Button>
            <Button
              type="button"
              onClick={() => handleSave(true)}
              disabled={isPending}
            >
              {isPending ? "Saving…" : "Save & approve"}
            </Button>
          </div>
        </form>
      </DialogPopup>
    </Dialog>
  );
}
