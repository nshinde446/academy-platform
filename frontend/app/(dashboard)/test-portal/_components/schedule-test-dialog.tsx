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
import { OMR_TYPES, type ScheduleTestInput } from "../_schemas/test-portal";

const SELECT_CLASS =
  "flex h-9 w-full rounded-lg border border-input bg-background px-3 text-sm";

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

interface Props {
  branchId: string | undefined;
  onSubmit: (data: ScheduleTestInput) => Promise<void> | void;
  isPending: boolean;
}

export function ScheduleTestDialog({ branchId, onSubmit, isPending }: Props) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [batchId, setBatchId] = useState("");
  const [subjectIds, setSubjectIds] = useState<string[]>([]);
  const [date, setDate] = useState(today());
  const [totalMarks, setTotalMarks] = useState("100");
  const [omrType, setOmrType] = useState<string>("100Q");
  const [error, setError] = useState("");

  const batchesQuery = useBatchesForLectures(branchId);
  const batches = useMemo(() => batchesQuery.data ?? [], [batchesQuery.data]);
  const selectedBatch = batches.find((b) => b.id === batchId);
  const subjectsQuery = useSubjectsByCourse(branchId, selectedBatch?.course_id);
  const subjects = subjectsQuery.data ?? [];

  function pickBatch(id: string) {
    setBatchId(id);
    setSubjectIds([]); // a new batch's course has its own subjects
  }

  function reset() {
    setName("");
    setBatchId("");
    setSubjectIds([]);
    setDate(today());
    setTotalMarks("100");
    setOmrType("100Q");
    setError("");
  }

  function toggleSubject(id: string) {
    setSubjectIds((prev) =>
      prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id],
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return setError("Test name is required");
    if (!batchId) return setError("Pick a batch");
    if (subjectIds.length === 0) return setError("Pick at least one subject");
    const marks = Number(totalMarks);
    if (!Number.isFinite(marks) || marks <= 0) return setError("Total marks must be > 0");
    try {
      await onSubmit({
        name: name.trim(),
        batch_id: batchId,
        subject_ids: subjectIds,
        scheduled_at: date ? new Date(date).toISOString() : null,
        total_marks: marks,
        omr_type: omrType,
      });
      reset();
      setOpen(false);
    } catch (err) {
      const e2 = err as { response?: { data?: { detail?: string; error?: { message?: string } } } };
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
          Pick the batch and subjects covered, set the total marks and OMR sheet
          type, then upload the ZipGrade CSV once scanning is done.
        </DialogDescription>
        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-4">
          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="test_name">Test name *</Label>
            <Input
              id="test_name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="11th CET PCM Test — 31 Aug"
            />
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="test_batch">Batch *</Label>
              <select
                id="test_batch"
                value={batchId}
                onChange={(e) => pickBatch(e.target.value)}
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
              <Label htmlFor="test_date">Date</Label>
              <Input
                id="test_date"
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
              />
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label>Subjects covered *</Label>
            {!selectedBatch ? (
              <p className="text-xs text-muted-foreground">Pick a batch first.</p>
            ) : subjects.length === 0 ? (
              <p className="text-xs text-muted-foreground">
                No subjects for this course.
              </p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {subjects.map((s) => {
                  const on = subjectIds.includes(s.id);
                  return (
                    <button
                      key={s.id}
                      type="button"
                      onClick={() => toggleSubject(s.id)}
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
