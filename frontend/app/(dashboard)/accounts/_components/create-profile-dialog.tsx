"use client";

import { useMemo, useState } from "react";
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
import { useToast } from "@/components/ui/toast";
import { useBatchesForLectures } from "../../lectures/_hooks/use-lectures";
import { useCourseFees, useCreateFeeProfile, useStudentsInBatch } from "../_hooks/use-fees";
import { inr } from "../_schemas/fees";

const SELECT = "h-9 w-full rounded-lg border border-input bg-background px-3 text-sm";

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

export function CreateProfileDialog({ branchId }: { branchId: string | undefined }) {
  const [open, setOpen] = useState(false);
  const toast = useToast();
  const create = useCreateFeeProfile(branchId);

  const batchesQuery = useBatchesForLectures(branchId);
  const batches = useMemo(() => batchesQuery.data ?? [], [batchesQuery.data]);
  const courseFees = useCourseFees(branchId);

  const [batchId, setBatchId] = useState("");
  const studentsQuery = useStudentsInBatch(branchId, batchId || undefined);
  const students = studentsQuery.data ?? [];

  const [studentId, setStudentId] = useState("");
  const [actual, setActual] = useState("");
  const [agreed, setAgreed] = useState("");
  const [mode, setMode] = useState<"INSTALLMENT" | "ONE_TIME">("INSTALLMENT");
  const [admission, setAdmission] = useState(today());
  const [firstInst, setFirstInst] = useState("");
  const [remaining, setRemaining] = useState("4");
  const [error, setError] = useState("");

  const selectedBatch = batches.find((b) => b.id === batchId);

  function reset() {
    setBatchId("");
    setStudentId("");
    setActual("");
    setAgreed("");
    setMode("INSTALLMENT");
    setAdmission(today());
    setFirstInst("");
    setRemaining("4");
    setError("");
  }

  // Prefill the actual fee from the course config matching the batch's course name.
  function pickBatch(id: string) {
    setBatchId(id);
    setStudentId("");
    const b = batches.find((x) => x.id === id);
    const match = (courseFees.data ?? []).find(
      (c) => b && b.name.toUpperCase().includes(c.course_name.toUpperCase()),
    );
    if (match) {
      setActual(String(Math.round(match.standard_fee)));
      setAgreed(String(Math.round(match.standard_fee)));
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!studentId) return setError("Pick a student");
    const a = Number(actual);
    const g = Number(agreed);
    if (!Number.isFinite(a) || a <= 0) return setError("Enter the actual fee");
    if (!Number.isFinite(g) || g <= 0) return setError("Enter the agreed fee");
    if (g > a) return setError("Agreed fee cannot exceed the actual fee");

    const body: Parameters<typeof create.mutateAsync>[0] = {
      student_id: studentId,
      batch_id: batchId,
      actual_fee: a,
      agreed_fee: g,
      payment_mode: mode,
      admission_date: admission,
    };
    if (mode === "INSTALLMENT") {
      const fi = Number(firstInst);
      const rem = Number(remaining);
      if (!Number.isFinite(fi) || fi <= 0) return setError("Enter the first installment amount");
      if (!Number.isInteger(rem) || rem < 0) return setError("Enter the number of remaining installments");
      if (fi > g) return setError("First installment cannot exceed the agreed fee");
      body.first_installment = fi;
      body.remaining_installments = rem;
    }

    try {
      await create.mutateAsync(body);
      toast.success("Fee profile created", `${inr(g)} · ${mode === "ONE_TIME" ? "one-time" : "installments"}`);
      reset();
      setOpen(false);
    } catch (err) {
      const e2 = err as { response?: { data?: { detail?: string; error?: { message?: string } } } };
      setError(e2?.response?.data?.error?.message || e2?.response?.data?.detail || "Failed to create the fee profile");
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) reset();
      }}
    >
      <DialogTrigger render={<Button onClick={() => setOpen(true)}>New fee profile</Button>} />
      <DialogPopup className="max-w-lg">
        <DialogTitle>New fee profile</DialogTitle>
        <DialogDescription>Set a student&apos;s fee at admission and the installment plan.</DialogDescription>
        <form onSubmit={submit} className="mt-4 flex flex-col gap-3">
          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1">
              <Label htmlFor="cp-batch">Batch</Label>
              <select id="cp-batch" value={batchId} onChange={(e) => pickBatch(e.target.value)} className={SELECT}>
                <option value="">Select…</option>
                {batches.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <Label htmlFor="cp-student">Student</Label>
              <select
                id="cp-student"
                value={studentId}
                onChange={(e) => setStudentId(e.target.value)}
                className={SELECT}
                disabled={!batchId}
              >
                <option value="">{batchId ? "Select…" : "Pick a batch first"}</option>
                {students.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.first_name} {s.last_name} {s.enrollment_number ? `(${s.enrollment_number})` : ""}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1">
              <Label htmlFor="cp-actual">Actual fee {selectedBatch ? "" : ""}</Label>
              <Input id="cp-actual" type="number" min={1} value={actual} onChange={(e) => setActual(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1">
              <Label htmlFor="cp-agreed">Agreed fee</Label>
              <Input id="cp-agreed" type="number" min={1} value={agreed} onChange={(e) => setAgreed(e.target.value)} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1">
              <Label htmlFor="cp-mode">Payment mode</Label>
              <select id="cp-mode" value={mode} onChange={(e) => setMode(e.target.value as "INSTALLMENT" | "ONE_TIME")} className={SELECT}>
                <option value="INSTALLMENT">Installment</option>
                <option value="ONE_TIME">One time</option>
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <Label htmlFor="cp-admission">Admission date</Label>
              <Input id="cp-admission" type="date" value={admission} onChange={(e) => setAdmission(e.target.value)} />
            </div>
          </div>

          {mode === "INSTALLMENT" && (
            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col gap-1">
                <Label htmlFor="cp-first">First installment</Label>
                <Input id="cp-first" type="number" min={1} value={firstInst} onChange={(e) => setFirstInst(e.target.value)} placeholder="Paid at admission" />
              </div>
              <div className="flex flex-col gap-1">
                <Label htmlFor="cp-remaining">Remaining installments</Label>
                <Input id="cp-remaining" type="number" min={0} value={remaining} onChange={(e) => setRemaining(e.target.value)} />
              </div>
              <p className="col-span-2 text-xs text-muted-foreground">
                Dates auto-calculate every 2.5 months from admission; the amounts split evenly and can be edited later.
              </p>
            </div>
          )}

          <div className="mt-2 flex justify-end gap-2">
            <DialogClose render={<Button type="button" variant="outline">Cancel</Button>} />
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? "Creating…" : "Create profile"}
            </Button>
          </div>
        </form>
      </DialogPopup>
    </Dialog>
  );
}
