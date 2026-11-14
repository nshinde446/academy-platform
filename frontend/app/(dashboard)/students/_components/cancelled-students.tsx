"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { TableSkeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import {
  useCancelledStudents,
  useRestoreStudent,
} from "../_hooks/use-students";

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
  });
}

// Cancelled Students tab (Point 4): PRN, name, batch, cancel date, reason + a
// Restore action. Managers only reach this view; the server enforces regardless.
export function CancelledStudents({
  branchId,
  canRestore,
}: {
  branchId: string | undefined;
  canRestore: boolean;
}) {
  const toast = useToast();
  const query = useCancelledStudents(branchId);
  const restore = useRestoreStudent(branchId);
  const rows = query.data ?? [];

  async function handleRestore(id: string, name: string) {
    try {
      await restore.mutateAsync(id);
      toast.success("Admission restored", `${name} is active again.`);
    } catch {
      toast.error("Restore failed", "Please try again.");
    }
  }

  if (query.isLoading) return <TableSkeleton rows={5} />;
  if (query.isError)
    return (
      <p className="text-sm text-destructive">
        Failed to load cancelled students.
      </p>
    );
  if (rows.length === 0)
    return (
      <Card size="sm">
        <CardContent>
          <p className="text-sm text-muted-foreground">
            No cancelled admissions. When you cancel a student&apos;s admission,
            their record is kept here and can be restored.
          </p>
        </CardContent>
      </Card>
    );

  return (
    <div className="rounded-xl border ring-1 ring-foreground/10 overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>PRN</TableHead>
            <TableHead>Student</TableHead>
            <TableHead>Batch</TableHead>
            <TableHead>Cancelled on</TableHead>
            <TableHead>Reason</TableHead>
            {canRestore && <TableHead className="text-right">Action</TableHead>}
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((r) => (
            <TableRow key={r.id}>
              <TableCell className="tabular-nums text-sm text-muted-foreground">
                {r.enrollment_number || "—"}
              </TableCell>
              <TableCell className="font-medium">
                {r.first_name} {r.last_name}
              </TableCell>
              <TableCell className="text-sm">{r.batch_name || "—"}</TableCell>
              <TableCell className="whitespace-nowrap text-sm tabular-nums">
                {formatDate(r.cancelled_at)}
              </TableCell>
              <TableCell className="text-sm text-muted-foreground max-w-xs">
                {r.cancellation_reason || "—"}
              </TableCell>
              {canRestore && (
                <TableCell className="text-right">
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={restore.isPending}
                    onClick={() =>
                      handleRestore(r.id, `${r.first_name} ${r.last_name}`)
                    }
                  >
                    Restore
                  </Button>
                </TableCell>
              )}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
