"use client";

import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import { useBatchesForLectures } from "../../lectures/_hooks/use-lectures";
import { useBatchSummary, useForecast, useOverallSummary } from "../_hooks/use-fees";
import { inr } from "../_schemas/fees";

const SELECT = "h-9 w-full rounded-lg border border-input bg-background px-3 text-sm";

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}
function plusDays(iso: string, n: number): string {
  const d = new Date(iso);
  d.setDate(d.getDate() + n);
  return d.toISOString().slice(0, 10);
}

export function ForecastPanel({ branchId }: { branchId: string | undefined }) {
  const overall = useOverallSummary(branchId);
  const batchesQuery = useBatchesForLectures(branchId);
  const batches = useMemo(() => batchesQuery.data ?? [], [batchesQuery.data]);
  const [batchId, setBatchId] = useState("");
  const batchSummary = useBatchSummary(branchId, batchId || undefined);

  const [from, setFrom] = useState(todayISO());
  const [to, setTo] = useState(plusDays(todayISO(), 7));
  const [range, setRange] = useState<{ from: string; to: string } | null>(null);
  const forecast = useForecast(branchId, range?.from ?? "", range?.to ?? "", range !== null);

  return (
    <div className="flex flex-col gap-5">
      {/* Overall summary card */}
      {overall.data && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <SummaryTile label="Total agreed" value={inr(overall.data.total_agreed)} />
          <SummaryTile label="Collected" value={inr(overall.data.total_collected)} tone="success" />
          <SummaryTile label="Pending" value={inr(overall.data.total_pending)} tone="destructive" />
          <SummaryTile label="Collection %" value={`${overall.data.collection_pct}%`} />
        </div>
      )}

      <div className="grid items-start gap-5 lg:grid-cols-2">
        {/* Batch summary */}
        <Card>
          <CardContent className="flex flex-col gap-3">
            <h3 className="text-sm font-semibold">Batch-wise fees</h3>
            <select value={batchId} onChange={(e) => setBatchId(e.target.value)} className={SELECT} aria-label="Select batch">
              <option value="">Select a batch…</option>
              {batches.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
            {batchId && batchSummary.data && (
              <div className="grid grid-cols-2 gap-3">
                <SummaryTile label="Agreed" value={inr(batchSummary.data.total_agreed)} />
                <SummaryTile label="Collected" value={inr(batchSummary.data.total_collected)} tone="success" />
                <SummaryTile label="Pending" value={inr(batchSummary.data.total_pending)} tone="destructive" />
                <SummaryTile label="Collection %" value={`${batchSummary.data.collection_pct}%`} />
              </div>
            )}
          </CardContent>
        </Card>

        {/* Date-range forecast */}
        <Card>
          <CardContent className="flex flex-col gap-3">
            <h3 className="text-sm font-semibold">Collection forecast</h3>
            <div className="flex flex-wrap items-end gap-2">
              <div className="flex flex-col gap-1">
                <Label htmlFor="fc-from">From</Label>
                <Input id="fc-from" type="date" value={from} onChange={(e) => setFrom(e.target.value)} className="w-40" />
              </div>
              <div className="flex flex-col gap-1">
                <Label htmlFor="fc-to">To</Label>
                <Input id="fc-to" type="date" value={to} onChange={(e) => setTo(e.target.value)} className="w-40" />
              </div>
              <Button type="button" onClick={() => setRange({ from, to })} disabled={forecast.isFetching}>
                {forecast.isFetching ? "…" : "Run"}
              </Button>
            </div>
            {forecast.data && (
              <div className="rounded-lg border overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Date</TableHead>
                      <TableHead className="text-right">Installments</TableHead>
                      <TableHead className="text-right">Expected</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {forecast.data.days.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={3} className="text-sm text-muted-foreground">
                          Nothing expected in this range.
                        </TableCell>
                      </TableRow>
                    ) : (
                      forecast.data.days.map((d) => (
                        <TableRow key={d.date}>
                          <TableCell className="tabular-nums text-sm">{d.date}</TableCell>
                          <TableCell className="text-right tabular-nums">{d.installments_due}</TableCell>
                          <TableCell className="text-right tabular-nums">{inr(d.expected_amount)}</TableCell>
                        </TableRow>
                      ))
                    )}
                    {forecast.data.days.length > 0 && (
                      <TableRow className="font-semibold">
                        <TableCell>Total</TableCell>
                        <TableCell className="text-right tabular-nums">{forecast.data.total_installments}</TableCell>
                        <TableCell className="text-right tabular-nums">{inr(forecast.data.total_expected)}</TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function SummaryTile({ label, value, tone = "default" }: { label: string; value: string; tone?: "default" | "success" | "destructive" }) {
  const cls =
    tone === "destructive" ? "text-destructive" : tone === "success" ? "text-emerald-600 dark:text-emerald-400" : "text-foreground";
  return (
    <div className="flex flex-col gap-0.5 rounded-lg border bg-card px-3 py-2">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className={`text-lg font-semibold tabular-nums ${cls}`}>{value}</span>
    </div>
  );
}
