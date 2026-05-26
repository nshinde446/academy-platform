"use client";

import { useMemo, useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useUserStore } from "@/store/user-store";
import {
  useBulkApprove,
  useBulkReject,
  useQuestionCount,
  useQuestionList,
  useUpdateQuestion,
} from "./_hooks/use-question-bank";
import { QuestionCard } from "./_components/question-card";
import { EditQuestionDialog } from "./_components/edit-question-dialog";
import {
  DIFFICULTIES,
  REVIEW_STATUSES,
  type QuestionResponse,
  type QuestionUpdate,
  type ReviewStatus,
} from "./_schemas/question";

const SELECT_CLASS =
  "h-9 rounded-lg border border-input bg-background px-3 text-sm";

export default function QuestionBankPage() {
  const user = useUserStore((s) => s.user);
  const branchId = user?.branch_roles?.[0]?.branch_id;

  const [activeTab, setActiveTab] = useState<ReviewStatus>("pending_review");
  const [search, setSearch] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [sourcePrefix, setSourcePrefix] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const [editTarget, setEditTarget] = useState<QuestionResponse | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [confirmAction, setConfirmAction] = useState<
    "approve" | "reject" | null
  >(null);
  const [alert, setAlert] = useState<string | null>(null);

  const filters = useMemo(
    () => ({
      review_status: activeTab,
      search: search || undefined,
      difficulty: difficulty || undefined,
      source_prefix: sourcePrefix || undefined,
    }),
    [activeTab, search, difficulty, sourcePrefix],
  );

  const listQuery = useQuestionList(branchId, filters);
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

  function toggleSelected(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  function toggleSelectAll() {
    if (selected.size === questions.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(questions.map((q) => q.id)));
    }
  }

  async function approveOne(id: string) {
    try {
      await approveMutation.mutateAsync([id]);
      setSelected((s) => {
        const n = new Set(s);
        n.delete(id);
        return n;
      });
    } catch (err: any) {
      setAlert(err?.response?.data?.detail || "Failed to approve");
    }
  }
  async function rejectOne(id: string) {
    try {
      await rejectMutation.mutateAsync([id]);
      setSelected((s) => {
        const n = new Set(s);
        n.delete(id);
        return n;
      });
    } catch (err: any) {
      setAlert(err?.response?.data?.detail || "Failed to reject");
    }
  }

  async function bulkApprove() {
    if (selected.size === 0) return;
    try {
      const res = await approveMutation.mutateAsync(Array.from(selected));
      setSelected(new Set());
      setAlert(`Approved ${res.updated} question${res.updated !== 1 ? "s" : ""}.`);
    } catch (err: any) {
      setAlert(err?.response?.data?.detail || "Bulk approve failed");
    }
  }

  async function bulkReject() {
    if (selected.size === 0) return;
    try {
      const res = await rejectMutation.mutateAsync(Array.from(selected));
      setSelected(new Set());
      setAlert(`Rejected ${res.updated} question${res.updated !== 1 ? "s" : ""}.`);
    } catch (err: any) {
      setAlert(err?.response?.data?.detail || "Bulk reject failed");
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

  const TABS: { value: ReviewStatus; label: string; count?: number }[] = [
    {
      value: "pending_review",
      label: "Pending review",
      count: pendingCount.data,
    },
    { value: "approved", label: "Approved", count: approvedCount.data },
    { value: "rejected", label: "Rejected", count: rejectedCount.data },
  ];

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h2 className="text-2xl font-semibold">Question bank</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Review AI-ingested + manually authored questions before they can be
          used to compose papers. Approve, reject, or edit inline.
        </p>
      </div>

      {/* Tabs */}
      <div className="flex flex-wrap gap-2 border-b">
        {TABS.map((t) => (
          <button
            key={t.value}
            type="button"
            onClick={() => {
              setActiveTab(t.value);
              setSelected(new Set());
            }}
            className={`px-3 py-2 text-sm font-medium border-b-2 -mb-px ${
              activeTab === t.value
                ? "border-foreground text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            {t.label}
            {typeof t.count === "number" && (
              <span className="ml-2 text-xs text-muted-foreground">
                {t.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-2 lg:flex-row lg:flex-wrap lg:items-center">
        <Input
          placeholder="Search question text…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full lg:max-w-xs"
        />
        <select
          value={difficulty}
          onChange={(e) => setDifficulty(e.target.value)}
          className={SELECT_CLASS}
          aria-label="Filter by difficulty"
        >
          <option value="">All difficulties</option>
          {DIFFICULTIES.map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
        </select>
        <select
          value={sourcePrefix}
          onChange={(e) => setSourcePrefix(e.target.value)}
          className={SELECT_CLASS}
          aria-label="Filter by source"
        >
          <option value="">All sources</option>
          <option value="studymat:">Study material</option>
          <option value="HUMAN">Manual / seed</option>
          <option value="AI-">AI generated</option>
        </select>
        <span className="text-sm text-muted-foreground">
          {questions.length} shown
        </span>
      </div>

      {/* Bulk action bar */}
      {questions.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 rounded-md border bg-muted/30 px-3 py-2">
          <input
            type="checkbox"
            checked={
              selected.size > 0 && selected.size === questions.length
            }
            onChange={toggleSelectAll}
            aria-label="Select all on this page"
          />
          <span className="text-sm">
            {selected.size > 0
              ? `${selected.size} selected`
              : `Select all (${questions.length})`}
          </span>
          {selected.size > 0 && (
            <>
              <Button
                size="sm"
                variant="outline"
                onClick={bulkReject}
                disabled={rejectMutation.isPending}
              >
                Reject {selected.size}
              </Button>
              <Button
                size="sm"
                onClick={bulkApprove}
                disabled={approveMutation.isPending}
              >
                Approve {selected.size}
              </Button>
            </>
          )}
        </div>
      )}

      {/* Content */}
      {listQuery.isLoading && (
        <p className="text-sm text-muted-foreground">Loading…</p>
      )}
      {listQuery.isError && (
        <p className="text-sm text-destructive">
          Failed to load. Make sure the backend is running.
        </p>
      )}
      {!listQuery.isLoading && questions.length === 0 && (
        <p className="text-sm text-muted-foreground italic">
          {activeTab === "pending_review"
            ? "No questions waiting for review. Run scripts/ingest_studymat.py to add more."
            : "Nothing matches the current filters."}
        </p>
      )}
      <div className="flex flex-col gap-3">
        {questions.map((q) => (
          <QuestionCard
            key={q.id}
            question={q}
            selected={selected.has(q.id)}
            onToggleSelected={toggleSelected}
            onApprove={approveOne}
            onReject={rejectOne}
            onEdit={handleEdit}
            pending={approveMutation.isPending || rejectMutation.isPending}
          />
        ))}
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

      <ConfirmDialog
        open={!!alert}
        onOpenChange={(o) => !o && setAlert(null)}
        title="Info"
        description={alert ?? ""}
        confirmLabel="OK"
        hideCancel
      />
    </div>
  );
}
