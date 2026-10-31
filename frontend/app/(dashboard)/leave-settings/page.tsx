"use client";

import { useEffect, useState } from "react";
import { useBranchId, useRoles } from "@/store/user-store";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import apiClient, { apiErrorMessage } from "@/services/api-client";

interface WofRow {
  teacher_id: string;
  emp_code: string | null;
  name: string;
  opening_balance: number | null;
  as_of_date: string | null;
  accrued: number | null;
  current_balance: number | null;
}

const QUOTA_TYPES = [
  { key: "casual", label: "Casual" },
  { key: "sick", label: "Sick" },
  { key: "paid", label: "Paid / Earned" },
] as const;

export default function LeaveSettingsPage() {
  const { branchId } = useBranchId();
  const { hasRole } = useRoles();
  const canEdit = hasRole("super_admin");
  const toast = useToast();
  const now = new Date();

  const [year, setYear] = useState(now.getFullYear());
  const [quotas, setQuotas] = useState<Record<string, string>>({ casual: "", sick: "", paid: "" });
  const [asOf, setAsOf] = useState(`${now.getFullYear()}-09-26`);
  const [wof, setWof] = useState<WofRow[]>([]);
  const [openings, setOpenings] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0); // bump to refetch after a save

  useEffect(() => {
    if (!branchId) return;
    let on = true;
    (async () => {
      setLoading(true);
      try {
        const [q, w] = await Promise.all([
          apiClient.get<{ quotas: Record<string, number | null> }>(
            "/api/v1/admin/leave-settings/quotas", { params: { branch_id: branchId, year } },
          ),
          apiClient.get<WofRow[]>("/api/v1/admin/leave-settings/wof", { params: { branch_id: branchId } }),
        ]);
        if (!on) return;
        setQuotas({
          casual: q.data.quotas.casual?.toString() ?? "",
          sick: q.data.quotas.sick?.toString() ?? "",
          paid: q.data.quotas.paid?.toString() ?? "",
        });
        setWof(w.data);
        setOpenings(Object.fromEntries(w.data.map((r) => [r.teacher_id, r.opening_balance?.toString() ?? ""])));
      } catch {
        /* non-super-admins get 403; page shows the notice below */
      } finally {
        if (on) setLoading(false);
      }
    })();
    return () => {
      on = false;
    };
  }, [branchId, year, tick]);

  async function saveQuotas() {
    try {
      await apiClient.put(
        "/api/v1/admin/leave-settings/quotas",
        { year, quotas: Object.fromEntries(Object.entries(quotas).filter(([, v]) => v !== "").map(([k, v]) => [k, Number(v)])) },
        { params: { branch_id: branchId } },
      );
      toast.success("Quotas saved");
    } catch (e) {
      toast.error("Could not save quotas", apiErrorMessage(e, "Try again."));
    }
  }

  async function saveWof(row: WofRow) {
    const val = openings[row.teacher_id];
    if (val === "" || val == null) return;
    try {
      await apiClient.put(
        "/api/v1/admin/leave-settings/wof",
        { teacher_id: row.teacher_id, opening_balance: Number(val), as_of_date: asOf },
        { params: { branch_id: branchId } },
      );
      toast.success(`Saved ${row.name}`);
      setTick((t) => t + 1);
    } catch (e) {
      toast.error("Could not save", apiErrorMessage(e, "Try again."));
    }
  }

  async function exportWof(fmt: "xlsx" | "pdf") {
    if (!branchId) return;
    try {
      const res = await apiClient.get(
        `/api/v1/admin/leave-settings/wof/export?branch_id=${branchId}&fmt=${fmt}`,
        { responseType: "blob" },
      );
      const disp = res.headers["content-disposition"] as string | undefined;
      const fname = disp?.match(/filename="?([^"]+)"?/)?.[1] ?? `WOF_Balance.${fmt}`;
      const url = window.URL.createObjectURL(res.data as Blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = fname;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      toast.error("Could not export", apiErrorMessage(e, "Try again."));
    }
  }

  const years = Array.from({ length: 4 }, (_, i) => now.getFullYear() - i);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Leave Settings"
        description="Set the per-year leave quota for each type, and each teacher's opening Weekly-Off balance. Super Admin only."
      >
        <div className="flex items-center gap-2">
          <Label htmlFor="year" className="text-xs">Year</Label>
          <select id="year" className="h-9 rounded-md border bg-background px-2 text-sm"
            value={year} onChange={(e) => setYear(Number(e.target.value))}>
            {years.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
        </div>
      </PageHeader>

      {!canEdit && (
        <p className="rounded-md border bg-muted/40 px-3 py-2 text-sm text-muted-foreground">
          Only a Super Admin can change leave settings.
        </p>
      )}

      {/* Quotas */}
      <Card>
        <CardContent className="flex flex-col gap-3 pt-5">
          <h2 className="text-sm font-semibold">Leave quota ({year})</h2>
          <div className="flex flex-wrap items-end gap-3">
            {QUOTA_TYPES.map((t) => (
              <div key={t.key} className="flex flex-col gap-1">
                <Label htmlFor={t.key}>{t.label}</Label>
                <Input id={t.key} type="number" min="0" step="0.5" className="w-28"
                  disabled={!canEdit}
                  value={quotas[t.key]} onChange={(e) => setQuotas((q) => ({ ...q, [t.key]: e.target.value }))} />
              </div>
            ))}
            {canEdit && <Button onClick={saveQuotas}>Save quotas</Button>}
          </div>
          <p className="text-xs text-muted-foreground">Leave Without Pay has no quota.</p>
        </CardContent>
      </Card>

      {/* WOF openings */}
      <Card>
        <CardContent className="flex flex-col gap-3 pt-5">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <h2 className="text-sm font-semibold">Weekly-Off balances</h2>
            <div className="flex items-end gap-2">
              <div className="flex flex-col gap-1">
                <Label htmlFor="asof" className="text-xs">Opening as of</Label>
                <Input id="asof" type="date" className="w-40" value={asOf}
                  disabled={!canEdit} onChange={(e) => setAsOf(e.target.value)} />
              </div>
              <Button variant="outline" size="sm" onClick={() => exportWof("xlsx")}>Excel</Button>
              <Button variant="outline" size="sm" onClick={() => exportWof("pdf")}>PDF</Button>
            </div>
          </div>
          {loading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : wof.length === 0 ? (
            <p className="text-sm text-muted-foreground">No teachers found.</p>
          ) : (
            <Table containerClassName="rounded-md border">
              <TableHeader>
                <TableRow>
                  <TableHead>Teacher</TableHead>
                  <TableHead>Code</TableHead>
                  <TableHead>Opening</TableHead>
                  <TableHead className="text-right">Earned</TableHead>
                  <TableHead className="text-right">Current balance</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {wof.map((r) => (
                  <TableRow key={r.teacher_id}>
                    <TableCell>{r.name}</TableCell>
                    <TableCell className="font-mono text-xs">{r.emp_code ?? "—"}</TableCell>
                    <TableCell>
                      <Input type="number" step="0.5" className="h-8 w-24" disabled={!canEdit}
                        value={openings[r.teacher_id] ?? ""}
                        onChange={(e) => setOpenings((o) => ({ ...o, [r.teacher_id]: e.target.value }))} />
                    </TableCell>
                    <TableCell className="text-right">{r.accrued ?? "—"}</TableCell>
                    <TableCell className="text-right font-medium">{r.current_balance ?? "—"}</TableCell>
                    <TableCell className="text-right">
                      {canEdit && (
                        <Button size="sm" variant="outline" onClick={() => saveWof(r)}>Save</Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
