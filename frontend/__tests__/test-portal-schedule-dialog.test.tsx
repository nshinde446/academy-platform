import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const BATCHES = [
  { id: "b-jee", name: "11th JEE", course_id: "c1" },
  { id: "b-cet", name: "11th CET-1", course_id: "c1" },
];
const SUBJECTS = [
  { id: "phy", name: "Physics" },
  { id: "chem", name: "Chemistry" },
];

vi.mock("@/app/(dashboard)/lectures/_hooks/use-lectures", () => ({
  useBatchesForLectures: () => ({ data: BATCHES }),
  useSubjectsByCourse: () => ({ data: SUBJECTS }),
}));

import { ScheduleTestDialog } from "@/app/(dashboard)/test-portal/_components/schedule-test-dialog";

function setup(onSubmit = vi.fn().mockResolvedValue(undefined)) {
  render(<ScheduleTestDialog branchId="br1" onSubmit={onSubmit} isPending={false} />);
  return onSubmit;
}

beforeEach(() => vi.clearAllMocks());

describe("ScheduleTestDialog — per-subject flow", () => {
  it("creates a multi-batch, per-subject test with JEE question type", async () => {
    const user = userEvent.setup();
    const onSubmit = setup();
    await user.click(screen.getByRole("button", { name: /schedule test/i }));

    await user.type(screen.getByLabelText(/test name/i), "PCP Test");
    // Per-subject is the default mode. Pick both batches (one is JEE).
    await user.click(screen.getByRole("button", { name: "11th JEE", pressed: false }));
    await user.click(screen.getByRole("button", { name: "11th CET-1", pressed: false }));

    // JEE batch selected → Question type radios appear.
    const mcqNum = await screen.findByLabelText(/mcq \+ numerical/i);
    await user.click(mcqNum);

    // Select Physics + Chemistry (default 80 each).
    await user.click(screen.getByRole("button", { name: "Physics", pressed: false }));
    await user.click(screen.getByRole("button", { name: "Chemistry", pressed: false }));

    await user.click(screen.getByRole("button", { name: /^schedule$/i }));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    const payload = onSubmit.mock.calls[0][0];
    expect(payload.name).toBe("PCP Test");
    expect(payload.batch_ids).toEqual(["b-jee", "b-cet"]);
    expect(payload.subjects).toEqual([
      { subject_id: "phy", total_marks: 80 },
      { subject_id: "chem", total_marks: 80 },
    ]);
    expect(payload.question_type).toBe("MCQ_NUMERICAL");
    expect(payload.total_marks).toBe(160);
  });

  it("hides the Question type control when no JEE batch is selected", async () => {
    const user = userEvent.setup();
    setup();
    await user.click(screen.getByRole("button", { name: /schedule test/i }));
    await user.click(screen.getByRole("button", { name: "11th CET-1", pressed: false }));
    expect(screen.queryByLabelText(/mcq \+ numerical/i)).not.toBeInTheDocument();
  });

  it("OMR mode shows the single-batch select and OMR sheet type", async () => {
    const user = userEvent.setup();
    setup();
    await user.click(screen.getByRole("button", { name: /schedule test/i }));
    await user.click(screen.getByRole("button", { name: /omr scan/i }));
    expect(screen.getByLabelText(/^batch \*/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/omr sheet type/i)).toBeInTheDocument();
  });
});
