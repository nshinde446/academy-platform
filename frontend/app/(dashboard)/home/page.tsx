"use client";

import { useMemo } from "react";
import Link from "next/link";
import { useUserStore } from "@/store/user-store";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  KpiBlock,
  KpiGrid,
  SectionLabel,
} from "@/components/dashboard/kpi-block";
import { useRoster } from "../today/_hooks/use-roster";
import {
  useAdherenceInsights,
  useOutcomeInsights,
} from "../insights/_hooks/use-adherence";
import {
  useQuestionCount,
  useQuestionList,
} from "../question-bank/_hooks/use-question-bank";

function isoToday(): string {
  return new Date().toISOString().slice(0, 10);
}
function isoNDaysAgo(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString().slice(0, 10);
}

export default function HomePage() {
  const user = useUserStore((s) => s.user);
  const branchId = user?.branch_roles?.[0]?.branch_id;

  const today = isoToday();
  const last30From = isoNDaysAgo(30);
  const last30To = today;

  const rosterQuery = useRoster(branchId, today);
  const adherenceQuery = useAdherenceInsights(branchId, last30From, last30To);
  const outcomesQuery = useOutcomeInsights(branchId, last30From, last30To);
  const pendingCount = useQuestionCount(branchId, {
    review_status: "pending_review",
  });
  const pendingList = useQuestionList(branchId, {
    review_status: "pending_review",
  });

  const roster = rosterQuery.data;
  const adherence = adherenceQuery.data;
  const outcomes = outcomesQuery.data;

  const friendly = useMemo(() => {
    const h = new Date().getHours();
    const greeting =
      h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
    return `${greeting}, ${user?.first_name ?? "there"}.`;
  }, [user]);

  const todayDate = new Date().toLocaleDateString(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
  });

  const subtitleBits: string[] = ["Branch console"];
  if (roster) {
    subtitleBits.push(
      `${roster.snapshot.planned} lecture${roster.snapshot.planned !== 1 ? "s" : ""} today`,
    );
  }
  if (pendingCount.data) {
    subtitleBits.push(`${pendingCount.data} questions pending review`);
  }

  const offPlan = roster
    ? roster.snapshot.off_plan_makeup +
      roster.snapshot.off_plan_ad_hoc +
      roster.snapshot.off_plan_merged
    : 0;

  const flaggedTeachers = useMemo(() => {
    if (!adherence) return [];
    return adherence.by_teacher
      .filter((t) => t.planned >= 2 && t.substitute_rate_pct > 0)
      .slice(0, 3);
  }, [adherence]);

  const flaggedBatches = useMemo(() => {
    if (!adherence) return [];
    return adherence.by_batch_syllabus
      .filter(
        (b) => b.pace_status === "behind" || b.pace_status === "critically_behind",
      )
      .slice(0, 3);
  }, [adherence]);

  const topPending = (pendingList.data ?? []).slice(0, 3);

  return (
    <div className="flex flex-col gap-6">
      {/* Page head — title + dated subtitle + action group */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-[22px] font-semibold tracking-tight">{friendly}</h2>
          <p className="mt-1 max-w-[720px] text-[13px] text-muted-foreground">
            {todayDate} · {subtitleBits.join(" · ")}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link href="/today">
            <Button size="sm">Open today&apos;s roster</Button>
          </Link>
          <Link href="/question-bank">
            <Button size="sm" variant="outline">
              Review queue
            </Button>
          </Link>
          <Link href="/insights">
            <Button size="sm" variant="outline">
              Full insights
            </Button>
          </Link>
        </div>
      </div>

      {/* Today at a glance — single card containing KPI grid */}
      <section className="flex flex-col gap-3">
        <SectionLabel>Today at a glance</SectionLabel>
        <Card>
          <CardContent>
            {rosterQuery.isLoading || !roster ? (
              <p className="text-sm text-muted-foreground">Loading…</p>
            ) : (
              <KpiGrid>
                <KpiBlock
                  label="Planned"
                  value={roster.snapshot.planned}
                  hint={`${roster.snapshot.completed} done · ${roster.snapshot.pending} pending`}
                />
                <KpiBlock
                  label="Live now"
                  value={roster.snapshot.in_progress}
                  tone={
                    roster.live_now.some((l) => l.kind === "overdue")
                      ? "destructive"
                      : roster.snapshot.in_progress > 0
                        ? "success"
                        : "default"
                  }
                  hint={
                    roster.live_now.length > 0
                      ? `${roster.live_now.filter((l) => l.kind === "overdue").length} overdue`
                      : "—"
                  }
                />
                <KpiBlock
                  label="Teacher no-shows"
                  value={roster.snapshot.no_show_teacher}
                  tone={
                    roster.snapshot.no_show_teacher > 0
                      ? "destructive"
                      : "default"
                  }
                  hint={
                    roster.snapshot.no_show_teacher === 0
                      ? "all clear"
                      : `+${roster.snapshot.no_show_other} other`
                  }
                />
                <KpiBlock
                  label="Off-plan"
                  value={offPlan}
                  hint={
                    offPlan > 0
                      ? `${roster.snapshot.off_plan_makeup} makeup · ${roster.snapshot.off_plan_ad_hoc} ad-hoc`
                      : "—"
                  }
                />
              </KpiGrid>
            )}
          </CardContent>
        </Card>
      </section>

      {/* Needs your attention — paired list cards */}
      <section className="flex flex-col gap-3">
        <SectionLabel>Needs your attention</SectionLabel>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {/* Pending question reviews */}
          <Card>
            <CardHeader>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <CardTitle className="text-base">
                    Questions pending review
                  </CardTitle>
                  <p className="mt-1 text-[12px] text-muted-foreground">
                    AI- and study-material-ingested questions waiting for a
                    subject expert.
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant="default">
                    {pendingCount.data ?? 0} pending
                  </Badge>
                  <Link href="/question-bank">
                    <Button size="sm" variant="outline">
                      Open queue →
                    </Button>
                  </Link>
                </div>
              </div>
            </CardHeader>
            <CardContent className="pt-0">
              {pendingList.isLoading ? (
                <p className="text-sm text-muted-foreground">Loading…</p>
              ) : topPending.length === 0 ? (
                <p className="text-sm italic text-muted-foreground">
                  No questions waiting for review.
                </p>
              ) : (
                <ul className="flex flex-col divide-y">
                  {topPending.map((q) => (
                    <li key={q.id} className="py-2.5">
                      <Link
                        href="/question-bank"
                        className="flex items-start gap-3 -mx-1 rounded-md px-1 hover:bg-muted/50"
                      >
                        <span className="mt-1.5 inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-amber-500" />
                        <div className="flex min-w-0 flex-1 flex-col">
                          <span className="line-clamp-1 text-sm font-medium">
                            {q.content.slice(0, 110)}
                            {q.content.length > 110 ? "…" : ""}
                          </span>
                          <span className="text-[11px] text-muted-foreground tabular-nums">
                            {q.difficulty} · {q.blooms_taxonomy}
                            {q.source ? ` · ${q.source}` : ""}
                          </span>
                        </div>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>

          {/* Branch outcome (last 30d) */}
          <Card>
            <CardHeader>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <CardTitle className="text-base">
                    Branch outcome (last 30 days)
                  </CardTitle>
                  <p className="mt-1 text-[12px] text-muted-foreground">
                    Tests evaluated and average score across the branch.
                  </p>
                </div>
                <Link href="/insights">
                  <Button size="sm" variant="outline">
                    Item analysis →
                  </Button>
                </Link>
              </div>
            </CardHeader>
            <CardContent className="pt-0">
              {outcomesQuery.isLoading || !outcomes ? (
                <p className="text-sm text-muted-foreground">Loading…</p>
              ) : (
                <KpiGrid>
                  <KpiBlock
                    label="Tests evaluated"
                    value={outcomes.summary.tests_evaluated}
                    hint="last 30 days"
                  />
                  <KpiBlock
                    label="Students"
                    value={outcomes.summary.students_with_marks}
                    hint="with at least 1 mark"
                  />
                  <KpiBlock
                    label="Branch avg"
                    value={`${outcomes.summary.branch_avg_score.toFixed(1)}%`}
                    tone={
                      outcomes.summary.branch_avg_score >= 70
                        ? "success"
                        : outcomes.summary.branch_avg_score < 50
                          ? "destructive"
                          : "default"
                    }
                  />
                </KpiGrid>
              )}
            </CardContent>
          </Card>
        </div>
      </section>

      {/* Last 30 days — single card KPI grid */}
      <section className="flex flex-col gap-3">
        <SectionLabel>Last 30 days</SectionLabel>
        <Card>
          <CardContent>
            {adherenceQuery.isLoading || !adherence ? (
              <p className="text-sm text-muted-foreground">Loading…</p>
            ) : (
              <KpiGrid>
                <KpiBlock
                  label="Adherence"
                  value={`${adherence.rates.adherence_pct.toFixed(1)}%`}
                  hint={`${adherence.totals.completed_as_planned}/${adherence.totals.planned} clean`}
                  tone={
                    adherence.rates.adherence_pct >= 75
                      ? "success"
                      : adherence.rates.adherence_pct < 50
                        ? "destructive"
                        : "default"
                  }
                />
                <KpiBlock
                  label="Substitute rate"
                  value={`${adherence.rates.substitute_pct.toFixed(1)}%`}
                  hint={`${adherence.totals.substituted} substituted`}
                  tone={
                    adherence.rates.substitute_pct >= 15 ? "warning" : "default"
                  }
                />
                <KpiBlock
                  label="Teacher no-show"
                  value={`${adherence.rates.teacher_no_show_pct.toFixed(1)}%`}
                  hint={`${adherence.no_show_breakdown.teacher} teacher · ${adherence.no_show_breakdown.student} student · ${adherence.no_show_breakdown.external} external`}
                  tone={
                    adherence.rates.teacher_no_show_pct >= 10
                      ? "destructive"
                      : adherence.rates.teacher_no_show_pct > 0
                        ? "warning"
                        : "default"
                  }
                />
                <KpiBlock
                  label="Branch avg score"
                  value={
                    outcomes
                      ? `${outcomes.summary.branch_avg_score.toFixed(1)}%`
                      : "—"
                  }
                  hint={
                    outcomes
                      ? `${outcomes.summary.tests_evaluated} test${outcomes.summary.tests_evaluated !== 1 ? "s" : ""} · ${outcomes.summary.students_with_marks} students`
                      : undefined
                  }
                  tone={
                    outcomes && outcomes.summary.branch_avg_score >= 70
                      ? "success"
                      : outcomes && outcomes.summary.branch_avg_score < 50
                        ? "destructive"
                        : "default"
                  }
                />
              </KpiGrid>
            )}
          </CardContent>
        </Card>
      </section>

      {/* Worth investigating — paired investigation cards */}
      {(flaggedTeachers.length > 0 || flaggedBatches.length > 0) && (
        <section className="flex flex-col gap-3">
          <SectionLabel>Worth investigating</SectionLabel>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {flaggedBatches.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">
                    Batches behind on syllabus
                  </CardTitle>
                  <p className="mt-1 text-[12px] text-muted-foreground">
                    Coverage vs. time-weighted expected progress.
                  </p>
                </CardHeader>
                <CardContent className="pt-0">
                  <ul className="flex flex-col divide-y">
                    {flaggedBatches.map((b) => (
                      <li
                        key={b.batch_id}
                        className="flex items-center justify-between gap-3 py-2 text-sm"
                      >
                        <Link
                          href="/insights"
                          className="font-medium hover:underline"
                        >
                          {b.batch_name}
                        </Link>
                        <span className="flex items-center gap-2 text-[12px] tabular-nums text-muted-foreground">
                          {b.coverage_pct.toFixed(0)}% of{" "}
                          {b.expected_coverage_pct.toFixed(0)}% expected
                          <Badge
                            variant={
                              b.pace_status === "critically_behind"
                                ? "destructive"
                                : "default"
                            }
                          >
                            {b.pace_delta_pct.toFixed(1)}pp
                          </Badge>
                        </span>
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            )}
            {flaggedTeachers.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">
                    Teachers with substitutes
                  </CardTitle>
                  <p className="mt-1 text-[12px] text-muted-foreground">
                    Lectures where someone other than the planned teacher
                    delivered.
                  </p>
                </CardHeader>
                <CardContent className="pt-0">
                  <ul className="flex flex-col divide-y">
                    {flaggedTeachers.map((t) => (
                      <li
                        key={t.teacher_id}
                        className="flex items-center justify-between gap-3 py-2 text-sm"
                      >
                        <Link
                          href={`/teachers/${t.teacher_id}`}
                          className="font-medium hover:underline"
                        >
                          {t.first_name} {t.last_name}
                        </Link>
                        <span className="flex items-center gap-2 text-[12px] tabular-nums text-muted-foreground">
                          {t.substituted_out}/{t.planned} sub
                          <Badge
                            variant={
                              t.substitute_rate_pct >= 30
                                ? "destructive"
                                : t.substitute_rate_pct >= 15
                                  ? "default"
                                  : "secondary"
                            }
                          >
                            {t.substitute_rate_pct.toFixed(1)}%
                          </Badge>
                        </span>
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            )}
          </div>
        </section>
      )}
    </div>
  );
}
