import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LectureTable } from "@/app/(dashboard)/lectures/_components/lecture-table";
import type {
  BatchSummary,
  LectureResponse,
  SubjectSummary,
  TeacherSummary,
  TopicSummary,
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
const TOPICS: TopicSummary[] = [
  { id: "tp1", name: "Newton's Laws", chapter_id: "ch1" },
];

function makeLecture(over: Partial<LectureResponse> = {}): LectureResponse {
  return {
    id: "l1",
    teacher_id: "t1",
    batch_id: "b1",
    classroom_id: null,
    subject_id: "s1",
    topic_id: "tp1",
    scheduled_start: "2026-05-20T10:00:00Z",
    scheduled_end: "2026-05-20T11:00:00Z",
    actual_start: null,
    actual_end: null,
    delivery_mode: "online",
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

const handlers = {
  onStart: vi.fn(),
  onComplete: vi.fn(),
  onCancel: vi.fn(),
  onDelete: vi.fn(),
  onSubstitute: vi.fn(),
  onNoShow: vi.fn(),
};

function renderTable(lectures: LectureResponse[]) {
  return render(
    <LectureTable
      lectures={lectures}
      batches={BATCHES}
      teachers={TEACHERS}
      subjects={SUBJECTS}
      topics={TOPICS}
      {...handlers}
    />
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("LectureTable", () => {
  it("renders table headers", () => {
    renderTable([]);

    expect(screen.getByText("Batch")).toBeInTheDocument();
    expect(screen.getByText("Teacher")).toBeInTheDocument();
    expect(screen.getByText("Subject")).toBeInTheDocument();
    expect(screen.getByText("Topic")).toBeInTheDocument();
    expect(screen.getByText("Scheduled Start")).toBeInTheDocument();
    expect(screen.getByText("Status")).toBeInTheDocument();
    expect(screen.getByText("Actions")).toBeInTheDocument();
  });

  it("renders looked-up batch, teacher, subject, topic", () => {
    renderTable([makeLecture()]);

    expect(screen.getByText("NEET 2025-A")).toBeInTheDocument();
    expect(screen.getByText("Asha Kulkarni")).toBeInTheDocument();
    expect(screen.getByText("Physics")).toBeInTheDocument();
    expect(screen.getByText("Newton's Laws")).toBeInTheDocument();
  });

  it("scheduled status shows Start + Cancel + Delete + Attendance, not Complete", () => {
    renderTable([makeLecture({ lecture_status: "scheduled" })]);

    expect(
      screen.getByRole("button", { name: /start lecture/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /cancel lecture/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /delete lecture/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /view attendance/i })
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /complete lecture/i })
    ).toBeNull();
  });

  it("started status shows Complete + Cancel, not Start", () => {
    renderTable([makeLecture({ lecture_status: "started" })]);

    expect(
      screen.queryByRole("button", { name: /^start lecture/i })
    ).toBeNull();
    expect(
      screen.getByRole("button", { name: /complete lecture/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /cancel lecture/i })
    ).toBeInTheDocument();
  });

  it("completed status shows only Delete + Attendance", () => {
    renderTable([makeLecture({ lecture_status: "completed" })]);

    expect(
      screen.queryByRole("button", { name: /start lecture/i })
    ).toBeNull();
    expect(
      screen.queryByRole("button", { name: /complete lecture/i })
    ).toBeNull();
    expect(
      screen.queryByRole("button", { name: /cancel lecture/i })
    ).toBeNull();
    expect(
      screen.getByRole("button", { name: /delete lecture/i })
    ).toBeInTheDocument();
  });

  it("Attendance link uses /attendance?lecture_id={id}", () => {
    renderTable([makeLecture()]);

    const link = screen.getByRole("link", { name: /view attendance/i });
    expect(link.getAttribute("href")).toBe("/attendance?lecture_id=l1");
  });

  it("invokes onStart/onCancel/onDelete with the row's lecture", async () => {
    const user = userEvent.setup();
    const l = makeLecture({ lecture_status: "scheduled" });
    renderTable([l]);

    await user.click(screen.getByRole("button", { name: /start lecture/i }));
    expect(handlers.onStart).toHaveBeenCalledWith(l);

    await user.click(screen.getByRole("button", { name: /cancel lecture/i }));
    expect(handlers.onCancel).toHaveBeenCalledWith(l);

    await user.click(screen.getByRole("button", { name: /delete lecture/i }));
    expect(handlers.onDelete).toHaveBeenCalledWith(l);
  });

  it("renders em-dashes when lookups miss", () => {
    renderTable([
      makeLecture({
        batch_id: "missing",
        teacher_id: "missing",
        subject_id: "missing",
        topic_id: null,
      }),
    ]);
    // Multiple "—" cells expected.
    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBeGreaterThanOrEqual(3);
  });

  it("renders empty tbody when no lectures", () => {
    const { container } = renderTable([]);
    const rows = container.querySelectorAll("tbody tr");
    expect(rows).toHaveLength(0);
  });
});
