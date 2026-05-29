"use client";

import { useMemo, useState } from "react";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useUserStore } from "@/store/user-store";
import type {
  Difficulty,
  QuestionResponse,
} from "@/app/(dashboard)/question-bank/_schemas/question";
import {
  DIFFICULTY_ORDER,
  PAPER_TYPE_LABEL,
  type ClassLabel,
  type DifficultyMix,
  type ExamType,
  type PaperType,
} from "./_schemas/paper";
import {
  useAutoPick,
  useAvailableCount,
  useBatchOptions,
  useDeleteTest,
  useDownloadPaperPdf,
  usePaperList,
  useSavePaper,
  useSubjectOptions,
  type PdfKind,
} from "./_hooks/use-papers";
import type { TestResponse } from "./_schemas/paper";
import { ComposeForm } from "./_components/compose-form";
import { PaperPreview } from "./_components/paper-preview";
import { RecentPapers } from "./_components/recent-papers";

const DEFAULT_MIX: DifficultyMix = { EASY: 3, MEDIUM: 5, HARD: 2 };

export default function PapersPage() {
  const user = useUserStore((s) => s.user);
  const branchId = user?.branch_roles?.[0]?.branch_id;

  const [paperType, setPaperType] = useState<PaperType>("DPP");
  const [batchId, setBatchId] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [classLabel, setClassLabel] = useState<ClassLabel | "">("");
  const [examType, setExamType] = useState<ExamType | "">("");
  const [mix, setMixState] = useState<DifficultyMix>(DEFAULT_MIX);

  const [picked, setPicked] = useState<QuestionResponse[]>([]);
  const [name, setName] = useState("");
  const [pickMode, setPickMode] = useState<"pick" | "reshuffle" | null>(null);
  const [swappingId, setSwappingId] = useState<string | null>(null);
  const [alert, setAlert] = useState<string | null>(null);

  const subjects = useSubjectOptions(branchId);
  const batches = useBatchOptions(branchId);
  const autoPick = useAutoPick(branchId);
  const savePaper = useSavePaper(branchId);
  const papers = usePaperList(branchId, batchId || undefined);
  const downloadPdf = useDownloadPaperPdf(branchId);
  const deleteTest = useDeleteTest(branchId);
  const [deleteTarget, setDeleteTarget] = useState<TestResponse | null>(null);

  function downloadPaper(p: TestResponse, kind: PdfKind) {
    downloadPdf.mutate(
      { testId: p.id, kind, name: p.name },
      {
        onError: (err: any) =>
          setAlert(err?.response?.data?.detail || "Could not generate the PDF"),
      },
    );
  }

  const downloadBusyKey =
    downloadPdf.isPending && downloadPdf.variables
      ? `${downloadPdf.variables.testId}:${downloadPdf.variables.kind}`
      : null;

  const baseFacets = {
    subject_id: subjectId || undefined,
    class_label: classLabel || undefined,
    exam_type: examType || undefined,
    review_status: "approved",
  };

  const easyCount = useAvailableCount(branchId, { ...baseFacets, difficulty: "EASY" });
  const medCount = useAvailableCount(branchId, { ...baseFacets, difficulty: "MEDIUM" });
  const hardCount = useAvailableCount(branchId, { ...baseFacets, difficulty: "HARD" });

  const availableByDifficulty: Record<Difficulty, number | undefined> = {
    EASY: easyCount.data,
    MEDIUM: medCount.data,
    HARD: hardCount.data,
  };

  function setMix(d: Difficulty, value: number) {
    setMixState((prev) => ({ ...prev, [d]: value }));
  }

  function buildMix(): Partial<DifficultyMix> {
    const out: Partial<DifficultyMix> = {};
    for (const d of DIFFICULTY_ORDER) {
      if (mix[d] > 0) out[d] = mix[d];
    }
    return out;
  }

  function draw(mode: "pick" | "reshuffle") {
    setPickMode(mode);
    autoPick.mutate(
      { ...baseFacets, difficulty_mix: buildMix() },
      {
        onSuccess: (res) => {
          setPicked(res);
          if (res.length === 0) {
            setAlert("No approved questions match these facets yet.");
          }
        },
        onError: (err: any) =>
          setAlert(err?.response?.data?.detail || "Auto-pick failed"),
        onSettled: () => setPickMode(null),
      },
    );
  }

  function swap(q: QuestionResponse) {
    setSwappingId(q.id);
    autoPick.mutate(
      {
        ...baseFacets,
        difficulty_mix: { [q.difficulty]: 1 },
        exclude_ids: picked.map((p) => p.id),
      },
      {
        onSuccess: (res) => {
          if (res[0]) {
            setPicked((prev) => prev.map((p) => (p.id === q.id ? res[0] : p)));
          } else {
            setAlert(`No other ${q.difficulty.toLowerCase()} question available to swap in.`);
          }
        },
        onError: (err: any) =>
          setAlert(err?.response?.data?.detail || "Swap failed"),
        onSettled: () => setSwappingId(null),
      },
    );
  }

  function remove(id: string) {
    setPicked((prev) => prev.filter((p) => p.id !== id));
  }

  function save() {
    if (picked.length === 0 || !name.trim() || !batchId || !subjectId) return;
    savePaper.mutate(
      {
        paper: {
          name: name.trim(),
          paper_type: paperType,
          batch_id: batchId,
          subject_id: subjectId,
          total_marks: picked.length,
        },
        questionIds: picked.map((p) => p.id),
      },
      {
        onSuccess: (t) => {
          setAlert(`Saved "${t.name}" as a ${PAPER_TYPE_LABEL[t.paper_type]} draft.`);
          setPicked([]);
          setName("");
        },
        onError: (err: any) =>
          setAlert(err?.response?.data?.detail || "Save failed"),
      },
    );
  }

  const recentPapers = useMemo(() => papers.data ?? [], [papers.data]);

  return (
    <div className="flex flex-col gap-5">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-semibold">Papers</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Compose a DPP, CPP or test by auto-picking approved questions from the
          bank, then save it as a draft.
        </p>
      </div>

      {/* Composer */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[320px_minmax(0,1fr)]">
        <div className="lg:sticky lg:top-4 lg:self-start">
          <ComposeForm
            paperType={paperType}
            onPaperType={setPaperType}
            batches={batches.data ?? []}
            batchId={batchId}
            onBatchId={setBatchId}
            subjects={subjects.data ?? []}
            subjectId={subjectId}
            onSubjectId={setSubjectId}
            classLabel={classLabel}
            onClassLabel={setClassLabel}
            examType={examType}
            onExamType={setExamType}
            mix={mix}
            onMix={setMix}
            availableByDifficulty={availableByDifficulty}
            onAutoPick={() => draw("pick")}
            picking={autoPick.isPending && pickMode === "pick"}
          />
        </div>

        <PaperPreview
          questions={picked}
          name={name}
          onName={setName}
          onRemove={remove}
          onSwap={swap}
          onReshuffle={() => draw("reshuffle")}
          onSave={save}
          swappingId={swappingId}
          reshuffling={autoPick.isPending && pickMode === "reshuffle"}
          saving={savePaper.isPending}
        />
      </div>

      {/* Recent drafts for the selected batch — with PDF downloads */}
      {batchId && (
        <RecentPapers
          papers={recentPapers}
          onDownload={downloadPaper}
          onDelete={(p) => setDeleteTarget(p)}
          busyKey={downloadBusyKey}
          deletingId={deleteTest.isPending ? deleteTest.variables ?? null : null}
        />
      )}

      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(o) => !o && setDeleteTarget(null)}
        title="Delete draft?"
        description={
          deleteTarget
            ? `"${deleteTarget.name}" will be removed from Recent papers. The questions in the bank are not affected.`
            : ""
        }
        confirmLabel="Delete"
        destructive
        onConfirm={async () => {
          if (!deleteTarget) return;
          await deleteTest.mutateAsync(deleteTarget.id);
          setDeleteTarget(null);
        }}
      />

      <ConfirmDialog
        open={!!alert}
        onOpenChange={(o) => !o && setAlert(null)}
        title="Papers"
        description={alert ?? ""}
        confirmLabel="OK"
        hideCancel
      />
    </div>
  );
}
