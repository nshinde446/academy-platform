"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
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
import { InfoHint } from "@/components/ui/info-hint";
import { TableSkeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { useRowSelection } from "@/hooks/use-row-selection";
import {
  useCancelCommand,
  useDeviceCommands,
  useProvisionDevices,
  useProvisionDryRun,
  useProvisionPush,
  useReconcile,
} from "../_hooks/use-provisioning";
import type {
  CommandStatus,
  DeviceCommandRow,
  ProvisionPlanResponse,
  ReconcileRow,
} from "../_schemas/provisioning";
import { PushPreviewDialog } from "./push-preview-dialog";

const CONTROL_CLASS =
  "h-9 rounded-lg border border-input bg-background px-3 text-sm";

function errorOf(err: unknown): string {
  const e = err as {
    response?: { data?: { error?: { message?: string }; detail?: string } };
  };
  return (
    e?.response?.data?.error?.message ||
    e?.response?.data?.detail ||
    "Action failed"
  );
}

interface DeviceSyncProps {
  branchId: string | undefined;
}

// Reconciliation + push between platform students and the BioMax device's own
// user table (mirrored from its realtime_enroll_data pushes). Read side: three
// groups — need pushing / only on device / name drift. Write side: pick the
// students that need registering, preview the plan (dry-run), confirm, and the
// commands land in the outbound queue. Nothing here emits to the device — the
// device drains the queue on its next contact (a later, capture-gated step).
export function DeviceSync({ branchId }: DeviceSyncProps) {
  const toast = useToast();
  const devicesQuery = useProvisionDevices(branchId);
  const enabled = devicesQuery.data?.enabled ?? false;
  const devices = useMemo(
    () => devicesQuery.data?.devices ?? [],
    [devicesQuery.data],
  );

  // Derive the effective device (default = first configured) rather than
  // defaulting through an effect — keeps the selection valid as devices load
  // without a setState-in-effect cascade.
  const [selectedDevId, setSelectedDevId] = useState("");
  const devId = selectedDevId || devices[0]?.dev_id || "";

  const reconcileQuery = useReconcile(branchId, devId || undefined, enabled);
  const data = reconcileQuery.data;
  const commandsQuery = useDeviceCommands(branchId, devId || undefined, enabled);

  // One selection model spanning both push-eligible groups (need-pushing +
  // drift). Device-only rows can't be pushed — no platform student behind them.
  const selection = useRowSelection();

  const dryRun = useProvisionDryRun(devId || undefined);
  const push = useProvisionPush(branchId, devId || undefined);
  const [plan, setPlan] = useState<ProvisionPlanResponse | null>(null);

  async function handlePreview() {
    try {
      const result = await dryRun.mutateAsync(selection.selected);
      setPlan(result);
    } catch (err) {
      toast.error(errorOf(err));
    }
  }

  async function handleConfirmPush() {
    const result = await push.mutateAsync(selection.selected);
    setPlan(null);
    selection.clear();
    toast.success(
      `Queued ${result.enqueued} command${result.enqueued === 1 ? "" : "s"}` +
        (result.skipped ? ` · ${result.skipped} skipped` : ""),
    );
  }

  if (!branchId) {
    return <p className="text-muted-foreground text-sm">No branch selected.</p>;
  }

  if (devicesQuery.isLoading) {
    return <TableSkeleton rows={6} />;
  }

  if (devicesQuery.isError) {
    // The endpoint is admin-only; a 403 lands here for non-admin staff.
    return (
      <p className="text-muted-foreground text-sm">
        Device provisioning is available to administrators only.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Controls + status */}
      <Card size="sm">
        <CardContent>
          <div className="flex flex-wrap items-end gap-3">
            <label className="flex flex-col gap-1 text-xs text-muted-foreground">
              Device
              <select
                value={devId}
                onChange={(e) => {
                  setSelectedDevId(e.target.value);
                  selection.clear();
                }}
                className={CONTROL_CLASS}
                aria-label="Select device"
                disabled={devices.length === 0}
              >
                {devices.length === 0 ? (
                  <option value="">No device configured</option>
                ) : (
                  devices.map((d) => (
                    <option key={d.dev_id} value={d.dev_id}>
                      {d.dev_id}
                    </option>
                  ))
                )}
              </select>
            </label>
            <div className="flex items-center gap-1 pb-1">
              <StatusPill enabled={enabled} />
              <InfoHint
                text={
                  <>
                    Compares the platform&apos;s students against the device&apos;s
                    own user table (mirrored from its enrollment pushes). Matching
                    is by device <em>userId</em>, which is the student&apos;s roll
                    number. Pushing queues a register command per student; the
                    device applies it on its next contact. Enrollment mirroring
                    and pushing only run when provisioning is enabled, so until
                    then the device side reads empty by design.
                  </>
                }
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Summary tiles */}
      {enabled && data && (
        <Card size="sm">
          <CardContent>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
              <Tile
                label="Need pushing"
                value={data.on_platform_not_on_device.length}
                tone="warn"
              />
              <Tile
                label="Awaiting face"
                value={(data.awaiting_face_enrollment ?? []).length}
              />
              <Tile
                label="Only on device"
                value={data.on_device_not_on_platform.length}
              />
              <Tile label="Name drift" value={data.drift.length} tone="warn" />
              <Tile
                label="In queue"
                value={
                  (commandsQuery.data ?? []).filter(
                    (c) => c.command_status === "pending" || c.command_status === "sent",
                  ).length
                }
              />
            </div>
          </CardContent>
        </Card>
      )}

      {/* Push action bar — explicit selection, never a blind bulk push */}
      {enabled && selection.count > 0 && (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-primary/30 bg-primary/5 px-3 py-2">
          <span className="text-sm font-medium">
            {selection.count} student{selection.count === 1 ? "" : "s"} selected
          </span>
          <Button
            size="sm"
            onClick={handlePreview}
            disabled={dryRun.isPending || push.isPending}
          >
            {dryRun.isPending ? "Preparing…" : "Push to device…"}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={selection.clear}
            disabled={dryRun.isPending || push.isPending}
          >
            Clear
          </Button>
        </div>
      )}

      {/* Body */}
      {!enabled ? (
        <p className="text-muted-foreground text-sm">
          Device provisioning is turned off. The reconciliation view activates
          once <code>BIOMAX_PROVISIONING_ENABLED</code> is set — the plumbing is
          in place and dormant until then.
        </p>
      ) : reconcileQuery.isLoading ? (
        <TableSkeleton rows={6} />
      ) : reconcileQuery.isError ? (
        <p className="text-destructive text-sm">
          Failed to reconcile with the device.
        </p>
      ) : !data ? null : (
        <div className="flex flex-col gap-6">
          <ReconcileSection
            title="Need pushing (no identity on device yet)"
            hint="Students with a valid device userId (roll number) that we have NOT confirmed onto the device — select and push to register their identity."
            rows={data.on_platform_not_on_device}
            emptyText="Every student's identity has been pushed to the device."
            linkStudents
            selection={selection}
          />
          <ReconcileSection
            title="Awaiting face enrollment"
            hint="Identity already pushed and confirmed on the device, but the device hasn't mirrored them back — in practice because no face is enrolled yet. The next step is enrolling their face at the terminal, NOT another push."
            rows={data.awaiting_face_enrollment ?? []}
            emptyText="No students are waiting on a face enrollment."
            linkStudents
          />
          <ReconcileSection
            title="Name drift"
            hint="Present on both, but the name on the device differs from the platform — pushing re-registers with the platform name."
            rows={data.drift}
            emptyText="No name mismatches."
            linkStudents
            selection={selection}
          />
          <ReconcileSection
            title="On the device, not on the platform"
            hint="Users enrolled on the device with no matching student here — a stale entry, a manual enrollment, or a roll number that doesn't exist on the platform. Not pushable from here."
            rows={data.on_device_not_on_platform}
            emptyText="No device users are unaccounted for."
          />

          <QueuePanel
            branchId={branchId}
            devId={devId}
            rows={commandsQuery.data ?? []}
            loading={commandsQuery.isLoading}
          />
        </div>
      )}

      <PushPreviewDialog
        plan={plan}
        pending={push.isPending}
        onConfirm={handleConfirmPush}
        onOpenChange={(open) => {
          if (!open) setPlan(null);
        }}
      />
    </div>
  );
}

