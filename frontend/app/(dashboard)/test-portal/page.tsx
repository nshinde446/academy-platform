"use client";

import { useMemo, useState } from "react";
import { useBranchId } from "@/store/user-store";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { TableSkeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { useTests, useScheduleTest } from "./_hooks/use-test-portal";
import type { ScheduleTestInput, TestSummary } from "./_schemas/test-portal";
import { ScheduleTestDialog } from "./_components/schedule-test-dialog";
import { RankList } from "./_components/rank-list";

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? "—"
    : d.toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" });
}

export default function TestPortalPage() {
  const { branchId } = useBranchId();
  const toast = useToast();
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const testsQuery = useTests(branchId);
  const schedule = useScheduleTest(branchId);

  // Only the offline-OMR tests belong in the Test Portal (composer papers are
  // DPP/CPP and live on the Papers page).
  const tests = useMemo(
    () => (testsQuery.data ?? []).filter((t) => t.omr_type != null || t.test_status !== "DRAFT"),
    [testsQuery.data],
  );
  const selected = tests.find((t) => t.id === selectedId) ?? null;

  async function handleSchedule(data: ScheduleTestInput) {
    await schedule.mutateAsync(data);
    toast.success("Test scheduled", data.name);
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Test Portal"
        description="Schedule offline OMR tests, upload the ZipGrade results CSV, and get an automatic rank list — no more rebuilding it in Excel."
        actions={
          <ScheduleTestDialog
            branchId={branchId}
            onSubmit={handleSchedule}
            isPending={schedule.isPending}
          />
        }
      />

      <div className="grid items-start gap-4 lg:grid-cols-[320px_1fr]">
        {/* Test list */}
        <div className="flex flex-col gap-2">
          {testsQuery.isLoading ? (
            <TableSkeleton rows={5} />
          ) : tests.length === 0 ? (
            <Card size="sm">
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  No tests yet. Schedule one to get started.
                </p>
              </CardContent>
            </Card>
          ) : (
            tests.map((t) => (
              <TestListItem
                key={t.id}
                test={t}
                active={t.id === selectedId}
                onClick={() => setSelectedId(t.id)}
                fmtDate={fmtDate}
              />
            ))
          )}
        </div>

        {/* Selected test rank list */}
        <div className="min-w-0">
          {!selected ? (
            <Card size="sm">
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  Select a test to upload its ZipGrade CSV and view the rank list.
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="flex flex-col gap-3">
              <div className="flex flex-wrap items-baseline gap-2">
                <h2 className="text-base font-semibold">{selected.name}</h2>
                <span className="text-xs text-muted-foreground">
                  {fmtDate(selected.scheduled_at)} · {selected.total_marks} marks
                  {selected.omr_type ? ` · ${selected.omr_type}` : ""}
                </span>
              </div>
              <RankList branchId={branchId} test={selected} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function TestListItem({
  test,
  active,
  onClick,
  fmtDate,
}: {
  test: TestSummary;
  active: boolean;
  onClick: () => void;
  fmtDate: (iso: string | null) => string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex flex-col items-start gap-0.5 rounded-lg border px-3 py-2 text-left transition-colors ${
        active ? "border-primary bg-primary/5" : "border-border hover:bg-muted"
      }`}
    >
      <span className="text-sm font-medium">{test.name}</span>
      <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
        {fmtDate(test.scheduled_at)} · {test.total_marks} marks
        {test.omr_type && <Badge variant="secondary">{test.omr_type}</Badge>}
      </span>
    </button>
  );
}
