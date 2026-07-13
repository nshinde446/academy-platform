"use client";

import { useMemo, useState } from "react";
import { useUserStore } from "@/store/user-store";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useToast } from "@/components/ui/toast";
import { PageHeader } from "@/components/layout/page-header";
import {
  useSmartOfficePull,
  useSmartOfficeStatus,
  type SmartOfficePullResult,
  type SmartOfficeStatus,
} from "./_hooks/use-integrations";

const SELECT_CLASS =
  "h-9 rounded-lg border border-input bg-background px-3 text-sm";

// Runbook for wiring a device (direct /iclock push, SmartOffice agent, env vars).
const SETUP_GUIDE_URL =
  "https://github.com/nshinde446/academy-platform/blob/master/docs/biomax-direct-push-setup.md";

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
        description="Connect the academy's BioMax SmartOffice biometric attendance. Punches flow into the day-attendance engine — register, timelines and reports update automatically."
      />

      <BiomaxCard branchId={branchId} />
    </div>
  );
}

// ── BioMax SmartOffice ──────────────────────────────────────────────────────

function BiomaxCard({ branchId }: { branchId: string | undefined }) {
  const statusQuery = useSmartOfficeStatus();
  const pull = useSmartOfficePull(branchId);
  const toast = useToast();

  const [start, setStart] = useState(monthStartISO());
  const [end, setEnd] = useState(todayISO());
  const [result, setResult] = useState<SmartOfficePullResult | null>(null);

  const status = statusQuery.data;

  const origin = useMemo(
    () => (typeof window === "undefined" ? "" : window.location.origin),
    [],
  );
  const agentUrl = `${origin}/api/v1/attendance/smartoffice/ingest`;
  const deviceUrl = `${origin}/iclock/cdata`;

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
        <div className="flex flex-col gap-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-2">
                <span className="text-base font-semibold">
                  BioMax SmartOffice
                </span>
                <span className="rounded border border-border px-1.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                  On-prem
                </span>
              </div>
              <p className="text-sm text-muted-foreground max-w-xl">
                SmartOffice runs on the institute PC and stores punches in its SQL
                database. A small on-prem agent reads new punches and pushes them
                here in near real time — no polling, no ports to open.
              </p>
              <a
                href={SETUP_GUIDE_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="w-fit text-sm text-primary underline underline-offset-2 hover:no-underline"
              >
                Device setup guide ↗
              </a>
            </div>
            <StatusBadges status={status} />
          </div>

          {/* Primary: on-prem agent push */}
          <CopyRow
            label="Agent ingest URL (point the on-prem agent's backend.url here)"
            value={agentUrl}
          />

          <ol className="flex flex-col gap-1.5 text-sm text-muted-foreground list-decimal pl-5">
            <li>
              Ask the provider for a read-only SQL login and the punch table/view
              name, then install the agent (<code>agent/smartoffice</code>) on the
              SmartOffice PC and fill in <code>agent.ini</code>.
            </li>
            <li>
              Set a shared secret <code>SMARTOFFICE_INGEST_TOKEN</code> on the
              backend and the same value as <code>token</code> in{" "}
              <code>agent.ini</code>; set <code>SMARTOFFICE_BRANCH_ID</code>.
            </li>
            <li>
              Enroll each student&apos;s SmartOffice <code>EmployeeCode</code> as
              their <code>rfid_number</code> so punches resolve to the right
              student.
            </li>
          </ol>

          {/* Alternative: direct device push (ADMS) */}
          <div className="rounded-lg border border-dashed border-border p-3">
            <p className="text-xs font-medium text-muted-foreground">
              Alternative — direct device push (ZKTeco/ADMS)
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              If devices can push directly instead of via SmartOffice, point each
              device&apos;s server/cloud setting at the URL below and set{" "}
              <code>BIOMAX_DEVICE_SERIALS</code> + <code>BIOMAX_BRANCH_ID</code>.
            </p>
            <div className="mt-2">
              <CopyRow label="Device server URL" value={deviceUrl} />
            </div>
          </div>

          {/* Manual cloud-pull test (SmartOffice REST API) */}
          <div className="flex flex-col gap-2 border-t pt-4">
            <span className="text-xs font-medium text-muted-foreground">
              Test cloud pull (SmartOffice REST API)
            </span>
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
                Cloud pull disabled. The on-prem agent works without it; to use the
                REST API instead, set <code>SMARTOFFICE_ENABLED=true</code> plus{" "}
                <code>SMARTOFFICE_BASE_URL</code>, <code>SMARTOFFICE_API_KEY</code>{" "}
                and <code>SMARTOFFICE_BRANCH_ID</code> on the backend.
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

function CopyRow({ label, value }: { label: string; value: string }) {
  const toast = useToast();
  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      toast.success("Copied.");
    } catch {
      toast.error("Couldn't copy — select and copy manually.");
    }
  }
  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs text-muted-foreground">{label}</span>
      <div className="flex flex-wrap items-center gap-2">
        <code className="rounded-lg border bg-muted/40 px-3 py-1.5 text-sm break-all">
          {value}
        </code>
        <Button type="button" variant="outline" size="sm" onClick={copy}>
          Copy
        </Button>
      </div>
    </div>
  );
}

function StatusBadges({ status }: { status: SmartOfficeStatus | undefined }) {
  if (!status) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      <Badge variant={status.enabled ? "success" : "secondary"}>
        {status.enabled ? "Cloud pull on" : "Cloud pull off"}
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
