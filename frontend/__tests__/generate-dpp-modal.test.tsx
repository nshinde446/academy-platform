import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { GenerateDppModal } from "@/app/(dashboard)/lectures/_components/generate-dpp-modal";
import type {
  BatchSummary,
  LectureResponse,
  SubjectSummary,
  TopicSummary,
} from "@/app/(dashboard)/lectures/_schemas/lecture";

const push = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

const BATCHES: BatchSummary[] = [
  { id: "b1", name: "NEET 2025 Batch A", code: "NEET-A", course_id: "c1" },
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
    late_flag: null,
    actual_duration_min: null,
    delivery_mode: "online",
    lecture_status: "completed",
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

beforeEach(() => {
  push.mockClear();
});

function renderModal(lecture: LectureResponse | null, open = true) {
  const onOpenChange = vi.fn();
  return {
    onOpenChange,
    ...render(
      <GenerateDppModal
        lecture={lecture}
        batches={BATCHES}
        subjects={SUBJECTS}
        topics={TOPICS}
        open={open}
        onOpenChange={onOpenChange}
      />
    ),
  };
}

describe("GenerateDppModal", () => {
  it("prefills name with the lecture's topic", () => {
    renderModal(makeLecture());
    const nameInput = screen.getByLabelText(/draft name/i) as HTMLInputElement;
    expect(nameInput.value).toContain("Newton's Laws");
  });

  it("shows the lecture summary (subject, batch, topic)", () => {
    renderModal(makeLecture());
    expect(screen.getByText("Physics")).toBeInTheDocument();
    expect(screen.getByText("NEET 2025 Batch A")).toBeInTheDocument();
    expect(screen.getByText("Newton's Laws")).toBeInTheDocument();
  });

  it("navigates to /papers with the prefill query params on submit", async () => {
    const user = userEvent.setup();
    const { onOpenChange } = renderModal(makeLecture());

    await user.click(
      screen.getByRole("button", { name: /open composer with this lecture/i })
    );

    expect(push).toHaveBeenCalledTimes(1);
    const url = push.mock.calls[0][0] as string;
    expect(url).toMatch(/^\/papers\?/);
    expect(url).toContain("paper_type=DPP");
    expect(url).toContain("batch_id=b1");
    expect(url).toContain("subject_id=s1");
    expect(url).toContain("source_lecture_id=l1");
    expect(url).toContain("name=");
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("disables submit when no lecture is bound", () => {
    renderModal(null);
    expect(
      screen.getByRole("button", { name: /open composer with this lecture/i })
    ).toBeDisabled();
  });

  it("respects user-edited number of questions and lean in the URL", async () => {
    const user = userEvent.setup();
    renderModal(makeLecture());

    const numInput = screen.getByLabelText(/number of qs/i);
    await user.clear(numInput);
    await user.type(numInput, "20");

    const leanSelect = screen.getByLabelText(/lean toward/i);
    await user.selectOptions(leanSelect, "stretch");

    await user.click(
      screen.getByRole("button", { name: /open composer with this lecture/i })
    );

    const url = push.mock.calls[0][0] as string;
    expect(url).toContain("num_qs=20");
    expect(url).toContain("lean=stretch");
  });
});
