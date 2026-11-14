"use client";

import { useRef, useState } from "react";
import { useBranchId } from "@/store/user-store";
import { useRoles } from "@/store/user-store";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/error-state";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { apiErrorMessage } from "@/lib/api-error";
import {
  useImportOpeningBalances,
  useOpeningBalances,
  useSetOpeningBalances,
} from "@/hooks/use-payroll";

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

export default function OpeningBalancesPage() {
  const { branchId } = useBranchId();
  const { hasRole } = useRoles();
  const canEdit = hasRole("super_admin") || hasRole("payroll_admin");
  const toast = useToast();
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);

  const query = useOpeningBalances(branchId, year, month);
  const save = useSetOpeningBalances(branchId);
  const importXlsx = useImportOpeningBalances(branchId);
  const fileRef = useRef<HTMLInputElement>(null);

  // Draft overlay of edited balances, keyed by staff_id.
  const [draft, setDraft] = useState<Record<string, number>>({});
  const [unmatched, setUnmatched] = useState<string[]>([]);

  const data = query.data;
  const locked = !!data?.locked;
  const years = Array.from({ length: 6 }, (_, i) => now.getFullYear() - i);

  function valueFor(staffId: string, current: number): number {
    return draft[staffId] ?? current;
  }

  function setValue(staffId: string, v: number) {
    setDraft((d) => ({ ...d, [staffId]: v }));
  }

  async function onPickFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ""; // allow re-selecting the same file
    if (!file) return;
    try {
      const res = await importXlsx.mutateAsync(file);
      const next: Record<string, number> = {};
      for (const row of res.matched) next[row.staff_id] = row.opening_balance;
      setDraft((d) => ({ ...d, ...next }));
      setUnmatched(res.unmatched);
      toast.success(
        "Imported from Excel",
        `${res.matched.length} matched${res.unmatched.length ? `, ${res.unmatched.length} unmatched` : ""}. Review, then Save.`,
      );
    } catch (err) {
      toast.error("Could not read the file", apiErrorMessage(err, "Please check the format."));
    }
  }

  async function onSave() {
    if (!data) return;
    const entries = data.rows
      .map((r) => ({ staff_id: r.staff_id, balance: valueFor(r.staff_id, r.opening_balance) }))
      .filter((e, i) => e.balance !== data.rows[i].opening_balance);
    if (entries.length === 0) {
      toast.info("Nothing to save", "No opening balances were changed.");
      return;
    }
    try {
      const res = await save.mutateAsync({
        effective_year: year,
        effective_month: month,
        entries,
      });
      setDraft({});
      setUnmatched([]);
      toast.success("Opening balances saved", `${res.written} staff updated.`);
    } catch (err) {
      toast.error("Could not save", apiErrorMessage(err, "Please try again."));
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Opening Balances"
        description="Enter each staff member's existing Extra Days balance (from before this system started), as of the start of the chosen first month. Carries forward from there. Enter by hand or import from Excel (columns: emp_code, opening_balance)."
        actions={
          canEdit && (
            <>
              <input
                ref={fileRef}
                type="file"
                accept=".xlsx"
                className="hidden"
                onChange={onPickFile}
              />
              <Button
                variant="outline"
                disabled={locked || importXlsx.isPending}
                onClick={() => fileRef.current?.click()}
              >
                Import Excel
              </Button>
              <Button onClick={onSave} disabled={locked || save.isPending}>
                Save
              </Button>
            </>
          )
        }
      >
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm text-muted-foreground">First month:</span>
          <select
            className="h-9 rounded-md border bg-background px-2 text-sm"
            value={month}
            onChange={(e) => setMonth(Number(e.target.value))}
          >
            {MONTHS.map((m, i) => (
              <option key={m} value={i + 1}>{m}</option>
            ))}
          </select>
          <select
            className="h-9 rounded-md border bg-background px-2 text-sm"
            value={year}
            onChange={(e) => setYear(Number(e.target.value))}
          >
            {years.map((y) => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
          {locked && <Badge variant="outline">Locked — a month is already closed</Badge>}
        </div>
      </PageHeader>

      {!canEdit && (
        <p className="rounded-md border bg-muted/40 px-3 py-2 text-sm text-muted-foreground">
          Only a Super Admin or Payroll Admin can set opening balances.
        </p>
      )}

      {locked && canEdit && (
        <p className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200">
          A payroll month has already been closed, so opening balances can no longer be set.
          Use the month reopen / recompute flow to correct history instead.
        </p>
      )}

      {unmatched.length > 0 && (
        <p className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive">
          {unmatched.length} employee code(s) from the file did not match any staff and were
          skipped: {unmatched.join(", ")}
        </p>
      )}

      {query.isLoading ? (
        <div className="flex flex-col gap-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-9 w-full" />
          ))}
        </div>
      ) : query.isError ? (
        <ErrorState onRetry={() => query.refetch()} />
      ) : !data || data.rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">No staff for this branch.</p>
      ) : (
        <Table containerClassName="rounded-md border">
          <TableHeader>
            <TableRow>
              <TableHead>Code</TableHead>
              <TableHead>Name</TableHead>
              <TableHead>Dept</TableHead>
              <TableHead className="text-right">Opening balance (days)</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.rows.map((r) => {
              const v = valueFor(r.staff_id, r.opening_balance);
              return (
                <TableRow key={r.staff_id}>
                  <TableCell className="font-mono text-xs">{r.emp_code}</TableCell>
                  <TableCell>{r.name}</TableCell>
                  <TableCell className="text-muted-foreground">{r.department}</TableCell>
                  <TableCell className="text-right">
                    <Input
                      type="number"
                      step="0.5"
                      className={`ml-auto w-28 text-right ${v < 0 ? "text-destructive" : ""}`}
                      value={v}
                      disabled={!canEdit || locked}
                      onChange={(e) => setValue(r.staff_id, Number(e.target.value))}
                    />
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
