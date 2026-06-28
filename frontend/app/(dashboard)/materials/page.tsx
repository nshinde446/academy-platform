"use client";

import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
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
import { MaterialListRow } from "./_components/list-row";
import { MaterialPreviewPane } from "./_components/preview-pane";
import { UploadDialog } from "./_components/upload-dialog";

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

  const items = listQuery.data?.items ?? [];
  const total = listQuery.data?.total ?? 0;
  // Falls back to first row whenever the explicit selection is stale
  // (filter changed and the previously-open material is no longer in the
  // list). Pure derivation — no effect needed.
  const openMaterial =
    items.find((m) => m.id === openId) ?? items[0] ?? null;

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
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold">Study materials</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Upload PDFs, Word docs, images, or text and tag them so the
            question bank and test composer can find them later.
          </p>
        </div>
        <Button onClick={() => setUploadOpen(true)}>+ Upload</Button>
      </div>

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

          <div className="flex items-center justify-between rounded-md border bg-muted/30 px-3 py-1.5">
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

          <div className="overflow-hidden rounded-xl border bg-card">
            {listQuery.isLoading && (
              <p className="p-4 text-sm text-muted-foreground">Loading…</p>
            )}
            {listQuery.isError && (
              <p className="p-4 text-sm text-destructive">
                Failed to load. Make sure the backend is running.
              </p>
            )}
            {!listQuery.isLoading && items.length === 0 && (
              <p className="p-4 text-sm italic text-muted-foreground">
                No materials yet. Click <strong>+ Upload</strong> to add some.
              </p>
            )}
            {items.map((m, i) => (
              <MaterialListRow
                key={m.id}
                material={m}
                selected={openMaterial?.id === m.id}
                onSelect={setOpenId}
                isLast={i === items.length - 1}
              />
            ))}
          </div>
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
