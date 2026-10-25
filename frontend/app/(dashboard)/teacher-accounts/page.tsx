"use client";

import { useCallback, useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { useToast } from "@/components/ui/toast";
import apiClient, { apiErrorMessage } from "@/services/api-client";
import { useBranchId } from "@/store/user-store";

interface Account {
  staff_id: string;
  employee_code: string;
  name: string;
  status: string;
  last_login_at: string | null;
}
interface Created {
  employee_code: string;
  name: string;
  temporary_password: string;
}

const STATUS_LABEL: Record<string, string> = {
  active: "Active",
  locked: "Locked",
  disabled: "Disabled",
  must_change_password: "Must change password",
};

export default function TeacherAccountsPage() {
  const { branchId } = useBranchId();
  const toast = useToast();
  const [rows, setRows] = useState<Account[]>([]);
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState(false);
  const [created, setCreated] = useState<Created[] | null>(null);

  const load = useCallback(async () => {
    if (!branchId) return;
    const r = await apiClient.get<Account[]>("/api/v1/admin/teacher-accounts", {
      params: { branch_id: branchId },
    });
    setRows(r.data);
  }, [branchId]);

  useEffect(() => {
    // load() sets state only after an await (not synchronously) — the rule's
    // cascading-render concern doesn't apply to this async fetch.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [load]);

  async function act(path: string, ok: string) {
    setBusy(true);
    try {
      await apiClient.post(`/api/v1/admin/teacher-accounts/${path}`, null, {
        params: { branch_id: branchId },
      });
      toast.success(ok);
      await load();
    } catch (e) {
      toast.error("Action failed", apiErrorMessage(e, "Try again."));
    } finally {
      setBusy(false);
    }
  }

  async function bulkCreate() {
    if (!branchId) return;
    setBusy(true);
    try {
      const r = await apiClient.post(
        "/api/v1/admin/teacher-accounts/bulk-create",
        {},
        { params: { branch_id: branchId } },
      );
      setCreated(r.data.created);
      toast.success(`${r.data.count} account(s) created`);
      await load();
    } catch (e) {
      toast.error("Bulk create failed", apiErrorMessage(e, "Try again."));
    } finally {
      setBusy(false);
    }
  }

  async function reset(staffId: string) {
    setBusy(true);
    try {
      const r = await apiClient.post(
        `/api/v1/admin/teacher-accounts/${staffId}/reset-password`,
        null,
        { params: { branch_id: branchId } },
      );
      setCreated([r.data]);
      toast.success("Password reset — new temporary password issued");
      await load();
    } catch (e) {
      toast.error("Reset failed", apiErrorMessage(e, "Try again."));
    } finally {
      setBusy(false);
    }
  }

  function downloadCsv() {
    if (!created) return;
    const lines = ["Employee Code,Name,Temporary Password"].concat(
      created.map((c) => `${c.employee_code},${c.name},${c.temporary_password}`),
    );
    const blob = new Blob([lines.join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "teacher-temporary-passwords.csv";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  const filtered = rows.filter(
    (r) =>
      !search ||
      r.employee_code?.toLowerCase().includes(search.toLowerCase()) ||
      r.name.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Teacher Accounts"
        description="Login accounts for teaching staff — create, reset, lock and disable."
        actions={
          <Button size="sm" onClick={bulkCreate} disabled={busy}>
            Bulk create
          </Button>
        }
      />

      {/* One-time temporary passwords (shown once). */}
      {created && created.length > 0 && (
        <Card>
          <CardContent className="flex flex-col gap-3 pt-4">
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold">
                Temporary passwords — shown once. Hand them out now.
              </p>
              <Button size="sm" variant="secondary" onClick={downloadCsv}>
                Download CSV
              </Button>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-muted-foreground">
                    <th className="py-1 pr-4">Code</th>
                    <th className="py-1 pr-4">Name</th>
                    <th className="py-1">Temporary password</th>
                  </tr>
                </thead>
                <tbody>
                  {created.map((c) => (
                    <tr key={c.employee_code} className="border-t">
                      <td className="py-1 pr-4 tabular-nums">{c.employee_code}</td>
                      <td className="py-1 pr-4">{c.name}</td>
                      <td className="py-1 font-mono">{c.temporary_password}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Button size="sm" variant="ghost" onClick={() => setCreated(null)}>
              Dismiss
            </Button>
          </CardContent>
        </Card>
      )}

      <Input
        placeholder="Search by code or name…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="max-w-sm"
      />

      <div className="overflow-x-auto rounded-lg border">
        <table className="w-full text-sm">
          <thead className="bg-muted/30 text-left">
            <tr>
              <th className="px-3 py-2">Code</th>
              <th className="px-3 py-2">Name</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Last login</th>
              <th className="px-3 py-2 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-3 py-6 text-center text-muted-foreground">
                  No teacher accounts. Use “Bulk create”.
                </td>
              </tr>
            ) : (
              filtered.map((a) => (
                <tr key={a.staff_id} className="border-t">
                  <td className="px-3 py-2 tabular-nums">{a.employee_code}</td>
                  <td className="px-3 py-2">{a.name}</td>
                  <td className="px-3 py-2">{STATUS_LABEL[a.status] ?? a.status}</td>
                  <td className="px-3 py-2 text-muted-foreground">
                    {a.last_login_at ? new Date(a.last_login_at).toLocaleString() : "—"}
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex flex-wrap justify-end gap-1">
                      <Button size="sm" variant="secondary" disabled={busy} onClick={() => reset(a.staff_id)}>
                        Reset
                      </Button>
                      {a.status === "locked" && (
                        <Button size="sm" variant="secondary" disabled={busy}
                          onClick={() => act(`${a.staff_id}/unlock`, "Unlocked")}>
                          Unlock
                        </Button>
                      )}
                      {a.status === "disabled" ? (
                        <Button size="sm" variant="secondary" disabled={busy}
                          onClick={() => act(`${a.staff_id}/enable`, "Enabled")}>
                          Enable
                        </Button>
                      ) : (
                        <Button size="sm" variant="secondary" disabled={busy}
                          onClick={() => act(`${a.staff_id}/disable`, "Disabled")}>
                          Disable
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
