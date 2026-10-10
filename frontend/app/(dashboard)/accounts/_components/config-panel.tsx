"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { useToast } from "@/components/ui/toast";
import { useCourseFees, useSetCourseFee } from "../_hooks/use-fees";
import { inr } from "../_schemas/fees";

export function ConfigPanel({ branchId }: { branchId: string | undefined }) {
  const toast = useToast();
  const q = useCourseFees(branchId);
  const save = useSetCourseFee(branchId);
  const [course, setCourse] = useState("");
  const [fee, setFee] = useState("");
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!course.trim()) return setError("Enter a course name (CET / JEE / NEET)");
    const n = Number(fee);
    if (!Number.isFinite(n) || n < 0) return setError("Enter a valid fee");
    try {
      await save.mutateAsync({ course_name: course.trim(), standard_fee: n });
      toast.success("Course fee saved", `${course.trim()} · ${inr(n)}`);
      setCourse("");
      setFee("");
      setError("");
    } catch {
      setError("Failed to save the course fee");
    }
  }

  return (
    <div className="grid items-start gap-5 lg:grid-cols-2">
      <Card>
        <CardContent className="flex flex-col gap-3">
          <h3 className="text-sm font-semibold">Standard course fees</h3>
          <p className="text-xs text-muted-foreground">
            Auto-fills a new student&apos;s actual fee. Changing a fee affects only new
            admissions — existing profiles are untouched.
          </p>
          {(q.data ?? []).length === 0 ? (
            <p className="text-sm text-muted-foreground">No course fees set yet.</p>
          ) : (
            <ul className="flex flex-col divide-y rounded-lg border">
              {(q.data ?? []).map((c) => (
                <li key={c.id} className="flex items-center justify-between px-3 py-2 text-sm">
                  <span className="font-medium">{c.course_name}</span>
                  <span className="tabular-nums">{inr(c.standard_fee)}</span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardContent>
          <form onSubmit={submit} className="flex flex-col gap-3">
            <h3 className="text-sm font-semibold">Set / update a course fee</h3>
            <div className="flex flex-col gap-1">
              <Label htmlFor="cfg-course">Course name</Label>
              <Input id="cfg-course" value={course} onChange={(e) => setCourse(e.target.value)} placeholder="CET / JEE / NEET" />
            </div>
            <div className="flex flex-col gap-1">
              <Label htmlFor="cfg-fee">Standard fee (₹)</Label>
              <Input id="cfg-fee" type="number" min={0} value={fee} onChange={(e) => setFee(e.target.value)} placeholder="160000" />
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <div className="flex justify-end">
              <Button type="submit" disabled={save.isPending}>
                {save.isPending ? "Saving…" : "Save fee"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
