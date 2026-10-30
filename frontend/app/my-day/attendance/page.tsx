"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import apiClient, { apiErrorMessage } from "@/services/api-client";

interface Row {
  date: string;
  in: string | null;
  out: string | null;
  hours: string | null;
  late_minutes: number | null;
  fine: number | null;
  status: string | null;
  closed: boolean;
  future: boolean;
}

interface AttendanceData {
  start: string;
  end: string;
  rows: Row[];
  summary: {
    present: number;
    absent: number;
    half: number;
    late: number;
    weekly_off: number;
    holiday: number;
    total_fine: number;
  };
}

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

// Status code → label + colour (P/A/L/HD/WO/HL).
const CODE: Record<string, { label: string; cls: string }> = {
  P: { label: "Present", cls: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300" },
  L: { label: "Late", cls: "bg-amber-500/15 text-amber-700 dark:text-amber-300" },
  HD: { label: "Half Day", cls: "bg-sky-500/15 text-sky-700 dark:text-sky-300" },
  A: { label: "Absent", cls: "bg-red-500/15 text-red-700 dark:text-red-300" },
  WO: { label: "Weekly Off", cls: "bg-muted text-muted-foreground" },
  HL: { label: "Holiday", cls: "bg-violet-500/15 text-violet-700 dark:text-violet-300" },
};

function ddmmyyyy(iso: string): string {
  const [y, m, d] = iso.split("-");
  return `${d}-${m}-${y}`;
}

function todayISO(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function StatusPill({ code }: { code: string | null }) {
  if (!code) return <span className="text-muted-foreground">—</span>;
  const c = CODE[code] ?? { label: code, cls: "bg-muted text-muted-foreground" };
  return <span className={`rounded px-1.5 py-0.5 text-[11px] font-medium ${c.cls}`}>{code}</span>;
}

export default function PortalAttendancePage() {
  const router = useRouter();
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [view, setView] = useState<"table" | "grid">("table");
  const [data, setData] = useState<AttendanceData | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await apiClient.get<AttendanceData>("/api/v1/me/attendance", {
        params: { year, month },
      });
      setData(r.data);
    } catch (e) {
      if (apiErrorMessage(e, "") === "PASSWORD_CHANGE_REQUIRED") router.push("/change-password");
    } finally {
      setLoading(false);
    }
  }, [year, month, router]);

  useEffect(() => {
    load();
  }, [load]);

  function shift(delta: number) {
    const m0 = month - 1 + delta;
    setYear((y) => y + Math.floor(m0 / 12));
    setMonth(((m0 % 12) + 12) % 12 + 1);
  }

  const isThisMonth = year === now.getFullYear() && month === now.getMonth() + 1;
  const today = todayISO();

  const summary = data?.summary;
  const chips = useMemo(
    () =>
      summary
        ? [
            { label: "Present", value: summary.present },
            { label: "Absent", value: summary.absent },
            { label: "Half days", value: summary.half },
            { label: "Late", value: summary.late },
            { label: "Weekly offs", value: summary.weekly_off },
            { label: "Holidays", value: summary.holiday },
            { label: "Total fine", value: `₹${summary.total_fine}` },
          ]
        : [],
    [summary],
  );

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold leading-tight">Attendance</h1>
          <p className="text-sm text-muted-foreground">
            Your day-by-day attendance — IN/OUT, hours, late minutes, fine and status.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => shift(-1)} aria-label="Previous month">‹</Button>
          <span className="min-w-[8.5rem] text-center text-sm font-medium">
            {MONTHS[month - 1]} {year}
          </span>
          <Button variant="outline" size="sm" onClick={() => shift(1)} disabled={isThisMonth} aria-label="Next month">›</Button>
        </div>
      </div>

      {/* Summary chips */}
      <div className="flex flex-wrap gap-2">
        {chips.map((c) => (
          <div key={c.label} className="rounded-md border px-3 py-1.5 text-sm">
            <span className="text-muted-foreground">{c.label}: </span>
            <span className="font-semibold">{c.value}</span>
          </div>
        ))}
      </div>

      {/* View toggle */}
      <div className="flex gap-1">
        {(["table", "grid"] as const).map((v) => (
          <button
            key={v}
            onClick={() => setView(v)}
            className={`rounded-md px-3 py-1 text-sm capitalize transition-colors ${
              view === v ? "bg-muted font-medium" : "text-muted-foreground hover:bg-muted"
            }`}
          >
            {v}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : !data || data.rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">No attendance for this month.</p>
      ) : view === "table" ? (
        <Card>
          <CardContent className="overflow-x-auto p-0">
            <table className="w-full text-sm">
              <thead className="border-b text-left text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 font-medium">Date</th>
                  <th className="px-3 py-2 font-medium">IN</th>
                  <th className="px-3 py-2 font-medium">OUT</th>
                  <th className="px-3 py-2 font-medium">Hours</th>
                  <th className="px-3 py-2 text-right font-medium">Late min</th>
                  <th className="px-3 py-2 text-right font-medium">Fine</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {data.rows.map((r) => {
                  const pending = !r.future && !r.closed && r.date === today;
                  return (
                    <tr key={r.date} className="border-b last:border-0">
                      <td className="px-3 py-2 whitespace-nowrap">{ddmmyyyy(r.date)}</td>
                      {r.future ? (
                        <td className="px-3 py-2 text-muted-foreground" colSpan={6}>—</td>
                      ) : pending ? (
                        <>
                          <td className="px-3 py-2">{r.in ?? "—"}</td>
                          <td className="px-3 py-2">{r.out ?? "—"}</td>
                          <td className="px-3 py-2 text-muted-foreground" colSpan={4}>Day not closed yet</td>
                        </>
                      ) : (
                        <>
                          <td className="px-3 py-2">{r.in ?? "—"}</td>
                          <td className="px-3 py-2">{r.out ?? "—"}</td>
                          <td className="px-3 py-2">{r.hours ?? "—"}</td>
                          <td className="px-3 py-2 text-right">{r.late_minutes ?? "—"}</td>
                          <td className="px-3 py-2 text-right">{r.fine ? `₹${r.fine}` : "—"}</td>
                          <td className="px-3 py-2"><StatusPill code={r.status} /></td>
                        </>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="pt-5">
            <div className="flex flex-wrap gap-1.5">
              {data.rows.map((r) => {
                const day = Number(r.date.split("-")[2]);
                const c = r.status ? CODE[r.status] : null;
                return (
                  <div
                    key={r.date}
                    title={`${ddmmyyyy(r.date)}${r.status ? ` · ${c?.label ?? r.status}` : ""}`}
                    className={`flex h-10 w-10 flex-col items-center justify-center rounded text-[10px] ${
                      r.future ? "border border-dashed text-muted-foreground" : c?.cls ?? "bg-muted"
                    }`}
                  >
                    <span className="font-semibold">{day}</span>
                    <span>{r.future ? "" : r.status ?? ""}</span>
                  </div>
                );
              })}
            </div>
            <div className="mt-4 flex flex-wrap gap-3 text-xs text-muted-foreground">
              {Object.entries(CODE).map(([code, c]) => (
                <span key={code} className="flex items-center gap-1">
                  <span className={`rounded px-1 ${c.cls}`}>{code}</span> {c.label}
                </span>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
