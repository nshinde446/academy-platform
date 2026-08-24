"use client";

import { useMemo, useState } from "react";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { useBranchId } from "@/store/user-store";
import { useAdminUsers } from "../users/_hooks/use-users";
import { useBatches } from "../batches/_hooks/use-batches";
import {
  useAccountsGrants,
  useCoordinatorBatches,
  useCreateGrant,
  useRevokeGrant,
  useSetCoordinatorBatches,
} from "./_hooks/use-access-control";

const CONTROL = "h-9 rounded-lg border border-input bg-background px-3 text-sm";

function apiError(err: unknown): string {
  const e = err as { response?: { data?: { detail?: string } } };
  return e?.response?.data?.detail ?? "Action failed";
}

export default function AccessControlPage() {
  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Access Control"
        description="Assign which batches each Floor Coordinator can act on, and grant Accounts users attendance visibility (optionally time-limited)."
      />
      <CoordinatorSection />
      <AccountsGrantSection />
    </div>
  );
}

// ── Floor Coordinator → batch assignment ─────────────────────────────────────

function CoordinatorSection() {
  const toast = useToast();
  const { branchId } = useBranchId();
  const usersQuery = useAdminUsers(true);
  const batchesQuery = useBatches(branchId);

  const coordinators = useMemo(
    () =>
      (usersQuery.data ?? []).filter((u) =>
        u.roles.includes("floor_coordinator"),
      ),
    [usersQuery.data],
  );

  const [userId, setUserId] = useState("");
  const assigned = useCoordinatorBatches(userId || undefined);
  const save = useSetCoordinatorBatches(userId || undefined);

  const [checked, setChecked] = useState<Set<string> | null>(null);
  // Derive the working set from the server data until the user edits it.
  const working =
    checked ?? new Set((assigned.data?.batches ?? []).map((b) => b.id));

  function toggle(id: string) {
    const next = new Set(working);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setChecked(next);
  }

  async function onSave() {
    try {
      await save.mutateAsync([...working]);
      setChecked(null);
      toast.success("Coordinator batches updated");
    } catch (err) {
      toast.error(apiError(err));
    }
  }

  return (
    <Card>
      <CardContent>
        <h2 className="mb-3 text-lg font-semibold">Floor Coordinators</h2>
        <label className="flex max-w-sm flex-col gap-1 text-xs text-muted-foreground">
          Coordinator
          <select
            value={userId}
            onChange={(e) => {
              setUserId(e.target.value);
              setChecked(null);
            }}
            className={CONTROL}
          >
            <option value="">Select a coordinator…</option>
            {coordinators.map((u) => (
              <option key={u.id} value={u.id}>
                {u.first_name} {u.last_name}
              </option>
            ))}
          </select>
        </label>

        {coordinators.length === 0 && (
          <p className="mt-2 text-xs text-muted-foreground">
            No users have the Floor Coordinator role yet — assign it in Users
            first.
          </p>
        )}

        {userId && (
          <div className="mt-4 flex flex-col gap-3">
            <p className="text-xs text-muted-foreground">
              Assigned batches — the coordinator can only act on these.
            </p>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {(batchesQuery.data ?? []).map((b) => (
                <label
                  key={b.id}
                  className="flex items-center gap-2 rounded-lg border px-3 py-2 text-sm"
                >
                  <input
                    type="checkbox"
                    checked={working.has(b.id)}
                    onChange={() => toggle(b.id)}
                  />
                  <span className="truncate">{b.name}</span>
                </label>
              ))}
            </div>
            <div>
              <Button
                size="sm"
                onClick={onSave}
                disabled={save.isPending || checked === null}
              >
                Save assignments
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ── Accounts attendance grants ───────────────────────────────────────────────

function AccountsGrantSection() {
  const toast = useToast();
  const { branchId } = useBranchId();
  const usersQuery = useAdminUsers(true);
  const batchesQuery = useBatches(branchId);
  const grantsQuery = useAccountsGrants(undefined);
  const createGrant = useCreateGrant();
  const revokeGrant = useRevokeGrant();

  const accountsUsers = useMemo(
    () => (usersQuery.data ?? []).filter((u) => u.roles.includes("accounts")),
    [usersQuery.data],
  );
  const userName = useMemo(() => {
    const m = new Map<string, string>();
    for (const u of usersQuery.data ?? []) {
      m.set(u.id, `${u.first_name} ${u.last_name}`);
    }
    return m;
  }, [usersQuery.data]);

  const [form, setForm] = useState({ userId: "", batchId: "", expires: "" });

  async function onGrant() {
    if (!form.userId) return;
    try {
      await createGrant.mutateAsync({
        user_id: form.userId,
        batch_id: form.batchId || null,
        expires_at: form.expires ? `${form.expires}T23:59:59Z` : null,
      });
      setForm({ userId: "", batchId: "", expires: "" });
      toast.success("Attendance access granted");
    } catch (err) {
      toast.error(apiError(err));
    }
  }

  async function onRevoke(id: string) {
    try {
      await revokeGrant.mutateAsync(id);
      toast.success("Grant revoked");
    } catch (err) {
      toast.error(apiError(err));
    }
  }

  return (
    <Card>
      <CardContent>
        <h2 className="mb-3 text-lg font-semibold">
          Accounts — attendance access
        </h2>
        <p className="mb-3 text-xs text-muted-foreground">
          Accounts users see fees only by default. Grant attendance visibility
          for a batch (or branch-wide), optionally with an expiry date.
        </p>

        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            Accounts user
            <select
              value={form.userId}
              onChange={(e) => setForm((f) => ({ ...f, userId: e.target.value }))}
              className={CONTROL}
            >
              <option value="">Select…</option>
              {accountsUsers.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.first_name} {u.last_name}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            Scope
            <select
              value={form.batchId}
              onChange={(e) => setForm((f) => ({ ...f, batchId: e.target.value }))}
              className={CONTROL}
            >
              <option value="">Whole branch</option>
              {(batchesQuery.data ?? []).map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            Expires (optional)
            <input
              type="date"
              value={form.expires}
              onChange={(e) => setForm((f) => ({ ...f, expires: e.target.value }))}
              className={CONTROL}
            />
          </label>
          <Button
            size="sm"
            onClick={onGrant}
            disabled={!form.userId || createGrant.isPending}
          >
            Grant access
          </Button>
        </div>

        {accountsUsers.length === 0 && (
          <p className="mt-2 text-xs text-muted-foreground">
            No users have the Accounts role yet — assign it in Users first.
          </p>
        )}

        <div className="mt-5 flex flex-col gap-2">
          {(grantsQuery.data ?? []).length === 0 ? (
            <p className="text-xs text-muted-foreground">
              No active grants.
            </p>
          ) : (
            (grantsQuery.data ?? []).map((g) => (
              <div
                key={g.id}
                className="flex items-center justify-between gap-3 rounded-lg border px-3 py-2 text-sm"
              >
                <span>
                  <span className="font-medium">
                    {userName.get(g.user_id) ?? g.user_id}
                  </span>{" "}
                  · {g.batch_name ?? "Whole branch"} ·{" "}
                  {g.expires_at
                    ? `expires ${new Date(g.expires_at).toLocaleDateString()}`
                    : "permanent"}
                </span>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => onRevoke(g.id)}
                  disabled={revokeGrant.isPending}
                >
                  Revoke
                </Button>
              </div>
            ))
          )}
        </div>
      </CardContent>
    </Card>
  );
}
