import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { SessionList } from "@/app/(dashboard)/lectures/_components/session-list";
import type {
  BatchSummary,
  LectureSessionResponse,
  SubjectSummary,
  TeacherSummary,
} from "@/app/(dashboard)/lectures/_schemas/lecture";

const batches: BatchSummary[] = [
  { id: "b1", name: "JEE-12-A", code: "J12A", course_id: "c1" },
];
const teachers: TeacherSummary[] = [
  { id: "t1", first_name: "Nitin", last_name: "Deshmukh" },
];
const subjects: SubjectSummary[] = [
  { id: "s1", name: "Physics", code: "PHY", course_id: "c1" },
];

function makeSessions(n: number): LectureSessionResponse[] {
  return Array.from({ length: n }, (_, i) => ({
    id: `sess-${i}`,
    teacher_id: "t1",
    subject_id: "s1",
    topic_id: null,
    classroom_id: null,
    actual_start: `2026-07-${String((i % 27) + 1).padStart(2, "0")}T09:00:00Z`,
    actual_end: `2026-07-${String((i % 27) + 1).padStart(2, "0")}T11:00:00Z`,
    delivery_mode: "offline",
    session_status: "completed",
    origin: "makeup",
    notes: `Session ${i} notes`,
    branch_id: "br1",
    academic_year_id: "ay1",
    batch_ids: ["b1"],
    lecture_ids: [],
    status: "active",
  }));
}

describe("SessionList", () => {
  it("renders nothing when there are no sessions", () => {
    const { container } = render(
      <SessionList
        sessions={[]}
        batches={batches}
        teachers={teachers}
        subjects={subjects}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("renders a table for a small number of sessions", () => {
    render(
      <SessionList
        sessions={makeSessions(3)}
        batches={batches}
        teachers={teachers}
        subjects={subjects}
      />,
    );
    // Table view, not the slider.
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(
      screen.queryByRole("group", { name: "Recorded sessions" }),
    ).not.toBeInTheDocument();
    expect(screen.getByText("3 sessions")).toBeInTheDocument();
  });

  it("switches to the card slider when the list is large", () => {
    render(
      <SessionList
        sessions={makeSessions(9)}
        batches={batches}
        teachers={teachers}
        subjects={subjects}
      />,
    );
    // Slider view, not the table.
    const slider = screen.getByRole("group", { name: "Recorded sessions" });
    expect(slider).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    // One card per session, and the paging controls exist.
    expect(within(slider).getAllByRole("article")).toHaveLength(9);
    expect(
      screen.getByRole("button", { name: "Next sessions" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Previous sessions" }),
    ).toBeInTheDocument();
    expect(screen.getByText("9 sessions")).toBeInTheDocument();
  });
});
