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
import { InfoHint } from "@/components/ui/info-hint";
import { useProductivityInsights } from "../_hooks/use-lectures";

interface TeacherProductivityPanelProps {
  branchId: string | undefined;
  fromDate: string;
  toDate: string;
}

function pctTone(pct: number): "success" | "secondary" | "destructive" {
  if (pct >= 90) return "success";
  if (pct >= 75) return "secondary";
  return "destructive";
}

// Turnout/attendance reads on the student 75% eligibility scale.
function attendanceTone(pct: number): "success" | "secondary" | "destructive" {
  if (pct >= 75) return "success";
  if (pct >= 60) return "secondary";
  return "destructive";
}

function pct(value: number | null): string {
  return value == null ? "—" : `${value}%`;
}

export function TeacherProductivityPanel({
  branchId,
  fromDate,
  toDate,
}: TeacherProductivityPanelProps) {
  const query = useProductivityInsights(branchId, fromDate, toDate);
  const data = query.data;

  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div className="flex items-center gap-1.5">
          <h3 className="text-lg font-semibold">Teacher Productivity</h3>
          <InfoHint
            text={
              <>
                Hours &amp; punctuality come from completed lectures.{" "}
                <span className="font-medium">Turnout</span> is the average
                student attendance in each teacher&apos;s classes (biometric
                day-presence).{" "}
                <span className="font-medium">Reliability</span> is how many of
                the classes assigned to a teacher they personally delivered —
                the rest were no-shows or handed to a substitute. Reliability is
                a lifecycle signal, not the teacher&apos;s own biometric
                attendance (teachers aren&apos;t on the device).
              </>
            }
          />
        </div>
        <p className="text-xs text-muted-foreground">
          {fromDate || toDate
            ? `${fromDate || "start"} → ${toDate || "now"}`
            : "all time"}
        </p>
      </div>

      {query.isLoading ? (
        <p className="text-sm text-muted-foreground">Loading productivity…</p>
      ) : query.isError ? (
        <p className="text-sm text-destructive">Failed to load productivity.</p>
      ) : !data || data.by_teacher.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No completed lectures with recorded actuals in this range yet. Use{" "}
          <span className="font-medium">End-of-Day Update</span> or
          Start/Complete to capture actuals.
        </p>
      ) : (
        <>
          {/* Summary KPI strip */}
          <div className="grid grid-cols-2 gap-3 rounded-xl border p-3 sm:grid-cols-3 lg:grid-cols-6">
            <Kpi label="Teachers" value={String(data.summary.teachers)} />
            <Kpi
              label="Lectures taught"
              value={String(data.summary.total_lectures)}
            />
            <Kpi label="Total hours" value={`${data.summary.total_hours}h`} />
            <Kpi
              label="On-time"
              value={pct(data.summary.branch_punctuality_pct)}
            />
            <Kpi
              label="Student turnout"
              value={pct(data.summary.branch_turnout_pct)}
              hint="attendance in their classes"
            />
            <Kpi
              label="Reliability"
              value={pct(data.summary.branch_reliability_pct)}
              hint={`${data.summary.total_teacher_no_show} teacher no-show${
                data.summary.total_teacher_no_show === 1 ? "" : "s"
              }`}
            />
          </div>

          <div className="rounded-xl border ring-1 ring-foreground/10 overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Teacher</TableHead>
                  <TableHead className="text-right">Lectures</TableHead>
                  <TableHead className="hidden sm:table-cell text-right">
                    Hours
                  </TableHead>
                  <TableHead className="text-right">Punctuality</TableHead>
                  <TableHead className="text-right">Turnout</TableHead>
                  <TableHead className="text-right">Reliability</TableHead>
                  <TableHead className="hidden md:table-cell text-right">
                    No-show
                  </TableHead>
                  <TableHead className="hidden lg:table-cell text-right">
                    Sub&apos;d
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.by_teacher.map((t) => (
                  <TableRow key={t.teacher_id}>
                    <TableCell className="font-medium">
                      {t.first_name} {t.last_name}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {t.lectures_taught}
                    </TableCell>
                    <TableCell className="hidden sm:table-cell text-right tabular-nums text-muted-foreground">
                      {t.hours_taught}h
                    </TableCell>
                    <TableCell className="text-right">
                      {t.punctuality_pct == null ? (
                        <span className="text-muted-foreground">—</span>
                      ) : (
                        <Badge variant={pctTone(t.punctuality_pct)}>
                          {t.punctuality_pct}%
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      {t.student_turnout_pct == null ? (
                        <span className="text-muted-foreground">—</span>
                      ) : (
                        <Badge variant={attendanceTone(t.student_turnout_pct)}>
                          {t.student_turnout_pct}%
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      {t.reliability_pct == null ? (
                        <span className="text-muted-foreground">—</span>
                      ) : (
                        <Badge variant={pctTone(t.reliability_pct)}>
                          {t.reliability_pct}%
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell className="hidden md:table-cell text-right tabular-nums text-muted-foreground">
                      {t.teacher_no_show}
                    </TableCell>
                    <TableCell className="hidden lg:table-cell text-right tabular-nums text-muted-foreground">
                      {t.substituted_out}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </>
      )}
    </section>
  );
}

function Kpi({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-xl font-semibold tabular-nums">{value}</span>
      {hint && <span className="text-[10px] text-muted-foreground">{hint}</span>}
    </div>
  );
}
