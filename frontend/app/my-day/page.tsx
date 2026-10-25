"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import apiClient, { apiErrorMessage } from "@/services/api-client";
import { useAuthStore } from "@/store/auth-store";

interface Profile {
  name: string;
  employee_code: string;
  department: string | null;
}
interface Lecture {
  batch: string;
  subject: string;
  scheduled_start: string | null;
  scheduled_end: string | null;
  actual_start: string | null;
  actual_end: string | null;
  status: string;
}
interface DayData {
  date: string;
  attendance: { in: string | null; out: string | null; status: string };
  first_lecture_start: string | null;
  late_minutes: number | null;
  fine: { amount: number | null; visible: boolean };
  lectures: Lecture[];
}
interface MonthSummary {
  present_days: number;
  half_days: number;
  absent_days: number;
  late_count: number;
  total_late_minutes: number;
  total_fine: number;
}

function todayISO(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
    d.getDate(),
  ).padStart(2, "0")}`;
}

const CHIP: Record<string, string> = {
  on_time: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
  delayed: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
  scheduled: "bg-muted text-muted-foreground",
};

export default function MyDayPage() {
  const router = useRouter();
  const logout = useAuthStore((s) => s.logout);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [date, setDate] = useState(todayISO());
  const [day, setDay] = useState<DayData | null>(null);
  const [month, setMonth] = useState<MonthSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    apiClient
      .get<Profile>("/api/v1/me/profile")
      .then((r) => setProfile(r.data))
      .catch((e) => {
        // Forced password change -> go set it; otherwise surface the error.
        if (apiErrorMessage(e, "") === "PASSWORD_CHANGE_REQUIRED") {
          router.push("/change-password");
        }
      });
    const now = new Date();
    apiClient
      .get<MonthSummary>("/api/v1/me/month-summary", {
        params: { year: now.getFullYear(), month: now.getMonth() + 1 },
      })
      .then((r) => setMonth(r.data))
      .catch(() => {});
  }, [router]);

  const loadDay = useCallback(async (d: string) => {
    setLoading(true);
    setError("");
    try {
      const r = await apiClient.get<DayData>("/api/v1/me/day", { params: { date: d } });
      setDay(r.data);
    } catch (e) {
      const msg = apiErrorMessage(e, "Could not load the day.");
      if (msg === "PASSWORD_CHANGE_REQUIRED") {
        router.push("/change-password");
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    // loadDay sets state only after an await (not synchronously).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadDay(date);
  }, [date, loadDay]);

  async function onLogout() {
    await logout();
    router.push("/login");
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col gap-4 bg-background p-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold leading-tight">
            {profile?.name ?? "My Day"}
          </h1>
          <p className="text-xs text-muted-foreground">
            {profile ? `${profile.employee_code}${profile.department ? ` · ${profile.department}` : ""}` : ""}
          </p>
        </div>
        <Button variant="secondary" size="sm" onClick={onLogout}>
          Sign out
        </Button>
      </div>

      {/* Month-to-date strip */}
      {month && (
        <div className="grid grid-cols-3 gap-2 text-center">
          {[
            ["Present", month.present_days],
            ["Half", month.half_days],
            ["Absent", month.absent_days],
            ["Late days", month.late_count],
            ["Late mins", month.total_late_minutes],
            ["Fine ₹", month.total_fine],
          ].map(([label, val]) => (
            <div key={String(label)} className="rounded-lg border bg-card px-2 py-2">
              <div className="text-base font-semibold tabular-nums">{val}</div>
              <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
                {label}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Date picker */}
      <Input type="date" value={date} max={todayISO()} onChange={(e) => setDate(e.target.value)} />

      {error && <p className="text-sm text-destructive">{error}</p>}

      {/* Day card */}
      {loading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : day ? (
        <>
          <Card>
            <CardContent className="grid grid-cols-2 gap-3 pt-4 text-sm">
              <Field label="IN" value={day.attendance.in ?? "Not available"} />
              <Field label="OUT" value={day.attendance.out ?? "—"} />
              <Field label="Status" value={day.attendance.status} />
              <Field label="First lecture" value={day.first_lecture_start ?? "—"} />
              <Field
                label="Late minutes"
                value={day.late_minutes == null ? "Not available" : String(day.late_minutes)}
              />
              <Field
                label="Fine"
                value={
                  day.fine.visible
                    ? day.fine.amount == null
                      ? "—"
                      : `₹${day.fine.amount}`
                    : "Pending until day close"
                }
              />
            </CardContent>
          </Card>

          {/* Lectures */}
          <div className="flex flex-col gap-2">
            <h2 className="text-sm font-semibold">Lectures</h2>
            {day.lectures.length === 0 ? (
              <p className="text-sm text-muted-foreground">No lectures this day.</p>
            ) : (
              day.lectures.map((l, i) => (
                <Card key={i}>
                  <CardContent className="flex items-center justify-between pt-4">
                    <div>
                      <div className="text-sm font-medium">
                        {l.subject} · {l.batch}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {l.scheduled_start ?? "—"}–{l.scheduled_end ?? "—"}
                        {l.actual_start ? ` · started ${l.actual_start}` : ""}
                      </div>
                    </div>
                    <span
                      className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${CHIP[l.status] ?? CHIP.scheduled}`}
                    >
                      {l.status.replace("_", " ")}
                    </span>
                  </CardContent>
                </Card>
              ))
            )}
          </div>
        </>
      ) : null}
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="font-medium tabular-nums">{value}</div>
    </div>
  );
}
