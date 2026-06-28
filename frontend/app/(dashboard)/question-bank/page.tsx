"use client";

import { useEffect, useMemo, useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { useUserStore } from "@/store/user-store";
import {
  useBulkApprove,
  useBulkReject,
  useQuestionCount,
  useQuestionList,
  useSubjectOptions,
  useUpdateQuestion,
} from "./_hooks/use-question-bank";
import { EditQuestionDialog } from "./_components/edit-question-dialog";
import { QBStatsStrip } from "./_components/qb-stats-strip";
import { QBFilterRail, type QBFilters } from "./_components/qb-filter-rail";
import { QBListRow } from "./_components/qb-list-row";
import { QBPreviewPane } from "./_components/qb-preview-pane";
import type {
  QuestionResponse,
  QuestionUpdate,
} from "./_schemas/question";

const DEFAULT_FILTERS: QBFilters = {
  review_status: "pending_review",
  difficulty: "",
  source_prefix: "",
  class_label: "",
  subject_id: "",
  exam_type: "",
};

export default function QuestionBankPage() {
  const user = useUserStore((s) => s.user);
  const branchId = user?.branch_roles?.[0]?.branch_id;

  const [filters, setFilters] = useState<QBFilters>(DEFAULT_FILTERS);
  const [search, setSearch] = useState("");
  // Bulk-action set (multi-select); separate from the row that's open in
  // the preview pane (single-select).
  const [bulkSelected, setBulkSelected] = useState<Set<string>>(new Set());
  const [openId, setOpenId] = useState<string | null>(null);

  const [editTarget, setEditTarget] = useState<QuestionResponse | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const toast = useToast();

  const queryFilters = useMemo(
    () => ({
      review_status: filters.review_status || undefined,
      difficulty: filters.difficulty || undefined,
      source_prefix: filters.source_prefix || undefined,
      class_label: filters.class_label || undefined,
      subject_id: filters.subject_id || undefined,
      exam_type: filters.exam_type || undefined,
      search: search || undefined,
    }),
    [filters, search],
  );

  const listQuery = useQuestionList(branchId, queryFilters);
  const subjectsQuery = useSubjectOptions(branchId);
  const pendingCount = useQuestionCount(branchId, {
    review_status: "pending_review",
  });
  const approvedCount = useQuestionCount(branchId, {
    review_status: "approved",
  });
  const rejectedCount = useQuestionCount(branchId, {
    review_status: "rejected",
  });

  const updateMutation = useUpdateQuestion(branchId);
  const approveMutation = useBulkApprove(branchId);
  const rejectMutation = useBulkReject(branchId);

  const questions = listQuery.data ?? [];
  const openQuestion =
    questions.find((q) => q.id === openId) ?? questions[0] ?? null;

  // When the list shifts (filter changes / data refresh), keep the
  // preview pane attached to the first row instead of going blank.
  useEffect(() => {
    if (!openId && questions[0]) {
      setOpenId(questions[0].id);
    }
    if (openId && questions.length > 0 && !questions.find((q) => q.id === openId)) {
      setOpenId(questions[0].id);
    }
  }, [questions, openId]);

  function toggleBulk(id: string) {
    setBulkSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleSelectAll() {
    if (bulkSelected.size === questions.length) {
      setBulkSelected(new Set());
    } else {
      setBulkSelected(new Set(questions.map((q) => q.id)));
    }
  }

  async function approveOne(id: string) {
    try {
      await approveMutation.mutateAsync([id]);
      setBulkSelected((s) => {
        const n = new Set(s);
        n.delete(id);
        return n;
      });
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to approve");
    }
  }
  async function rejectOne(id: string) {
    try {
      await rejectMutation.mutateAsync([id]);
      setBulkSelected((s) => {
        const n = new Set(s);
        n.delete(id);
        return n;
      });
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to reject");
    }
  }

  async function bulkApprove() {
    if (bulkSelected.size === 0) return;
    try {
      const res = await approveMutation.mutateAsync(Array.from(bulkSelected));
      setBulkSelected(new Set());
      toast.success(`Approved ${res.updated} question${res.updated !== 1 ? "s" : ""}.`);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Bulk approve failed");
    }
  }
  async function bulkReject() {
    if (bulkSelected.size === 0) return;
    try {
      const res = await rejectMutation.mutateAsync(Array.from(bulkSelected));
      setBulkSelected(new Set());
      toast.success(`Rejected ${res.updated} question${res.updated !== 1 ? "s" : ""}.`);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Bulk reject failed");
    }
  }

  function handleEdit(q: QuestionResponse) {
    setEditTarget(q);
    setEditOpen(true);
  }
  async function handleEditSubmit(data: QuestionUpdate) {
    if (!editTarget) return;
    await updateMutation.mutateAsync({ questionId: editTarget.id, data });
  }

  const total =
    (pendingCount.data ?? 0) +
    (approvedCount.data ?? 0) +
    (rejectedCount.data ?? 0);

  const mutationPending = approveMutation.isPending || rejectMutation.isPending;

  return (
    <div className="flex flex-col gap-5">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-semibold">Question bank</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Browse, filter, and approve ingested questions before they feed into
          papers.
        </p>
      </div>

      {/* Stats */}
      <QBStatsStrip
        kpis={[
          { label: "Total", value: total },
          {
            label: "Approved",
            value: approvedCount.data ?? 0,
            hint:
              total > 0
                ? `${Math.round(((approvedCount.data ?? 0) / total) * 100)}%`
                : undefined,
            tone: "success",
          },
          {
            label: "Pending review",
            value: pendingCount.data ?? 0,
            tone: "warning",
          },
          { label: "Rejected", value: rejectedCount.data ?? 0, tone: "muted" },
        ]}
      />

      {/* Three-pane */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[220px_minmax(0,1fr)_440px]">
        {/* LEFT: filter rail (sticky on lg+) */}
        <div className="lg:sticky lg:top-4 lg:self-start">
          <QBFilterRail
            filters={filters}
            onChange={setFilters}
            counts={{
              pending: pendingCount.data ?? 0,
              approved: approvedCount.data ?? 0,
              rejected: rejectedCount.data ?? 0,
            }}
            subjects={subjectsQuery.data ?? []}
          />
        </div>

        {/* MIDDLE: search + bulk bar + list */}
        <div className="flex flex-col gap-3">
          <Input
            placeholder="Search question text…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />

          {questions.length > 0 && (
            <div className="flex flex-wrap items-center gap-2 rounded-md border bg-muted/30 px-3 py-1.5">
              <input
                type="checkbox"
                checked={
                  bulkSelected.size > 0 &&
                  bulkSelected.size === questions.length
                }
                onChange={toggleSelectAll}
                aria-label="Select all on this page"
              />
              <span className="text-xs">
                {bulkSelected.size > 0
                  ? `${bulkSelected.size} selected`
                  : `${questions.length} shown`}
              </span>
              {bulkSelected.size > 0 && (
                <div className="ml-auto flex gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={bulkReject}
                    disabled={mutationPending}
                  >
                    Reject {bulkSelected.size}
                  </Button>
                  <Button
                    size="sm"
                    onClick={bulkApprove}
                    disabled={mutationPending}
                  >
                    Approve {bulkSelected.size}
                  </Button>
                </div>
              )}
            </div>
          )}

          <div className="overflow-hidden rounded-xl border bg-card">
            {listQuery.isLoading && (
              <p className="p-4 text-sm text-muted-foreground">Loading…</p>
            )}
            {listQuery.isError && (
              <p className="p-4 text-sm text-destructive">
                Failed to load. Make sure the backend is running.
              </p>
            )}
            {!listQuery.isLoading && questions.length === 0 && (
              <p className="p-4 text-sm italic text-muted-foreground">
                {filters.review_status === "pending_review"
                  ? "No questions waiting for review. Run scripts/ingest_studymat.py to add more."
                  : "Nothing matches the current filters."}
              </p>
            )}
            {questions.map((q, i) => (
              <QBListRow
                key={q.id}
                question={q}
                selected={openQuestion?.id === q.id}
                bulkChecked={bulkSelected.has(q.id)}
                onSelect={setOpenId}
                onToggleBulk={toggleBulk}
                isLast={i === questions.length - 1}
              />
            ))}
          </div>
        </div>

        {/* RIGHT: preview pane (sticky on lg+) */}
        <div className="lg:sticky lg:top-4 lg:self-start">
          <QBPreviewPane
            question={openQuestion}
            onApprove={approveOne}
            onReject={rejectOne}
            onEdit={handleEdit}
            pending={mutationPending}
          />
        </div>
      </div>

      <EditQuestionDialog
        question={editTarget}
        open={editOpen}
        onOpenChange={(o) => {
          setEditOpen(o);
          if (!o) setEditTarget(null);
        }}
        onSubmit={handleEditSubmit}
        isPending={updateMutation.isPending}
      />
    </div>
  );
}
