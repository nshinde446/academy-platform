"use client";

import { useState } from "react";
import { PageHeader } from "@/components/layout/page-header";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { TableSkeleton } from "@/components/ui/skeleton";
import { useDeliveryLog } from "./_hooks/use-delivery-log";

const CONTROL = "h-9 rounded-lg border border-input bg-background px-3 text-sm";

function statusTone(s: string): "success" | "destructive" | "secondary" {
  if (s === "SENT") return "success";
  if (s === "FAILED") return "destructive";
  return "secondary";
}

function fmtTime(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

export default function WhatsappLogPage() {
  const [statusFilter, setStatusFilter] = useState("");
  const query = useDeliveryLog(statusFilter);
  const rows = query.data ?? [];

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="WhatsApp Delivery Log"
        description="Which parents received an absence notification — confirm coverage and spot anyone to re-send to."
      />

      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          Status
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className={CONTROL}
          >
            <option value="">All</option>
            <option value="SENT">Sent</option>
            <option value="FAILED">Failed</option>
            <option value="PENDING">Pending</option>
          </select>
        </label>
      </div>

      {query.isLoading ? (
        <TableSkeleton rows={8} />
      ) : query.isError ? (
        <p className="text-sm text-destructive">Failed to load the delivery log.</p>
      ) : rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No WhatsApp messages logged yet.
        </p>
      ) : (
        <div className="rounded-xl border ring-1 ring-foreground/10 overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Student</TableHead>
                <TableHead className="hidden sm:table-cell">PRN</TableHead>
                <TableHead>Parent contact</TableHead>
                <TableHead className="hidden md:table-cell">Date</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="hidden lg:table-cell">Sent by</TableHead>
                <TableHead className="hidden lg:table-cell">When</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((r) => (
                <TableRow key={r.id}>
                  <TableCell className="text-sm font-medium">
                    {r.student_name ?? "—"}
                  </TableCell>
                  <TableCell className="hidden sm:table-cell tabular-nums text-sm text-muted-foreground">
                    {r.prn ?? "—"}
                  </TableCell>
                  <TableCell className="tabular-nums text-sm">
                    {r.parent_contact}
                  </TableCell>
                  <TableCell className="hidden md:table-cell text-sm text-muted-foreground">
                    {r.date ?? "—"}
                  </TableCell>
                  <TableCell>
                    <Badge variant={statusTone(r.delivery_status)}>
                      {r.delivery_status}
                    </Badge>
                  </TableCell>
                  <TableCell className="hidden lg:table-cell text-sm text-muted-foreground">
                    {r.sent_by ?? "—"}
                  </TableCell>
                  <TableCell className="hidden lg:table-cell text-sm text-muted-foreground">
                    {fmtTime(r.sent_at)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
