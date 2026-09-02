"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogPopup,
  DialogTitle,
  DialogDescription,
  DialogClose,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toast";
import { useStudentsRoster } from "../../students/_hooks/use-students";
import { useResolveReview } from "../_hooks/use-test-portal";
import type { ReviewRow } from "../_schemas/test-portal";

interface Props {
  branchId: string | undefined;
  testId: string;
  review: ReviewRow | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

// Assign an unmatched ZipGrade row (PRN typo / wrong batch) to the right
// student. Searches the whole branch roster — the student may sit outside the
// test's batch — and writes their mark on resolve.
export function ResolveReviewDialog({
  branchId,
  testId,
  review,
  open,
  onOpenChange,
}: Props) {
  const toast = useToast();
  // Seed the search box with the CSV name so the likely match surfaces first.
  // The parent keys this component on the review id, so it remounts (and these
  // initializers re-run) whenever a different row is opened — no effect needed.
  const [search, setSearch] = useState(review?.csv_name ?? "");
  const [picked, setPicked] = useState<string | null>(null);
  const resolve = useResolveReview(branchId);

  const roster = useStudentsRoster(branchId, {
    offset: 0,
    limit: 15,
    search,
  });
  const students = roster.data?.items ?? [];

  async function handleResolve() {
    if (!review || !picked) return;
    try {
      await resolve.mutateAsync({
        testId,
        reviewId: review.id,
        studentId: picked,
      });
      toast.success("Row resolved", "The student's mark has been recorded.");
      onOpenChange(false);
    } catch {
      toast.error("Could not resolve", "Pick a valid student and try again.");
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogPopup className="max-w-lg">
        <DialogTitle>Resolve unmatched row</DialogTitle>
        <DialogDescription>
          {review?.csv_prn ? (
            <>
              PRN <span className="font-medium">{review.csv_prn}</span>
              {review.csv_name ? ` · ${review.csv_name}` : ""} didn&apos;t match a
              student in this batch. Pick the correct student to record their mark.
            </>
          ) : (
            <>
              This ZipGrade row had no PRN
              {review?.csv_name ? ` (${review.csv_name})` : ""}. Pick the correct
              student to record their mark.
            </>
          )}
        </DialogDescription>

        <div className="mt-4 flex flex-col gap-3">
          <Input
            autoFocus
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search students by name or PRN…"
          />

          <div className="max-h-64 overflow-y-auto rounded-lg border">
            {roster.isLoading ? (
              <p className="px-3 py-4 text-sm text-muted-foreground">Searching…</p>
            ) : students.length === 0 ? (
              <p className="px-3 py-4 text-sm text-muted-foreground">
                No students match “{search}”.
              </p>
            ) : (
              students.map((s) => {
                const on = picked === s.id;
                return (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => setPicked(s.id)}
                    aria-pressed={on}
                    className={`flex w-full items-center justify-between gap-2 border-b px-3 py-2 text-left text-sm last:border-b-0 transition-colors ${
                      on ? "bg-primary/10 text-foreground" : "hover:bg-muted"
                    }`}
                  >
                    <span className="font-medium">
                      {s.first_name} {s.last_name}
                    </span>
                    <span className="tabular-nums text-xs text-muted-foreground">
                      {s.enrollment_number || "no PRN"}
                      {s.batch_name ? ` · ${s.batch_name}` : ""}
                    </span>
                  </button>
                );
              })
            )}
          </div>

          <div className="flex justify-end gap-2 pt-1">
            <DialogClose render={<Button variant="outline" type="button">Cancel</Button>} />
            <Button
              type="button"
              disabled={!picked || resolve.isPending}
              onClick={handleResolve}
            >
              {resolve.isPending ? "Resolving…" : "Resolve"}
            </Button>
          </div>
        </div>
      </DialogPopup>
    </Dialog>
  );
}
