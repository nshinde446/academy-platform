"use client";

import { useMemo, useState } from "react";
import { useBranchId } from "@/store/user-store";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { TableSkeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { useBatches } from "../../batches/_hooks/use-batches";
import { useTeachers } from "../_hooks/use-teachers";
import {
  useDownloadProductivityReport,
  useProductivityReport,
  useSubjectOptions,
} from "./_hooks/use-productivity-report";
import type { ProductivityReportFilters } from "./_schemas/productivity-report";
import { MultiSelect } from "./_components/multi-select";
import { ReportCards } from "./_components/report-cards";
import { ReportCharts } from "./_components/report-charts";
import { ReportTable } from "./_components/report-table";

const CONTROL =
  "h-9 rounded-lg border border-input bg-background px-3 text-sm";

function isoDaysAgo(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

// Default window: the last 30 days. Computed once at module load — not during
// render (avoids the impure-call rule) and not in an effect (avoids the
// setState-in-effect rule), and it saves an extra initial fetch.
const DEFAULT_FROM = isoDaysAgo(30);
const DEFAULT_TO = isoDaysAgo(0);

export default function TeacherProductivityReportPage() {
  const { branchId } = useBranchId();
  const toast = useToast();

  const [fromDate, setFromDate] = useState(DEFAULT_FROM);
  const [toDate, setToDate] = useState(DEFAULT_TO);
  const [batchIds, setBatchIds] = useState<string[]>([]);
  const [subjectIds, setSubjectIds] = useState<string[]>([]);
  const [teacherIds, setTeacherIds] = useState<string[]>([]);

  const filters: ProductivityReportFilters = useMemo(
    () => ({ fromDate, toDate, batchIds, subjectIds, teacherIds }),
    [fromDate, toDate, batchIds, subjectIds, teacherIds],
  );

  const reportQuery = useProductivityReport(branchId, filters);
  const download = useDownloadProductivityReport(branchId);
  const batchesQuery = useBatches(branchId);
  const teachersQuery = useTeachers(branchId);
  const subjectsQuery = useSubjectOptions(branchId);

  const batchOptions = useMemo(
    () => (batchesQuery.data ?? []).map((b) => ({ value: b.id, label: b.name })),
    [batchesQuery.data],
  );
  const subjectOptions = useMemo(
    () => (subjectsQuery.data ?? []).map((s) => ({ value: s.id, label: s.name })),
    [subjectsQuery.data],
  );
  const teacherOptions = useMemo(
    () =>
      (teachersQuery.data ?? []).map((t) => ({
        value: t.id,
        label: `${t.first_name} ${t.last_name}`,
      })),
    [teachersQuery.data],
  );

  async function exportAs(fmt: "xlsx" | "pdf") {
    try {
      await download.mutateAsync({ filters, fmt });
    } catch {
      toast.error("Export failed. Please try again.");
    }
  }

  const data = reportQuery.data;

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Teacher Productivity"
        description={
          <>
            Scheduled vs conducted lectures, completion &amp; punctuality, average
            late-start delay and topic coverage — per teacher, subject and batch,
            with a week-wise trend. Built live from the schedule and captured
            actuals; click a teacher for their day-by-day log.
          </>
        }
        actions={
          <>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => exportAs("xlsx")}
              disabled={download.isPending || !data}
            >
              Export Excel
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => exportAs("pdf")}
              disabled={download.isPending || !data}
            >
              Export PDF
            </Button>
          </>
        }
      />

      {/* Filters */}
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          From
          <input
            type="date"
            value={fromDate}
            onChange={(e) => setFromDate(e.target.value)}
            className={CONTROL}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          To
          <input
            type="date"
            value={toDate}
            onChange={(e) => setToDate(e.target.value)}
            className={CONTROL}
          />
        </label>
        <MultiSelect
          label="Batch"
          options={batchOptions}
          selected={batchIds}
          onChange={setBatchIds}
        />
        <MultiSelect
          label="Subject"
          options={subjectOptions}
          selected={subjectIds}
          onChange={setSubjectIds}
        />
        <MultiSelect
          label="Teacher"
          options={teacherOptions}
          selected={teacherIds}
          onChange={setTeacherIds}
        />
      </div>

      {reportQuery.isLoading ? (
        <TableSkeleton rows={6} />
      ) : reportQuery.isError ? (
        <p className="text-sm text-destructive">Failed to load the report.</p>
      ) : !data || data.by_teacher.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No scheduled lectures in this range for the selected filters.
        </p>
      ) : (
        <>
          <ReportCards summary={data.summary} />
          <ReportCharts report={data} />
          <ReportTable rows={data.by_teacher} />
        </>
      )}
    </div>
  );
}
