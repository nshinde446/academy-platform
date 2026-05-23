"use client";

import { use, useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import apiClient from "@/services/api-client";
import { useUserStore } from "@/store/user-store";
import { Input } from "@/components/ui/input";
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
  useLectures,
  useLectureSessions,
} from "../../lectures/_hooks/use-lectures";
import { useAdherenceInsights } from "../../insights/_hooks/use-adherence";
import type {
  LectureResponse,
  LectureSessionResponse,
} from "../../lectures/_schemas/lecture";
import type { TeacherResponse } from "../_schemas/teacher";

const NO_SHOW_REASON_LABEL: Record<string, string> = {
  TEACHER_NO_SHOW: "teacher",
  STUDENT_NO_SHOW: "students",
  EXTERNAL: "external",
  OTHER: "other",
};

type StatusTone = "default" | "secondary" | "success" | "destructive";

// Mirror of lecture-table.deriveStatus so the pill renders identically.
function deriveLectureStatus(
  l: LectureResponse,
  isCovered: boolean,
): { label: string; tone: StatusTone; subLabel?: string } {
  const hasSub = !!l.actual_teacher_id;
  if (
    isCovered &&
    (l.lecture_status === "cancelled" || l.lecture_status === "no_show")
  ) {
    return {
      label: "Made up",
      tone: "success",
      subLabel: l.lecture_status === "cancelled" ? "was cancelled" : "was no-show",
    };
  }
  if (l.lecture_status === "no_show") {
    const r = (l.no_show_reason ?? "OTHER").toUpperCase();
    return {
      label: `No-show · ${NO_SHOW_REASON_LABEL[r] ?? "other"}`,
      tone: r === "TEACHER_NO_SHOW" ? "destructive" : "secondary",
    };
  }
  if (l.lecture_status === "cancelled")
    return { label: "Cancelled", tone: "secondary" };
  if (l.lecture_status === "started")
    return {
      label: "In progress",
      tone: "default",
      subLabel: hasSub ? "with substitute" : undefined,
    };
  if (l.lecture_status === "paused")
    return { label: "Paused", tone: "secondary" };
  if (l.lecture_status === "completed")
    return hasSub
      ? { label: "Completed", tone: "default", subLabel: "by substitute" }
      : { label: "Completed", tone: "success" };
  if (l.lecture_status === "rescheduled")
    return { label: "Rescheduled", tone: "secondary" };
  return { label: "Scheduled", tone: "default" };
}

function formatDateTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function isoDateNDaysAgo(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString().slice(0, 10);
}

function isoToday(): string {
  return new Date().toISOString().slice(0, 10);
}

