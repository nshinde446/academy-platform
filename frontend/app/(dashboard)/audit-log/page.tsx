"use client";

import { useMemo, useState } from "react";
import { PageHeader } from "@/components/layout/page-header";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { TableSkeleton } from "@/components/ui/skeleton";
import { useAdminUsers } from "../users/_hooks/use-users";
import { useAuditLog, type AuditLogFilters } from "./_hooks/use-audit-log";

const CONTROL = "h-9 rounded-lg border border-input bg-background px-3 text-sm";
const PAGE = 50;

// Friendly module names for the raw table names in the audit log.
const MODULE_LABEL: Record<string, string> = {
  students: "Students",
  teachers: "Teachers",
  batches: "Batches",
  lectures: "Lectures",
  daily_attendance: "Attendance",
  attendance_records: "Attendance",
  batch_coordinators: "Access Control",
  accounts_attendance_grants: "Access Control",
  users: "Users",
};

function moduleLabel(table: string): string {
  return MODULE_LABEL[table] ?? table;
}

function fmtTime(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

function summarizeValues(v: Record<string, unknown> | null): string {
  if (!v) return "";
  return Object.entries(v)
    .map(([k, val]) => `${k}: ${JSON.stringify(val)}`)
    .join(", ");
}

export default function AuditLogPage() {
  const [filters, setFilters] = useState<AuditLogFilters>({
    userId: "",
    tableName: "",
    action: "",
  });
  const [page, setPage] = useState(0);

  const usersQuery = useAdminUsers(true);
  const logQuery = useAuditLog(filters, page * PAGE, PAGE);

  const userMap = useMemo(() => {
    const m = new Map<string, string>();
    for (const u of usersQuery.data ?? []) {
      m.set(u.id, `${u.first_name} ${u.last_name} · ${u.roles.join(", ")}`);
    }
    return m;
  }, [usersQuery.data]);

  const data = logQuery.data;
  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  function setFilter(key: keyof AuditLogFilters, value: string) {
    setFilters((f) => ({ ...f, [key]: value }));
    setPage(0);
  }

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Audit Log"
        description="Every change made across the platform — who did what, where, and when. Filter by user, module or action."
      />

      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          User
          <select
            value={filters.userId}
            onChange={(e) => setFilter("userId", e.target.value)}
            className={CONTROL}
          >
            <option value="">All users</option>
            {(usersQuery.data ?? []).map((u) => (
              <option key={u.id} value={u.id}>
                {u.first_name} {u.last_name}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          Module
          <select
            value={filters.tableName}
            onChange={(e) => setFilter("tableName", e.target.value)}
            className={CONTROL}
          >
            <option value="">All modules</option>
            {Object.entries(MODULE_LABEL).map(([table, label]) => (
              <option key={table} value={table}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          Action
          <input
            type="text"
            placeholder="e.g. Delete"
            value={filters.action}
            onChange={(e) => setFilter("action", e.target.value)}
            className={CONTROL}
          />
        </label>
      </div>

      {logQuery.isLoading ? (
        <TableSkeleton rows={8} />
      ) : logQuery.isError ? (
        <p className="text-sm text-destructive">Failed to load the audit log.</p>
      ) : items.length === 0 ? (
        <p className="text-sm text-muted-foreground">No matching activity.</p>
      ) : (
        <>
          <div className="rounded-xl border ring-1 ring-foreground/10 overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>When</TableHead>
                  <TableHead>User</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Module</TableHead>
                  <TableHead className="hidden lg:table-cell">Change</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((it) => (
                  <TableRow key={it.id}>
                    <TableCell className="whitespace-nowrap text-sm text-muted-foreground">
                      {fmtTime(it.timestamp)}
                    </TableCell>
                    <TableCell className="text-sm">
                      {it.user_id ? (userMap.get(it.user_id) ?? it.user_id) : "—"}
                    </TableCell>
                    <TableCell className="text-sm font-medium">{it.action}</TableCell>
                    <TableCell className="text-sm">{moduleLabel(it.table_name)}</TableCell>
                    <TableCell className="hidden lg:table-cell max-w-md truncate text-xs text-muted-foreground">
                      {summarizeValues(it.new_values) || summarizeValues(it.old_values)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>
              {page * PAGE + 1}–{Math.min((page + 1) * PAGE, total)} of {total}
            </span>
            <div className="flex gap-2">
              <Button
                variant="secondary"
                size="sm"
                disabled={page === 0}
                onClick={() => setPage((p) => Math.max(0, p - 1))}
              >
                Previous
              </Button>
              <Button
                variant="secondary"
                size="sm"
                disabled={(page + 1) * PAGE >= total}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
