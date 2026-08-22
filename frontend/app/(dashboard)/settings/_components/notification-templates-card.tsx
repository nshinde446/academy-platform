"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { InfoHint } from "@/components/ui/info-hint";
import { useToast } from "@/components/ui/toast";
import {
  useNotificationTemplates,
  useUpdateNotificationTemplate,
} from "../_hooks/use-notification-settings";
import {
  EVENT_TYPE_LABELS,
  type NotificationTemplate,
} from "../_schemas/settings";

const INPUT =
  "h-8 rounded-md border border-input bg-background px-2 text-xs";

// One editable template row: the admin edits the message wording (and, for
// WhatsApp, the Meta template name/language) and saves.
function TemplateRow({
  template,
  branchId,
}: {
  template: NotificationTemplate;
  branchId: string | undefined;
}) {
  const toast = useToast();
  const update = useUpdateNotificationTemplate(branchId);
  const [body, setBody] = useState(template.body_template);
  const [active, setActive] = useState(template.is_active);
  const [providerName, setProviderName] = useState(
    template.provider_template_name ?? "",
  );
  const [providerLang, setProviderLang] = useState(
    template.provider_language ?? "en",
  );

  const isWhatsApp = template.channel === "WHATSAPP";
  const dirty =
    body !== template.body_template ||
    active !== template.is_active ||
    providerName !== (template.provider_template_name ?? "") ||
    providerLang !== (template.provider_language ?? "en");

  async function save() {
    try {
      await update.mutateAsync({
        id: template.id,
        data: {
          body_template: body,
          is_active: active,
          provider_template_name: isWhatsApp ? providerName || null : null,
          provider_language: isWhatsApp ? providerLang || null : null,
        },
      });
      toast.success("Template saved", template.name);
    } catch {
      toast.error("Couldn't save", "Please try again.");
    }
  }

  return (
    <div className="flex flex-col gap-2 border-t py-4 first:border-t-0 first:pt-0">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium text-foreground">
          {template.name}
        </span>
        <Badge variant="secondary">{template.channel}</Badge>
        <label className="ml-auto flex items-center gap-1.5 text-xs text-muted-foreground">
          <input
            type="checkbox"
            checked={active}
            onChange={(e) => setActive(e.target.checked)}
            className="size-3.5"
          />
          Active
        </label>
      </div>

      <textarea
        value={body}
        onChange={(e) => setBody(e.target.value)}
        rows={2}
        aria-label={`Message for ${template.name}`}
        className="w-full rounded-md border border-input bg-background p-2 text-sm"
      />
      <p className="text-[11px] text-muted-foreground">
        Tokens like <code>{"{student_name}"}</code>,{" "}
        <code>{"{attendance_date}"}</code>, <code>{"{status}"}</code>,{" "}
        <code>{"{subjects}"}</code> are filled in per student.
      </p>

      {isWhatsApp && (
        <div className="flex flex-wrap items-end gap-2">
          <label className="flex flex-col gap-1 text-[11px] text-muted-foreground">
            Meta template name
            <input
              value={providerName}
              onChange={(e) => setProviderName(e.target.value)}
              className={`${INPUT} min-w-52`}
              placeholder="attendance_absent_alert"
            />
          </label>
          <label className="flex flex-col gap-1 text-[11px] text-muted-foreground">
            Language
            <input
              value={providerLang}
              onChange={(e) => setProviderLang(e.target.value)}
              className={`${INPUT} w-16`}
              placeholder="en"
            />
          </label>
        </div>
      )}

      <div className="flex items-center gap-2">
        <Button size="sm" onClick={save} disabled={!dirty || update.isPending}>
          Save
        </Button>
        {dirty && (
          <span className="text-xs text-muted-foreground">Unsaved changes</span>
        )}
      </div>
    </div>
  );
}

export function NotificationTemplatesCard({
  branchId,
}: {
  branchId: string | undefined;
}) {
  const query = useNotificationTemplates(branchId);
  const templates = query.data ?? [];

  // Show the attendance + lecture templates first (the ones the client edits),
  // then anything else, grouped only by display order.
  const order = ["STUDENT_ABSENT", "DAILY_ATTENDANCE_DIGEST", "LECTURE_REMINDER"];
  const sorted = [...templates].sort(
    (a, b) =>
      (order.indexOf(a.event_type) + 1 || 99) -
      (order.indexOf(b.event_type) + 1 || 99),
  );

  return (
    <Card className="max-w-2xl">
      <CardContent className="flex flex-col gap-1">
        <div className="flex items-center gap-1.5">
          <span className="text-sm font-medium text-foreground">
            Notification templates
          </span>
          <InfoHint
            text={
              <>
                Edit the message parents receive for attendance and lecture
                reminders. For WhatsApp, wording changes require Meta to
                re-approve the template before they take effect on the WhatsApp
                channel — the text is saved here now and used once WhatsApp is
                enabled and the template is approved.
              </>
            }
          />
        </div>

        {query.isLoading ? (
          <p className="py-3 text-sm text-muted-foreground">Loading templates…</p>
        ) : query.isError ? (
          <p className="py-3 text-sm text-destructive">
            Failed to load templates.
          </p>
        ) : sorted.length === 0 ? (
          <p className="py-3 text-sm text-muted-foreground">
            No templates yet.
          </p>
        ) : (
          <div className="mt-1 flex flex-col">
            {sorted.map((t) => (
              <TemplateRow key={t.id} template={t} branchId={branchId} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
