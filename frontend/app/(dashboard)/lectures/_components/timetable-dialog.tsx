"use client";

import { useEffect, useMemo, useState } from "react";
import { useQueries } from "@tanstack/react-query";
import apiClient from "@/services/api-client";
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
  teacherKeys,
  useBatchTimetable,
  useGenerateSchedule,
  useSetBatchTimetable,
  useSubjectsByCourse,
} from "../_hooks/use-lectures";
import type {
  BatchSummary,
  ClassroomSummary,
  GenerateScheduleSummary,
  TeacherSummary,
  TimetableSlot,
} from "../_schemas/lecture";

const SELECT_CLASS =
  "h-9 rounded-lg border border-input bg-background px-2 text-sm";

// Mon=0 … Sun=6 to match the backend (Python date.weekday()).
const DAYS = [
  { value: 0, label: "Mon" },
  { value: 1, label: "Tue" },
  { value: 2, label: "Wed" },
  { value: 3, label: "Thu" },
  { value: 4, label: "Fri" },
  { value: 5, label: "Sat" },
  { value: 6, label: "Sun" },
];

interface TimetableDialogProps {
  branchId: string | undefined;
  batches: BatchSummary[];
  teachers: TeacherSummary[];
  classrooms: ClassroomSummary[];
  /** Controlled mode (driven from the page's "Manage" menu). */
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  /** Hide the built-in trigger button when the dialog is opened externally. */
  hideTrigger?: boolean;
}

function todayIso(): string {
  const d = new Date();
  const shifted = new Date(d.getTime() - d.getTimezoneOffset() * 60_000);
  return shifted.toISOString().slice(0, 10);
}

function addDaysIso(iso: string, days: number): string {
  const d = new Date(`${iso}T00:00:00`);
  d.setDate(d.getDate() + days);
  const shifted = new Date(d.getTime() - d.getTimezoneOffset() * 60_000);
  return shifted.toISOString().slice(0, 10);
}

function emptySlot(): TimetableSlot {
  return {
    day_of_week: 0,
    start_time: "09:00",
    end_time: "10:00",
    subject_id: null,
    teacher_id: null,
    classroom_id: null,
    delivery_mode: "offline",
  };
}