export default function TeacherDetailPage({
  params,
}: {
  params: Promise<{ teacherId: string }>;
}) {
  const { teacherId } = use(params);

  const user = useUserStore((s) => s.user);
  const branchId = user?.branch_roles?.[0]?.branch_id;

  const [fromDate, setFromDate] = useState(isoDateNDaysAgo(30));
  const [toDate, setToDate] = useState(isoToday());

  const teacherQuery = useQuery<TeacherResponse>({
    queryKey: ["teachers", "detail", branchId ?? "", teacherId],
    queryFn: async () => {
      const res = await apiClient.get<TeacherResponse>(
        `/api/v1/teachers/${teacherId}`,
        { params: { branch_id: branchId } },
      );
      return res.data;
    },
    enabled: !!branchId && !!teacherId,
  });

  const lecturesQuery = useLectures(branchId);
  const sessionsQuery = useLectureSessions(branchId);
  const insightsQuery = useAdherenceInsights(branchId, fromDate, toDate);

  const teacher = teacherQuery.data;
  const allLectures = lecturesQuery.data ?? [];
  const allSessions = sessionsQuery.data ?? [];

  // Lectures where this teacher is either the planner or the actual.
  const myLectures = useMemo(() => {
    return allLectures
      .filter(
        (l) => l.teacher_id === teacherId || l.actual_teacher_id === teacherId,
      )
      .filter((l) => {
        const d = new Date(l.scheduled_start);
        return (
          d >= new Date(`${fromDate}T00:00:00`) &&
          d <= new Date(`${toDate}T23:59:59`)
        );
      })
      .sort(
        (a, b) =>
          new Date(b.scheduled_start).getTime() -
          new Date(a.scheduled_start).getTime(),
      );
  }, [allLectures, teacherId, fromDate, toDate]);

  const mySessions: LectureSessionResponse[] = useMemo(() => {
    return allSessions
      .filter((s) => s.teacher_id === teacherId)
      .filter((s) => {
        const d = new Date(s.actual_start);
        return (
          d >= new Date(`${fromDate}T00:00:00`) &&
          d <= new Date(`${toDate}T23:59:59`)
        );
      })
      .sort(
        (a, b) =>
          new Date(b.actual_start).getTime() -
          new Date(a.actual_start).getTime(),
      );
  }, [allSessions, teacherId, fromDate, toDate]);

  const coveredLectureIds = useMemo(() => {
    const set = new Set<string>();
    for (const s of allSessions) for (const lid of s.lecture_ids) set.add(lid);
    return set;
  }, [allSessions]);

  const insightsRow = useMemo(
    () =>
      insightsQuery.data?.by_teacher.find((t) => t.teacher_id === teacherId),
    [insightsQuery.data, teacherId],
  );

  const kpis = (() => {
    if (insightsRow) {
      return {
        planned: insightsRow.planned,
        sub_out: insightsRow.substituted_out,
        sub_in: insightsRow.substituted_in,
        cancelled: insightsRow.cancelled,
        sub_rate: insightsRow.substitute_rate_pct,
      };
    }
    // Fallback: compute from the filtered lectures (covers branches the
    // insights endpoint hasn't aggregated yet, e.g. teacher with 0 planned).
    const planned = myLectures.filter((l) => l.teacher_id === teacherId).length;
    const sub_out = myLectures.filter(
      (l) => l.teacher_id === teacherId && l.actual_teacher_id,
    ).length;
    const sub_in = myLectures.filter(
      (l) => l.actual_teacher_id === teacherId,
    ).length;
    const cancelled = myLectures.filter(
      (l) => l.teacher_id === teacherId && l.lecture_status === "cancelled",
    ).length;
    const sub_rate = planned > 0 ? (sub_out * 100) / planned : 0;
    return { planned, sub_out, sub_in, cancelled, sub_rate };
  })();

  const ORIGIN_TONE: Record<string, StatusTone> = {
    planned: "secondary",
    makeup: "success",
    ad_hoc: "default",
  };

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-3">
        <Link
          href="/today"
          className="text-xs text-muted-foreground hover:text-foreground"
        >
          ← Back to Today
        </Link>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-baseline sm:justify-between">
          <div>
            <h2 className="text-2xl font-semibold">
              {teacher ? `${teacher.first_name} ${teacher.last_name}` : "—"}
            </h2>
            {teacher && (
              <p className="text-sm text-muted-foreground mt-1">
                {teacher.qualification || "—"}
                {teacher.email && <span> · {teacher.email}</span>}
                {teacher.phone && <span> · {teacher.phone}</span>}
              </p>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2">
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
          </div>
        </div>
      </div>

      <Card size="sm">
        <CardContent>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
            <Kpi label="Planned" value={kpis.planned} />
            <Kpi
              label="Substituted out"
              value={kpis.sub_out}
              tone={kpis.sub_out > 0 ? "warning" : "default"}
            />
            <Kpi label="Covered for others" value={kpis.sub_in} />
            <Kpi
              label="Cancelled"
              value={kpis.cancelled}
              tone={kpis.cancelled > 0 ? "destructive" : "default"}
            />
            <Kpi
              label="Sub rate"
              value={`${kpis.sub_rate.toFixed(1)}%`}
              tone={
                kpis.sub_rate >= 30
                  ? "destructive"
                  : kpis.sub_rate >= 15
                    ? "warning"
                    : "default"
              }
            />
          </div>
        </CardContent>
      </Card>

      <div className="flex flex-col gap-2">
        <h3 className="text-lg font-semibold">Lectures in range</h3>
        {myLectures.length === 0 ? (
          <p className="text-sm text-muted-foreground italic">
            No lectures for this teacher in the selected range.
          </p>
        ) : (
          <div className="rounded-xl border ring-1 ring-foreground/10 overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>When</TableHead>
                  <TableHead>Subject · Batch</TableHead>
                  <TableHead className="hidden sm:table-cell">Topic</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {myLectures.map((l) => {
                  const s = deriveLectureStatus(
                    l,
                    coveredLectureIds.has(l.id),
                  );
                  const isCover = l.actual_teacher_id === teacherId && l.teacher_id !== teacherId;
                  return (
                    <TableRow key={l.id}>
                      <TableCell className="whitespace-nowrap">
                        {formatDateTime(l.scheduled_start)}
                      </TableCell>
                      <TableCell>
                        <span className="text-xs">
                          {isCover && (
                            <span className="mr-1 inline-block rounded bg-emerald-500/10 px-1 text-[10px] text-emerald-700 dark:text-emerald-400">
                              COVERED
                            </span>
                          )}
                          subject {l.subject_id.slice(0, 6)}… · batch{" "}
                          {l.batch_id.slice(0, 6)}…
                        </span>
                      </TableCell>
                      <TableCell className="hidden sm:table-cell text-xs text-muted-foreground">
                        {l.topic_id ? `${l.topic_id.slice(0, 6)}…` : "—"}
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-col items-start gap-0.5">
                          <Badge variant={s.tone}>{s.label}</Badge>
                          {s.subLabel && (
                            <span className="text-[10px] text-muted-foreground">
                              {s.subLabel}
                            </span>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        )}
      </div>

      <div className="flex flex-col gap-2">
        <h3 className="text-lg font-semibold">Off-plan sessions</h3>
        {mySessions.length === 0 ? (
          <p className="text-sm text-muted-foreground italic">
            No makeup / ad-hoc sessions in the selected range.
          </p>
        ) : (
          <div className="rounded-xl border ring-1 ring-foreground/10 overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>When</TableHead>
                  <TableHead>Origin</TableHead>
                  <TableHead className="hidden sm:table-cell">Notes</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {mySessions.map((s) => (
                  <TableRow key={s.id}>
                    <TableCell className="whitespace-nowrap">
                      {formatDateTime(s.actual_start)}
                    </TableCell>
                    <TableCell>
                      <Badge variant={ORIGIN_TONE[s.origin] ?? "default"}>
                        {s.origin}
                      </Badge>
                    </TableCell>
                    <TableCell className="hidden sm:table-cell text-xs text-muted-foreground max-w-md truncate">
                      {s.notes ?? "—"}
                    </TableCell>
                  </TableRow>
                ))}
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
  tone?: "default" | "warning" | "destructive";
}) {
  const cls =
    tone === "destructive"
      ? "text-destructive"
      : tone === "warning"
        ? "text-amber-600 dark:text-amber-400"
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
