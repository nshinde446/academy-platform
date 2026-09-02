"use client";

import { useEffect, useMemo, useState } from "react";
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
  useInstituteReconcile,
  useProvisionDevices,
  useProvisionDryRun,
  useProvisionPush,
} from "../_hooks/use-provisioning";
import type {
  CommandStatus,
  DeviceCommandRow,
  MachineLiveStatus,
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

// Institute-wide enrollment status across ALL terminals, each student counted
// ONCE (a face on either machine = enrolled, never double-counted per device).
// Read side: face-enrolled (count) + the actionable buckets — awaiting face /
// not pushed / name drift / on-device-not-on-platform. Write side: pick students
// that need registering, choose the target machine, preview (dry-run), confirm;
// the command lands in that machine's outbound queue. Nothing emits directly —
// the device drains the queue on its next contact.
export function DeviceSync({ branchId }: DeviceSyncProps) {
  const toast = useToast();
  const devicesQuery = useProvisionDevices(branchId);
  const enabled = devicesQuery.data?.enabled ?? false;

  const reconcileQuery = useInstituteReconcile(branchId, enabled);
  const data = reconcileQuery.data;
  const machines = useMemo(() => data?.machines ?? [], [data]);

  // A single machine selector drives BOTH the push target and which queue you
  // watch — the roster/status above is device-independent, so this never
  // duplicates the student data, it just picks where a write lands.
  const [selectedDevId, setSelectedDevId] = useState("");
  const targetDevId = selectedDevId || machines[0]?.dev_id || "";

  const commandsQuery = useDeviceCommands(
    branchId,
    targetDevId || undefined,
    enabled,
  );

  // One selection model spanning both push-eligible groups (not-pushed + drift).
  // Device-only rows can't be pushed — no platform student behind them.
  const selection = useRowSelection();

  const dryRun = useProvisionDryRun(targetDevId || undefined);
  const push = useProvisionPush(branchId, targetDevId || undefined);
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
      {/* Status pill + what this screen is */}
      <Card size="sm">
        <CardContent>
          <div className="flex items-center gap-1">
            <StatusPill enabled={enabled} />
            <InfoHint
              text={
                <>
                  Institute-wide enrollment across{" "}
                  <em>every</em> terminal, each student counted once — a face on
                  either machine means enrolled, so the same student is never
                  shown twice. Matching is by device <em>userId</em> (the
                  student&apos;s roll number). Each machine&apos;s own live counts
                  appear as a small health strip. Pushing queues a register
                  command onto the chosen machine; it applies on the next
                  contact. Everything is dormant until{" "}
                  <code>BIOMAX_PROVISIONING_ENABLED</code> is set.
                </>
              }
            />
          </div>
        </CardContent>
      </Card>

      {/* Per-machine live health strip (each terminal's own self-report) */}
      {enabled && machines.length > 0 && <MachinesStrip machines={machines} />}

      {/* Institute summary — each student counted once */}
      {enabled && data && (
        <Card size="sm">
          <CardContent>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
              <Tile label="Students" value={data.total_students} />
              <Tile label="Face enrolled" value={data.face_enrolled} tone="ok" />
              <Tile label="Awaiting face" value={data.awaiting_face.length} />
              <Tile
                label="Not pushed"
                value={data.not_pushed.length}
                tone="warn"
              />
              <Tile
                label="Name drift"
                value={data.name_drift.length}
                tone="warn"
              />
            </div>
          </CardContent>
        </Card>
      )}

      {/* Push action bar — explicit selection + explicit target machine */}
      {enabled && selection.count > 0 && (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-primary/30 bg-primary/5 px-3 py-2">
          <span className="text-sm font-medium">
            {selection.count} student{selection.count === 1 ? "" : "s"} selected
          </span>
          <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
            Target machine
            <select
              value={targetDevId}
              onChange={(e) => setSelectedDevId(e.target.value)}
              className={CONTROL_CLASS}
              aria-label="Target machine for push"
            >
              {machines.map((m) => (
                <option key={m.dev_id} value={m.dev_id}>
                  {m.dev_id}
                </option>
              ))}
            </select>
          </label>
          <Button
            size="sm"
            onClick={handlePreview}
            disabled={!targetDevId || dryRun.isPending || push.isPending}
          >
            {dryRun.isPending ? "Preparing…" : "Push to machine…"}
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
          Failed to load institute enrollment status.
        </p>
      ) : !data ? null : (
        <div className="flex flex-col gap-6">
          <ReconcileSection
            title="Not pushed (no identity on any machine)"
            hint="Students with a valid device userId (roll number) not confirmed onto ANY terminal — select, choose a target machine, and push to register their identity."
            rows={data.not_pushed}
            emptyText="Every student's identity has been pushed to a machine."
            linkStudents
            selection={selection}
          />
          <ReconcileSection
            title="Awaiting face enrollment"
            hint="Identity pushed and confirmed on a machine, but no face is enrolled yet (the device hasn't mirrored them back with a face). The next step is enrolling their face at a terminal, NOT another push."
            rows={data.awaiting_face}
            emptyText="No students are waiting on a face enrollment."
            linkStudents
          />
          <ReconcileSection
            title="Name drift"
            hint="Enrolled, but a machine's stored name differs from the platform — pushing re-registers with the platform name."
            rows={data.name_drift}
            emptyText="No name mismatches."
            linkStudents
            selection={selection}
          />
          <ReconcileSection
            title="On a machine, not on the platform"
            hint="Users on a terminal with no matching student here — a stale entry, a manual enrollment, or a roll number that doesn't exist on the platform. Not pushable from here."
            rows={data.on_device_not_on_platform}
            emptyText="No device users are unaccounted for."
          />

          {targetDevId && (
            <QueuePanel
              branchId={branchId}
              devId={targetDevId}
              machines={machines}
              onDevIdChange={setSelectedDevId}
              rows={commandsQuery.data ?? []}
              loading={commandsQuery.isLoading}
            />
          )}
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

// Friendly names for the raw device command codes — the wire codes (e.g.
// GET_USER_INFO) are opaque to staff. Unknown codes fall back to the raw value.
const COMMAND_LABEL: Record<string, string> = {
  GET_USER_INFO: "Refresh face status",
  SET_USER_INFO: "Register / update user",
};

function commandLabel(command: string): string {
  return COMMAND_LABEL[command] ?? command;
}

// What to show in the "User ID" column. User-scoped commands show the id; batch
// commands (no vendor_user_id) show how many users they cover instead of "—".
function commandTarget(row: DeviceCommandRow): string {
  if (row.vendor_user_id) return row.vendor_user_id;
  if (row.batch_user_count != null) {
    return `batch · ${row.batch_user_count} user${row.batch_user_count === 1 ? "" : "s"}`;
  }
  return "—";
}

function QueuePanel({
  branchId,
  devId,
  machines,
  onDevIdChange,
  rows,
  loading,
}: {
  branchId: string;
  devId: string;
  machines: MachineLiveStatus[];
  onDevIdChange: (devId: string) => void;
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
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-sm font-semibold">Command queue</h3>
        <Badge variant="secondary" className="text-[10px] tabular-nums">
          {rows.length}
        </Badge>
        <InfoHint
          text={
            <>
              Register commands waiting for the selected machine. It drains them
              on its next contact: <b>pending</b> &rarr; <b>sent</b> &rarr;{" "}
              <b>confirmed</b> (or <b>failed</b>). A pending command can be
              cancelled; once sent, the device already has it.
            </>
          }
        />
        {machines.length > 1 && (
          <select
            value={devId}
            onChange={(e) => onDevIdChange(e.target.value)}
            className={`${CONTROL_CLASS} ml-auto h-8`}
            aria-label="Queue for machine"
          >
            {machines.map((m) => (
              <option key={m.dev_id} value={m.dev_id}>
                {m.dev_id}
              </option>
            ))}
          </select>
        )}
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
                    {c.vendor_user_id ? (
                      c.vendor_user_id
                    ) : c.batch_user_count != null ? (
                      <span className="text-muted-foreground">
                        {commandTarget(c)}
                      </span>
                    ) : (
                      "—"
                    )}
                  </TableCell>
                  <TableCell className="text-sm">
                    {commandLabel(c.command)}
                  </TableCell>
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

function relTime(secs: number): string {
  if (secs < 60) return `${secs}s ago`;
  if (secs < 3600) return `${Math.round(secs / 60)}m ago`;
  return `${Math.round(secs / 3600)}h ago`;
}

function LiveTile({ label, value }: { label: string; value: number | null | undefined }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-xl font-semibold tabular-nums">{value ?? "—"}</span>
    </div>
  );
}

// Each terminal's OWN live counts, reported on every poll — a real-time view of
// what's physically on each machine (and its heartbeat), shown once per machine.
// This is the ground truth the device reports about itself, distinct from the
// platform-side reconcile above.
function MachinesStrip({ machines }: { machines: MachineLiveStatus[] }) {
  // Tick a "now" from an effect so heartbeats stay fresh without an impure
  // Date.now() during render (react-hooks purity rule).
  const [now, setNow] = useState(0);
  useEffect(() => {
    setNow(Date.now());
    const t = setInterval(() => setNow(Date.now()), 10_000);
    return () => clearInterval(t);
  }, []);

  return (
    <Card size="sm">
      <CardContent>
        <div className="flex flex-col gap-3">
          {machines.map((m) => {
            const seen = m.last_seen_at ? new Date(m.last_seen_at) : null;
            const secsAgo =
              seen && now
                ? Math.max(0, Math.round((now - seen.getTime()) / 1000))
                : null;
            const online = secsAgo != null && secsAgo < 120; // polls every ~20–30s
            return (
              <div
                key={m.dev_id}
                className="flex flex-wrap items-center gap-x-8 gap-y-2"
              >
                <div className="flex min-w-[13rem] items-center gap-2">
                  <span
                    className={`h-2 w-2 rounded-full ${online ? "bg-emerald-500" : "bg-muted-foreground/40"}`}
                  />
                  <div className="flex flex-col leading-tight">
                    <span className="font-mono text-xs">{m.dev_id}</span>
                    <span className="text-[11px] text-muted-foreground">
                      {seen
                        ? online
                          ? "on device — live"
                          : `last seen ${relTime(secsAgo!)}`
                        : "waiting for the device to report…"}
                    </span>
                  </div>
                </div>
                <LiveTile label="Users on device" value={m.user_count} />
                <LiveTile label="Faces enrolled" value={m.face_count} />
                <LiveTile label="Fingerprints" value={m.fp_count} />
                {m.firmware && (
                  <span className="text-[11px] text-muted-foreground">
                    fw {m.firmware}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
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
  tone?: "default" | "warn" | "ok";
}) {
  const cls =
    tone === "warn" && value > 0
      ? "text-amber-600 dark:text-amber-400"
      : tone === "ok" && value > 0
        ? "text-emerald-600 dark:text-emerald-400"
        : "text-foreground";
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className={`text-xl font-semibold tabular-nums ${cls}`}>{value}</span>
    </div>
  );
}
