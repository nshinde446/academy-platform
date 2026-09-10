"use client";

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { InfoHint } from "@/components/ui/info-hint";
import { useToast } from "@/components/ui/toast";
import {
  useDownloadAttendanceReport,
  type ReportScope,
} from "../_hooks/use-attendance";

const CONTROL =
  "h-9 rounded-lg border border-input bg-background px-3 text-sm";

function localISO(d: Date): string {
  const off = d.getTimezoneOffset();
  return new Date(d.getTime() - off * 60000).toISOString().slice(0, 10);
}
function monthStartISO(): string {
  const d = new Date();
  return localISO(new Date(d.getFullYear(), d.getMonth(), 1));
}
function todayISO(): string {
  return localISO(new Date());
}

function errorOf(err: unknown): string {
  const e = err as {
    response?: { data?: { error?: { message?: string }; detail?: string } };
  };
  return (
    e?.response?.data?.error?.message ||
    e?.response?.data?.detail ||
    "Download failed"
  );
}

type Fmt = "xlsx" | "pdf";

interface Batch {
  id: string;
  name: string;
}

interface ReportDef {
  key: string;
  scope: ReportScope;
  title: string;
  desc: string;
  needsBatch?: boolean;
  needsDay?: boolean; // uses a single day rather than a start/end range
  formats: Fmt[];
}

// The two biometric summary reports (from the institute's shared samples) lead,
// then the pre-existing reports — one place for every attendance download.
const REPORTS: ReportDef[] = [
  {
    key: "daywise-batchwise",
    scope: "daywise-batchwise",
    title: "Daywise · Batchwise (biometric)",
    desc: "Every batch's enrolled / present / absent for each day in the range.",
    formats: ["xlsx", "pdf"],
  },
  {
    key: "batchwise-datewise",
    scope: "batchwise-datewise",
    title: "Batchwise · Datewise (biometric)",
    desc: "One batch's enrolled / present / absent, day by day.",
    needsBatch: true,
    formats: ["xlsx", "pdf"],
  },
  {
    key: "daily-ledger",
    scope: "daily-ledger",
    title: "Daily ledger (all students)",
    desc: "Every student's per-day record over the range — batch-independent.",
    formats: ["xlsx", "pdf"],
  },
  {
    key: "all-batches",
    scope: "all-batches",
    title: "All-batches summary",
    desc: "Per-batch attendance % over the range, with a sheet per batch.",
    formats: ["xlsx", "pdf"],
  },
  {
    key: "batch",
    scope: "batch",
    title: "Single-batch register",
    desc: "Students × days grid (present / late / absent) for one batch.",
    needsBatch: true,
    formats: ["xlsx", "pdf"],
  },
  {
    key: "day",
    scope: "day",
    title: "Single-day snapshot",
    desc: "One batch's in/out roster for a single day (uses the From date).",
    needsBatch: true,
    needsDay: true,
    formats: ["pdf", "xlsx"],
  },
];

const FMT_LABEL: Record<Fmt, string> = { xlsx: "Excel", pdf: "PDF" };

export function ReportsHub({
  branchId,
  batches,
}: {
  branchId: string;
  batches: Batch[];
}) {
  const toast = useToast();
  const download = useDownloadAttendanceReport(branchId);
  const [start, setStart] = useState(monthStartISO);
  const [end, setEnd] = useState(todayISO);
  const [batchId, setBatchId] = useState("");
  // Which button is mid-download, so only it shows a spinner. Key = "report:fmt".
  const [busy, setBusy] = useState<string | null>(null);

  async function run(def: ReportDef, fmt: Fmt) {
    if (def.needsBatch && !batchId) {
      toast.error("Pick a batch first for this report.");
      return;
    }
    const tag = `${def.key}:${fmt}`;
    setBusy(tag);
    try {
      await download.mutateAsync({
        scope: def.scope,
        fmt,
        id: def.needsBatch ? batchId : undefined,
        // The single-day snapshot reuses the "From" date — no separate field.
        ...(def.needsDay ? { day: start } : { start, end }),
      });
    } catch (err) {
      toast.error(errorOf(err));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Shared controls — date range, single day, and batch */}
      <Card size="sm">
        <CardContent>
          <div className="flex flex-wrap items-end gap-3">
            <label className="flex flex-col gap-1 text-xs text-muted-foreground">
              From
              <input
                type="date"
                value={start}
                max={end}
                onChange={(e) => setStart(e.target.value)}
                className={CONTROL}
                aria-label="Report range start"
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-muted-foreground">
              To
              <input
                type="date"
                value={end}
                min={start}
                onChange={(e) => setEnd(e.target.value)}
                className={CONTROL}
                aria-label="Report range end"
              />
            </label>
            <label className="flex min-w-[12rem] flex-col gap-1 text-xs text-muted-foreground">
              Batch (for batch reports)
              <select
                value={batchId}
                onChange={(e) => setBatchId(e.target.value)}
                className={CONTROL}
                aria-label="Batch for batch-scoped reports"
              >
                <option value="">Select a batch…</option>
                {batches.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </CardContent>
      </Card>

      {/* Report cards */}
      <div className="grid gap-3 sm:grid-cols-2">
        {REPORTS.map((def) => {
          const blocked = def.needsBatch && !batchId;
          return (
            <div
              key={def.key}
              className="flex flex-col gap-2 rounded-xl border bg-card p-3 shadow-sm ring-1 ring-foreground/10"
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2 text-sm font-semibold">
                  {def.title}
                  {def.needsBatch && (
                    <InfoHint text="Pick a batch above to enable this report." />
                  )}
                </div>
                <p className="mt-0.5 text-xs leading-snug text-muted-foreground">
                  {def.desc}
                </p>
              </div>
              <div className="mt-auto flex flex-wrap gap-2 pt-1">
                {def.formats.map((fmt) => {
                  const tag = `${def.key}:${fmt}`;
                  return (
                    <Button
                      key={fmt}
                      size="sm"
                      variant="outline"
                      disabled={blocked || busy !== null}
                      onClick={() => run(def, fmt)}
                    >
                      {busy === tag ? "Preparing…" : FMT_LABEL[fmt]}
                    </Button>
                  );
                })}
                {blocked && (
                  <span className="self-center text-[11px] text-muted-foreground">
                    select a batch
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <p className="text-xs text-muted-foreground">
        &ldquo;Biometric present&rdquo; counts students marked present or late from
        their device punches that day; absent is the rest of the enrolled batch.
      </p>
    </div>
  );
}
