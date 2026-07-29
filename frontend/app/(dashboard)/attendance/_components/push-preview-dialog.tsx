"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogPopup,
  DialogTitle,
  DialogDescription,
  DialogClose,
} from "@/components/ui/dialog";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import type {
  PlannedAction,
  ProvisionPlanResponse,
} from "../_schemas/provisioning";

const ACTION_TONE: Record<PlannedAction, "default" | "secondary" | "destructive"> = {
  create: "default",
  update: "default",
  no_change: "secondary",
  skipped: "destructive",
};

const ACTION_LABEL: Record<PlannedAction, string> = {
  create: "Create",
  update: "Update",
  no_change: "No change",
  skipped: "Skipped",
};

// Only this many rows are listed; the rest are summarised. A 2000-student push
// shouldn't render 2000 rows into a dialog.
const MAX_ROWS = 50;

// Dry-run preview: what a push WOULD do. Confirming enqueues the commands; it
// does not touch the device. Open state is driven by whether `plan` is set.
export function PushPreviewDialog({
  plan,
  pending,
  onConfirm,
  onOpenChange,
}: {
  plan: ProvisionPlanResponse | null;
  pending: boolean;
  onConfirm: () => Promise<void>;
  onOpenChange: (open: boolean) => void;
}) {
  const [error, setError] = useState("");
  const open = plan !== null;

  const willQueue = plan ? plan.to_create + plan.to_update : 0;
  const shown = plan ? plan.commands.slice(0, MAX_ROWS) : [];
  const extra = plan ? plan.commands.length - shown.length : 0;

  async function handleConfirm() {
    setError("");
    try {
      await onConfirm();
    } catch (err: unknown) {
      const e = err as {
        response?: { data?: { error?: { message?: string }; detail?: string } };
      };
      setError(
        e?.response?.data?.error?.message ||
          e?.response?.data?.detail ||
          "Push failed",
      );
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (pending) return;
        if (!o) setError("");
        onOpenChange(o);
      }}
    >
      <DialogPopup className="max-w-2xl">
        <DialogTitle>Push to device</DialogTitle>
        <DialogDescription>
          {plan ? (
            <>
              This queues <b>{willQueue}</b> register command
              {willQueue === 1 ? "" : "s"} for the device to apply on its next
              contact. Nothing is sent to the terminal right now.
            </>
          ) : null}
        </DialogDescription>

        {plan && (
          <>
            <div className="mt-4 flex flex-wrap gap-2">
              <Count label="Create" value={plan.to_create} />
              <Count label="Update" value={plan.to_update} />
              <Count label="No change" value={plan.no_change} muted />
              <Count label="Skipped" value={plan.skipped} muted={plan.skipped === 0} />
            </div>

            {plan.skipped > 0 && (
              <p className="mt-2 text-xs text-muted-foreground">
                Skipped students have no valid device userId (a numeric roll
                number is required) — they&apos;re left out of the queue.
              </p>
            )}

            <div className="mt-4 rounded-lg border ring-1 ring-foreground/10 overflow-hidden">
              <Table stickyHeader containerClassName="max-h-[45vh]">
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-28">User ID</TableHead>
                    <TableHead>Name</TableHead>
                    <TableHead className="w-28">Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {shown.map((c) => (
                    <TableRow key={c.student_id}>
                      <TableCell className="tabular-nums text-sm">
                        {c.vendor_user_id ?? "—"}
                      </TableCell>
                      <TableCell>
                        <span className={c.name ? "" : "text-muted-foreground"}>
                          {c.name ?? "—"}
                        </span>
                        {c.action === "skipped" && c.reason && (
                          <span className="mt-0.5 block text-[11px] text-muted-foreground">
                            {c.reason}
                          </span>
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={ACTION_TONE[c.action]}
                          className="text-[10px]"
                        >
                          {ACTION_LABEL[c.action]}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
            {extra > 0 && (
              <p className="mt-2 text-xs text-muted-foreground">
                …and {extra} more.
              </p>
            )}
          </>
        )}

        {error && (
          <p className="mt-3 text-sm text-destructive" role="alert">
            {error}
          </p>
        )}

        <div className="mt-5 flex justify-end gap-2">
          <DialogClose
            render={
              <Button variant="outline" type="button" disabled={pending}>
                Cancel
              </Button>
            }
          />
          <Button
            type="button"
            onClick={handleConfirm}
            disabled={pending || willQueue === 0}
          >
            {pending
              ? "Queuing…"
              : willQueue === 0
                ? "Nothing to queue"
                : `Queue ${willQueue} command${willQueue === 1 ? "" : "s"}`}
          </Button>
        </div>
      </DialogPopup>
    </Dialog>
  );
}

function Count({
  label,
  value,
  muted = false,
}: {
  label: string;
  value: number;
  muted?: boolean;
}) {
  return (
    <div
      className={`flex items-baseline gap-1.5 rounded-lg border px-3 py-1.5 ${
        muted ? "text-muted-foreground" : ""
      }`}
    >
      <span className="text-lg font-semibold tabular-nums">{value}</span>
      <span className="text-xs">{label}</span>
    </div>
  );
}
