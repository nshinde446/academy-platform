import { describe, it, expect, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MarkSubstituteDialog } from "@/app/(dashboard)/lectures/_components/mark-substitute-dialog";
import type {
  EligibleSubstitute,
  LectureResponse,
  TeacherSummary,
} from "@/app/(dashboard)/lectures/_schemas/lecture";

// The dialog restricts its picker to the backend's eligible set. Mock that hook
// so we can drive the same-subject vs cross-subject candidates directly, keying
// off the allowCrossSubject arg the dialog passes.
const eligibleMock = vi.fn();
vi.mock("@/app/(dashboard)/lectures/_hooks/use-lectures", () => ({
  useEligibleSubstitutes: (...args: unknown[]) => eligibleMock(...args),
}));

const T1: TeacherSummary = { id: "t1", first_name: "Sched", last_name: "Uled" };
const T2: TeacherSummary = { id: "t2", first_name: "Same", last_name: "Subject" };
const T3: TeacherSummary = { id: "t3", first_name: "Cross", last_name: "Cover" };
const TEACHERS = [T1, T2, T3];

const SAME: EligibleSubstitute = {
  teacher_id: "t2",
  first_name: "Same",
  last_name: "Subject",
  same_subject: true,
  subjects: ["Maths"],
};
const CROSS: EligibleSubstitute = {
  teacher_id: "t3",
  first_name: "Cross",
  last_name: "Cover",
  same_subject: false,
  subjects: ["Physics"],
};

const LECTURE = {
  id: "lec1",
  teacher_id: "t1",
  actual_teacher_id: null,
  change_reason: null,
  change_notes: null,
  subject_id: "subjMaths",
} as unknown as LectureResponse;

// The 4th arg (allowCrossSubject) decides which candidates come back.
function wireEligible() {
  eligibleMock.mockImplementation(
    (_b: unknown, _l: unknown, _open: unknown, allowCross: boolean) => ({
      data: allowCross ? [SAME, CROSS] : [SAME],
      isSuccess: true,
    }),
  );
}

describe("MarkSubstituteDialog — cross-subject", () => {
  beforeEach(() => {
    eligibleMock.mockReset();
    wireEligible();
  });

  it("hides other-subject teachers until the toggle is on", () => {
    render(
      <MarkSubstituteDialog
        lecture={LECTURE}
        teachers={TEACHERS}
        branchId="br1"
        open
        onOpenChange={() => {}}
        onSubmit={vi.fn()}
        isPending={false}
      />,
    );
    // Same-subject teacher is offered; cross-subject one is not (toggle off).
    expect(screen.getByRole("option", { name: /Same Subject/ })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: /Cross Cover/ })).toBeNull();
  });

  it("reveals other-subject teachers (labelled) when the toggle is ticked", () => {
    render(
      <MarkSubstituteDialog
        lecture={LECTURE}
        teachers={TEACHERS}
        branchId="br1"
        open
        onOpenChange={() => {}}
        onSubmit={vi.fn()}
        isPending={false}
      />,
    );
    fireEvent.click(
      screen.getByRole("checkbox", { name: /Allow teachers from other subjects/ }),
    );
    const opt = screen.getByRole("option", { name: /Cross Cover/ });
    expect(opt).toBeInTheDocument();
    // Labelled with the subject they actually teach.
    expect(opt.textContent).toMatch(/Physics \(other subject\)/);
  });

  it("submits allow_cross_subject=true when a cross-subject teacher is picked", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(
      <MarkSubstituteDialog
        lecture={LECTURE}
        teachers={TEACHERS}
        branchId="br1"
        open
        onOpenChange={() => {}}
        onSubmit={onSubmit}
        isPending={false}
      />,
    );
    fireEvent.click(
      screen.getByRole("checkbox", { name: /Allow teachers from other subjects/ }),
    );
    fireEvent.change(screen.getByLabelText(/Actual teacher/), {
      target: { value: "t3" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^Save$/ }));

    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          actual_teacher_id: "t3",
          allow_cross_subject: true,
        }),
      ),
    );
  });
});
