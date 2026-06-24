"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogTrigger,
  DialogPopup,
  DialogTitle,
  DialogDescription,
  DialogClose,
} from "@/components/ui/dialog";
import { useCopyToNextDay } from "../_hooks/use-lectures";
import type { CopyScheduleSummary } from "../_schemas/lecture";

interface CopyScheduleDialogProps {
  branchId: string | undefined;
}

function todayIso(): string {
  const d = new Date();
  const shifted = new Date(d.getTime() - d.getTimezoneOffset() * 60_000);
  return shifted.toISOString().slice(0, 10);
}

function nextDay(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  d.setDate(d.getDate() + 1);
  const shifted = new Date(d.getTime() - d.getTimezoneOffset() * 60_000);
  return shifted.toISOString().slice(0, 10);
}

export function CopyScheduleDialog({ branchId }: CopyScheduleDialogProps) {
  const [open, setOpen] = useState(false);
  const [sourceDate, setSourceDate] = useState(todayIso());
  const [targetDate, setTargetDate] = useState(nextDay(todayIso()));
  const [result, setResult] = useState<CopyScheduleSummary | null>(null);
  const [error, setError] = useState("");

  const copyMutation = useCopyToNextDay(branchId);

  function reset() {
    const t = todayIso();
    setSourceDate(t);
    setTargetDate(nextDay(t));
    setResult(null);
    setError("");
  }

  async function handleCopy() {
    setError("");
    setResult(null);
    try {
      const summary = await copyMutation.mutateAsync({
        sourceDate,
        targetDate: targetDate || undefined,
      });
      setResult(summary);
    } catch (err: any) {
      setError(
        err?.response?.data?.error?.message ||
          err?.response?.data?.detail ||
          "Copy failed"
      );
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(isOpen) => {
        setOpen(isOpen);
        if (!isOpen) reset();
      }}
    >
      <DialogTrigger
        render={
          <Button variant="outline" onClick={() => setOpen(true)}>
            Copy to Next Day
          </Button>
        }
      />
      <DialogPopup className="max-w-md">
        <DialogTitle>Copy Schedule</DialogTitle>
        <DialogDescription>
          Duplicates a day&apos;s full lecture plan to another date — same batch,
          subject, teacher, and times. Actuals, topic, and late flag are reset
          for the new day. Rows that would clash on the target day are skipped,
          so it&apos;s safe to run twice.
        </DialogDescription>

        <div className="mt-4 flex flex-col gap-4">
          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="copy_source">Copy from *</Label>
              <Input
                id="copy_source"
                type="date"
                value={sourceDate}
                onChange={(e) => {
                  setSourceDate(e.target.value);
                  setTargetDate(nextDay(e.target.value));
                }}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="copy_target">Copy to *</Label>
              <Input
                id="copy_target"
                type="date"
                value={targetDate}
                onChange={(e) => setTargetDate(e.target.value)}
              />
            </div>
          </div>

          {result && (
            <div
              className={
                "rounded-lg border p-3 text-sm " +
                (result.skipped === 0
                  ? "border-emerald-500/40 bg-emerald-500/10"
                  : "border-amber-500/40 bg-amber-500/10")
              }
            >
              <p>
                <span className="font-medium">{result.copied}</span> copied to{" "}
                {result.target_date}
                {result.skipped > 0 && (
                  <>
                    {" · "}
                    <span className="font-medium">{result.skipped}</span> skipped
                    (conflict)
                  </>
                )}
                .
              </p>
              {result.errors.length > 0 && (
                <ul className="mt-2 list-disc pl-5 text-xs text-muted-foreground">
                  {result.errors.slice(0, 8).map((e, i) => (
                    <li key={i}>{e}</li>
                  ))}
                  {result.errors.length > 8 && (
                    <li>…and {result.errors.length - 8} more</li>
                  )}
                </ul>
              )}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <DialogClose
              render={
                <Button variant="outline" type="button">
                  {result ? "Close" : "Cancel"}
                </Button>
              }
            />
            <Button
              type="button"
              onClick={handleCopy}
              disabled={copyMutation.isPending || !sourceDate || !targetDate}
            >
              {copyMutation.isPending ? "Copying..." : "Copy"}
            </Button>
          </div>
        </div>
      </DialogPopup>
    </Dialog>
  );
}
