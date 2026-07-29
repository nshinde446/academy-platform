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
import { Card, CardContent } from "@/components/ui/card";
import { InfoHint } from "@/components/ui/info-hint";
import { TableSkeleton } from "@/components/ui/skeleton";
import { useProvisionDevices, useReconcile } from "../_hooks/use-provisioning";
import type { ReconcileRow } from "../_schemas/provisioning";

const CONTROL_CLASS =
  "h-9 rounded-lg border border-input bg-background px-3 text-sm";

interface DeviceSyncProps {
  branchId: string | undefined;
}

// Read-only reconciliation between platform students and the BioMax device's
// own user table (mirrored from its realtime_enroll_data pushes). Three groups:
// who still needs pushing, who's on the device but not the platform, and whose
// name drifted. The actual push (SET_USER_INFO) is a separate, gated increment —
// this view never writes to the device.
export function DeviceSync({ branchId }: DeviceSyncProps) {
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
                onChange={(e) => setSelectedDevId(e.target.value)}
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
                    number. This is a read-only view — pushing students onto the
                    device is a separate step. Enrollment mirroring only runs when
                    provisioning is enabled, so until then the device side reads
                    empty by design.
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
            <div className="grid grid-cols-3 gap-3">
              <Tile
                label="Need pushing"
                value={data.on_platform_not_on_device.length}
                tone="warn"
              />
              <Tile
                label="Only on device"
                value={data.on_device_not_on_platform.length}
              />
              <Tile label="Name drift" value={data.drift.length} tone="warn" />
            </div>
          </CardContent>
        </Card>
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
            title="On the platform, not on the device"
            hint="Students who have a valid device userId (roll number) but aren't in the device's user table yet — the set a push would register."
            rows={data.on_platform_not_on_device}
            emptyText="Every student with a device userId is already on the device."
            linkStudents
          />
          <ReconcileSection
            title="On the device, not on the platform"
            hint="Users enrolled on the device with no matching student here — a stale entry, a manual enrollment, or a roll number that doesn't exist on the platform."
            rows={data.on_device_not_on_platform}
            emptyText="No device users are unaccounted for."
          />
          <ReconcileSection
            title="Name drift"
            hint="Present on both, but the name on the device differs from the platform — a re-push would correct it."
            rows={data.drift}
            emptyText="No name mismatches."
            linkStudents
          />
        </div>
      )}
    </div>
  );
}

function ReconcileSection({
  title,
  hint,
  rows,
  emptyText,
  linkStudents = false,
}: {
  title: string;
  hint: string;
  rows: ReconcileRow[];
  emptyText: string;
  linkStudents?: boolean;
}) {
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
                <TableHead className="w-32">User ID</TableHead>
                <TableHead>Name</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((r) => (
                <TableRow key={r.vendor_user_id}>
                  <TableCell className="tabular-nums text-sm">
                    {r.vendor_user_id}
                  </TableCell>
                  <TableCell>
                    {linkStudents && r.student_id ? (
                      <Link
                        href={`/students/${r.student_id}`}
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
