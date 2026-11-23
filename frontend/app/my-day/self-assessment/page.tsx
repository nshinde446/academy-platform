"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/toast";
import apiClient, { apiErrorMessage } from "@/services/api-client";

type Status = "DRAFT" | "PENDING" | "APPROVED" | "REJECTED" | "ABSENT";

interface Item {
  id: string;
  name: string;
  input_type: string;
  options: string[];
}
interface Category {
  id: string;
  name: string;
  is_deduction: boolean;
  rated: boolean;
  items: Item[];
}
interface FormDef {
  categories: Category[];
  max_total_star: number;
}
interface Assessment {
  id: string;
  assess_date: string;
  status: Status;
  final_total_star: number;
  max_total_star: number;
  miscellaneous_text: string | null;
  latest_approver_comment: string | null;
  can_edit: boolean;
  items: Record<string, string>;
  stars: Record<string, number>;
}

const STATUS_CHIP: Record<Status, string> = {
  DRAFT: "bg-muted text-muted-foreground",
  PENDING: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
  APPROVED: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
  REJECTED: "bg-red-500/15 text-red-700 dark:text-red-300",
  ABSENT: "bg-zinc-500/15 text-zinc-700 dark:text-zinc-300",
};

function today(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function StarPicker({
  value, onChange, disabled,
}: { value: number; onChange: (v: number) => void; disabled: boolean }) {
  return (
    <div className="flex items-center gap-1" role="radiogroup" aria-label="Star rating">
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          disabled={disabled}
          aria-label={`${n} star${n > 1 ? "s" : ""}`}
          aria-pressed={value >= n}
          onClick={() => onChange(n)}
          className={`text-lg leading-none transition-colors disabled:cursor-not-allowed ${
            value >= n ? "text-amber-500" : "text-muted-foreground/40"
          }`}
        >
          ★
        </button>
      ))}
      <span className="ml-1 text-xs text-muted-foreground">({value || 0}/5)</span>
    </div>
  );
}

