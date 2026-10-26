"use client";

import { useState } from "react";
import { useRoles } from "@/store/user-store";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { apiErrorMessage } from "@/lib/api-error";
import { usePayrollConfig, useUpdatePayrollConfig, type PayrollConfig } from "@/hooks/use-payroll";

function Row({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b py-3 last:border-0">
      <div className="min-w-0">
        <div className="text-sm font-medium">{label}</div>
        {hint && <div className="text-xs text-muted-foreground">{hint}</div>}
      </div>
      {children}
    </div>
  );
}

export default function PayrollSettingsPage() {
  const { hasRole } = useRoles();
  const canEdit = hasRole("super_admin");
  const toast = useToast();
  const configQuery = usePayrollConfig();
  const update = useUpdatePayrollConfig();

  // Draft overlay over the fetched config — editable without a sync effect.
  const [draft, setDraft] = useState<Partial<PayrollConfig>>({});
  const form: PayrollConfig | null = configQuery.data
    ? { ...configQuery.data, ...draft }
    : null;

  function set<K extends keyof PayrollConfig>(key: K, value: PayrollConfig[K]) {
    setDraft((d) => ({ ...d, [key]: value }));
  }

  async function save() {
    if (!form) return;
    try {
      await update.mutateAsync(form);
      setDraft({});
      toast.success("Settings saved");
    } catch (e) {
      toast.error("Could not save", apiErrorMessage(e, "Please try again."));
    }
  }

  if (configQuery.isLoading || !form) {
    return (
      <div className="flex flex-col gap-3">
        <Skeleton className="h-8 w-48" />
        {Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
      </div>
    );
  }

  return (
    <div className="flex max-w-2xl flex-col gap-5">
      <PageHeader
        title="Payroll Settings"
        description="Each payroll rule can be retuned here without a code change. These are the defaults from the spec; changing them affects future calculations."
        actions={
          canEdit && (
            <Button onClick={save} disabled={update.isPending}>Save</Button>
          )
        }
      >
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Module status:</span>
          <Badge variant={form.payroll_enabled ? "default" : "outline"}>
            {form.payroll_enabled ? "Enabled" : "Dormant"}
          </Badge>
        </div>
      </PageHeader>

      {!canEdit && (
        <p className="rounded-md border bg-muted/40 px-3 py-2 text-sm text-muted-foreground">
          Only a Super Admin can change payroll settings.
        </p>
      )}

      <section className="rounded-md border px-4">
        <Row
          label="Enable payroll module"
          hint="Master switch. While off, the Payroll nav is hidden (the module stays dormant)."
        >
          <Switch
            checked={form.payroll_enabled}
            onCheckedChange={(v) => set("payroll_enabled", v)}
            disabled={!canEdit}
          />
        </Row>

        <Row label="Paid holiday treatment" hint="Credit as present, or reduce required days.">
          <select
            className="h-9 rounded-md border bg-background px-2 text-sm"
            value={form.holiday_treatment}
            disabled={!canEdit}
            onChange={(e) => set("holiday_treatment", e.target.value)}
          >
            <option value="credited">Count as credited</option>
            <option value="reduce_required">Reduce required days</option>
          </select>
        </Row>

        <Row label="Allow half days" hint="Fractions in 0.5 steps, or whole days only.">
          <Switch checked={form.allow_half_day} onCheckedChange={(v) => set("allow_half_day", v)} disabled={!canEdit} />
        </Row>

        <Row label="Carry-forward cap (days)" hint="Maximum balance a staff member can carry.">
          <Input
            type="number" min="0" className="w-24"
            value={form.carry_forward_cap} disabled={!canEdit}
            onChange={(e) => set("carry_forward_cap", Number(e.target.value))}
          />
        </Row>

        <Row label="Carry-forward expiry (months)" hint="0 = never expires.">
          <Input
            type="number" min="0" className="w-24"
            value={form.carry_forward_expiry_months} disabled={!canEdit}
            onChange={(e) => set("carry_forward_expiry_months", Number(e.target.value))}
          />
        </Row>

        <Row label="Allow negative balance" hint="Normally a balance never goes below zero.">
          <Switch checked={form.allow_negative_balance} onCheckedChange={(v) => set("allow_negative_balance", v)} disabled={!canEdit} />
        </Row>

        <Row label="Unapproved shortfall" hint="How an un-made-up shortfall is treated.">
          <select
            className="h-9 rounded-md border bg-background px-2 text-sm"
            value={form.unapproved_shortfall}
            disabled={!canEdit}
            onChange={(e) => set("unapproved_shortfall", e.target.value)}
          >
            <option value="unpaid">Unpaid (LWP)</option>
            <option value="absent">Mark absent</option>
          </select>
        </Row>

        <Row label="Request approver role" hint="Who approves extra-day requests (super_admin always can).">
          <Input
            className="w-40" value={form.request_approver_role} disabled={!canEdit}
            onChange={(e) => set("request_approver_role", e.target.value)}
          />
        </Row>

        <Row label="Allow Manager to approve" hint="Let a Manager approve requests too.">
          <Switch checked={form.allow_manager_approver} onCheckedChange={(v) => set("allow_manager_approver", v)} disabled={!canEdit} />
        </Row>

        <Row label="Prorate on join/leave" hint="Prorate required days for mid-month joiners/leavers.">
          <Switch checked={form.prorate_on_join_leave} onCheckedChange={(v) => set("prorate_on_join_leave", v)} disabled={!canEdit} />
        </Row>
      </section>
    </div>
  );
}
