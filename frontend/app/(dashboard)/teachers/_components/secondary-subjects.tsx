"use client";

import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { InfoHint } from "@/components/ui/info-hint";
import { useBatches } from "../../batches/_hooks/use-batches";
import {
  useSubjectCatalog,
  useSecondaryForTeacher,
  useAssignSecondarySubjects,
  useRemoveSecondarySubject,
  type SecondarySubjectRow,
} from "../_hooks/use-secondary-subjects";

const SELECT_CLASS =
  "h-9 rounded-md border border-input bg-background px-3 text-sm";

/**
 * "Also teaches (secondary subjects)" — lets an admin set up a teacher to teach
 * an extra subject for specific batches, on top of their core subject. The core
 * subject is never changed. Per the flexible-assignment feature.
 */
export function SecondarySubjects({
  branchId,
  teacherId,
}: {
  branchId: string | undefined;
  teacherId: string;
}) {
  const catalogQuery = useSubjectCatalog(branchId);
  const batchesQuery = useBatches(branchId);
  const rowsQuery = useSecondaryForTeacher(branchId, teacherId);
  const assign = useAssignSecondarySubjects(branchId);
  const remove = useRemoveSecondarySubject(branchId);

  const catalog = catalogQuery.data ?? [];
  const batches = batchesQuery.data ?? [];

  const [subject, setSubject] = useState("");
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [error, setError] = useState("");

  // Group existing assignments by subject for a compact display.
  const bySubject = useMemo(() => {
    const rows = rowsQuery.data ?? [];
    const m = new Map<string, SecondarySubjectRow[]>();
    for (const r of rows) {
      const list = m.get(r.subject_name) ?? [];
      list.push(r);
      m.set(r.subject_name, list);
    }
    return [...m.entries()];
  }, [rowsQuery.data]);

  function toggle(id: string) {
    setPicked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function handleAdd() {
    setError("");
    if (!subject) {
      setError("Pick a subject.");
      return;
    }
    if (picked.size === 0) {
      setError("Pick at least one batch.");
      return;
    }
    try {
      await assign.mutateAsync({
        teacherId,
        subjectName: subject,
        batchIds: [...picked],
      });
      setSubject("");
      setPicked(new Set());
    } catch {
      setError("Could not add the assignment.");
    }
  }

  return (
    <Card size="sm">
      <CardContent>
        <div className="mb-3 flex items-center gap-2">
          <h2 className="text-sm font-semibold">Also teaches (secondary subjects)</h2>
          <InfoHint
            text="Extra subjects this teacher teaches for specific batches, on top of their core subject. The core subject is never changed. A teacher is only offered for a secondary subject in the batches set up here."
          />
        </div>

        {/* Existing assignments */}
        {bySubject.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            No secondary subjects. This teacher teaches their core subject only.
          </p>
        ) : (
          <ul className="flex flex-col gap-2">
            {bySubject.map(([subjectName, list]) => (
              <li key={subjectName} className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-medium">{subjectName}</span>
                <span className="text-xs text-muted-foreground">for</span>
                {list.map((r) => (
                  <Badge key={r.id} variant="secondary" className="gap-1">
                    {r.batch_name}
                    <button
                      type="button"
                      aria-label={`Remove ${subjectName} for ${r.batch_name}`}
                      className="ml-0.5 text-muted-foreground hover:text-destructive"
                      onClick={() => remove.mutate(r.id)}
                      disabled={remove.isPending}
                    >
                      ×
                    </button>
                  </Badge>
                ))}
              </li>
            ))}
          </ul>
        )}

        {/* Add form */}
        <div className="mt-4 flex flex-col gap-3 rounded-md border p-3">
          {error && <p className="text-sm text-destructive">{error}</p>}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ss_subject">Subject</Label>
            <select
              id="ss_subject"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              className={SELECT_CLASS}
            >
              <option value="">Select subject…</option>
              {catalog.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label>
              Batches
              {picked.size > 0 && (
                <span className="ml-2 text-xs font-normal text-muted-foreground">
                  {picked.size} selected
                </span>
              )}
            </Label>
            {batches.length === 0 ? (
              <p className="text-xs text-muted-foreground">No batches yet.</p>
            ) : (
              <div className="max-h-44 overflow-y-auto rounded-md border p-1.5 text-sm">
                {batches.map((b) => (
                  <label
                    key={b.id}
                    className="flex cursor-pointer items-center gap-2 rounded px-2 py-1 hover:bg-muted"
                  >
                    <input
                      type="checkbox"
                      checked={picked.has(b.id)}
                      onChange={() => toggle(b.id)}
                    />
                    <span>{b.name}</span>
                    <span className="text-xs text-muted-foreground">{b.code}</span>
                  </label>
                ))}
              </div>
            )}
          </div>

          <div>
            <Button size="sm" onClick={handleAdd} disabled={assign.isPending}>
              {assign.isPending ? "Adding…" : "Add secondary subject"}
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
