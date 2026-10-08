"use client";

import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogTrigger,
  DialogPopup,
  DialogTitle,
  DialogDescription,
  DialogClose,
} from "@/components/ui/dialog";
import {
  useBatchesForLectures,
  useSubjectsByCourse,
} from "../../lectures/_hooks/use-lectures";
import {
  OMR_TYPES,
  QUESTION_TYPES,
  type ScheduleTestInput,
} from "../_schemas/test-portal";

const SELECT_CLASS =
  "flex h-9 w-full rounded-lg border border-input bg-background px-3 text-sm";

type Mode = "subject" | "omr";

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function isJeeBatchName(name: string): boolean {
  return /\bjee\b/i.test(name);
}

interface Props {
  branchId: string | undefined;
  onSubmit: (data: ScheduleTestInput) => Promise<void> | void;
  isPending: boolean;
}

export function ScheduleTestDialog({ branchId, onSubmit, isPending }: Props) {
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<Mode>("subject");
  const [name, setName] = useState("");
  const [date, setDate] = useState(today());
  const [error, setError] = useState("");

  // OMR mode
  const [batchId, setBatchId] = useState("");
  const [subjectIds, setSubjectIds] = useState<string[]>([]);
  const [totalMarks, setTotalMarks] = useState("100");
  const [omrType, setOmrType] = useState<string>("100Q");

  // Per-subject mode
  const [batchIds, setBatchIds] = useState<string[]>([]);
  const [subjectMarks, setSubjectMarks] = useState<Record<string, string>>({});
  const [questionType, setQuestionType] = useState("NA");

  const batchesQuery = useBatchesForLectures(branchId);
  const batches = useMemo(() => batchesQuery.data ?? [], [batchesQuery.data]);

  // Subjects come from the (first) selected batch's course for both modes.
  const courseBatchId = mode === "omr" ? batchId : batchIds[0];
  const courseId = batches.find((b) => b.id === courseBatchId)?.course_id;
  const subjectsQuery = useSubjectsByCourse(branchId, courseId);
  const subjects = subjectsQuery.data ?? [];

  const anyJee = useMemo(
    () => batchIds.some((id) => isJeeBatchName(batches.find((b) => b.id === id)?.name ?? "")),
    [batchIds, batches],
  );

  function reset() {
    setMode("subject");
    setName("");
    setDate(today());
    setError("");
    setBatchId("");
    setSubjectIds([]);
    setTotalMarks("100");
    setOmrType("100Q");
    setBatchIds([]);
    setSubjectMarks({});
    setQuestionType("NA");
  }

  function pickOmrBatch(id: string) {
    setBatchId(id);
    setSubjectIds([]); // a new course has its own subjects
  }

  function toggleOmrSubject(id: string) {
    setSubjectIds((prev) =>
      prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id],
    );
  }

  function toggleBatch(id: string) {
    setBatchIds((prev) => {
      const next = prev.includes(id) ? prev.filter((b) => b !== id) : [...prev, id];
      if (next[0] !== prev[0]) setSubjectMarks({}); // course may change
      return next;
    });
  }

  function toggleSubjectMark(id: string) {
    setSubjectMarks((prev) => {
      const next = { ...prev };
      if (id in next) delete next[id];
      else next[id] = "80";
      return next;
    });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return setError("Test name is required");
    const scheduled_at = date ? new Date(date).toISOString() : null;

    try {
      if (mode === "omr") {
        if (!batchId) return setError("Pick a batch");
        if (subjectIds.length === 0) return setError("Pick at least one subject");
        const marks = Number(totalMarks);
        if (!Number.isFinite(marks) || marks <= 0) return setError("Total marks must be > 0");
        await onSubmit({
          name: name.trim(),
          batch_id: batchId,
          subject_ids: subjectIds,
          scheduled_at,
          total_marks: marks,
          omr_type: omrType,
        });
      } else {
        if (batchIds.length === 0) return setError("Pick at least one batch");
        const entries = Object.entries(subjectMarks);
        if (entries.length === 0) return setError("Pick at least one subject");
        const subjectsPayload = [];
        for (const [sid, raw] of entries) {
          const m = Number(raw);
          if (!Number.isFinite(m) || m <= 0)
            return setError("Each subject needs total marks > 0");
          subjectsPayload.push({ subject_id: sid, total_marks: m });
        }
        await onSubmit({
          name: name.trim(),
          batch_ids: batchIds,
          subjects: subjectsPayload,
          scheduled_at,
          total_marks: subjectsPayload.reduce((a, s) => a + s.total_marks, 0),
          question_type: anyJee ? questionType : "NA",
        });
      }
      reset();
      setOpen(false);
    } catch (err) {
      const e2 = err as {
        response?: { data?: { detail?: string; error?: { message?: string } } };
      };
      setError(
        e2?.response?.data?.error?.message ||
          e2?.response?.data?.detail ||
          "Failed to schedule test",
      );
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) reset();
      }}
    >
      <DialogTrigger render={<Button onClick={() => setOpen(true)}>Schedule test</Button>} />
      <DialogPopup className="max-w-xl">
        <DialogTitle>Schedule a test</DialogTitle>
        <DialogDescription>
          Choose how marks will come in, pick the batches and subjects, then upload
          results once the test is done.
        </DialogDescription>
        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-4">
          {error && <p className="text-sm text-destructive">{error}</p>}

          {/* Marks-entry mode */}
          <div className="flex flex-col gap-1.5">
            <Label>Marks entry</Label>
            <div className="inline-flex rounded-lg border p-0.5 text-sm w-fit">
              {(["subject", "omr"] as Mode[]).map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => setMode(m)}
                  aria-pressed={mode === m}
                  className={`rounded-md px-3 py-1 transition-colors ${
                    mode === m
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:bg-muted"
                  }`}
                >
                  {m === "subject" ? "Per-subject CSV" : "OMR scan (ZipGrade)"}
                </button>
              ))}
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="test_name">Test name *</Label>
            <Input
              id="test_name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="11th CET PCM Test — 31 Aug"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="test_date">Date</Label>
            <Input
              id="test_date"
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
            />
          </div>

          {mode === "omr" ? (
            <>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="test_batch">Batch *</Label>
                <select
                  id="test_batch"
                  value={batchId}
                  onChange={(e) => pickOmrBatch(e.target.value)}
                  className={SELECT_CLASS}
                >
                  <option value="">Select a batch…</option>
                  {batches.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>Subjects covered *</Label>
                {!batchId ? (
                  <p className="text-xs text-muted-foreground">Pick a batch first.</p>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {subjects.map((s) => {
                      const on = subjectIds.includes(s.id);
                      return (
                        <button
                          key={s.id}
                          type="button"
                          onClick={() => toggleOmrSubject(s.id)}
                          aria-pressed={on}
                          className={`rounded-md border px-2.5 py-1 text-[13px] transition-colors ${
                            on
                              ? "border-primary bg-primary/10 text-foreground"
                              : "border-input text-muted-foreground hover:bg-muted"
                          }`}
                        >
                          {s.name}
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="test_marks">Total marks *</Label>
                  <Input
                    id="test_marks"
                    type="number"
                    min={1}
                    value={totalMarks}
                    onChange={(e) => setTotalMarks(e.target.value)}
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="test_omr">OMR sheet type</Label>
                  <select
                    id="test_omr"
                    value={omrType}
                    onChange={(e) => setOmrType(e.target.value)}
                    className={SELECT_CLASS}
                  >
                    {OMR_TYPES.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </>
          ) : (
            <>
              <div className="flex flex-col gap-1.5">
                <Label>Batches * (one or many)</Label>
                <div className="flex flex-wrap gap-2">
                  {batches.map((b) => {
                    const on = batchIds.includes(b.id);
                    return (
                      <button
                        key={b.id}
                        type="button"
                        onClick={() => toggleBatch(b.id)}
                        aria-pressed={on}
                        className={`rounded-md border px-2.5 py-1 text-[13px] transition-colors ${
                          on
                            ? "border-primary bg-primary/10 text-foreground"
                            : "border-input text-muted-foreground hover:bg-muted"
                        }`}
                      >
                        {b.name}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="flex flex-col gap-1.5">
                <Label>Subjects &amp; total marks *</Label>
                {batchIds.length === 0 ? (
                  <p className="text-xs text-muted-foreground">Pick a batch first.</p>
                ) : (
                  <div className="flex flex-col gap-2">
                    {subjects.map((s) => {
                      const on = s.id in subjectMarks;
                      return (
                        <div key={s.id} className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() => toggleSubjectMark(s.id)}
                            aria-pressed={on}
                            className={`flex-1 rounded-md border px-2.5 py-1.5 text-left text-[13px] transition-colors ${
                              on
                                ? "border-primary bg-primary/10 text-foreground"
                                : "border-input text-muted-foreground hover:bg-muted"
                            }`}
                          >
                            {s.name}
                          </button>
                          {on && (
                            <Input
                              type="number"
                              min={1}
                              aria-label={`${s.name} total marks`}
                              className="w-24"
                              value={subjectMarks[s.id]}
                              onChange={(e) =>
                                setSubjectMarks((prev) => ({
                                  ...prev,
                                  [s.id]: e.target.value,
                                }))
                              }
                            />
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Question Type — only for JEE batches (spec Section 1). */}
              {anyJee && (
                <div className="flex flex-col gap-1.5">
                  <Label>Question type (JEE)</Label>
                  <div className="flex flex-wrap gap-4 text-sm">
                    {QUESTION_TYPES.map((q) => (
                      <label key={q.value} className="flex items-center gap-1.5">
                        <input
                          type="radio"
                          name="question_type"
                          value={q.value}
                          checked={questionType === q.value}
                          onChange={() => setQuestionType(q.value)}
                        />
                        {q.label}
                      </label>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <DialogClose render={<Button variant="outline" type="button">Cancel</Button>} />
            <Button type="submit" disabled={isPending}>
              {isPending ? "Scheduling…" : "Schedule"}
            </Button>
          </div>
        </form>
      </DialogPopup>
    </Dialog>
  );
}
