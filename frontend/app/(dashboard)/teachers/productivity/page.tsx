"use client";

import { useMemo, useState } from "react";
import { useBranchId } from "@/store/user-store";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { TableSkeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { useTeachers } from "../_hooks/use-teachers";
import {
  useDownloadProductivityReport,
  useProductivityReport,
} from "./_hooks/use-productivity-report";
import type { ProductivityFilters } from "./_schemas/productivity-report";
import { MultiSelect } from "./_components/multi-select";
import { ReportTable } from "./_components/report-table";
import { PieChart, withOthers } from "./_components/pie-chart";

const CONTROL = "h-9 rounded-lg border border-input bg-background px-3 text-sm";

type Preset = "daily" | "weekly" | "monthly" | "custom";

function localISO(d: Date): string {
  const off = d.getTimezoneOffset();
  return new Date(d.getTime() - off * 60000).toISOString().slice(0, 10);
}

// Preset → [from, to]. Weekly = last 7 days incl. today; Monthly = month-to-date.
function presetRange(p: Exclude<Preset, "custom">): [string, string] {
  const today = new Date();
  const to = localISO(today);
  if (p === "daily") return [to, to];
  if (p === "weekly") {
    const from = new Date(today);
    from.setDate(from.getDate() - 6);
    return [localISO(from), to];
  }
  const from = new Date(today.getFullYear(), today.getMonth(), 1);
  return [localISO(from), to];
}

const [MONTH_FROM, MONTH_TO] = presetRange("monthly");

export default function TeacherProductivityReportPage() {
  const { branchId } = useBranchId();
  const toast = useToast();

  const [preset, setPreset] = useState<Preset>("monthly");
  const [fromDate, setFromDate] = useState(MONTH_FROM);
  const [toDate, setToDate] = useState(MONTH_TO);
  const [teacherIds, setTeacherIds] = useState<string[]>([]);

  function applyPreset(p: Preset) {
    setPreset(p);
    if (p !== "custom") {
      const [from, to] = presetRange(p);
      setFromDate(from);
      setToDate(to);
    }
  }

  const filters: ProductivityFilters = useMemo(
    () => ({ fromDate, toDate, teacherIds }),
    [fromDate, toDate, teacherIds],
  );

  const reportQuery = useProductivityReport(branchId, filters);
  const download = useDownloadProductivityReport(branchId);
  const teachersQuery = useTeachers(branchId);

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
        description="Per-teacher present days, lectures conducted and scheduled vs delivered hours over a date range, with subject-wise and teacher-wise lecture pie charts. Built from staff biometric attendance joined with the lecture schedule."
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

      {/* Date-range presets + custom range + optional teacher filter */}
      <div className="flex flex-wrap items-end gap-3">
        <div
          role="radiogroup"
          aria-label="Date range preset"
          className="inline-flex rounded-lg border border-input p-0.5"
        >
          {(
            [
              ["daily", "Daily"],
              ["weekly", "Weekly"],
              ["monthly", "Monthly"],
              ["custom", "Custom"],
            ] as [Preset, string][]
          ).map(([value, label]) => (
            <button
              key={value}
              type="button"
              role="radio"
              aria-checked={preset === value}
              onClick={() => applyPreset(value)}
              className={`rounded-md px-3 py-1 text-[13px] font-medium transition-colors ${
                preset === value
                  ? "bg-primary text-primary-foreground"
                  : "text-foreground hover:bg-muted"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          From
          <input
            type="date"
            value={fromDate}
            max={toDate}
            onChange={(e) => {
              setFromDate(e.target.value);
              setPreset("custom");
            }}
            className={CONTROL}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          To
          <input
            type="date"
            value={toDate}
            min={fromDate}
            onChange={(e) => {
              setToDate(e.target.value);
              setPreset("custom");
            }}
            className={CONTROL}
          />
        </label>
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
      ) : !data || data.rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No teaching staff / lectures in this range for the selected filters.
        </p>
      ) : (
        <>
          <ReportTable rows={data.rows} />
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <PieChart
              title="Subject-wise Lectures"
              slices={withOthers(
                data.by_subject.map((s) => ({ label: s.label, value: s.lectures })),
              )}
            />
            <PieChart
              title="Teacher-wise Lectures"
              slices={withOthers(
                data.by_teacher.map((t) => ({ label: t.label, value: t.lectures })),
              )}
            />
          </div>
        </>
      )}
    </div>
  );
}
