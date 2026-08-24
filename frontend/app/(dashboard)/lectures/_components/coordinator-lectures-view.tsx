"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import apiClient from "@/services/api-client";
import { useBranchId } from "@/store/user-store";
import { useMyBatches } from "@/hooks/use-my-batches";
import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import { TableSkeleton } from "@/components/ui/skeleton";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useToast } from "@/components/ui/toast";
import {
  useBatchesForLectures,
  useCancelLecture,
  useClassrooms,
  useCreateLecture,
  useLectures,
  useTeachers,
} from "../_hooks/use-lectures";
import type {
  LectureCreate,
  LectureResponse,
  SubjectSummary,
} from "../_schemas/lecture";
import { CreateLectureDialog } from "./create-lecture-dialog";

const CONTROL = "h-9 rounded-lg border border-input bg-background px-3 text-sm";

function apiError(err: unknown): string {
  const e = err as { response?: { data?: { error?: { message?: string }; detail?: string } } };
  return e?.response?.data?.error?.message || e?.response?.data?.detail || "Action failed";
}

function fmt(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleString(undefined, {
        month: "short",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      });
}

function statusTone(s: string): "success" | "secondary" | "destructive" | "default" {
  if (s === "completed") return "success";
  if (s === "cancelled" || s === "no_show") return "destructive";
  if (s === "started" || s === "scheduled") return "default";
  return "secondary";
}

// A Floor Coordinator's Lectures page — scoped to their assigned batches. A lean
// view (schedule / list / cancel) instead of the institute-wide roster
// dashboard, which stays Manager/academic-head only. Lecture writes are
// server-enforced to the coordinator's batches regardless.
export function CoordinatorLecturesView() {
  const { branchId } = useBranchId();
  const toast = useToast();

  const myBatchesQuery = useMyBatches(true);
  const allBatchesQuery = useBatchesForLectures(branchId);
  const classroomsQuery = useClassrooms(branchId);
  const teachersQuery = useTeachers(branchId);
  const lecturesQuery = useLectures(branchId);
  const createLecture = useCreateLecture(branchId);
  const cancelLecture = useCancelLecture(branchId);

  const subjectsQuery = useQuery<SubjectSummary[]>({
    queryKey: ["subjects-all", branchId ?? ""],
    queryFn: async () => {
      const res = await apiClient.get<SubjectSummary[]>("/api/v1/academic/subjects", {
        params: { branch_id: branchId },
      });
      return res.data;
    },
    enabled: !!branchId,
  });

  const myBatchIds = useMemo(
    () => new Set((myBatchesQuery.data ?? []).map((b) => b.id)),
    [myBatchesQuery.data],
  );
  // Full BatchSummary objects (with course_id, needed by the create dialog) for
  // just the coordinator's assigned batches.
  const scopedBatches = useMemo(
    () => (allBatchesQuery.data ?? []).filter((b) => myBatchIds.has(b.id)),
    [allBatchesQuery.data, myBatchIds],
  );

  const batchName = useMemo(() => {
    const m = new Map<string, string>();
    for (const b of scopedBatches) m.set(b.id, b.name);
    return m;
  }, [scopedBatches]);
  const teacherName = useMemo(() => {
    const m = new Map<string, string>();
    for (const t of teachersQuery.data ?? []) m.set(t.id, `${t.first_name} ${t.last_name}`);
    return m;
  }, [teachersQuery.data]);
  const subjectName = useMemo(() => {
    const m = new Map<string, string>();
    for (const s of subjectsQuery.data ?? []) m.set(s.id, s.name);
    return m;
  }, [subjectsQuery.data]);

  const [filterBatch, setFilterBatch] = useState("");
  const [cancelTarget, setCancelTarget] = useState<LectureResponse | null>(null);

  const rows = useMemo(() => {
    let list = (lecturesQuery.data ?? []).filter((l) => myBatchIds.has(l.batch_id));
    if (filterBatch) list = list.filter((l) => l.batch_id === filterBatch);
    return [...list].sort((a, b) => b.scheduled_start.localeCompare(a.scheduled_start));
  }, [lecturesQuery.data, myBatchIds, filterBatch]);

  async function handleCreate(data: LectureCreate) {
    try {
      await createLecture.mutateAsync(data);
      toast.success("Lecture scheduled");
    } catch (err) {
      toast.error(apiError(err));
    }
  }

  async function handleCancel() {
    if (!cancelTarget) return;
    try {
      await cancelLecture.mutateAsync(cancelTarget.id);
      toast.success("Lecture cancelled");
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setCancelTarget(null);
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Lectures"
        description="Schedule and manage lectures for your assigned batches."
        actions={
          <CreateLectureDialog
            branchId={branchId}
            batches={scopedBatches}
            classrooms={classroomsQuery.data ?? []}
            onSubmit={handleCreate}
            isPending={createLecture.isPending}
          />
        }
      />

      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          Batch
          <select
            value={filterBatch}
            onChange={(e) => setFilterBatch(e.target.value)}
            className={CONTROL}
          >
            <option value="">All my batches</option>
            {scopedBatches.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      {lecturesQuery.isLoading ? (
        <TableSkeleton rows={8} />
      ) : scopedBatches.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          You have no assigned batches yet. Ask a Manager to assign your batches
          in Access Control.
        </p>
      ) : rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No lectures for your batches yet — use “Schedule lecture” to add one.
        </p>
      ) : (
        <div className="rounded-xl border ring-1 ring-foreground/10 overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>When</TableHead>
                <TableHead>Batch</TableHead>
                <TableHead className="hidden sm:table-cell">Subject</TableHead>
                <TableHead className="hidden md:table-cell">Teacher</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="w-20" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((l) => (
                <TableRow key={l.id}>
                  <TableCell className="whitespace-nowrap text-sm">
                    {fmt(l.scheduled_start)}
                  </TableCell>
                  <TableCell className="text-sm font-medium">
                    {batchName.get(l.batch_id) ?? "—"}
                  </TableCell>
                  <TableCell className="hidden sm:table-cell text-sm text-muted-foreground">
                    {subjectName.get(l.subject_id) ?? "—"}
                  </TableCell>
                  <TableCell className="hidden md:table-cell text-sm text-muted-foreground">
                    {teacherName.get(l.actual_teacher_id ?? l.teacher_id) ?? "—"}
                  </TableCell>
                  <TableCell>
                    <Badge variant={statusTone(l.lecture_status)}>
                      {l.lecture_status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    {l.lecture_status === "scheduled" && (
                      <Button
                        type="button"
                        size="sm"
                        variant="destructive"
                        onClick={() => setCancelTarget(l)}
                      >
                        Cancel
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <ConfirmDialog
        open={!!cancelTarget}
        onOpenChange={(o) => !o && setCancelTarget(null)}
        title="Cancel this lecture?"
        description={
          cancelTarget
            ? `${batchName.get(cancelTarget.batch_id) ?? "Lecture"} · ${fmt(cancelTarget.scheduled_start)} will be marked cancelled.`
            : ""
        }
        confirmLabel="Cancel lecture"
        onConfirm={handleCancel}
      />
    </div>
  );
}