export default function PortalSelfAssessmentPage() {
  const router = useRouter();
  const toast = useToast();

  const [form, setForm] = useState<FormDef | null>(null);
  const [date, setDate] = useState(today());
  const [existing, setExisting] = useState<Assessment | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const [itemValues, setItemValues] = useState<Record<string, string>>({});
  const [stars, setStars] = useState<Record<string, number>>({});
  const [misc, setMisc] = useState("");
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let on = true;
    (async () => {
      try {
        const f = await apiClient.get<FormDef>("/api/v1/me/self-assessment-form");
        if (on) setForm(f.data);
      } catch (e) {
        if (apiErrorMessage(e, "") === "PASSWORD_CHANGE_REQUIRED") router.push("/change-password");
      }
    })();
    return () => { on = false; };
  }, [router]);

  useEffect(() => {
    let on = true;
    (async () => {
      try {
        const res = await apiClient.get<Assessment | null>("/api/v1/me/self-assessments/by-date", {
          params: { date },
        });
        const a = res.data;
        if (on) {
          setExisting(a);
          setItemValues(a?.items ?? {});
          setStars(a?.stars ?? {});
          setMisc(a?.miscellaneous_text ?? "");
        }
      } catch (e) {
        if (apiErrorMessage(e, "") === "PASSWORD_CHANGE_REQUIRED") router.push("/change-password");
      } finally {
        if (on) setLoading(false);
      }
    })();
    return () => { on = false; };
  }, [date, tick, router]);

  const locked = existing != null && !existing.can_edit;

  const ratedCategories = useMemo(
    () => (form?.categories ?? []).filter((c) => c.rated),
    [form],
  );
  const finalTotal = useMemo(
    () => ratedCategories.reduce((sum, c) => sum + (stars[c.id] || 0), 0),
    [ratedCategories, stars],
  );

  function body() {
    return {
      assess_date: date,
      approver_id: null,
      miscellaneous_text: misc.trim() || null,
      items: Object.entries(itemValues)
        .filter(([, v]) => v)
        .map(([item_master_id, selected_value]) => ({ item_master_id, selected_value })),
      stars: Object.entries(stars)
        .filter(([, v]) => v)
        .map(([category_id, v]) => ({ category_id, stars: v })),
    };
  }

  async function save(submit: boolean) {
    if (submit && ratedCategories.some((c) => !stars[c.id])) {
      toast.error("Rate all four categories", "Give each main category a 1–5 star rating before submitting.");
      return;
    }
    setSaving(true);
    try {
      await apiClient.put("/api/v1/me/self-assessments", body(), { params: { submit } });
      toast.success(submit ? "Submitted for approval" : "Draft saved");
      setTick((t) => t + 1);
    } catch (err) {
      toast.error("Could not save", apiErrorMessage(err, "Try again."));
    } finally {
      setSaving(false);
    }
  }

  async function withdraw() {
    if (!existing) return;
    try {
      await apiClient.post(`/api/v1/me/self-assessments/${existing.id}/withdraw`);
      toast.success("Withdrawn", "Back to draft and editable.");
      setTick((t) => t + 1);
    } catch (err) {
      toast.error("Could not withdraw", apiErrorMessage(err, "Try again."));
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold leading-tight">Daily Self-Assessment</h1>
        <p className="text-sm text-muted-foreground">
          Record your day using the Star System. Pick a value for each item,
          rate each of the four main areas 1–5 stars, and submit for approval.
          Miscellaneous is the only free-text field.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          <Label htmlFor="adate" className="text-xs">Date</Label>
          <input id="adate" type="date" max={today()} value={date}
            onChange={(e) => setDate(e.target.value)}
            className="h-8 rounded-md border bg-background px-2 text-xs" />
        </div>
        {existing && (
          <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${STATUS_CHIP[existing.status]}`}>
            {existing.status}
          </span>
        )}
      </div>

      {existing?.latest_approver_comment && (
        <Card>
          <CardContent className="pt-4">
            <p className={`text-sm ${existing.status === "REJECTED" ? "text-red-600 dark:text-red-400" : "text-foreground"}`}>
              Approver comment: {existing.latest_approver_comment}
            </p>
          </CardContent>
        </Card>
      )}

      {loading || !form ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-2">
            {form.categories.map((c) => (
              <Card key={c.id}>
                <CardContent className="pt-4">
                  <div className="mb-3 text-sm font-semibold">{c.name}</div>
                  <div className="flex flex-col gap-2">
                    {c.items.map((it) => (
                      <div key={it.id} className="flex items-center justify-between gap-2">
                        <Label className="text-xs">{it.name}</Label>
                        <select
                          className="h-8 w-40 rounded-md border bg-background px-2 text-xs disabled:opacity-60"
                          disabled={locked}
                          value={itemValues[it.id] ?? ""}
                          onChange={(e) => setItemValues((v) => ({ ...v, [it.id]: e.target.value }))}
                        >
                          <option value="">—</option>
                          {it.options.map((o) => <option key={o} value={o}>{o}</option>)}
                        </select>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Star rating */}
          <Card>
            <CardContent className="pt-4">
              <div className="mb-3 text-sm font-semibold">Star rating</div>
              <div className="flex flex-col gap-2">
                {ratedCategories.map((c) => (
                  <div key={c.id} className="flex items-center justify-between gap-2">
                    <Label className="text-xs">{c.name}</Label>
                    <StarPicker
                      value={stars[c.id] || 0}
                      disabled={locked}
                      onChange={(v) => setStars((s) => ({ ...s, [c.id]: v }))}
                    />
                  </div>
                ))}
                <div className="mt-2 flex items-center justify-between border-t pt-2 text-sm font-semibold">
                  <span>Final Total Star</span>
                  <span>
                    {finalTotal} / {form.max_total_star}
                    <span className="ml-2 text-xs font-normal text-muted-foreground">
                      ({Math.round((finalTotal / form.max_total_star) * 100)}%)
                    </span>
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Miscellaneous */}
          <Card>
            <CardContent className="pt-4">
              <Label htmlFor="misc" className="text-xs">Miscellaneous (optional, 300 chars)</Label>
              <textarea id="misc" maxLength={300} disabled={locked}
                className="mt-2 min-h-16 w-full rounded-md border bg-background px-3 py-2 text-sm disabled:opacity-60"
                value={misc} onChange={(e) => setMisc(e.target.value)} />
            </CardContent>
          </Card>

          {locked ? (
            existing?.status === "PENDING" ? (
              <div>
                <Button variant="secondary" onClick={withdraw}>Withdraw</Button>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                This assessment is {existing?.status.toLowerCase()} and can no longer be edited.
              </p>
            )
          ) : (
            <div className="flex gap-2">
              <Button variant="secondary" disabled={saving} onClick={() => save(false)}>
                {saving ? "Saving…" : "Save draft"}
              </Button>
              <Button disabled={saving} onClick={() => save(true)}>
                {saving ? "Submitting…" : "Submit for approval"}
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
