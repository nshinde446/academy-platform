import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ComposeForm } from "@/app/(dashboard)/papers/_components/compose-form";
import { PaperPreview } from "@/app/(dashboard)/papers/_components/paper-preview";
import type { QuestionResponse } from "@/app/(dashboard)/question-bank/_schemas/question";
import type { DifficultyMix } from "@/app/(dashboard)/papers/_schemas/paper";

const MIX: DifficultyMix = { EASY: 2, MEDIUM: 3, HARD: 1 };
const AVAIL = { EASY: 10, MEDIUM: 12, HARD: 5 };

function q(id: string, content: string, difficulty = "MEDIUM"): QuestionResponse {
  return {
    id,
    content,
    options: null,
    correct_answer: "A",
    explanation: null,
    subject_id: "s1",
    topic_id: null,
    difficulty: difficulty as QuestionResponse["difficulty"],
    blooms_taxonomy: "APPLY",
    concept_tags: null,
    source: null,
    source_ref: null,
    diagram_ref: null,
    review_status: "approved",
    quality_score: null,
    branch_id: "b1",
    academic_year_id: "ay1",
    status: "active",
  };
}

function renderForm(overrides: Partial<Parameters<typeof ComposeForm>[0]> = {}) {
  const props = {
    paperType: "DPP" as const,
    onPaperType: vi.fn(),
    batches: [{ id: "b1", name: "NEET-A", code: "NA" }],
    batchId: "",
    onBatchId: vi.fn(),
    subjects: [{ id: "s1", name: "Physics", academic_year_id: "ay1" }],
    subjectId: "",
    onSubjectId: vi.fn(),
    classLabel: "" as const,
    onClassLabel: vi.fn(),
    examType: "" as const,
    onExamType: vi.fn(),
    mix: MIX,
    onMix: vi.fn(),
    availableByDifficulty: AVAIL,
    onAutoPick: vi.fn(),
    picking: false,
    ...overrides,
  };
  render(<ComposeForm {...props} />);
  return props;
}

describe("ComposeForm", () => {
  it("disables Auto-pick until batch + subject + a non-zero mix", () => {
    renderForm();
    expect(screen.getByRole("button", { name: /auto-pick/i })).toBeDisabled();
  });

  it("enables Auto-pick once batch and subject are set", async () => {
    const user = userEvent.setup();
    const props = renderForm({ batchId: "b1", subjectId: "s1" });
    const btn = screen.getByRole("button", { name: /auto-pick/i });
    expect(btn).toBeEnabled();
    await user.click(btn);
    expect(props.onAutoPick).toHaveBeenCalled();
  });

  it("shows the total of the difficulty mix", () => {
    renderForm();
    // 2 + 3 + 1 = 6
    expect(screen.getByText("6")).toBeInTheDocument();
  });

  it("surfaces available counts per difficulty", () => {
    renderForm();
    expect(screen.getByText("10 available")).toBeInTheDocument();
    expect(screen.getByText("12 available")).toBeInTheDocument();
    expect(screen.getByText("5 available")).toBeInTheDocument();
  });
});

function renderPreview(overrides: Partial<Parameters<typeof PaperPreview>[0]> = {}) {
  const props = {
    questions: [q("1", "First question"), q("2", "Second question", "HARD")],
    name: "",
    onName: vi.fn(),
    onRemove: vi.fn(),
    onSwap: vi.fn(),
    onReshuffle: vi.fn(),
    onSave: vi.fn(),
    swappingId: null,
    reshuffling: false,
    saving: false,
    ...overrides,
  };
  render(<PaperPreview {...props} />);
  return props;
}

describe("PaperPreview", () => {
  it("shows an empty-state hint when nothing is picked", () => {
    renderPreview({ questions: [] });
    expect(screen.getByText(/auto-pick/i)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /save draft/i }),
    ).not.toBeInTheDocument();
  });

  it("disables Save until a name is entered", () => {
    renderPreview({ name: "" });
    expect(screen.getByRole("button", { name: /save draft/i })).toBeDisabled();
  });

  it("enables Save with a name and fires onSave", async () => {
    const user = userEvent.setup();
    const props = renderPreview({ name: "Mechanics DPP" });
    const save = screen.getByRole("button", { name: /save draft/i });
    expect(save).toBeEnabled();
    await user.click(save);
    expect(props.onSave).toHaveBeenCalled();
  });

  it("fires onRemove and onSwap for a row, and onReshuffle", async () => {
    const user = userEvent.setup();
    const props = renderPreview();
    await user.click(screen.getAllByRole("button", { name: /^remove$/i })[0]);
    expect(props.onRemove).toHaveBeenCalledWith("1");
    await user.click(screen.getAllByRole("button", { name: /^swap$/i })[0]);
    expect(props.onSwap).toHaveBeenCalledWith(
      expect.objectContaining({ id: "1" }),
    );
    await user.click(screen.getByRole("button", { name: /reshuffle/i }));
    expect(props.onReshuffle).toHaveBeenCalled();
  });
});
