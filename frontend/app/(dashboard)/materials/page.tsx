"use client";

import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useToast } from "@/components/ui/toast";
import { useUserStore } from "@/store/user-store";
import {
  useBatches,
  useDeleteMaterial,
  useIngestMaterial,
  useMaterialFacets,
  useMaterialList,
  useSubjects,
} from "./_hooks/use-materials";
import {
  MaterialFilterRail,
  type MaterialFilters,
} from "./_components/filter-rail";
import { MaterialGridCard, MaterialListRow } from "./_components/list-row";
import { MaterialPreviewPane } from "./_components/preview-pane";
import { UploadDialog } from "./_components/upload-dialog";

type SortKey = "recent" | "questions" | "name";
type ViewMode = "list" | "grid";

const SORT_LABEL: Record<SortKey, string> = {
  recent: "Most recent",
  questions: "Most questions",
  name: "Filename A–Z",
};

const DEFAULT_FILTERS: MaterialFilters = {
  academic_year_id: "",
  class_label: "",
  subject_id: "",
  category: "",
  exam_type: "",
  batch_id: "",
};

export default function MaterialsPage() {
  const user = useUserStore((s) => s.user);
  const branchId = user?.branch_roles?.[0]?.branch_id;

  const [filters, setFilters] = useState<MaterialFilters>(DEFAULT_FILTERS);
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<SortKey>("recent");
  const [view, setView] = useState<ViewMode>("list");
  const [openId, setOpenId] = useState<string | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const toast = useToast();
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);

  const queryFilters = useMemo(
    () => ({
      academic_year_id: filters.academic_year_id || undefined,
      class_label: filters.class_label || undefined,
      subject_id: filters.subject_id || undefined,
      category: filters.category || undefined,
      exam_type: filters.exam_type || undefined,
      batch_id: filters.batch_id || undefined,
      search: search || undefined,
    }),
    [filters, search],
  );

  const listQuery = useMaterialList(branchId, queryFilters);
  const facetsQuery = useMaterialFacets(branchId, queryFilters);
  const subjectsQuery = useSubjects(branchId);
  const batchesQuery = useBatches(branchId);

  const ingestMutation = useIngestMaterial(branchId);
  const deleteMutation = useDeleteMaterial(branchId);

  // The Subject table can carry multiple rows with the same name (one per
  // course it's offered in). For the filter rail we just want one entry
  // per subject name — clicking "Physics" should mean "all Physics rows".
  const dedupedSubjects = useMemo(() => {
    const seen = new Set<string>();
    const out: { id: string; name: string }[] = [];
    for (const s of subjectsQuery.data ?? []) {
      if (seen.has(s.name)) continue;
      seen.add(s.name);
      out.push({ id: s.id, name: s.name });
    }
    return out;
  }, [subjectsQuery.data]);

  const items = useMemo(
    () => listQuery.data?.items ?? [],
    [listQuery.data],
  );
  const total = listQuery.data?.total ?? 0;
  // Falls back to first row whenever the explicit selection is stale
  // (filter changed and the previously-open material is no longer in the
  // list). Pure derivation — no effect needed.
  // KPI strip — derived from the loaded set (list returns the full branch up
  // to 200). Mirrors the MSA console's stat row.
  const kpis = useMemo(() => {
    let ingested = 0;
    let pending = 0;
    let failed = 0;
    let questions = 0;
    for (const m of items) {
      if (m.ingest_status === "ingested") ingested += 1;
      else if (m.ingest_status === "uploaded" || m.ingest_status === "ingesting")
        pending += 1;
      else if (m.ingest_status === "ingest_failed") failed += 1;
      questions += m.question_count;
    }
    const ingestedPct = items.length > 0 ? Math.round((ingested / items.length) * 100) : 0;
    return { ingested, pending, failed, questions, ingestedPct };
  }, [items]);

  const subjectCount =
    facetsQuery.data?.subjects.length ?? dedupedSubjects.length;

  const sortedItems = useMemo(() => {
    const copy = [...items];
    if (sort === "questions") {
      copy.sort((a, b) => b.question_count - a.question_count);
    } else if (sort === "name") {
      copy.sort((a, b) => a.filename.localeCompare(b.filename));
    } else {
      copy.sort(
        (a, b) =>
          new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
      );
    }
    return copy;
  }, [items, sort]);

  const openMaterial =
    sortedItems.find((m) => m.id === openId) ?? sortedItems[0] ?? null;

  async function handleIngest(id: string) {
    try {
      await ingestMutation.mutateAsync(id);
      // Extraction runs in the background; the list polls until it
      // flips to "ingested". Don't claim completion here.
      toast.info("Ingest started — extracting questions in the background. The count updates when it's done.");
    } catch (err) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "Ingest failed";
      toast.error(msg);
    }
  }

  async function confirmDelete() {
    if (!deleteTarget) return;
    const id = deleteTarget;
    setDeleteTarget(null);
    try {
      await deleteMutation.mutateAsync(id);
      setOpenId(null);
    } catch (err) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "Delete failed";
      toast.error(msg);
    }
  }

  const pending = ingestMutation.isPending || deleteMutation.isPending;

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Study materials"
        description={
          <>
            {total} material{total !== 1 ? "s" : ""}
            {subjectCount > 0 &&
              ` across ${subjectCount} subject${subjectCount !== 1 ? "s" : ""}`}
            . Upload, tag, and ingest so the question bank and test composer can
            find them.
          </>
        }
        actions={<Button onClick={() => setUploadOpen(true)}>+ Upload</Button>}
      />

      {/* KPI strip */}
      <Card size="sm">
        <CardContent>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
            <Kpi label="Total" value={String(total)} />
            <Kpi
              label="Ingested"
              value={String(kpis.ingested)}
              hint={`${kpis.ingestedPct}% of loaded`}
              tone="success"
            />
            <Kpi
              label="Awaiting ingest"
              value={String(kpis.pending)}
              hint="uploaded / extracting"
              tone={kpis.pending > 0 ? "primary" : "default"}
            />
            <Kpi
              label="Questions extracted"
              value={String(kpis.questions)}
              hint="across loaded materials"
            />
            <Kpi
              label="Ingest failures"
              value={String(kpis.failed)}
              hint={kpis.failed > 0 ? "need attention" : "none"}
              tone={kpis.failed > 0 ? "destructive" : "default"}
            />
          </div>
        </CardContent>
      </Card>

      {/* Three-pane */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[240px_minmax(0,1fr)_360px]">
        {/* LEFT: filters */}
        <div className="lg:sticky lg:top-4 lg:self-start">
          <MaterialFilterRail
            filters={filters}
            onChange={setFilters}
            facets={facetsQuery.data}
            subjects={dedupedSubjects}
            batches={batchesQuery.data ?? []}
          />
        </div>

        {/* MIDDLE: search + list */}
        <div className="flex flex-col gap-3">
          <Input
            placeholder="Search filename or topic…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />

          <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border bg-muted/30 px-3 py-1.5">
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">
                {total} material{total !== 1 ? "s" : ""}
              </span>
              {(filters.category ||
                filters.class_label ||
                filters.subject_id ||
                filters.exam_type ||
                filters.batch_id) && (
                <button
                  type="button"
                  onClick={() => setFilters(DEFAULT_FILTERS)}
                  className="text-xs text-muted-foreground hover:text-foreground"
                >
                  Clear filters
                </button>
              )}
            </div>
            <div className="flex items-center gap-2">
              <select
                value={sort}
                onChange={(e) => setSort(e.target.value as SortKey)}
                aria-label="Sort materials"
                className="h-7 rounded-md border border-input bg-background px-2 text-xs"
              >
                {(Object.keys(SORT_LABEL) as SortKey[]).map((k) => (
                  <option key={k} value={k}>
                    {SORT_LABEL[k]}
                  </option>
                ))}
              </select>
              <div
                role="group"
                aria-label="View mode"
                className="inline-flex overflow-hidden rounded-md border"
              >
                {(["list", "grid"] as ViewMode[]).map((v) => (
                  <button
                    key={v}
                    type="button"
                    aria-pressed={view === v}
                    onClick={() => setView(v)}
                    className={
                      "h-7 px-2.5 text-xs font-medium capitalize transition-colors " +
                      (view === v
                        ? "bg-primary text-primary-foreground"
                        : "bg-background text-muted-foreground hover:bg-muted hover:text-foreground")
                    }
                  >
                    {v}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {listQuery.isLoading ? (
            <p className="rounded-xl border bg-card p-4 text-sm text-muted-foreground">
              Loading…
            </p>
          ) : listQuery.isError ? (
            <p className="rounded-xl border bg-card p-4 text-sm text-destructive">
              Failed to load. Make sure the backend is running.
            </p>
          ) : items.length === 0 ? (
            <p className="rounded-xl border bg-card p-4 text-sm italic text-muted-foreground">
              No materials yet. Click <strong>+ Upload</strong> to add some.
            </p>
          ) : view === "grid" ? (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {sortedItems.map((m) => (
                <MaterialGridCard
                  key={m.id}
                  material={m}
                  selected={openMaterial?.id === m.id}
                  onSelect={setOpenId}
                />
              ))}
            </div>
          ) : (
            <div className="overflow-hidden rounded-xl border bg-card">
              {sortedItems.map((m, i) => (
                <MaterialListRow
                  key={m.id}
                  material={m}
                  selected={openMaterial?.id === m.id}
                  onSelect={setOpenId}
                  isLast={i === sortedItems.length - 1}
                />
              ))}
            </div>
          )}
        </div>

        {/* RIGHT: preview */}
        <div className="lg:sticky lg:top-4 lg:self-start">
          <MaterialPreviewPane
            material={openMaterial}
            onIngest={handleIngest}
            onDelete={setDeleteTarget}
            pending={pending}
          />
        </div>
      </div>

      <UploadDialog
        open={uploadOpen}
        onOpenChange={setUploadOpen}
        branchId={branchId}
        onUploaded={(n) =>
          toast.success(`Uploaded ${n} material${n !== 1 ? "s" : ""}.`)
        }
      />

      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(o) => !o && setDeleteTarget(null)}
        title="Delete material?"
        description="Linked questions stay attached. The file remains on disk; this only flags the row as deleted in the database."
        confirmLabel="Delete"
        destructive
        onConfirm={confirmDelete}
      />
    </div>
  );
}

const KPI_TONE: Record<string, string> = {
  default: "text-foreground",
  success: "text-emerald-600 dark:text-emerald-400",
  primary: "text-primary",
  destructive: "text-destructive",
};

function Kpi({
  label,
  value,
  hint,
  tone = "default",
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "default" | "success" | "primary" | "destructive";
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[11px] uppercase tracking-wide text-muted-foreground">
        {label}
      </span>
      <span className={`text-2xl font-semibold tabular-nums ${KPI_TONE[tone]}`}>
        {value}
      </span>
      {hint && <span className="text-[11px] text-muted-foreground">{hint}</span>}
    </div>
  );
}
