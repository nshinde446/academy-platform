"use client";

import { useMemo, useState } from "react";
import { useUserStore } from "@/store/user-store";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useToast } from "@/components/ui/toast";
import { PageHeader } from "@/components/layout/page-header";
import {
  useEtoPull,
  useEtoStatus,
  type EtoPullResult,
} from "./_hooks/use-integrations";

const SELECT_CLASS =
  "h-9 rounded-lg border border-input bg-background px-3 text-sm";

function localISO(d: Date): string {
  const off = d.getTimezoneOffset();
  return new Date(d.getTime() - off * 60000).toISOString().slice(0, 10);
}
function todayISO(): string {
  return localISO(new Date());
}
function monthStartISO(): string {
  const d = new Date();
  return localISO(new Date(d.getFullYear(), d.getMonth(), 1));
}

function errorOf(err: unknown): string {
  const e = err as {
    response?: { data?: { error?: { message?: string }; detail?: string } };
  };
  return (
    e?.response?.data?.error?.message ||
    e?.response?.data?.detail ||
    "Request failed"
  );
}

export default function IntegrationsPage() {
  const user = useUserStore((s) => s.user);
  const branchId = user?.branch_roles?.[0]?.branch_id;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Integrations"
        description="Connect the academy's biometric attendance devices. Punches from either source flow into the same day-attendance engine — register, timelines and reports update automatically."
      />

      <EtimeOfficeCard branchId={branchId} />
      <BiomaxCard branchId={branchId} />
    </div>
  );
}

// ── eTimeOffice (cloud pull) ────────────────────────────────────────────────

function EtimeOfficeCard({ branchId }: { branchId: string | undefined }) {
  const statusQuery = useEtoStatus();
  const pull = useEtoPull(branchId);
  const toast = useToast();

  const [start, setStart] = useState(monthStartISO());
  const [end, setEnd] = useState(todayISO());
  const [result, setResult] = useState<EtoPullResult | null>(null);

  const status = statusQuery.data;

  async function handlePull() {
    setResult(null);
    try {
      const res = await pull.mutateAsync({ start, end });
      setResult(res);
      toast.success(
        `Pulled ${res.rows} row(s) — ${res.inserted} new punch(es), ${res.days_rebuilt} day(s) updated.`,
      );
    } catch (err) {
      toast.error(errorOf(err));
    }
  }

  return (
    <Card>
      <CardContent>
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-2">
                <span className="text-base font-semibold">
                  eTimeOffice / TeamOffice
                </span>
                <span className="rounded border border-border px-1.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                  Cloud · Pull
                </span>
              </div>
              <p className="text-sm text-muted-foreground max-w-xl">
                Hosted SaaS — punches live in their cloud. We poll their API on a
                schedule and import new punches. Use the button below to pull a
                date range on demand.
              </p>
            </div>
            <StatusBadges status={status} />
          </div>

          <div className="flex flex-wrap items-end gap-3">
            <label className="flex flex-col gap-1 text-xs text-muted-foreground">
              From
              <input
                type="date"
                value={start}
                max={end}
                onChange={(e) => setStart(e.target.value)}
                className={SELECT_CLASS}
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-muted-foreground">
              To
              <input
                type="date"
                value={end}
                min={start}
                onChange={(e) => setEnd(e.target.value)}
                className={SELECT_CLASS}
              />
            </label>
            <Button
              type="button"
              disabled={!status?.enabled || pull.isPending}
              onClick={handlePull}
            >
              {pull.isPending ? "Pulling…" : "Pull now"}
            </Button>
          </div>

          {!status?.enabled && (
            <p className="text-xs text-amber-600 dark:text-amber-500">
              Disabled. Set <code>ETO_ENABLED=true</code> plus{" "}
              <code>ETO_CORP_ID</code>, <code>ETO_USERNAME</code>,{" "}
              <code>ETO_PASSWORD</code> and <code>ETO_BRANCH_ID</code> on the
              backend to activate.
            </p>
          )}

          {result && (
            <div className="grid grid-cols-2 gap-3 rounded-lg border bg-muted/40 p-3 sm:grid-cols-4">
              <Stat label="Rows" value={result.rows} />
              <Stat label="New punches" value={result.inserted} />
              <Stat label="Duplicates" value={result.skipped_duplicate} />
              <Stat label="Days updated" value={result.days_rebuilt} />
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function StatusBadges({
  status,
}: {
  status:
    | { enabled: boolean; configured: boolean }
    | undefined;
}) {
  if (!status) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      <Badge variant={status.enabled ? "success" : "secondary"}>
        {status.enabled ? "Enabled" : "Disabled"}
      </Badge>
      <Badge variant={status.configured ? "success" : "destructive"}>
        {status.configured ? "Credentials set" : "Not configured"}
      </Badge>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-lg font-semibold tabular-nums">{value}</span>
    </div>
  );
}

// ── BioMax SmartOffice (on-prem push) ───────────────────────────────────────

function BiomaxCard({ branchId }: { branchId: string | undefined }) {
  const toast = useToast();
  const pushUrl = useMemo(() => {
    if (typeof window === "undefined") return "/iclock/cdata";
    return `${window.location.origin}/iclock/cdata`;
  }, []);

  async function copy() {
    try {
      await navigator.clipboard.writeText(pushUrl);
      toast.success("Push URL copied.");
    } catch {
      toast.error("Couldn't copy — select and copy manually.");
    }
  }

  return (
    <Card>
      <CardContent>
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-2">
              <span className="text-base font-semibold">BioMax SmartOffice</span>
              <span className="rounded border border-border px-1.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                On-prem · Push
              </span>
            </div>
            <p className="text-sm text-muted-foreground max-w-xl">
              On-site devices push punches in real time over the ZKTeco/ADMS
              protocol. Point each device&apos;s server/cloud setting at the URL
              below; punches arrive automatically — no polling.
            </p>
          </div>

          <div className="flex flex-col gap-1">
            <span className="text-xs text-muted-foreground">
              Device server URL
            </span>
            <div className="flex flex-wrap items-center gap-2">
              <code className="rounded-lg border bg-muted/40 px-3 py-1.5 text-sm break-all">
                {pushUrl}
              </code>
              <Button type="button" variant="outline" size="sm" onClick={copy}>
                Copy
              </Button>
            </div>
          </div>

          <ol className="flex flex-col gap-1.5 text-sm text-muted-foreground list-decimal pl-5">
            <li>
              On the device (or SmartOffice → Device → Cloud/ADMS), set the
              server address/path to the URL above and enable real-time push.
            </li>
            <li>
              Allowlist each device serial on the backend via{" "}
              <code>BIOMAX_DEVICE_SERIALS</code> (comma-separated) and set{" "}
              <code>BIOMAX_BRANCH_ID</code>.
            </li>
            <li>
              Enroll each student&apos;s device user id as their{" "}
              <code>rfid_number</code> so punches resolve to the right student.
            </li>
          </ol>

          {!branchId && (
            <p className="text-xs text-amber-600 dark:text-amber-500">
              No branch resolved for your account — punches need a branch to land
              against.
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
