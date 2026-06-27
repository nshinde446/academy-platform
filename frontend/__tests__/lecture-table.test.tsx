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
    late_flag: null,
    actual_duration_min: null,
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
  onActuals: vi.fn(),
  onGenerateDpp: vi.fn(),
  onRecordMakeup: vi.fn(),
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
    expect(screen.getByText("Scheduled")).toBeInTheDocument();
    expect(screen.getByText("Actual")).toBeInTheDocument();
    expect(screen.getByText("Duration")).toBeInTheDocument();
    expect(screen.getByText("Status")).toBeInTheDocument();
    expect(screen.getByText("Actions")).toBeInTheDocument();
  });

  it("shows scheduled end time and actual window + duration", () => {
    renderTable([
      makeLecture({
        lecture_status: "completed",
        actual_start: "2026-05-20T10:05:00Z",
        actual_end: "2026-05-20T11:02:00Z",
        actual_duration_min: 57,
      }),
    ]);
    // Duration renders in its own column (and a small-screen echo).
    expect(screen.getAllByText("57m").length).toBeGreaterThanOrEqual(1);
  });

  it("renders looked-up batch, teacher, subject, topic", () => {
    renderTable([makeLecture()]);

    expect(screen.getByText("NEET 2025-A")).toBeInTheDocument();
    expect(screen.getByText("Asha Kulkarni")).toBeInTheDocument();
    expect(screen.getByText("Physics")).toBeInTheDocument();
    expect(screen.getByText("Newton's Laws")).toBeInTheDocument();
  });

  async function openMenu(user: ReturnType<typeof userEvent.setup>) {
    await user.click(
      screen.getByRole("button", { name: /more actions for lecture/i })
    );
    // The Base UI menu mounts asynchronously — wait for the popup to appear.
    await screen.findByRole("menu");
  }

  it("scheduled (past): Start is the quick-action; menu has Cancel, not Start", async () => {
    const user = userEvent.setup();
    renderTable([makeLecture({ lecture_status: "scheduled" })]); // 2026-05-20, past
    // Quick action + separate Delete, both outside the overflow.
    expect(screen.getByRole("button", { name: "Start" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /delete lecture/i })
    ).toBeInTheDocument();
    await openMenu(user);
    expect(screen.getByRole("menuitem", { name: "Cancel" })).toBeInTheDocument();
    expect(
      screen.getByRole("menuitem", { name: "Attendance" })
    ).toBeInTheDocument();
    // Start is the primary, so it's not duplicated in the overflow.
    expect(screen.queryByRole("menuitem", { name: "Start" })).toBeNull();
  });

  it("started: Complete is the quick-action; menu keeps Cancel, not Complete", async () => {
    const user = userEvent.setup();
    renderTable([makeLecture({ lecture_status: "started" })]);
    expect(screen.getByRole("button", { name: "Complete" })).toBeInTheDocument();
    await openMenu(user);
    expect(screen.getByRole("menuitem", { name: "Cancel" })).toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: "Complete" })).toBeNull();
    expect(screen.queryByRole("menuitem", { name: "Start" })).toBeNull();
  });

  it("completed: Generate DPP is the quick-action; no Start/Complete/Cancel in menu", async () => {
    const user = userEvent.setup();
    renderTable([makeLecture({ lecture_status: "completed" })]);
    expect(
      screen.getByRole("button", { name: /generate dpp/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /delete lecture/i })
    ).toBeInTheDocument();
    await openMenu(user);
    expect(screen.queryByRole("menuitem", { name: "Start" })).toBeNull();
    expect(screen.queryByRole("menuitem", { name: "Complete" })).toBeNull();
    expect(screen.queryByRole("menuitem", { name: "Cancel" })).toBeNull();
  });

  it("no-show: Record makeup is the quick-action", async () => {
    const user = userEvent.setup();
    renderTable([
      makeLecture({ lecture_status: "no_show", no_show_reason: "EXTERNAL" }),
    ]);
    expect(
      screen.getByRole("button", { name: /record makeup/i })
    ).toBeInTheDocument();
  });

  it("Attendance menuitem links to /attendance?lecture_id={id}", async () => {
    const user = userEvent.setup();
    renderTable([makeLecture()]);
    await openMenu(user);
    const item = screen.getByRole("menuitem", { name: "Attendance" });
    expect(item.getAttribute("href")).toBe("/attendance?lecture_id=l1");
  });

  it("invokes onStart (quick action), onCancel (menu), onDelete (button)", async () => {
    const user = userEvent.setup();
    const l = makeLecture({ lecture_status: "scheduled" });
    renderTable([l]);

    await user.click(screen.getByRole("button", { name: "Start" }));
    expect(handlers.onStart).toHaveBeenCalledWith(l);

    await openMenu(user);
    await user.click(screen.getByRole("menuitem", { name: "Cancel" }));
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

  it("renders selection checkboxes and toggles a row when selectable", async () => {
    const user = userEvent.setup();
    const onToggleSelect = vi.fn();
    const l = makeLecture();
    render(
      <LectureTable
        lectures={[l]}
        batches={BATCHES}
        teachers={TEACHERS}
        subjects={SUBJECTS}
        topics={TOPICS}
        selectedIds={new Set()}
        onToggleSelect={onToggleSelect}
        onToggleAll={vi.fn()}
        {...handlers}
      />
    );
    const rowCb = screen.getByRole("checkbox", { name: /select lecture l1/i });
    await user.click(rowCb);
    expect(onToggleSelect).toHaveBeenCalledWith("l1");
  });

  it("future-dated lecture: Plan topic is the quick-action (no End of day)", async () => {
    const user = userEvent.setup();
    const future = new Date();
    future.setFullYear(future.getFullYear() + 1);
    const iso = future.toISOString();
    renderTable([
      makeLecture({
        scheduled_start: iso,
        scheduled_end: iso,
        lecture_status: "scheduled",
      }),
    ]);
    expect(
      screen.getByRole("button", { name: "Plan topic" })
    ).toBeInTheDocument();
    await openMenu(user);
    // The actuals/plan action is the primary, so not duplicated in the menu.
    expect(screen.queryByRole("menuitem", { name: "End of day" })).toBeNull();
    expect(screen.queryByRole("menuitem", { name: "Plan topic" })).toBeNull();
  });

  it("past-dated lecture: Start is the quick-action; menu offers End of day", async () => {
    const user = userEvent.setup();
    renderTable([
      makeLecture({
        scheduled_start: "2020-01-01T09:00:00Z",
        scheduled_end: "2020-01-01T10:00:00Z",
        lecture_status: "scheduled",
      }),
    ]);
    expect(screen.getByRole("button", { name: "Start" })).toBeInTheDocument();
    await openMenu(user);
    expect(
      screen.getByRole("menuitem", { name: "End of day" })
    ).toBeInTheDocument();
  });

  it("sorts rows when a column header is clicked", async () => {
    const user = userEvent.setup();
    const batches = [
      { id: "bz", name: "Zeta", code: "Z", course_id: "c1" },
      { id: "ba", name: "Alpha", code: "A", course_id: "c1" },
    ];
    const l1 = makeLecture({
      id: "l1",
      batch_id: "bz",
      scheduled_start: "2026-05-21T10:00:00Z",
    });
    const l2 = makeLecture({
      id: "l2",
      batch_id: "ba",
      scheduled_start: "2026-05-20T10:00:00Z",
    });
    render(
      <LectureTable
        lectures={[l1, l2]}
        batches={batches}
        teachers={TEACHERS}
        subjects={SUBJECTS}
        topics={TOPICS}
        {...handlers}
      />
    );
    // Default sort is scheduled desc → 05-21 (Zeta) row first.
    expect(screen.getAllByRole("row")[1]).toHaveTextContent("Zeta");
    // Click Batch → ascending by name → Alpha first.
    await user.click(screen.getByRole("button", { name: /sort by batch/i }));
    expect(screen.getAllByRole("row")[1]).toHaveTextContent("Alpha");
  });

  it("renders no checkbox column when selection props are omitted", () => {
    renderTable([makeLecture()]);
    expect(
      screen.queryByRole("checkbox", { name: /select all lectures/i })
    ).toBeNull();
  });
});
