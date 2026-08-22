"use client";

import { useUserStore } from "@/store/user-store";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/components/ui/toast";
import {
  useNotificationSettings,
  useUpdateNotificationSettings,
} from "./_hooks/use-notification-settings";
import type { DigestScope } from "./_schemas/settings";
import { NotificationTemplatesCard } from "./_components/notification-templates-card";

const SCOPES: { value: DigestScope; label: string; hint: string }[] = [
  {
    value: "ALL",
    label: "All students",
    hint: "Every parent gets their child's daily status (present or absent).",
  },
  {
    value: "ABSENT_ONLY",
    label: "Absent only",
    hint: "Only absent students' parents are messaged. Cheaper, higher signal.",
  },
];

export default function SettingsPage() {
  const user = useUserStore((s) => s.user);
  const branchId = user?.branch_roles?.[0]?.branch_id;

  const toast = useToast();
  const settingsQuery = useNotificationSettings(branchId);
  const updateMutation = useUpdateNotificationSettings(branchId);

  const settings = settingsQuery.data;
  const whatsappEnabled = settings?.whatsapp_enabled ?? false;
  const enabled = settings?.daily_digest_enabled ?? false;
  const scope: DigestScope = settings?.daily_digest_scope ?? "ABSENT_ONLY";

  const busy = settingsQuery.isLoading || updateMutation.isPending;

  async function handleWhatsAppMaster(next: boolean) {
    try {
      await updateMutation.mutateAsync({ whatsapp_enabled: next });
      toast.success(
        "Settings saved",
        next ? "WhatsApp notifications turned on." : "WhatsApp notifications turned off.",
      );
    } catch {
      toast.error("Couldn't save", "Please try again.");
    }
  }

  async function handleToggle(next: boolean) {
    try {
      await updateMutation.mutateAsync({ daily_digest_enabled: next });
      toast.success(
        "Settings saved",
        next ? "Daily digest turned on." : "Daily digest turned off.",
      );
    } catch {
      toast.error("Couldn't save", "Please try again.");
    }
  }

  async function handleScope(next: DigestScope) {
    if (next === scope) return;
    try {
      await updateMutation.mutateAsync({ daily_digest_scope: next });
      toast.success("Settings saved", "Recipient scope updated.");
    } catch {
      toast.error("Couldn't save", "Please try again.");
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Settings"
        description="Branch-level configuration for parent notifications."
      />

      {/* Master WhatsApp switch — the overall on/off for all WhatsApp sends. */}
      <Card className="max-w-2xl">
        <CardContent className="flex items-start justify-between gap-4">
          <div className="flex flex-col gap-1">
            <span className="text-sm font-medium text-foreground">
              WhatsApp notifications
            </span>
            <span className="text-sm text-muted-foreground">
              Master switch for all parent WhatsApp messages (attendance alerts,
              daily digest, lecture reminders). When off, nothing is sent even if
              individual rules below are enabled.
            </span>
          </div>
          <Switch
            checked={whatsappEnabled}
            onCheckedChange={handleWhatsAppMaster}
            disabled={busy}
            aria-label="Enable WhatsApp notifications"
          />
        </CardContent>
      </Card>

      {/* Daily digest rule */}
      <Card className="max-w-2xl">
        <CardContent className="flex flex-col gap-5">
          <div className="flex items-start justify-between gap-4">
            <div className="flex flex-col gap-1">
              <span className="text-sm font-medium text-foreground">
                Daily attendance digest
              </span>
              <span className="text-sm text-muted-foreground">
                Send parents a message each evening with their child&apos;s
                attendance for the day.
              </span>
            </div>
            <Switch
              checked={enabled}
              onCheckedChange={handleToggle}
              disabled={busy}
              aria-label="Enable daily attendance digest"
            />
          </div>

          {enabled && (
            <div className="flex flex-col gap-2 border-t pt-4">
              <span className="text-sm font-medium text-foreground">
                Who gets a message?
              </span>
              <div
                role="radiogroup"
                aria-label="Digest recipient scope"
                className="inline-flex w-fit rounded-lg border border-border p-0.5"
              >
                {SCOPES.map((s) => {
                  const active = s.value === scope;
                  return (
                    <button
                      key={s.value}
                      type="button"
                      role="radio"
                      aria-checked={active}
                      onClick={() => handleScope(s.value)}
                      disabled={updateMutation.isPending}
                      className={`rounded-md px-3 py-1.5 text-[13px] font-medium transition-colors disabled:opacity-50 ${
                        active
                          ? "bg-primary text-primary-foreground"
                          : "text-foreground hover:bg-muted"
                      }`}
                    >
                      {s.label}
                    </button>
                  );
                })}
              </div>
              <span className="text-sm text-muted-foreground">
                {SCOPES.find((s) => s.value === scope)?.hint}
              </span>
            </div>
          )}

          {settingsQuery.isError && (
            <p className="text-sm text-destructive">
              Failed to load settings. Make sure the backend is running.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Editable message templates */}
      <NotificationTemplatesCard branchId={branchId} />
    </div>
  );
}
