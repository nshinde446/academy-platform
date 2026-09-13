"use client";

import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { InfoHint } from "@/components/ui/info-hint";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/components/ui/toast";
import {
  useWhatsappBatches,
  useUpdateWhatsappBatches,
} from "../_hooks/use-notification-settings";

function sameSet(a: Set<string>, b: Set<string>): boolean {
  if (a.size !== b.size) return false;
  for (const v of a) if (!b.has(v)) return false;
  return true;
}

/**
 * Per-batch WhatsApp selection. Under the master switch, the admin picks exactly
 * which batches' parents get messages — so a pilot can start with one batch
 * instead of the whole branch. A batch is only notified when the master switch is
 * on AND it is enabled here; with nothing selected, nobody is messaged.
 */
export function WhatsappBatchesCard({
  branchId,
}: {
  branchId: string | undefined;
}) {
  const toast = useToast();
  const query = useWhatsappBatches(branchId);
  const update = useUpdateWhatsappBatches(branchId);
  const batches = useMemo(() => query.data ?? [], [query.data]);

  // The saved enabled set is the source of truth; `draft` holds unsaved edits.
  const serverEnabled = useMemo(
    () => new Set(batches.filter((b) => b.enabled).map((b) => b.batch_id)),
    [batches],
  );
  const [draft, setDraft] = useState<Set<string> | null>(null);
  const selected = draft ?? serverEnabled;
  const dirty = draft !== null && !sameSet(draft, serverEnabled);

  function toggle(batchId: string) {
    const next = new Set(selected);
    if (next.has(batchId)) next.delete(batchId);
    else next.add(batchId);
    setDraft(next);
  }

  function selectAll() {
    setDraft(new Set(batches.map((b) => b.batch_id)));
  }

  function clear() {
    setDraft(new Set());
  }

  async function save() {
    try {
      await update.mutateAsync([...selected]);
      setDraft(null);
      toast.success(
        "Batches saved",
        selected.size === 0
          ? "No batches selected — no parents will be messaged."
          : `WhatsApp on for ${selected.size} batch${selected.size === 1 ? "" : "es"}.`,
      );
    } catch {
      toast.error("Couldn't save", "Please try again.");
    }
  }

  const totalReach = batches
    .filter((b) => selected.has(b.batch_id))
    .reduce((sum, b) => sum + b.student_count, 0);

  return (
    <Card className="max-w-2xl">
      <CardContent className="flex flex-col gap-3">
        <div className="flex items-center gap-1.5">
          <span className="text-sm font-medium text-foreground">
            Batches to message
          </span>
          <InfoHint
            text={
              <>
                Choose which batches&apos; parents receive WhatsApp messages.
                Only enabled batches are messaged — start a pilot with one batch,
                then widen it. With nothing selected, no parents are messaged even
                though the master switch is on.
              </>
            }
          />
        </div>

        {query.isLoading ? (
          <p className="py-3 text-sm text-muted-foreground">Loading batches…</p>
        ) : query.isError ? (
          <p className="py-3 text-sm text-destructive">Failed to load batches.</p>
        ) : batches.length === 0 ? (
          <p className="py-3 text-sm text-muted-foreground">
            No batches in this branch yet.
          </p>
        ) : (
          <>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={selectAll}
                disabled={update.isPending || selected.size === batches.length}
              >
                Select all
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={clear}
                disabled={update.isPending || selected.size === 0}
              >
                Clear
              </Button>
              <span className="ml-auto text-xs text-muted-foreground">
                {selected.size} of {batches.length} · {totalReach} student
                {totalReach === 1 ? "" : "s"}
              </span>
            </div>

            <div className="flex flex-col divide-y divide-border rounded-lg border border-border">
              {batches.map((b) => (
                <div
                  key={b.batch_id}
                  className="flex items-center justify-between gap-3 px-3 py-2.5"
                >
                  <div className="flex min-w-0 flex-col">
                    <span className="truncate text-sm font-medium text-foreground">
                      {b.name}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {b.code} · {b.student_count} student
                      {b.student_count === 1 ? "" : "s"}
                    </span>
                  </div>
                  <Switch
                    checked={selected.has(b.batch_id)}
                    onCheckedChange={() => toggle(b.batch_id)}
                    disabled={update.isPending}
                    aria-label={`WhatsApp notifications for ${b.name}`}
                  />
                </div>
              ))}
            </div>

            <div className="flex items-center gap-2">
              <Button size="sm" onClick={save} disabled={!dirty || update.isPending}>
                Save
              </Button>
              {dirty && (
                <span className="text-xs text-muted-foreground">
                  Unsaved changes
                </span>
              )}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
