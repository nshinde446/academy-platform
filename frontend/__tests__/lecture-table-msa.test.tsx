import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  LectureTableMsa,
  groupStatus,
} from "@/app/(dashboard)/lectures/_components/lecture-table-msa";
import type {
  BatchSummary,
  LectureResponse,
  SubjectSummary,
  TeacherSummary,
  TopicSummary,
} from "@/app/(dashboard)/lectures/_schemas/lecture";

const BATCHES: BatchSummary[] = [
  { id: "b1", name: "NEET 2025 Batch A", code: "NEET-A", course_id: "c1" },
];
const TEACHERS: TeacherSummary[] = [
  { id: "t1", first_name: "Asha", last_name: "Kulkarni" },
  { id: "t2", first_name: "Rohan", last_name: "Patil" },
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
    scheduled_start: "2026-05-27T10:00:00Z",
    scheduled_end: "2026-05-27T11:00:00Z",
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
  onGenerateDpp: vi.fn(),
  onRecordMakeup: vi.fn(),
};

function renderTable(lectures: LectureResponse[]) {
  return render(
    <LectureTableMsa
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

describe("groupStatus", () => {
  it("collapses backend statuses into the 4 MSA groups", () => {
    expect(groupStatus("scheduled")).toBe("scheduled");
    expect(groupStatus("rescheduled")).toBe("scheduled");
    expect(groupStatus("started")).toBe("live");
    expect(groupStatus("paused")).toBe("live");
    expect(groupStatus("completed")).toBe("completed");
    expect(groupStatus("no_show")).toBe("no_show");
  });

  it("drops cancelled rows from the MSA view", () => {
    expect(groupStatus("cancelled")).toBeNull();
  });
});

describe("LectureTableMsa", () => {
  it("renders the MSA columns", () => {
    renderTable([]);

    expect(screen.getByText("When")).toBeInTheDocument();
    expect(screen.getByText("Teacher")).toBeInTheDocument();
    expect(screen.getByText("Batch · Subject")).toBeInTheDocument();
    expect(screen.getByText("Topic")).toBeInTheDocument();
    expect(screen.getByText("Status")).toBeInTheDocument();
    expect(screen.getByText("Quick action")).toBeInTheDocument();
  });

  it("scheduled row shows Start as the single Quick Action", () => {
    renderTable([makeLecture({ lecture_status: "scheduled" })]);

    expect(
      screen.getByRole("button", { name: /start lecture/i })
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /complete lecture/i })
    ).toBeNull();
    expect(
      screen.queryByRole("button", { name: /generate dpp/i })
    ).toBeNull();
  });

  it("started status maps to Live and shows Complete as Quick Action", () => {
    renderTable([makeLecture({ lecture_status: "started" })]);

    expect(screen.getByText("Live")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /complete lecture/i })
    ).toBeInTheDocument();
  });

  it("paused also maps to Live", () => {
    renderTable([makeLecture({ lecture_status: "paused" })]);
    expect(screen.getByText("Live")).toBeInTheDocument();
  });

  it("completed row shows Generate DPP as Quick Action", () => {
    renderTable([makeLecture({ lecture_status: "completed" })]);

    expect(screen.getByText("Completed")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /generate dpp for lecture/i })
    ).toBeInTheDocument();
  });

  it("no_show row shows Record makeup as Quick Action", () => {
    renderTable([makeLecture({ lecture_status: "no_show" })]);

    expect(screen.getByText("No-show")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /record makeup for lecture/i })
    ).toBeInTheDocument();
  });

  it("cancelled rows are dropped from the MSA table", () => {
    const { container } = renderTable([
      makeLecture({ id: "l1", lecture_status: "cancelled" }),
    ]);
    expect(container.querySelectorAll("tbody tr")).toHaveLength(0);
  });

  it("shows the substitute audit trail on the teacher column", () => {
    renderTable([
      makeLecture({
        lecture_status: "completed",
        actual_teacher_id: "t2",
        change_reason: "SUBSTITUTE",
      }),
    ]);

    // Original teacher rendered with strikethrough; substitute is primary.
    expect(screen.getByText("Asha Kulkarni")).toBeInTheDocument();
    expect(screen.getByText("Rohan Patil")).toBeInTheDocument();
    expect(screen.getByText(/by substitute/i)).toBeInTheDocument();
  });

  it("invokes onGenerateDpp with the row's lecture when clicked", async () => {
    const user = userEvent.setup();
    const l = makeLecture({ lecture_status: "completed" });
    renderTable([l]);

    await user.click(
      screen.getByRole("button", { name: /generate dpp for lecture/i })
    );
    expect(handlers.onGenerateDpp).toHaveBeenCalledWith(l);
  });

  it("invokes onRecordMakeup with the row's lecture when clicked", async () => {
    const user = userEvent.setup();
    const l = makeLecture({ lecture_status: "no_show" });
    renderTable([l]);

    await user.click(
      screen.getByRole("button", { name: /record makeup for lecture/i })
    );
    expect(handlers.onRecordMakeup).toHaveBeenCalledWith(l);
  });
});
