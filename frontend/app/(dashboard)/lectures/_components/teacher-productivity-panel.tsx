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
import { useProductivityInsights } from "../_hooks/use-lectures";

interface TeacherProductivityPanelProps {
  branchId: string | undefined;
  fromDate: string;
  toDate: string;
}

function punctualityTone(pct: number): "success" | "secondary" | "destructive" {
  if (pct >= 90) return "success";
  if (pct >= 75) return "secondary";
  return "destructive";
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
        <div>
          <h3 className="text-lg font-semibold">Teacher Productivity</h3>
          <p className="text-xs text-muted-foreground">
            Hours taught & punctuality from completed lectures
            {fromDate || toDate
              ? ` · ${fromDate || "start"} → ${toDate || "now"}`
              : " · all time"}
            . Reflects lectures whose actuals were recorded.
          </p>
        </div>
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
          <div className="grid grid-cols-2 gap-3 rounded-xl border p-3 sm:grid-cols-4">
            <Kpi label="Teachers" value={String(data.summary.teachers)} />
            <Kpi
              label="Lectures taught"
              value={String(data.summary.total_lectures)}
            />
            <Kpi label="Total hours" value={`${data.summary.total_hours}h`} />
            <Kpi
              label="On-time"
              value={`${data.summary.branch_punctuality_pct}%`}
            />
          </div>

          <div className="rounded-xl border ring-1 ring-foreground/10 overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Teacher</TableHead>
                  <TableHead className="text-right">Lectures</TableHead>
                  <TableHead className="text-right">Hours</TableHead>
                  <TableHead className="hidden sm:table-cell text-right">
                    Avg / lecture
                  </TableHead>
                  <TableHead className="text-right">Punctuality</TableHead>
                  <TableHead className="hidden md:table-cell text-right">
                    Late
                  </TableHead>
                  <TableHead className="hidden lg:table-cell text-right">
                    Topics
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
                    <TableCell className="text-right tabular-nums">
                      {t.hours_taught}h
                    </TableCell>
                    <TableCell className="hidden sm:table-cell text-right tabular-nums text-muted-foreground">
                      {t.avg_lecture_min}m
                    </TableCell>
                    <TableCell className="text-right">
                      <Badge variant={punctualityTone(t.punctuality_pct)}>
                        {t.punctuality_pct}%
                      </Badge>
                    </TableCell>
                    <TableCell className="hidden md:table-cell text-right tabular-nums text-muted-foreground">
                      {t.late_count}
                    </TableCell>
                    <TableCell className="hidden lg:table-cell text-right tabular-nums text-muted-foreground">
                      {t.distinct_topics}
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

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-xl font-semibold tabular-nums">{value}</span>
    </div>
  );
}
