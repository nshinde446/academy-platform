import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MakeupQueuePanel } from "@/app/(dashboard)/lectures/_components/makeup-queue-panel";
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
    lecture_status: "cancelled",
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

describe("MakeupQueuePanel", () => {
  it("renders nothing when nothing is owed a makeup", () => {
    const { container } = render(
      <MakeupQueuePanel
        lectures={[]}
        batches={BATCHES}
        teachers={TEACHERS}
        subjects={SUBJECTS}
        onRecordMakeup={vi.fn()}
      />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("lists missed lectures and fires onRecordMakeup", async () => {
    const user = userEvent.setup();
    const onRecordMakeup = vi.fn();
    const cancelled = makeLecture();
    const noShow = makeLecture({
      id: "l2",
      lecture_status: "no_show",
      no_show_reason: "TEACHER_NO_SHOW",
    });
    render(
      <MakeupQueuePanel
        lectures={[cancelled, noShow]}
        batches={BATCHES}
        teachers={TEACHERS}
        subjects={SUBJECTS}
        onRecordMakeup={onRecordMakeup}
      />
    );
    expect(
      screen.getByText(/2 lectures need a makeup/i)
    ).toBeInTheDocument();
    const panel = screen.getByTestId("makeup-queue-panel");
    expect(panel).toHaveTextContent("cancelled");
    expect(panel).toHaveTextContent("no-show · teacher");

    await user.click(
      screen.getAllByRole("button", { name: /record makeup/i })[0]
    );
    expect(onRecordMakeup).toHaveBeenCalledWith(cancelled);
  });
});
