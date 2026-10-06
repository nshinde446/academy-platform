"use client";

import { useState } from "react";
import { useUserStore } from "@/store/user-store";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { useTeachers } from "../../teachers/_hooks/use-teachers";
import {
  useSubjectCatalog,
  useSecondaryForBatch,
  useAssignSecondarySubjects,
  useRemoveSecondarySubject,
} from "../../teachers/_hooks/use-secondary-subjects";

const SELECT_CLASS =
  "h-9 rounded-md border border-input bg-background px-3 text-sm";

/**
 * Batch-side view of the flexible teacher-subject assignment: which teachers
 * teach an EXTRA subject for this batch (on top of their core subject). Same
 * backend as the teacher page; scoped to one batch.
 */
export function SecondaryTeachers({ batchId }: { batchId: string }) {
  const user = useUserStore((s) => s.user);
  const branchId = user?.branch_roles?.[0]?.branch_id;

  const teachersQuery = useTeachers(branchId);
  const catalogQuery = useSubjectCatalog(branchId);
  const rowsQuery = useSecondaryForBatch(branchId, batchId);
  const assign = useAssignSecondarySubjects(branchId);
  const remove = useRemoveSecondarySubject(branchId);

  const teachers = teachersQuery.data ?? [];
  const catalog = catalogQuery.data ?? [];
  const rows = rowsQuery.data ?? [];

  const [teacherId, setTeacherId] = useState("");
  const [subject, setSubject] = useState("");
  const [error, setError] = useState("");

  async function handleAdd() {
    setError("");
    if (!teacherId || !subject) {
      setError("Pick a teacher and a subject.");
      return;
    }
    try {
      await assign.mutateAsync({ teacherId, subjectName: subject, batchIds: [batchId] });
      setTeacherId("");
      setSubject("");
    } catch {
      setError("Could not add the assignment.");
    }
  }

  return (
    <div className="flex flex-col gap-3 rounded-md border p-3">
      <div>
        <h3 className="text-sm font-semibold">Extra teachers (secondary subjects)</h3>
        <p className="text-xs text-muted-foreground">
          Teachers who teach an additional subject for this batch. Their core
          subject is unaffected.
        </p>
      </div>

      {rows.length === 0 ? (
        <p className="text-xs text-muted-foreground">None for this batch.</p>
      ) : (
        <ul className="flex flex-col gap-1.5">
          {rows.map((r) => (
            <li key={r.id} className="flex items-center gap-2 text-sm">
              <span className="font-medium">{r.teacher_name}</span>
              <span className="text-xs text-muted-foreground">teaches</span>
              <Badge variant="secondary">{r.subject_name}</Badge>
              <button
                type="button"
                aria-label={`Remove ${r.subject_name} for ${r.teacher_name}`}
                className="ml-auto text-xs text-muted-foreground hover:text-destructive"
                onClick={() => remove.mutate(r.id)}
                disabled={remove.isPending}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}

      {error && <p className="text-sm text-destructive">{error}</p>}
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="st_teacher">Teacher</Label>
          <select
            id="st_teacher"
            value={teacherId}
            onChange={(e) => setTeacherId(e.target.value)}
            className={SELECT_CLASS}
          >
            <option value="">Select…</option>
            {teachers.map((t) => (
              <option key={t.id} value={t.id}>
                {t.first_name} {t.last_name}
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="st_subject">Subject</Label>
          <select
            id="st_subject"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            className={SELECT_CLASS}
          >
            <option value="">Select…</option>
            {catalog.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-end">
          <Button
            type="button"
            size="sm"
            onClick={handleAdd}
            disabled={assign.isPending}
            className="w-full"
          >
            {assign.isPending ? "Adding…" : "Add"}
          </Button>
        </div>
      </div>
    </div>
  );
}
