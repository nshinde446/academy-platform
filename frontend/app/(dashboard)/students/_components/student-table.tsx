"use client";

import Link from "next/link";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  NumCell,
  RosterAvatar,
  ScoreCell,
} from "@/components/roster/roster-primitives";
import {
  STANDARDS,
  STREAMS,
  type StudentUpdate,
  type StudentWithStats,
} from "../_schemas/student";

// Inline-editable fees values (the four allowed Student.fees_status enum values).
const FEES_OPTIONS = ["paid", "due", "overdue", "partial"] as const;

interface StudentTableProps {
  rows: StudentWithStats[];
  // Handlers act on the (paginated) roster row; the page fetches the full
  // record on Edit, since the stats payload omits some fields.
  onEdit: (student: StudentWithStats) => void;
  onDelete: (student: StudentWithStats) => void;
  // Inline cell edits (stream / class / fees) — each persisted via PATCH by the
  // page. One generic handler so adding more inline fields stays cheap.
  onFieldChange: (student: StudentWithStats, patch: Partial<StudentUpdate>) => void;
  // Server-side sort: current key/direction + a click handler per column.
  sortBy: string;
  order: "asc" | "desc";
  onSort: (key: string) => void;
  // Row selection for bulk actions — optional; when omitted the checkbox
  // column is hidden (keeps the table usable without a selection model).
  selectedIds?: Set<string>;
  onToggleSelect?: (id: string) => void;
  onToggleSelectAll?: () => void;
}

// Shared styling for the small inline-edit <select>s in the roster cells.
const INLINE_SELECT =
  "h-8 rounded-md border border-input bg-background px-2 text-xs";