export function TimetableDialog({
  branchId,
  batches,
  classrooms,
  open: openProp,
  onOpenChange,
  hideTrigger,
}: TimetableDialogProps) {
  const [openInternal, setOpenInternal] = useState(false);
  const open = openProp ?? openInternal;
  const setOpen = (v: boolean) => {
    if (openProp === undefined) setOpenInternal(v);
    onOpenChange?.(v);
  };
  const [batchId, setBatchId] = useState("");
  const [slots, setSlots] = useState<TimetableSlot[]>([]);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [fromDate, setFromDate] = useState(todayIso());
  const [toDate, setToDate] = useState(addDaysIso(todayIso(), 6));
  const [genAllBatches, setGenAllBatches] = useState(false);
  const [genResult, setGenResult] = useState<GenerateScheduleSummary | null>(
    null
  );

  const batch = batches.find((b) => b.id === batchId);
  const timetableQuery = useBatchTimetable(branchId, batchId || undefined);
  const subjectsQuery = useSubjectsByCourse(branchId, batch?.course_id);
  const setMutation = useSetBatchTimetable(branchId);
  const genMutation = useGenerateSchedule(branchId);

  const subjects = subjectsQuery.data ?? [];

  // Subject→Teacher lock: each slot's teacher dropdown must list only teachers
  // assigned to that slot's subject (not every branch teacher). Fetch the
  // by-subject teacher set for each distinct subject referenced by the slots.
  const distinctSubjectIds = useMemo(
    () =>
      Array.from(
        new Set(slots.map((s) => s.subject_id).filter(Boolean))
      ) as string[],
    [slots]
  );
  const teacherQueries = useQueries({
    queries: distinctSubjectIds.map((sid) => ({
      queryKey: teacherKeys.bySubject(branchId ?? "", sid),
      queryFn: async () => {
        const res = await apiClient.get<TeacherSummary[]>(
          "/api/v1/teachers/by-subject",
          { params: { branch_id: branchId, subject_id: sid } }
        );
        return res.data;
      },
      enabled: !!branchId && !!sid,
    })),
  });
  const teachersBySubject = useMemo(() => {
    const map = new Map<string, TeacherSummary[]>();
    distinctSubjectIds.forEach((sid, i) => {
      map.set(sid, (teacherQueries[i]?.data as TeacherSummary[] | undefined) ?? []);
    });
    return map;
  }, [distinctSubjectIds, teacherQueries]);

  // Load the saved slots whenever a batch's timetable arrives.
  useEffect(() => {
    if (timetableQuery.data) {
      setSlots(
        timetableQuery.data.map((s) => ({
          day_of_week: s.day_of_week,
          start_time: s.start_time,
          end_time: s.end_time,
          subject_id: s.subject_id,
          teacher_id: s.teacher_id,
          classroom_id: s.classroom_id,
          delivery_mode: s.delivery_mode,
        }))
      );
    }
  }, [timetableQuery.data]);

  function update(i: number, patch: Partial<TimetableSlot>) {
    setSlots((prev) =>
      prev.map((s, idx) => (idx === i ? { ...s, ...patch } : s))
    );
    setSaved(false);
  }

  async function handleSave() {
    setError("");
    setSaved(false);
    if (!batchId) {
      setError("Pick a batch first.");
      return;
    }
    try {
      await setMutation.mutateAsync({ batchId, slots });
      setSaved(true);
    } catch (err: any) {
      setError(
        err?.response?.data?.error?.message ||
          err?.response?.data?.detail ||
          "Save failed"
      );
    }
  }

  async function handleGenerate() {
    setError("");
    setGenResult(null);
    try {
      const summary = await genMutation.mutateAsync({
        fromDate,
        toDate,
        // "All batches" omits batch scope so the backend generates from every
        // batch's saved timetable in one run.
        batchId: genAllBatches ? undefined : batchId || undefined,
      });
      setGenResult(summary);
    } catch (err: any) {
      setError(
        err?.response?.data?.error?.message ||
          err?.response?.data?.detail ||
          "Generate failed"
      );
    }
  }

  function reset() {
    setBatchId("");
    setSlots([]);
    setError("");
    setSaved(false);
    setGenResult(null);
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(isOpen) => {
        setOpen(isOpen);
        if (!isOpen) reset();
      }}
    >
      {!hideTrigger && (
        <DialogTrigger
          render={
            <Button variant="outline" onClick={() => setOpen(true)}>
              Weekly Timetable
            </Button>
          }
        />
      )}
      <DialogPopup className="max-w-3xl">
        <DialogTitle>Weekly Timetable</DialogTitle>
        <DialogDescription>
          Define a batch&apos;s recurring weekly classes once, then generate the
          actual scheduled lectures for any date range. Re-generating is safe —
          slots that would clash are skipped.
        </DialogDescription>

        <div className="mt-4 flex flex-col gap-4">
          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="tt_batch">Batch *</Label>
            <select
              id="tt_batch"
              value={batchId}
              onChange={(e) => {
                setBatchId(e.target.value);
                setSaved(false);
                setGenResult(null);
              }}
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

          {batchId && (
            <>
              {/* Slot editor */}
              <div className="flex flex-col gap-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">
                    Weekly slots ({slots.length})
                  </span>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => setSlots((p) => [...p, emptySlot()])}
                  >
                    + Add slot
                  </Button>
                </div>

                {slots.length === 0 ? (
                  <p className="text-sm text-muted-foreground italic">
                    No weekly classes yet. Add a slot to build the pattern.
                  </p>
                ) : (
                  <div className="flex flex-col gap-2">
                    {slots.map((s, i) => {
                      // Teacher options are scoped to the slot's subject
                      // (Subject→Teacher lock) — never the full teacher list.
                      const slotTeachers = s.subject_id
                        ? teachersBySubject.get(s.subject_id) ?? []
                        : [];
                      const teacherPlaceholder = !s.subject_id
                        ? "Pick subject first"
                        : slotTeachers.length
                          ? "Teacher…"
                          : "No teacher for this subject";
                      return (
                        <div
                          key={i}
                          className="flex flex-wrap items-center gap-2 rounded-lg border p-2"
                          data-testid="timetable-slot"
                        >
                          <select
                            aria-label={`Day for slot ${i + 1}`}
                            value={s.day_of_week}
                            onChange={(e) =>
                              update(i, { day_of_week: Number(e.target.value) })
                            }
                            className={`${SELECT_CLASS} w-[88px] shrink-0`}
                          >
                            {DAYS.map((d) => (
                              <option key={d.value} value={d.value}>
                                {d.label}
                              </option>
                            ))}
                          </select>
                          <Input
                            aria-label={`Start for slot ${i + 1}`}
                            type="time"
                            value={s.start_time}
                            onChange={(e) =>
                              update(i, { start_time: e.target.value })
                            }
                            className="h-9 w-[116px] shrink-0"
                          />
                          <Input
                            aria-label={`End for slot ${i + 1}`}
                            type="time"
                            value={s.end_time}
                            onChange={(e) =>
                              update(i, { end_time: e.target.value })
                            }
                            className="h-9 w-[116px] shrink-0"
                          />
                          <select
                            aria-label={`Subject for slot ${i + 1}`}
                            value={s.subject_id ?? ""}
                            onChange={(e) =>
                              // Changing subject invalidates the picked teacher —
                              // clear it so only a valid teacher can be re-picked.
                              update(i, {
                                subject_id: e.target.value || null,
                                teacher_id: null,
                              })
                            }
                            className={`${SELECT_CLASS} min-w-[140px] flex-1`}
                          >
                            <option value="">Subject…</option>
                            {subjects.map((sub) => (
                              <option key={sub.id} value={sub.id}>
                                {sub.name}
                              </option>
                            ))}
                          </select>
                          <select
                            aria-label={`Teacher for slot ${i + 1}`}
                            value={s.teacher_id ?? ""}
                            disabled={!s.subject_id}
                            onChange={(e) =>
                              update(i, { teacher_id: e.target.value || null })
                            }
                            className={`${SELECT_CLASS} min-w-[140px] flex-1 disabled:opacity-60`}
                          >
                            <option value="">{teacherPlaceholder}</option>
                            {slotTeachers.map((t) => (
                              <option key={t.id} value={t.id}>
                                {t.first_name} {t.last_name}
                              </option>
                            ))}
                          </select>
                          <select
                            aria-label={`Classroom for slot ${i + 1}`}
                            value={s.classroom_id ?? ""}
                            onChange={(e) =>
                              update(i, { classroom_id: e.target.value || null })
                            }
                            className={`${SELECT_CLASS} min-w-[140px] flex-1`}
                          >
                            <option value="">Room…</option>
                            {classrooms.map((c) => (
                              <option key={c.id} value={c.id}>
                                {c.name}
                              </option>
                            ))}
                          </select>
                          <Button
                            type="button"
                            size="sm"
                            variant="destructive"
                            onClick={() =>
                              setSlots((p) => p.filter((_, idx) => idx !== i))
                            }
                            aria-label={`Remove slot ${i + 1}`}
                            className="shrink-0"
                          >
                            Remove
                          </Button>
                        </div>
                      );
                    })}
                  </div>
                )}

                <div className="flex items-center gap-2">
                  <Button
                    type="button"
                    onClick={handleSave}
                    disabled={setMutation.isPending}
                  >
                    {setMutation.isPending ? "Saving…" : "Save timetable"}
                  </Button>
                  {saved && (
                    <span className="text-sm text-emerald-600 dark:text-emerald-400">
                      Saved.
                    </span>
                  )}
                </div>
              </div>

              {/* Generate */}
              <div className="flex flex-col gap-2 border-t pt-4">
                <span className="text-sm font-medium">
                  Generate lectures from this pattern
                </span>
                <div className="flex flex-wrap items-end gap-3">
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="tt_from">From *</Label>
                    <Input
                      id="tt_from"
                      type="date"
                      value={fromDate}
                      onChange={(e) => setFromDate(e.target.value)}
                      className="w-40"
                    />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="tt_to">To *</Label>
                    <Input
                      id="tt_to"
                      type="date"
                      value={toDate}
                      onChange={(e) => setToDate(e.target.value)}
                      className="w-40"
                    />
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={handleGenerate}
                    disabled={genMutation.isPending || !fromDate || !toDate}
                  >
                    {genMutation.isPending ? "Generating…" : "Generate"}
                  </Button>
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={genAllBatches}
                      onChange={(e) => setGenAllBatches(e.target.checked)}
                      className="h-4 w-4 rounded border-input"
                    />
                    All batches
                  </label>
                </div>
                <p className="text-[11px] text-muted-foreground">
                  {genAllBatches
                    ? "Generates from every batch's saved timetable across the date range."
                    : "Generates from this batch's timetable. Tick “All batches” to run the whole branch."}
                </p>

                {genResult && (
                  <div
                    className={
                      "rounded-lg border p-3 text-sm " +
                      (genResult.skipped === 0
                        ? "border-emerald-500/40 bg-emerald-500/10"
                        : "border-amber-500/40 bg-amber-500/10")
                    }
                  >
                    <p>
                      <span className="font-medium">{genResult.generated}</span>{" "}
                      lecture(s) generated
                      {genResult.skipped > 0 && (
                        <>
                          {" · "}
                          <span className="font-medium">
                            {genResult.skipped}
                          </span>{" "}
                          skipped
                        </>
                      )}
                      .
                    </p>
                    {genResult.errors.length > 0 && (
                      <ul className="mt-2 list-disc pl-5 text-xs text-muted-foreground">
                        {genResult.errors.slice(0, 8).map((e, i) => (
                          <li key={i}>{e}</li>
                        ))}
                        {genResult.errors.length > 8 && (
                          <li>…and {genResult.errors.length - 8} more</li>
                        )}
                      </ul>
                    )}
                  </div>
                )}
              </div>
            </>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <DialogClose
              render={
                <Button variant="outline" type="button">
                  Close
                </Button>
              }
            />
          </div>
        </div>
      </DialogPopup>
    </Dialog>
  );
}
