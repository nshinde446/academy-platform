"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogTrigger,
  DialogPopup,
  DialogTitle,
  DialogDescription,
  DialogClose,
} from "@/components/ui/dialog";
import { apiErrorMessage } from "@/lib/api-error";
import {
  useProvisionDevices,
  useStaffProvisionDryRun,
  useStaffProvisionPush,
  type StaffProvisionPlanResponse,
  type StaffProvisionPushResponse,
} from "../_hooks/use-staff-provisioning";

interface PushToDeviceDialogProps {
  branchId: string;
  staffIds: string[];
}

export function PushToDeviceDialog({
  branchId,
  staffIds,
}: PushToDeviceDialogProps) {
  const [open, setOpen] = useState(false);
  const [devId, setDevId] = useState("");
  const [error, setError] = useState("");
  const [plan, setPlan] = useState<StaffProvisionPlanResponse | null>(null);
  const [pushed, setPushed] = useState<StaffProvisionPushResponse | null>(null);

  const devicesQuery = useProvisionDevices(open ? branchId : undefined);
  const dryRun = useStaffProvisionDryRun(devId || undefined);
  const push = useStaffProvisionPush(devId || undefined);

  const devices = devicesQuery.data?.devices ?? [];
  const enabled = devicesQuery.data?.enabled ?? false;

  function reset() {
    setDevId("");
    setError("");
    setPlan(null);
    setPushed(null);
  }

  async function preview() {
    if (!devId) return setError("Select a device.");
    setError("");
    setPushed(null);
    try {
      setPlan(await dryRun.mutateAsync(staffIds));
    } catch (err) {
      setError(apiErrorMessage(err, "Dry-run failed"));
    }
  }

  async function confirmPush() {
    if (!devId) return;
    setError("");
    try {
      setPushed(await push.mutateAsync(staffIds));
      setPlan(null);
    } catch (err) {
      setError(apiErrorMessage(err, "Push failed"));
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
      <DialogTrigger
        render={
          <Button variant="secondary" size="sm" onClick={() => setOpen(true)}>
            Push to device
          </Button>
        }
      />
      <DialogPopup>
        <DialogTitle>Push staff to device</DialogTitle>
        <DialogDescription>
          Registers the selected {staffIds.length} staff member(s) on a terminal
          (their 9xxxx code + name). Each person still enrols their face/finger
          once at the device — the push only pre-loads the identity.
        </DialogDescription>

        <div className="mt-4 flex flex-col gap-4">
          {error && <p className="text-sm text-destructive">{error}</p>}

          {devicesQuery.isLoading ? (
            <p className="text-sm text-muted-foreground">Loading devices…</p>
          ) : !enabled ? (
            <p className="text-sm text-muted-foreground">
              Device provisioning is dormant (BIOMAX_PROVISIONING_ENABLED is off).
              Nothing will be pushed until it&apos;s enabled.
            </p>
          ) : (
            <>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="pd_dev">Device</Label>
                <select
                  id="pd_dev"
                  value={devId}
                  onChange={(e) => {
                    setDevId(e.target.value);
                    setPlan(null);
                    setPushed(null);
                  }}
                  className="h-9 rounded-md border border-input bg-background px-3 text-sm"
                >
                  <option value="">Select terminal…</option>
                  {devices.map((d) => (
                    <option key={d.dev_id} value={d.dev_id}>
                      {d.dev_id}
                    </option>
                  ))}
                </select>
              </div>

              {plan && (
                <div className="rounded-lg border bg-muted/40 p-3 text-sm">
                  Preview: <span className="font-medium">{plan.to_create}</span> to
                  register, <span className="font-medium">{plan.to_update}</span>{" "}
                  to update, <span className="font-medium">{plan.skipped}</span>{" "}
                  skipped.
                  {plan.skipped > 0 && (
                    <ul className="mt-2 list-disc pl-5 text-xs text-muted-foreground">
                      {plan.commands
                        .filter((c) => c.action === "skipped")
                        .slice(0, 8)
                        .map((c) => (
                          <li key={c.staff_id}>
                            {c.name ?? c.staff_id}: {c.reason}
                          </li>
                        ))}
                    </ul>
                  )}
                </div>
              )}

              {pushed && (
                <div className="rounded-lg border bg-muted/40 p-3 text-sm">
                  Queued <span className="font-medium">{pushed.enqueued}</span>{" "}
                  registration(s) for {pushed.dev_id} ·{" "}
                  <span className="font-medium">{pushed.skipped}</span> skipped.
                  They&apos;ll register on the terminal; face/finger enrolment is
                  the next physical step.
                </div>
              )}
            </>
          )}

          <div className="flex justify-end gap-2">
            <DialogClose
              render={
                <Button variant="outline" type="button">
                  {pushed ? "Close" : "Cancel"}
                </Button>
              }
            />
            {enabled && !pushed && (
              <>
                <Button
                  type="button"
                  variant="outline"
                  disabled={!devId || dryRun.isPending}
                  onClick={preview}
                >
                  {dryRun.isPending ? "Checking…" : "Preview"}
                </Button>
                <Button
                  type="button"
                  disabled={!devId || push.isPending}
                  onClick={confirmPush}
                >
                  {push.isPending ? "Pushing…" : "Push"}
                </Button>
              </>
            )}
          </div>
        </div>
      </DialogPopup>
    </Dialog>
  );
}
