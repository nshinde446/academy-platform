"use client";

import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { TableSkeleton } from "@/components/ui/skeleton";
import { useUserStore } from "@/store/user-store";
import { useDevMonitoring, type Alert } from "./_hooks/use-monitoring";

function fmtBytes(n: number | null | undefined): string {
  if (n == null) return "—";
  if (n < 1024) return `${n} B`;
  const u = ["KB", "MB", "GB", "TB"];
  let v = n / 1024;
  let i = 0;
  while (v >= 1024 && i < u.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toFixed(1)} ${u[i]}`;
}

function fmtTime(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

function ago(iso: string | null): string {
  if (!iso) return "never";
  const secs = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (secs < 3600) return `${Math.round(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.round(secs / 3600)}h ago`;
  return `${Math.round(secs / 86400)}d ago`;
}

export default function DevMonitoringPage() {
  const user = useUserStore((s) => s.user);
  const query = useDevMonitoring();
  const data = query.data;

  // Client-side guard (server enforces via email allowlist regardless).
  if (user && user.is_developer === false) {
    return (
      <p className="text-sm text-muted-foreground">
        This page is available to developers only.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Developer Monitoring"
        description="Whole-institute health — device connectivity, attendance freshness, backups, database, and live alerts. Visible to developers only; refreshes every minute."
      />

      {query.isLoading ? (
        <TableSkeleton rows={6} />
      ) : query.isError ? (
        <p className="text-sm text-destructive">
          Failed to load monitoring (developer access required).
        </p>
      ) : !data ? null : (
        <>
          <AlertsPanel alerts={data.alerts} />

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {/* Devices */}
            <Card>
              <CardContent>
                <h2 className="mb-3 text-sm font-semibold">Biometric devices</h2>
                {data.devices.length === 0 ? (
                  <p className="text-xs text-muted-foreground">No devices reporting.</p>
                ) : (
                  <div className="flex flex-col gap-3">
                    {data.devices.map((d) => {
                      const silent = d.silent_hours != null && d.silent_hours > 6;
                      return (
                        <div key={d.dev_id} className="flex flex-col gap-0.5">
                          <div className="flex items-center gap-2">
                            <span
                              className={`h-2 w-2 rounded-full ${silent ? "bg-destructive" : "bg-emerald-500"}`}
                            />
                            <span className="text-sm font-medium">{d.dev_id}</span>
                            <span className="text-xs text-muted-foreground">
                              last seen {ago(d.last_seen_at)}
                            </span>
                          </div>
                          <span className="pl-4 text-xs text-muted-foreground tabular-nums">
                            {d.user_count ?? "—"} users · {d.face_count ?? "—"} faces
                          </span>
                        </div>
                      );
                    })}
                  </div>
                )}
                <div className="mt-3 border-t pt-3 text-xs text-muted-foreground">
                  Last punch: <span className="text-foreground">{ago(data.attendance.last_punch_at)}</span>
                  {" · "}today: <span className="tabular-nums text-foreground">{data.attendance.punches_today}</span>
                </div>
              </CardContent>
            </Card>

            {/* Backups */}
            <Card>
              <CardContent>
                <h2 className="mb-3 text-sm font-semibold">Backups</h2>
                {!data.backup ? (
                  <p className="text-sm text-destructive">No backup has run yet.</p>
                ) : (
                  <div className="flex flex-col gap-1 text-sm">
                    <div className="flex items-center gap-2">
                      <Badge variant={data.backup.status === "ok" ? "success" : "destructive"}>
                        {data.backup.status}
                      </Badge>
                      <span className="text-muted-foreground">
                        {ago(data.backup.created_at)} ({fmtTime(data.backup.created_at)})
                      </span>
                    </div>
                    <span className="text-muted-foreground">
                      Size: <span className="text-foreground">{fmtBytes(data.backup.size_bytes)}</span>
                    </span>
                    <span className="text-muted-foreground">
                      Off-box:{" "}
                      <Badge
                        variant={
                          data.backup.offbox === "ok"
                            ? "success"
                            : data.backup.offbox === "failed"
                              ? "destructive"
                              : "secondary"
                        }
                      >
                        {data.backup.offbox}
                      </Badge>
                    </span>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Database + system */}
            <Card>
              <CardContent>
                <h2 className="mb-3 text-sm font-semibold">Database</h2>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <Metric label="DB size" value={fmtBytes(data.system.db_size_bytes)} />
                  <Metric label="Connections" value={String(data.system.connections ?? "—")} />
                  {Object.entries(data.system.counts).map(([k, v]) => (
                    <Metric key={k} label={k.replace(/_/g, " ")} value={String(v)} />
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Command queue */}
            <Card>
              <CardContent>
                <h2 className="mb-3 text-sm font-semibold">Device command queue</h2>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <Metric label="pending" value={String(data.queue.pending)} />
                  <Metric label="in-flight (sent)" value={String(data.queue.sent)} />
                </div>
                <p className="mt-2 text-xs text-muted-foreground">
                  Drains when the device polls; the daily job keeps it bounded.
                </p>
              </CardContent>
            </Card>
          </div>

          <p className="text-xs text-muted-foreground">
            Snapshot generated {fmtTime(data.generated_at)} · auto-refreshes every minute.
          </p>
        </>
      )}
    </div>
  );
}

function AlertsPanel({ alerts }: { alerts: Alert[] }) {
  if (alerts.length === 0) {
    return (
      <Card size="sm">
        <CardContent>
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-emerald-500" />
            <span className="text-sm font-medium">All clear — no active alerts.</span>
          </div>
        </CardContent>
      </Card>
    );
  }
  return (
    <Card size="sm">
      <CardContent>
        <h2 className="mb-2 text-sm font-semibold">
          Active alerts ({alerts.length})
        </h2>
        <div className="flex flex-col gap-2">
          {alerts.map((a, i) => (
            <div key={i} className="flex items-start gap-2 text-sm">
              <Badge variant={a.level === "critical" ? "destructive" : "secondary"}>
                {a.level}
              </Badge>
              <span>
                <span className="font-medium">{a.area}</span> — {a.message}
              </span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs text-muted-foreground capitalize">{label}</span>
      <span className="text-lg font-semibold tabular-nums">{value}</span>
    </div>
  );
}
