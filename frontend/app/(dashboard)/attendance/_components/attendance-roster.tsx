"use client";

import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import type {
  AttendanceRecord,
  AttendanceStatus,
  RosterStudent,
} from "../_schemas/attendance";

// The four statuses an operator marks by hand. PARTIAL / MANUAL_OVERRIDE
// exist in the backend enum but aren't part of the quick-mark flow; they
// still render correctly via STATUS_META if a record already has them.
const QUICK_STATUSES: { value: AttendanceStatus; label: string; short: string }[] = [
  { value: "PRESENT", label: "Present", short: "P" },
  { value: "ABSENT", label: "Absent", short: "A" },
  { value: "LATE", label: "Late", short: "L" },
  { value: "EXCUSED", label: "Excused", short: "E" },
];

const STATUS_META: Record<
  AttendanceStatus,
  { label: string; tone: "success" | "destructive" | "warning" | "secondary" }
> = {
  PRESENT: { label: "Present", tone: "success" },
  ABSENT: { label: "Absent", tone: "destructive" },
  LATE: { label: "Late", tone: "warning" },
  EXCUSED: { label: "Excused", tone: "secondary" },
  PARTIAL: { label: "Partial", tone: "warning" },
  MANUAL_OVERRIDE: { label: "Override", tone: "secondary" },
};

// Active-state classes for the segmented quick-mark buttons, by status.
const ACTIVE_CLASS: Record<string, string> = {
  PRESENT: "bg-[var(--success)] text-white border-transparent",
  ABSENT: "bg-destructive text-white border-transparent",
  LATE: "bg-[oklch(0.42_0.13_75)] text-white border-transparent",
  EXCUSED: "bg-muted-foreground text-white border-transparent",
};

interface AttendanceRosterProps {
  roster: RosterStudent[];
  recordByStudent: Map<string, AttendanceRecord>;
  onMark: (studentId: string, status: AttendanceStatus) => void;
  pendingStudentId?: string | null;
  disabled?: boolean;
}

export function AttendanceRoster({
  roster,
  recordByStudent,
  onMark,
  pendingStudentId,
  disabled,
}: AttendanceRosterProps) {
  return (
    <div className="rounded-xl border ring-1 ring-foreground/10 overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-10 text-right tabular-nums">#</TableHead>
            <TableHead>Student</TableHead>
            <TableHead className="hidden sm:table-cell">Current</TableHead>
            <TableHead className="hidden md:table-cell">Source</TableHead>
            <TableHead className="text-right">Mark</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {roster.map((s, i) => {
            const record = recordByStudent.get(s.id);
            const current = record?.attendance_status ?? null;
            const meta = current ? STATUS_META[current] : null;
            const isPending = pendingStudentId === s.id;
            return (
              <TableRow key={s.id} data-pending={isPending || undefined}>
                <TableCell className="text-right tabular-nums text-muted-foreground text-xs">
                  {i + 1}
                </TableCell>
                <TableCell>
                  <div className="flex flex-col gap-0.5">
                    <span className="font-medium">
                      {s.first_name} {s.last_name}
                    </span>
                    {s.enrollment_number && (
                      <span className="text-xs text-muted-foreground tabular-nums">
                        {s.enrollment_number}
                      </span>
                    )}
                  </div>
                </TableCell>
                <TableCell className="hidden sm:table-cell">
                  {meta ? (
                    <Badge variant={meta.tone}>{meta.label}</Badge>
                  ) : (
                    <span className="text-xs text-muted-foreground italic">
                      Not marked
                    </span>
                  )}
                </TableCell>
                <TableCell className="hidden md:table-cell">
                  {record ? (
                    <span className="text-xs text-muted-foreground">
                      {record.source === "BIOMETRIC"
                        ? "Biometric"
                        : record.source === "SYSTEM"
                          ? "System"
                          : record.source === "IMPORT"
                            ? "Import"
                            : "Manual"}
                    </span>
                  ) : (
                    <span className="text-xs text-muted-foreground">—</span>
                  )}
                </TableCell>
                <TableCell>
                  <div className="flex justify-end">
                    <div
                      role="group"
                      aria-label={`Mark attendance for ${s.first_name} ${s.last_name}`}
                      className="inline-flex overflow-hidden rounded-lg border"
                    >
                      {QUICK_STATUSES.map((q) => {
                        const active = current === q.value;
                        return (
                          <button
                            key={q.value}
                            type="button"
                            disabled={disabled || isPending}
                            aria-pressed={active}
                            title={q.label}
                            onClick={() => onMark(s.id, q.value)}
                            className={
                              "h-7 w-8 border-l text-xs font-semibold transition-colors first:border-l-0 disabled:opacity-50 " +
                              (active
                                ? ACTIVE_CLASS[q.value]
                                : "bg-background text-muted-foreground hover:bg-muted hover:text-foreground")
                            }
                          >
                            {q.short}
                          </button>
                        );
                      })}
                    </div>
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
