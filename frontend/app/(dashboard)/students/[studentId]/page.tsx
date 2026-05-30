"use client";

import { use, useMemo } from "react";
import Link from "next/link";
import { useUserStore } from "@/store/user-store";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import {
  useStudent,
  useStudentTestHistory,
  useStudentsWithStats,
} from "../_hooks/use-students";
import type { StudentTestHistoryRow } from "../_schemas/student";

function formatScheduled(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
  });
}

function rankCell(rank: number | null, size: number): string {
  if (rank == null || size === 0) return "—";
  return `#${rank} / ${size}`;
}

function paperTypeBadge(t: string): {
  label: string;
  tone: "default" | "secondary" | "success" | "destructive";
} {
  if (t === "DPP") return { label: "DPP", tone: "secondary" };
  if (t === "CPP") return { label: "CPP", tone: "secondary" };
  return { label: t || "TEST", tone: "default" };
}

export default function StudentDetailPage({
  params,
}: {
  params: Promise<{ studentId: string }>;
}) {
  const { studentId } = use(params);
  const user = useUserStore((s) => s.user);
  const branchId = user?.branch_roles?.[0]?.branch_id;

  const studentQuery = useStudent(branchId, studentId);
  const historyQuery = useStudentTestHistory(branchId, studentId);
  // Pulled for batch / attendance / current-batch-rank from the same
  // payload that backs /students — keeps numbers consistent.
  const statsQuery = useStudentsWithStats(branchId);

  const student = studentQuery.data;
  const stats = useMemo(
    () => statsQuery.data?.find((s) => s.id === studentId),
    [statsQuery.data, studentId],
  );
  const history: StudentTestHistoryRow[] = historyQuery.data ?? [];

  const presentRows = history.filter((r) => !r.is_absent);
  const avgPct =
    presentRows.length > 0
      ? presentRows.reduce((sum, r) => sum + r.percentage, 0) /
        presentRows.length
      : 0;

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-3">
        <Link
          href="/students"
          className="text-xs text-muted-foreground hover:text-foreground"
        >
          ← Back to Students
        </Link>
        <div className="flex flex-col gap-1">
          <h2 className="text-2xl font-semibold">
            {student
              ? `${student.first_name} ${student.last_name}`
              : studentQuery.isLoading
                ? "Loading…"
                : "—"}
          </h2>
          {student && (
            <p className="text-sm text-muted-foreground">
              {student.enrollment_number ? (
                <span className="tabular-nums">{student.enrollment_number}</span>
              ) : null}
              {student.standard && (
                <span>
                  {student.enrollment_number ? " · " : ""}
                  {student.standard === "Dropper"
                    ? "Dropper"
                    : `Class ${student.standard}`}
                </span>
              )}
              {student.target_exam && <span> · {student.target_exam}</span>}
              {stats?.batch_name && <span> · {stats.batch_name}</span>}
            </p>
          )}
          {student && (student.email || student.phone || student.parent_mobile) && (
            <p className="text-xs text-muted-foreground">
              {student.email && <span>{student.email}</span>}
              {student.phone && (
                <span>{student.email ? " · " : ""}{student.phone}</span>
              )}
              {student.parent_mobile && (
                <span>
                  {student.email || student.phone ? " · " : ""}Parent{" "}
                  {student.parent_mobile}
                </span>
              )}
            </p>
          )}
        </div>
      </div>

      <Card size="sm">
        <CardContent>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Kpi label="Tests taken" value={history.length} />
            <Kpi
              label="Avg score"
              value={`${avgPct.toFixed(1)}%`}
              tone={
                avgPct >= 75 ? "success" : avgPct < 40 ? "destructive" : "default"
              }
            />
            <Kpi
              label="Attendance"
              value={
                stats ? `${stats.attendance_pct.toFixed(0)}%` : "—"
              }
              tone={
                stats && stats.attendance_pct < 60 ? "destructive" : "default"
              }
            />
            <Kpi
              label="Current batch rank"
              value={
                stats?.batch_rank
                  ? `#${stats.batch_rank} / ${stats.batch_size}`
                  : "—"
              }
            />
          </div>
        </CardContent>
      </Card>

      <div className="flex flex-col gap-2">
        <h3 className="text-lg font-semibold">Test history</h3>
        <p className="text-sm text-muted-foreground">
          Every test this student has marks for. Rank columns show
          ordering by percentage within the same batch and across the
          whole institute — absentees aren&apos;t ranked.
        </p>
        {historyQuery.isLoading ? (
          <p className="text-sm text-muted-foreground italic">Loading…</p>
        ) : history.length === 0 ? (
          <p className="text-sm text-muted-foreground italic">
            No test marks recorded for this student yet.
          </p>
        ) : (
          <div className="rounded-xl border ring-1 ring-foreground/10 overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Test</TableHead>
                  <TableHead className="hidden sm:table-cell">Subject</TableHead>
                  <TableHead className="hidden md:table-cell">Topics</TableHead>
                  <TableHead className="text-right">Marks</TableHead>
                  <TableHead className="text-right">%</TableHead>
                  <TableHead className="text-right hidden sm:table-cell">
                    Batch rank
                  </TableHead>
                  <TableHead className="text-right hidden md:table-cell">
                    Institute rank
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {history.map((r) => {
                  const pt = paperTypeBadge(r.paper_type);
                  return (
                    <TableRow key={r.test_id}>
                      <TableCell className="whitespace-nowrap text-sm">
                        {formatScheduled(r.scheduled_at)}
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-col gap-0.5">
                          <span className="font-medium">{r.test_name}</span>
                          <Badge variant={pt.tone} className="w-fit text-[10px]">
                            {pt.label}
                          </Badge>
                        </div>
                      </TableCell>
                      <TableCell className="hidden sm:table-cell text-sm">
                        {r.subject_name || "—"}
                      </TableCell>
                      <TableCell className="hidden md:table-cell text-xs text-muted-foreground max-w-xs">
                        {r.topics.length > 0 ? r.topics.join(", ") : "—"}
                      </TableCell>
                      <TableCell className="text-right tabular-nums whitespace-nowrap">
                        {r.is_absent ? (
                          <span className="text-muted-foreground italic">
                            Absent
                          </span>
                        ) : (
                          <>
                            {r.marks_obtained}/{r.max_marks}
                          </>
                        )}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {r.is_absent ? "—" : `${r.percentage.toFixed(1)}%`}
                      </TableCell>
                      <TableCell className="text-right tabular-nums hidden sm:table-cell">
                        {rankCell(r.batch_rank, r.batch_size)}
                      </TableCell>
                      <TableCell className="text-right tabular-nums hidden md:table-cell">
                        {rankCell(r.institute_rank, r.institute_size)}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        )}
      </div>
    </div>
  );
}

function Kpi({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: string | number;
  tone?: "default" | "success" | "destructive";
}) {
  const cls =
    tone === "destructive"
      ? "text-destructive"
      : tone === "success"
        ? "text-emerald-600 dark:text-emerald-400"
        : "text-foreground";
  return (
    <div className="flex flex-col">
      <span className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </span>
      <span className={`text-2xl font-semibold ${cls}`}>{value}</span>
    </div>
  );
}
