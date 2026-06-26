import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PendingActualsPanel } from "@/app/(dashboard)/lectures/_components/pending-actuals-panel";
import type {
  BatchSummary,
  LectureResponse,
  SubjectSummary,
  TeacherSummary,
} from "@/app/(dashboard)/lectures/_schemas/lecture";

const BATCHES: BatchSummary[] = [
  { id: "b1", name: "NEET 2025-A", code: "NEET-A", course_id: "c1" },
];
const TEACHERS: TeacherSummary[] = [
  { id: "t1", first_name: "Asha", last_name: "Kulkarni" },
];
const SUBJECTS: SubjectSummary[] = [
  { id: "s1", name: "Physics", code: "PHY", course_id: "c1" },
];

function makeLecture(over: Partial<LectureResponse> = {}): LectureResponse {
  return {
    id: "l1",
    teacher_id: "t1",
    batch_id: "b1",
    classroom_id: null,
    subject_id: "s1",
    topic_id: null,
    scheduled_start: "2026-05-20T10:00:00Z",
    scheduled_end: "2026-05-20T11:00:00Z",
    actual_start: null,
    actual_end: null,
    late_flag: null,
    actual_duration_min: null,
    delivery_mode: "offline",
    lecture_status: "scheduled",
    notes: null,
    actual_teacher_id: null,
    change_reason: null,
    change_notes: null,
    no_show_reason: null,
    branch_id: "br1",
    academic_year_id: "ay1",
    status: "active",
    ...over,
  };
}

describe("PendingActualsPanel", () => {
  it("renders nothing when there is no backlog", () => {
    const { container } = render(
      <PendingActualsPanel
        lectures={[]}
        batches={BATCHES}
        teachers={TEACHERS}
        subjects={SUBJECTS}
        onActuals={vi.fn()}
      />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("lists overdue lectures and fires onActuals from the row button", async () => {
    const user = userEvent.setup();
    const onActuals = vi.fn();
    const l = makeLecture();
    render(
      <PendingActualsPanel
        lectures={[l]}
        batches={BATCHES}
        teachers={TEACHERS}
        subjects={SUBJECTS}
        onActuals={onActuals}
      />
    );
    expect(
      screen.getByText(/1 lecture needs an end-of-day update/i)
    ).toBeInTheDocument();
    const panel = screen.getByTestId("pending-actuals-panel");
    expect(panel).toHaveTextContent("NEET 2025-A");
    expect(panel).toHaveTextContent("Physics");
    expect(panel).toHaveTextContent("Asha Kulkarni");

    await user.click(
      screen.getByRole("button", { name: /record end-of-day actuals/i })
    );
    expect(onActuals).toHaveBeenCalledWith(l);
  });
});