export function StudentTable({
  rows,
  onEdit,
  onDelete,
  onFieldChange,
  sortBy,
  order,
  onSort,
  selectedIds,
  onToggleSelect,
  onToggleSelectAll,
}: StudentTableProps) {
  const selectable = !!onToggleSelect;
  const allSelected =
    selectable &&
    rows.length > 0 &&
    rows.every((r) => selectedIds?.has(r.id));
  // A clickable, sort-aware column header. `align="right"` matches the
  // numeric columns' right alignment.
  function SortHead({
    label,
    sortKey,
    className = "",
    align = "left",
  }: {
    label: string;
    sortKey: string;
    className?: string;
    align?: "left" | "right";
  }) {
    const active = sortBy === sortKey;
    const arrow = active ? (order === "asc" ? " ↑" : " ↓") : "";
    return (
      <TableHead className={className}>
        <button
          type="button"
          onClick={() => onSort(sortKey)}
          aria-label={`Sort by ${label}`}
          aria-sort={active ? (order === "asc" ? "ascending" : "descending") : "none"}
          className={
            "inline-flex items-center gap-0.5 hover:text-foreground " +
            (active ? "font-semibold text-foreground" : "") +
            (align === "right" ? " w-full justify-end" : "")
          }
        >
          {label}
          <span className="tabular-nums">{arrow}</span>
        </button>
      </TableHead>
    );
  }

  return (
    <div className="rounded-xl border ring-1 ring-foreground/10 overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow>
            {selectable && (
              <TableHead className="w-9">
                <input
                  type="checkbox"
                  aria-label="Select all on this page"
                  checked={allSelected}
                  onChange={() => onToggleSelectAll?.()}
                />
              </TableHead>
            )}
            <TableHead className="w-9"></TableHead>
            <SortHead label="Name" sortKey="name" />
            <TableHead className="hidden sm:table-cell">Class</TableHead>
            <TableHead className="hidden md:table-cell">Target</TableHead>
            <TableHead className="hidden md:table-cell">Stream</TableHead>
            <TableHead className="hidden lg:table-cell">Batch</TableHead>
            <SortHead
              label="Rank"
              sortKey="batch_rank"
              align="right"
              className="text-right hidden md:table-cell"
            />
            <SortHead
              label="Avg score"
              sortKey="avg_score_pct"
              align="right"
              className="text-right"
            />
            <SortHead
              label="Attendance"
              sortKey="attendance_pct"
              align="right"
              className="text-right hidden sm:table-cell"
            />
            <SortHead
              label="DPP"
              sortKey="dpp_completion_pct"
              align="right"
              className="text-right hidden lg:table-cell"
            />
            <TableHead className="hidden md:table-cell">Fees</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((r) => {
            return (
              <TableRow key={r.id}>
                {selectable && (
                  <TableCell>
                    <input
                      type="checkbox"
                      aria-label={`Select ${r.first_name} ${r.last_name}`}
                      checked={selectedIds?.has(r.id) ?? false}
                      onChange={() => onToggleSelect?.(r.id)}
                    />
                  </TableCell>
                )}
                <TableCell>
                  <RosterAvatar first={r.first_name} last={r.last_name} />
                </TableCell>
                <TableCell className="font-medium">
                  <Link
                    href={`/students/${r.id}`}
                    className="hover:underline"
                  >
                    {r.first_name} {r.last_name}
                  </Link>
                  {r.enrollment_number ? (
                    <span className="ml-2 text-xs text-muted-foreground tabular-nums">
                      {r.enrollment_number}
                    </span>
                  ) : null}
                </TableCell>
                <TableCell className="hidden sm:table-cell">
                  <select
                    aria-label={`Class for ${r.first_name} ${r.last_name}`}
                    className={INLINE_SELECT}
                    value={r.standard ?? ""}
                    onChange={(e) => {
                      const v = e.target.value;
                      if (v) onFieldChange(r, { standard: v as (typeof STANDARDS)[number] });
                    }}
                  >
                    {!r.standard && <option value="">—</option>}
                    {STANDARDS.map((s) => (
                      <option key={s} value={s}>
                        {s === "Dropper" ? "Dropper" : `Class ${s}`}
                      </option>
                    ))}
                  </select>
                </TableCell>
                <TableCell className="hidden md:table-cell">
                  {r.target_exam ? (
                    <Badge variant="secondary">{r.target_exam}</Badge>
                  ) : (
                    "—"
                  )}
                </TableCell>
                <TableCell className="hidden md:table-cell">
                  <select
                    aria-label={`Stream for ${r.first_name} ${r.last_name}`}
                    className={INLINE_SELECT}
                    value={r.stream ?? ""}
                    onChange={(e) => {
                      const v = e.target.value;
                      if (v) onFieldChange(r, { stream: v as (typeof STREAMS)[number] });
                    }}
                  >
                    {!r.stream && <option value="">—</option>}
                    {STREAMS.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </TableCell>
                <TableCell className="hidden lg:table-cell text-xs text-muted-foreground">
                  {r.batch_name ?? "—"}
                </TableCell>
                <TableCell className="text-right hidden md:table-cell">
                  {r.batch_rank ? (
                    <NumCell>#{r.batch_rank}</NumCell>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </TableCell>
                <TableCell className="text-right">
                  <ScoreCell value={r.avg_score_pct} />
                </TableCell>
                <TableCell className="text-right hidden sm:table-cell">
                  <NumCell>{r.attendance_pct.toFixed(0)}%</NumCell>
                </TableCell>
                <TableCell className="text-right hidden lg:table-cell">
                  <ScoreCell value={r.dpp_completion_pct} tone="muted" />
                </TableCell>
                <TableCell className="hidden md:table-cell">
                  <select
                    aria-label={`Fees for ${r.first_name} ${r.last_name}`}
                    className={INLINE_SELECT}
                    value={r.fees_status ?? ""}
                    onChange={(e) => {
                      const v = e.target.value;
                      if (v)
                        onFieldChange(r, {
                          fees_status: v as (typeof FEES_OPTIONS)[number],
                        });
                    }}
                  >
                    {!r.fees_status && <option value="">—</option>}
                    {FEES_OPTIONS.map((s) => (
                      <option key={s} value={s}>
                        {s[0].toUpperCase() + s.slice(1)}
                      </option>
                    ))}
                  </select>
                </TableCell>
                <TableCell className="text-right">
                  <div className="flex justify-end gap-1">
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => onEdit(r)}
                    >
                      Edit
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="destructive"
                      onClick={() => onDelete(r)}
                      aria-label={`Delete ${r.first_name} ${r.last_name}`}
                    >
                      Delete
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
