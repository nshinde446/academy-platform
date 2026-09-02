"use client";

import { useRef } from "react";
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
  useDownloadRankList,
  useRankList,
  useUploadResult,
} from "../_hooks/use-test-portal";
import type { TestSummary } from "../_schemas/test-portal";

export function RankList({
  branchId,
  test,
}: {
  branchId: string | undefined;
  test: TestSummary;
}) {
  const toast = useToast();
  const fileRef = useRef<HTMLInputElement>(null);
  const query = useRankList(branchId, test.id);
  const upload = useUploadResult(branchId);
  const download = useDownloadRankList(branchId);
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
        <Button size="sm" onClick={() => fileRef.current?.click()} disabled={upload.isPending}>
          {upload.isPending ? "Uploading…" : "Upload ZipGrade CSV"}
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
        {rl && rl.needs_review.length > 0 && (
          <Badge variant="warning" className="ml-auto">
            {rl.needs_review.length} row{rl.needs_review.length === 1 ? "" : "s"} need review
          </Badge>
        )}
      </div>

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
    </div>
  );
}
