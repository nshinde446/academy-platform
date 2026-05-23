"use client";

import { useMemo } from "react";
import Link from "next/link";
import { useUserStore } from "@/store/user-store";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useRoster } from "../today/_hooks/use-roster";
import {
  useAdherenceInsights,
  useOutcomeInsights,
} from "../insights/_hooks/use-adherence";

function isoToday(): string {
  return new Date().toISOString().slice(0, 10);
}

function isoNDaysAgo(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString().slice(0, 10);
}

type Tone = "default" | "success" | "warning" | "destructive";

const TONE_CLASS: Record<Tone, string> = {
  default: "text-foreground",
  success: "text-emerald-600 dark:text-emerald-400",
  warning: "text-amber-600 dark:text-amber-400",
  destructive: "text-destructive",
};

function Tile({
  label,
  value,
  hint,
  tone = "default",
  href,
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: Tone;
  href?: string;
}) {
  const inner = (
    <Card size="sm" className="min-w-0 h-full hover:ring-2 transition-shadow">
      <CardHeader>
        <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          {label}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className={`text-3xl font-semibold ${TONE_CLASS[tone]}`}>
          {value}
        </div>
        {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
      </CardContent>
    </Card>
  );
  return href ? <Link href={href}>{inner}</Link> : inner;
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

  const roster = rosterQuery.data;
  const adherence = adherenceQuery.data;
  const outcomes = outcomesQuery.data;

  const friendly = useMemo(() => {
    const greeting =
      new Date().getHours() < 12
        ? "Good morning"
        : new Date().getHours() < 17
          ? "Good afternoon"
          : "Good evening";
    const name = user?.first_name ?? "there";
    return `${greeting}, ${name}.`;
  }, [user]);

  const todayDate = new Date().toLocaleDateString(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
  });

  // Needs attention — top 3 teachers by substitute-out rate among those
  // with at least 2 planned lectures (filter out noise).
  const flaggedTeachers = useMemo(() => {
    if (!adherence) return [];
    return adherence.by_teacher
      .filter((t) => t.planned >= 2 && t.substitute_rate_pct > 0)
      .slice(0, 3);
  }, [adherence]);

  // Needs attention — batches with the worst pace delta.
  const flaggedBatches = useMemo(() => {
    if (!adherence) return [];
    return adherence.by_batch_syllabus
      .filter((b) => b.pace_status === "behind" || b.pace_status === "critically_behind")
      .slice(0, 3);
  }, [adherence]);

  const sessionsOffPlan = roster
    ? roster.snapshot.off_plan_makeup +
      roster.snapshot.off_plan_ad_hoc +
      roster.snapshot.off_plan_merged
    : 0;

  return (
    <div className="flex flex-col gap-6">
      {/* Greeting + quick actions */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-2xl font-semibold">{friendly}</h2>
          <p className="text-sm text-muted-foreground mt-1">
            {todayDate} · Branch dashboard
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link href="/today">
            <Button variant="default" size="sm">
              Open today&apos;s roster
            </Button>
          </Link>
          <Link href="/lectures">
            <Button variant="outline" size="sm">
              Schedule a lecture
            </Button>
          </Link>
          <Link href="/insights">
            <Button variant="outline" size="sm">
              Full insights
            </Button>
          </Link>
        </div>
      </div>

      {/* Today at a glance */}
      <section className="flex flex-col gap-3">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Today at a glance
        </h3>
        {rosterQuery.isLoading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Tile
              label="Planned today"
              value={roster ? String(roster.snapshot.planned) : "—"}
              hint={
                roster
                  ? `${roster.snapshot.completed} done · ${roster.snapshot.pending} pending`
                  : undefined
              }
              href="/today"
            />
            <Tile
              label="Live now"
              value={roster ? String(roster.snapshot.in_progress) : "—"}
              hint={
                roster && roster.live_now.length > 0
                  ? `${roster.live_now.filter((l) => l.kind === "overdue").length} overdue`
                  : undefined
              }
              tone={
                roster && roster.live_now.some((l) => l.kind === "overdue")
                  ? "destructive"
                  : roster && roster.snapshot.in_progress > 0
                    ? "success"
                    : "default"
              }
              href="/today"
            />
            <Tile
              label="Teacher no-shows"
              value={roster ? String(roster.snapshot.no_show_teacher) : "—"}
              hint={
                roster && roster.snapshot.no_show_other > 0
                  ? `+${roster.snapshot.no_show_other} other`
                  : undefined
              }
              tone={
                roster && roster.snapshot.no_show_teacher > 0
                  ? "destructive"
                  : "default"
              }
              href="/today"
            />
            <Tile
              label="Off-plan sessions"
              value={String(sessionsOffPlan)}
              hint={
                roster && sessionsOffPlan > 0
                  ? `${roster.snapshot.off_plan_makeup} makeup · ${roster.snapshot.off_plan_ad_hoc} ad-hoc`
                  : undefined
              }
              href="/today"
            />
          </div>
        )}
      </section>

      {/* Last 30 days */}
      <section className="flex flex-col gap-3">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Last 30 days
        </h3>
        {adherenceQuery.isLoading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Tile
              label="Adherence"
              value={adherence ? `${adherence.rates.adherence_pct.toFixed(1)}%` : "—"}
              hint={
                adherence
                  ? `${adherence.totals.completed_as_planned}/${adherence.totals.planned} clean completion`
                  : undefined
              }
              tone={
                adherence && adherence.rates.adherence_pct >= 75
                  ? "success"
                  : adherence && adherence.rates.adherence_pct < 50
                    ? "destructive"
                    : "default"
              }
              href="/insights"
            />
            <Tile
              label="Substitute rate"
              value={
                adherence ? `${adherence.rates.substitute_pct.toFixed(1)}%` : "—"
              }
              hint={
                adherence
                  ? `${adherence.totals.substituted} substituted`
                  : undefined
              }
              tone={
                adherence && adherence.rates.substitute_pct >= 15
                  ? "warning"
                  : "default"
              }
              href="/insights"
            />
            <Tile
              label="Teacher no-show"
              value={
                adherence
                  ? `${adherence.rates.teacher_no_show_pct.toFixed(1)}%`
                  : "—"
              }
              hint={
                adherence
                  ? `${adherence.no_show_breakdown.teacher} teacher · ${adherence.no_show_breakdown.student} student · ${adherence.no_show_breakdown.external} external`
                  : undefined
              }
              tone={
                adherence && adherence.rates.teacher_no_show_pct >= 10
                  ? "destructive"
                  : adherence && adherence.rates.teacher_no_show_pct > 0
                    ? "warning"
                    : "default"
              }
              href="/insights"
            />
            <Tile
              label="Avg test score"
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
              href="/insights"
            />
          </div>
        )}
      </section>

      {/* Needs attention */}
      {(flaggedTeachers.length > 0 || flaggedBatches.length > 0) && (
        <section className="flex flex-col gap-3">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Needs attention
          </h3>
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            {flaggedTeachers.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">
                    Teachers with substitutes (last 30 days)
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <ul className="flex flex-col gap-2">
                    {flaggedTeachers.map((t) => (
                      <li
                        key={t.teacher_id}
                        className="flex items-center justify-between text-sm"
                      >
                        <Link
                          href={`/teachers/${t.teacher_id}`}
                          className="font-medium hover:underline"
                        >
                          {t.first_name} {t.last_name}
                        </Link>
                        <span className="flex items-center gap-2 text-xs text-muted-foreground">
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
            {flaggedBatches.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">
                    Batches behind on syllabus
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <ul className="flex flex-col gap-2">
                    {flaggedBatches.map((b) => (
                      <li
                        key={b.batch_id}
                        className="flex items-center justify-between text-sm"
                      >
                        <Link
                          href="/insights"
                          className="font-medium hover:underline"
                        >
                          {b.batch_name}
                        </Link>
                        <span className="flex items-center gap-2 text-xs text-muted-foreground">
                          {b.coverage_pct.toFixed(1)}% of{" "}
                          {b.expected_coverage_pct.toFixed(1)}% expected
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
          </div>
        </section>
      )}
    </div>
  );
}