function ReconcileSection({
  title,
  hint,
  rows,
  emptyText,
  linkStudents = false,
  selection,
}: {
  title: string;
  hint: string;
  rows: ReconcileRow[];
  emptyText: string;
  linkStudents?: boolean;
  // When provided, the section is push-selectable (checkbox column).
  selection?: ReturnType<typeof useRowSelection>;
}) {
  const selectable = !!selection;
  const sectionIds = useMemo(
    () => rows.map((r) => r.student_id).filter((id): id is string => !!id),
    [rows],
  );
  const allSelected =
    selectable &&
    sectionIds.length > 0 &&
    sectionIds.every((id) => selection!.isSelected(id));

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <h3 className="text-sm font-semibold">{title}</h3>
        <Badge variant="secondary" className="text-[10px] tabular-nums">
          {rows.length}
        </Badge>
        <InfoHint text={hint} />
      </div>
      {rows.length === 0 ? (
        <p className="text-muted-foreground text-sm">{emptyText}</p>
      ) : (
        <div className="rounded-xl border ring-1 ring-foreground/10 overflow-hidden">
          <Table stickyHeader containerClassName="max-h-[50vh]">
            <TableHeader>
              <TableRow>
                {selectable && (
                  <TableHead className="w-10">
                    <input
                      type="checkbox"
                      aria-label={`Select all in ${title}`}
                      checked={allSelected}
                      onChange={() => selection!.toggleAll(sectionIds)}
                      className="h-4 w-4 accent-primary"
                    />
                  </TableHead>
                )}
                <TableHead className="w-32">User ID</TableHead>
                <TableHead>Name</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((r) => {
                const id = r.student_id;
                const checked = selectable && !!id && selection!.isSelected(id);
                return (
                  <TableRow key={r.vendor_user_id} data-state={checked ? "selected" : undefined}>
                    {selectable && (
                      <TableCell>
                        <input
                          type="checkbox"
                          aria-label={`Select ${r.name ?? r.vendor_user_id}`}
                          checked={checked}
                          disabled={!id}
                          onChange={() => id && selection!.toggle(id)}
                          className="h-4 w-4 accent-primary"
                        />
                      </TableCell>
                    )}
                    <TableCell className="tabular-nums text-sm">
                      {r.vendor_user_id}
                    </TableCell>
                    <TableCell>
                      {linkStudents && id ? (
                        <Link
                          href={`/students/${id}`}
                          className="font-medium hover:underline"
                        >
                          {r.name ?? "—"}
                        </Link>
                      ) : (
                        <span className={r.name ? "" : "text-muted-foreground"}>
                          {r.name ?? "—"}
                        </span>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}

const STATUS_TONE: Record<CommandStatus, string> = {
  pending: "bg-amber-500/15 text-amber-700 dark:text-amber-400",
  sent: "bg-blue-500/15 text-blue-700 dark:text-blue-400",
  confirmed: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
  failed: "bg-destructive/15 text-destructive",
  cancelled: "bg-muted text-muted-foreground",
};

function QueuePanel({
  branchId,
  devId,
  rows,
  loading,
}: {
  branchId: string;
  devId: string;
  rows: DeviceCommandRow[];
  loading: boolean;
}) {
  const toast = useToast();
  const cancel = useCancelCommand(branchId, devId);
  const [cancelingId, setCancelingId] = useState<string | null>(null);

  async function handleCancel(id: string) {
    setCancelingId(id);
    try {
      await cancel.mutateAsync(id);
    } catch (err) {
      toast.error(errorOf(err));
    } finally {
      setCancelingId(null);
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <h3 className="text-sm font-semibold">Command queue</h3>
        <Badge variant="secondary" className="text-[10px] tabular-nums">
          {rows.length}
        </Badge>
        <InfoHint
          text={
            <>
              Register commands waiting for the device. It drains them on its
              next contact: <b>pending</b> &rarr; <b>sent</b> &rarr;{" "}
              <b>confirmed</b> (or <b>failed</b>). A pending command can be
              cancelled; once sent, the device already has it.
            </>
          }
        />
      </div>
      {loading ? (
        <TableSkeleton rows={3} />
      ) : rows.length === 0 ? (
        <p className="text-muted-foreground text-sm">
          The queue is empty — nothing waiting for the device.
        </p>
      ) : (
        <div className="rounded-xl border ring-1 ring-foreground/10 overflow-hidden">
          <Table stickyHeader containerClassName="max-h-[50vh]">
            <TableHeader>
              <TableRow>
                <TableHead className="w-32">User ID</TableHead>
                <TableHead>Command</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right hidden sm:table-cell">
                  Attempts
                </TableHead>
                <TableHead className="w-20" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((c) => (
                <TableRow key={c.id}>
                  <TableCell className="tabular-nums text-sm">
                    {c.vendor_user_id ?? "—"}
                  </TableCell>
                  <TableCell className="text-sm">{c.command}</TableCell>
                  <TableCell>
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${STATUS_TONE[c.command_status]}`}
                    >
                      {c.command_status}
                    </span>
                    {c.command_status === "failed" && c.last_error && (
                      <span className="mt-0.5 block text-[11px] text-muted-foreground">
                        {c.last_error}
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="text-right tabular-nums text-sm text-muted-foreground hidden sm:table-cell">
                    {c.attempts}
                  </TableCell>
                  <TableCell className="text-right">
                    {c.command_status === "pending" && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleCancel(c.id)}
                        disabled={cancelingId === c.id}
                      >
                        Cancel
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}

function StatusPill({ enabled }: { enabled: boolean }) {
  return (
    <Badge
      variant={enabled ? "default" : "secondary"}
      className="text-[10px] uppercase tracking-wide"
    >
      {enabled ? "Provisioning on" : "Provisioning off"}
    </Badge>
  );
}

function Tile({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: number;
  tone?: "default" | "warn";
}) {
  const cls =
    tone === "warn" && value > 0
      ? "text-amber-600 dark:text-amber-400"
      : "text-foreground";
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className={`text-xl font-semibold tabular-nums ${cls}`}>{value}</span>
    </div>
  );
}
