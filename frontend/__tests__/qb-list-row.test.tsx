import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QBListRow } from "@/app/(dashboard)/question-bank/_components/qb-list-row";
import type { QuestionResponse } from "@/app/(dashboard)/question-bank/_schemas/question";

const mockSelect = vi.fn();
const mockBulk = vi.fn();

beforeEach(() => {
  vi.clearAllMocks();
});

const Q: QuestionResponse = {
  id: "q1",
  content: "Current $I = \\frac{dQ}{dt}$. At $t=5s$, find $I$.",
  options: { A: "9A", B: "49A", C: "53A", D: "None" },
  correct_answer: "C",
  explanation: null,
  subject_id: "sub1",
  topic_id: null,
  difficulty: "MEDIUM",
  blooms_taxonomy: "APPLY",
  concept_tags: ["physics", "current"],
  source: "studymat:ncert",
  source_ref: "physics/class-12/current.pdf#p1q2",
  diagram_ref: null,
  review_status: "pending_review",
  quality_score: null,
  branch_id: "b1",
  academic_year_id: "ay1",
  status: "active",
};

describe("QBListRow", () => {
  it("renders the question preview + difficulty + source tag", () => {
    render(
      <QBListRow
        question={Q}
        selected={false}
        bulkChecked={false}
        onSelect={mockSelect}
        onToggleBulk={mockBulk}
        isLast={false}
      />,
    );

    expect(screen.getByText(/At t=5s, find I/)).toBeInTheDocument();
    expect(screen.getByText("MEDIUM")).toBeInTheDocument();
    expect(screen.getByText("APPLY")).toBeInTheDocument();
    expect(screen.getByText(/studymat/)).toBeInTheDocument();
  });

  it("clicking the row calls onSelect with the question id", async () => {
    const user = userEvent.setup();
    render(
      <QBListRow
        question={Q}
        selected={false}
        bulkChecked={false}
        onSelect={mockSelect}
        onToggleBulk={mockBulk}
        isLast={false}
      />,
    );

    await user.click(screen.getByText(/At t=5s, find I/));
    expect(mockSelect).toHaveBeenCalledWith("q1");
  });

  it("toggling the checkbox calls onToggleBulk WITHOUT triggering onSelect", async () => {
    const user = userEvent.setup();
    render(
      <QBListRow
        question={Q}
        selected={false}
        bulkChecked={false}
        onSelect={mockSelect}
        onToggleBulk={mockBulk}
        isLast={false}
      />,
    );

    await user.click(
      screen.getByRole("checkbox", { name: /select q1 for bulk action/i }),
    );

    expect(mockBulk).toHaveBeenCalledWith("q1");
    expect(mockSelect).not.toHaveBeenCalled();
  });
});
