"use client";

import { useMemo, useState } from "react";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/layout/page-header";
import { useUserStore } from "@/store/user-store";
import {
  useAdherenceInsights,
  useOutcomeInsights,
} from "./_hooks/use-adherence";
import { KpiCard } from "./_components/kpi-card";
import { SessionsBreakdown } from "./_components/sessions-breakdown";
import { TeacherLeaderboard } from "./_components/teacher-leaderboard";
import { SyllabusCoverage } from "./_components/syllabus-coverage";
import { OutcomeBuckets } from "./_components/outcome-buckets";
import { OutcomeTeachers } from "./_components/outcome-teachers";

function isoDateNDaysAgo(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString().slice(0, 10);
}

function isoToday(): string {
  return new Date().toISOString().slice(0, 10);
}

function rateTone(pct: number): "success" | "default" | "warning" | "destructive" {
  if (pct >= 80) return "success";
  if (pct >= 60) return "default";
  if (pct >= 40) return "warning";
  return "destructive";
}

function subRateTone(pct: number): "success" | "default" | "warning" | "destructive" {
  if (pct >= 30) return "destructive";
  if (pct >= 15) return "warning";
  if (pct > 0) return "default";
  return "success";
}

export default function InsightsPage() {
  const user = useUserStore((s) => s.user);
  const branchId = user?.branch_roles?.[0]?.branch_id;

  const [fromDate, setFromDate] = useState(isoDateNDaysAgo(30));
  const [toDate, setToDate] = useState(isoToday());

  const insightsQuery = useAdherenceInsights(branchId, fromDate, toDate);
  const outcomesQuery = useOutcomeInsights(branchId, fromDate, toDate);
  const data = insightsQuery.data;
  const outcomes = outcomesQuery.data;

  const totals = data?.totals;
  const sessions = data?.sessions;
  const rates = data?.rates;
  const noShowBreakdown = data?.no_show_breakdown;
  const byTeacher = data?.by_teacher ?? [];
  const bySyllabus = data?.by_batch_syllabus ?? [];

  const dateValid = useMemo(() => {
    if (!fromDate || !toDate) return true;
    return new Date(fromDate) <= new Date(toDate);
  }, [fromDate, toDate]);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Insights"
        description="Plan-vs-Actual adherence: how much of what you scheduled actually happened, and which teachers drive the deviations."
        actions={
          <>
            <Input
              type="date"
              value={fromDate}
              onChange={(e) => setFromDate(e.target.value)}
              aria-label="From date"
              className="w-40"
            />
            <span className="text-muted-foreground text-sm">to</span>
            <Input
              type="date"
              value={toDate}
              onChange={(e) => setToDate(e.target.value)}
              aria-label="To date"
              className="w-40"
            />
          </>
        }
      />

      {!dateValid && (
        <p className="text-sm text-destructive">
          From date must be on or before To date.
        </p>
      )}

      {insightsQuery.isLoading && (
        <p className="text-muted-foreground text-sm">Loading insights...</p>
      )}

      {insightsQuery.isError && (
        <p className="text-destructive text-sm">
          Failed to load insights. Make sure the backend is running.
        </p>
      )}

      {!insightsQuery.isLoading && !insightsQuery.isError && data && (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <KpiCard
              label="Adherence"
              value={rates ? `${rates.adherence_pct.toFixed(1)}%` : "—"}
              hint={
                totals
                  ? `${totals.completed_as_planned} of ${totals.planned} planned`
                  : undefined
              }
              tone={rates ? rateTone(rates.adherence_pct) : "default"}
            />
            <KpiCard
              label="Substitute rate"
              value={rates ? `${rates.substitute_pct.toFixed(1)}%` : "—"}
              hint={totals ? `${totals.substituted} substituted` : undefined}
              tone={rates ? subRateTone(rates.substitute_pct) : "default"}
            />
            <KpiCard
              label="Teacher no-show"
              value={
                rates ? `${rates.teacher_no_show_pct.toFixed(1)}%` : "—"
              }
              hint={
                noShowBreakdown
                  ? `${noShowBreakdown.teacher} teacher · ${noShowBreakdown.student} student · ${noShowBreakdown.external} external · ${noShowBreakdown.other} other`
                  : undefined
              }
              tone={
                rates && rates.teacher_no_show_pct >= 10
                  ? "destructive"
                  : rates && rates.teacher_no_show_pct > 0
                  ? "warning"
                  : "default"
              }
            />
            <KpiCard
              label="Cancellation rate"
              value={rates ? `${rates.cancellation_pct.toFixed(1)}%` : "—"}
              hint={totals ? `${totals.cancelled} cancelled` : undefined}
              tone={rates && rates.cancellation_pct >= 15 ? "destructive" : "default"}
            />
          </div>

          {sessions && <SessionsBreakdown sessions={sessions} />}

          <div className="flex flex-col gap-3">
            <div>
              <h3 className="text-lg font-semibold">
                Teachers — substitute leaderboard
              </h3>
              <p className="text-sm text-muted-foreground">
                Top by substitute-out rate (i.e. their scheduled lectures most
                often delivered by someone else). Higher = bigger plan-vs-actual
                gap.
              </p>
            </div>
            <TeacherLeaderboard rows={byTeacher} limit={10} />
          </div>

          <div className="flex flex-col gap-3">
            <div>
              <h3 className="text-lg font-semibold">Syllabus coverage</h3>
              <p className="text-sm text-muted-foreground">
                Distinct topics actually delivered (completed lectures +
                sessions) vs. total topics in each batch&apos;s syllabus.
                Sorted lowest-first to surface batches falling behind.
              </p>
            </div>
            <SyllabusCoverage rows={bySyllabus} />
          </div>

          {outcomes && (
            <div className="flex flex-col gap-5 border-t pt-5">
              <div>
                <h3 className="text-lg font-semibold">Outcomes</h3>
                <p className="text-sm text-muted-foreground">
                  Are the lectures actually working? Cross-references
                  completed lectures with student test scores in this window.
                  Based on {outcomes.summary.tests_evaluated} test
                  {outcomes.summary.tests_evaluated !== 1 ? "s" : ""},{" "}
                  {outcomes.summary.students_with_marks} student
                  {outcomes.summary.students_with_marks !== 1 ? "s" : ""};
                  branch avg{" "}
                  <span className="font-medium text-foreground">
                    {outcomes.summary.branch_avg_score.toFixed(1)}%
                  </span>
                  .
                </p>
              </div>
              <OutcomeBuckets buckets={outcomes.attendance_buckets} />
              <div className="flex flex-col gap-2">
                <h4 className="text-base font-semibold">
                  Per-teacher score vs. branch
                </h4>
                <p className="text-sm text-muted-foreground">
                  Each row is a (teacher × subject) where the teacher
                  delivered at least one completed lecture AND a test
                  was held for that subject. Positive delta = students
                  scored above the branch average.
                </p>
                <OutcomeTeachers
                  rows={outcomes.by_teacher}
                  branchAvg={outcomes.summary.branch_avg_score}
                />
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
