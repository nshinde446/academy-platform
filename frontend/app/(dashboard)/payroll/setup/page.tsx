"use client";

import { useState } from "react";
import Link from "next/link";
import { useBranchId, useRoles } from "@/store/user-store";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { PromptDialog } from "@/components/ui/prompt-dialog";
import { useToast } from "@/components/ui/toast";
import { apiErrorMessage } from "@/lib/api-error";
import {
  useAddHoliday,
  useMonth,
  useMonthLifecycle,
  useRemoveHoliday,
  useUpsertMonth,
  type Holiday,
} from "@/hooks/use-payroll";

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

const LIFECYCLE_TONE: Record<string, "default" | "secondary" | "outline"> = {
  OPEN: "secondary", CLOSED: "default", LOCKED: "outline", NOT_SET: "outline",
};

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

export default function PayrollSetupPage() {
  const { branchId } = useBranchId();
  const { hasRole } = useRoles();
  const canEdit = hasRole("super_admin");
  const toast = useToast();

  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);

  const monthQuery = useMonth(branchId, year, month);
  const data = monthQuery.data;
  const notSet = !data || data.lifecycle === "NOT_SET";
  const locked = data?.lifecycle === "LOCKED";
  const closed = data?.lifecycle === "CLOSED" || locked;

  const upsert = useUpsertMonth(branchId);
  const lifecycle = useMonthLifecycle(branchId);
  const addHoliday = useAddHoliday(branchId);
  const removeHoliday = useRemoveHoliday(branchId);

  // Draft overlays over server data — editable without a sync effect. Cleared
  // when the selected month changes or after a successful save.
  const [draft, setDraft] = useState<{ required: string; notes: string } | null>(null);
  const baseRequired = notSet ? "26" : String(data!.required_days);
  const baseNotes = data?.notes ?? "";
  const required = draft?.required ?? baseRequired;
  const notes = draft?.notes ?? baseNotes;
  function edit(part: Partial<{ required: string; notes: string }>) {
    setDraft({ required, notes, ...part });
  }

  const defaultHDate = `${year}-${pad(month)}-01`;
  const [hDateDraft, setHDateDraft] = useState<string | null>(null);
  const hDate = hDateDraft ?? defaultHDate;
  const [hTitle, setHTitle] = useState("");
  const [hKind, setHKind] = useState("HOLIDAY");

  const [removeTarget, setRemoveTarget] = useState<Holiday | null>(null);
  // One prompt dialog, shared by the two reason-gated actions.
  const [reasonFor, setReasonFor] = useState<"save" | "reopen" | null>(null);

  function pickMonth(nextMonth: number, nextYear: number) {
    setMonth(nextMonth);
    setYear(nextYear);
    setDraft(null);
    setHDateDraft(null);
  }

  async function saveMonth(reason: string | null) {
    try {
      await upsert.mutateAsync({ year, month, required_days: Number(required), notes, reason });
      setDraft(null);
      toast.success("Saved", closed ? "Month recomputed." : "Required days updated.");
    } catch (e) {
      toast.error("Could not save", apiErrorMessage(e, "Please try again."));
    }
  }

  async function onSaveClick() {
    if (closed) setReasonFor("save");
    else await saveMonth(null);
  }

  async function doLifecycle(verb: "close" | "lock" | "reopen", reason: string | null) {
    try {
      await lifecycle.mutateAsync({ year, month, verb, reason });
      toast.success(`Month ${verb === "reopen" ? "reopened" : verb + "d"}`);
    } catch (e) {
      toast.error(`Could not ${verb}`, apiErrorMessage(e, "Please try again."));
    }
  }

  async function submitHoliday() {
    if (!hTitle.trim()) return toast.error("Add a title");
    try {
      await addHoliday.mutateAsync({
        year, month, holiday_date: hDate, title: hTitle.trim(), kind: hKind, credit_days: 1,
      });
      setHTitle("");
      setHDateDraft(null);
      toast.success("Holiday added");
    } catch (e) {
      toast.error("Could not add holiday", apiErrorMessage(e, "Please try again."));
    }
  }

  const years = Array.from({ length: 6 }, (_, i) => now.getFullYear() - i);

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Payroll Month Setup"
        description="Set the required working days for the month and declare paid holidays or leaves. Close a month to finalise its figures, lock it when payroll is done, or reopen it (with a reason) to make a correction."
        actions={
          <Button variant="outline" render={<Link href="/payroll" />}>
            View Report
          </Button>
        }
      >
        <div className="flex flex-wrap items-center gap-2">
          <select
            className="h-9 rounded-md border bg-background px-2 text-sm"
            value={month}
            onChange={(e) => pickMonth(Number(e.target.value), year)}
          >
            {MONTHS.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
          </select>
          <select
            className="h-9 rounded-md border bg-background px-2 text-sm"
            value={year}
            onChange={(e) => pickMonth(month, Number(e.target.value))}
          >
            {years.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
          {data && (
            <Badge variant={LIFECYCLE_TONE[data.lifecycle] ?? "outline"}>
              {data.lifecycle === "NOT_SET" ? "Not set up" : data.lifecycle}
            </Badge>
          )}
        </div>
      </PageHeader>

      {!canEdit && (
        <p className="rounded-md border bg-muted/40 px-3 py-2 text-sm text-muted-foreground">
          You can view the setup. Only a Super Admin can change required days,
          holidays or the month status.
        </p>
      )}

      {/* Required days + notes */}
      <section className="flex flex-col gap-3 rounded-md border p-4">
        <h2 className="text-sm font-semibold">Required working days</h2>
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1">
            <Label htmlFor="required">Days this month</Label>
            <Input
              id="required"
              type="number"
              step="0.5"
              min="0"
              max="31"
              value={required}
              disabled={!canEdit || locked}
              onChange={(e) => edit({ required: e.target.value })}
              className="w-28"
            />
          </div>
          <div className="flex min-w-[220px] flex-1 flex-col gap-1">
            <Label htmlFor="notes">Notes (optional)</Label>
            <Input
              id="notes"
              value={notes}
              disabled={!canEdit || locked}
              onChange={(e) => edit({ notes: e.target.value })}
            />
          </div>
          {canEdit && !locked && (
            <Button onClick={onSaveClick} disabled={upsert.isPending}>
              {notSet ? "Create month" : "Save"}
            </Button>
          )}
        </div>
        <p className="text-xs text-muted-foreground">
          A 30-day month usually means ~26 required days (about 4 weekly offs).
        </p>

        {/* Lifecycle actions */}
        {canEdit && data && data.lifecycle !== "NOT_SET" && (
          <div className="flex flex-wrap gap-2 border-t pt-3">
            {data.lifecycle === "OPEN" && (
              <Button variant="outline" onClick={() => doLifecycle("close", null)} disabled={lifecycle.isPending}>
                Close month
              </Button>
            )}
            {data.lifecycle === "CLOSED" && (
              <Button variant="outline" onClick={() => doLifecycle("lock", null)} disabled={lifecycle.isPending}>
                Lock
              </Button>
            )}
            {closed && (
              <Button variant="outline" onClick={() => setReasonFor("reopen")} disabled={lifecycle.isPending}>
                Reopen…
              </Button>
            )}
          </div>
        )}
      </section>

      {/* Holidays */}
      <section className="flex flex-col gap-3 rounded-md border p-4">
        <h2 className="text-sm font-semibold">Paid holidays &amp; leaves</h2>
        {data && data.holidays.length > 0 ? (
          <ul className="flex flex-col divide-y">
            {data.holidays.map((h) => (
              <li key={h.id} className="flex items-center justify-between gap-3 py-2">
                <span className="text-sm">
                  <span className="font-medium">{h.holiday_date}</span>
                  <span className="mx-2 text-muted-foreground">·</span>
                  {h.title}
                  <Badge variant="outline" className="ml-2 text-[10px]">{h.kind}</Badge>
                </span>
                {canEdit && !locked && (
                  <Button variant="ghost" size="sm" onClick={() => setRemoveTarget(h)}>
                    Remove
                  </Button>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">No paid holidays declared for this month.</p>
        )}

        {canEdit && !locked && !notSet && (
          <div className="flex flex-wrap items-end gap-2 border-t pt-3">
            <div className="flex flex-col gap-1">
              <Label htmlFor="hdate">Date</Label>
              <Input id="hdate" type="date" value={hDate} onChange={(e) => setHDateDraft(e.target.value)} className="w-40" />
            </div>
            <div className="flex min-w-[180px] flex-1 flex-col gap-1">
              <Label htmlFor="htitle">Title</Label>
              <Input id="htitle" value={hTitle} onChange={(e) => setHTitle(e.target.value)} placeholder="e.g. Republic Day" />
            </div>
            <div className="flex flex-col gap-1">
              <Label htmlFor="hkind">Type</Label>
              <select
                id="hkind"
                className="h-9 rounded-md border bg-background px-2 text-sm"
                value={hKind}
                onChange={(e) => setHKind(e.target.value)}
              >
                <option value="HOLIDAY">Holiday</option>
                <option value="LEAVE">Leave</option>
              </select>
            </div>
            <Button variant="outline" onClick={submitHoliday} disabled={addHoliday.isPending}>
              Add
            </Button>
          </div>
        )}
        {notSet && (
          <p className="text-xs text-muted-foreground">Create the month first to add holidays.</p>
        )}
      </section>

      <ConfirmDialog
        open={!!removeTarget}
        onOpenChange={(o) => !o && setRemoveTarget(null)}
        title="Remove holiday?"
        description={removeTarget ? `Remove "${removeTarget.title}" on ${removeTarget.holiday_date}?` : ""}
        confirmLabel="Remove"
        destructive
        onConfirm={async () => {
          if (!removeTarget) return;
          try {
            await removeHoliday.mutateAsync({ year, month, holidayId: removeTarget.id });
            toast.success("Holiday removed");
          } catch (e) {
            toast.error("Could not remove", apiErrorMessage(e, "Please try again."));
          } finally {
            setRemoveTarget(null);
          }
        }}
      />

      <PromptDialog
        open={reasonFor !== null}
        onOpenChange={(o) => !o && setReasonFor(null)}
        title={reasonFor === "reopen" ? "Reopen month" : "Change a closed month"}
        description={
          reasonFor === "reopen"
            ? "Reopening recomputes later months. Enter a reason (recorded in the audit log)."
            : "This month is closed. Enter a reason for the change (audited; the month is recomputed)."
        }
        label="Reason"
        required
        confirmLabel={reasonFor === "reopen" ? "Reopen" : "Save"}
        onConfirm={async (reason) => {
          if (reasonFor === "reopen") await doLifecycle("reopen", reason);
          else await saveMonth(reason);
          setReasonFor(null);
        }}
      />
    </div>
  );
}
