"use client";

import { useRef, useState } from "react";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { TableSkeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import {
  useDownloadAnswerKey,
  useDownloadRankList,
  useRankList,
  useUploadAnswerKey,
  useUploadResult,
} from "../_hooks/use-test-portal";
import type { ReviewRow, TestSummary } from "../_schemas/test-portal";
import { ResolveReviewDialog } from "./resolve-review-dialog";

export function RankList({
  branchId,
  test,
}: {
  branchId: string | undefined;
  test: TestSummary;
}) {
  const toast = useToast();
  const fileRef = useRef<HTMLInputElement>(null);
  const keyRef = useRef<HTMLInputElement>(null);
  const query = useRankList(branchId, test.id);
  const upload = useUploadResult(branchId);
  const download = useDownloadRankList(branchId);
  const uploadKey = useUploadAnswerKey(branchId);
  const downloadKey = useDownloadAnswerKey(branchId);
  const [resolving, setResolving] = useState<ReviewRow | null>(null);
  const rl = query.data;

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ""; // allow re-uploading the same file
    if (!file) return;
    try {
      const res = await upload.mutateAsync({ testId: test.id, file });
      toast.success(
        "Result uploaded",
        `${res.matched} matched · ${res.absent} absent · ${res.needs_review} to review`,
      );
    } catch {
      toast.error("Upload failed", "Check the CSV and try again.");
    }
  }

  async function onAnswerKey(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    try {
      await uploadKey.mutateAsync({ testId: test.id, file });
      toast.success("Answer key saved", file.name);
    } catch {
      toast.error("Upload failed", "Could not save the answer key.");
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <input
          ref={fileRef}
          type="file"
          accept=".csv,text/csv"
          onChange={onFile}
          className="hidden"
        />
        <input
          ref={keyRef}
          type="file"
          onChange={onAnswerKey}
          className="hidden"
        />
        <Button size="sm" onClick={() => fileRef.current?.click()} disabled={upload.isPending}>
          {upload.isPending ? "Uploading…" : "Upload ZipGrade CSV"}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          title="Download a sample ZipGrade export to see the expected format"
          render={<a href="/zipgrade-sample.csv" download="zipgrade-sample.csv" />}
        >
          Sample CSV
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={!rl || rl.ranked.length === 0 || download.isPending}
          onClick={() => download.mutate({ testId: test.id, format: "pdf" })}
        >
          Download PDF
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={!rl || rl.ranked.length === 0 || download.isPending}
          onClick={() => download.mutate({ testId: test.id, format: "xlsx" })}
        >
          Download Excel
        </Button>
        <span className="mx-1 h-4 w-px bg-border" aria-hidden />
        <Button
          size="sm"
          variant="outline"
          onClick={() => keyRef.current?.click()}
          disabled={uploadKey.isPending}
        >
          {uploadKey.isPending
            ? "Uploading…"
            : test.answer_key_file
              ? "Replace answer key"
              : "Upload answer key"}
        </Button>
        {test.answer_key_file && (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => downloadKey.mutate({ testId: test.id })}
            disabled={downloadKey.isPending}
          >
            Answer key
          </Button>
        )}
        {rl && rl.needs_review.length > 0 && (
          <Badge variant="warning" className="ml-auto">
            {rl.needs_review.length} row{rl.needs_review.length === 1 ? "" : "s"} need review
          </Badge>
        )}
      </div>

      {/* Unmatched rows — actionable so the admin can assign each to a student. */}
      {rl && rl.needs_review.length > 0 && (
        <Card size="sm" className="border-warning/40">
          <CardContent className="flex flex-col gap-2">
            <p className="text-sm font-medium">Needs review</p>
            <p className="text-xs text-muted-foreground">
              These scanned rows didn&apos;t match a student in this batch (a PRN
              typo, or a student who sat the test outside their batch). Assign each
              to the right student to add their mark.
            </p>
            <div className="flex flex-col divide-y rounded-lg border">
              {rl.needs_review.map((r) => (
                <div
                  key={r.id}
                  className="flex items-center justify-between gap-2 px-3 py-2 text-sm"
                >
                  <span className="min-w-0 truncate">
                    <span className="tabular-nums text-muted-foreground">
                      {r.csv_prn || "— no PRN —"}
                    </span>
                    {r.csv_name ? <span className="ml-2">{r.csv_name}</span> : null}
                  </span>
                  <Button size="xs" variant="outline" onClick={() => setResolving(r)}>
                    Resolve
                  </Button>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {query.isLoading ? (
        <TableSkeleton rows={6} />
      ) : query.isError ? (
        <p className="text-sm text-destructive">Failed to load the rank list.</p>
      ) : !rl || (rl.ranked.length === 0 && rl.absentees.length === 0) ? (
        <Card size="sm">
          <CardContent>
            <p className="text-sm text-muted-foreground">
              No results yet. Upload the ZipGrade CSV to build the rank list.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="rounded-xl border ring-1 ring-foreground/10 overflow-hidden">
          <Table stickyHeader containerClassName="max-h-[65vh]">
            <TableHeader>
              <TableRow>
                <TableHead className="w-14 text-right">Rank</TableHead>
                <TableHead>PRN</TableHead>
                <TableHead>Student</TableHead>
                <TableHead className="text-right">Marks</TableHead>
                <TableHead className="text-right">%</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rl.ranked.map((r) => (
                <TableRow key={r.student_id}>
                  <TableCell className="text-right font-semibold tabular-nums">
                    {r.rank}
                  </TableCell>
                  <TableCell className="tabular-nums text-sm text-muted-foreground">
                    {r.prn || "—"}
                  </TableCell>
                  <TableCell className="font-medium">{r.name}</TableCell>
                  <TableCell className="text-right tabular-nums">
                    {r.marks_obtained ?? 0} / {rl.total_marks}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {r.percentage != null ? `${r.percentage.toFixed(1)}` : "—"}
                  </TableCell>
                </TableRow>
              ))}
              {rl.absentees.map((r) => (
                <TableRow key={r.student_id} className="bg-destructive/5">
                  <TableCell className="text-right text-muted-foreground">—</TableCell>
                  <TableCell className="tabular-nums text-sm text-muted-foreground">
                    {r.prn || "—"}
                  </TableCell>
                  <TableCell className="font-medium">{r.name}</TableCell>
                  <TableCell className="text-right">
                    <Badge variant="destructive">ABSENT</Badge>
                  </TableCell>
                  <TableCell className="text-right text-muted-foreground">—</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <ResolveReviewDialog
        key={resolving?.id ?? "none"}
        branchId={branchId}
        testId={test.id}
        review={resolving}
        open={resolving !== null}
        onOpenChange={(o) => {
          if (!o) setResolving(null);
        }}
      />
    </div>
  );
}
