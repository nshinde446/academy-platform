import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TimetableDialog } from "@/app/(dashboard)/lectures/_components/timetable-dialog";
import type {
  BatchSummary,
  ClassroomSummary,
  TeacherSummary,
} from "@/app/(dashboard)/lectures/_schemas/lecture";
import apiClient from "@/services/api-client";

vi.mock("@/services/api-client", () => ({
  default: { get: vi.fn(), put: vi.fn(), post: vi.fn() },
}));

const BATCHES: BatchSummary[] = [
  { id: "b1", name: "NEET 2025-A", code: "NEET-A", course_id: "c1" },
];
const TEACHERS: TeacherSummary[] = [
  { id: "t1", first_name: "Asha", last_name: "Kulkarni" },
];
const CLASSROOMS: ClassroomSummary[] = [
  { id: "r1", name: "Room 101", code: "R101", capacity: 40 },
];

function withQuery(ui: React.ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{ui}</QueryClientProvider>;
}

beforeEach(() => {
  vi.clearAllMocks();
  (apiClient.get as ReturnType<typeof vi.fn>).mockImplementation(
    (url: string) => {
      // Subject→Teacher lock: teachers come from the by-subject endpoint.
      if (url.includes("/teachers/by-subject"))
        return Promise.resolve({ data: TEACHERS });
      if (url.includes("/timetable")) return Promise.resolve({ data: [] });
      if (url.includes("/subjects"))
        return Promise.resolve({
          data: [{ id: "s1", name: "Physics", code: "PHY", course_id: "c1" }],
        });
      return Promise.resolve({ data: [] });
    }
  );
  (apiClient.put as ReturnType<typeof vi.fn>).mockResolvedValue({ data: [] });
});

function renderDialog() {
  return render(
    withQuery(
      <TimetableDialog
        branchId="br1"
        batches={BATCHES}
        teachers={TEACHERS}
        classrooms={CLASSROOMS}
      />
    )
  );
}

describe("TimetableDialog", () => {
  it("renders the trigger button", () => {
    renderDialog();
    expect(
      screen.getByRole("button", { name: "Weekly Timetable" })
    ).toBeInTheDocument();
  });

  it("controlled mode: hideTrigger drops the trigger and `open` drives the dialog", async () => {
    // Closed + hidden trigger → nothing rendered (the page's Manage menu owns it).
    const { rerender } = render(
      withQuery(
        <TimetableDialog
          branchId="br1"
          batches={BATCHES}
          teachers={TEACHERS}
          classrooms={CLASSROOMS}
          hideTrigger
          open={false}
          onOpenChange={() => {}}
        />
      )
    );
    expect(
      screen.queryByRole("button", { name: "Weekly Timetable" })
    ).toBeNull();
    expect(screen.queryByRole("dialog")).toBeNull();

    // Flip `open` → the dialog appears without any trigger click.
    rerender(
      withQuery(
        <TimetableDialog
          branchId="br1"
          batches={BATCHES}
          teachers={TEACHERS}
          classrooms={CLASSROOMS}
          hideTrigger
          open
          onOpenChange={() => {}}
        />
      )
    );
    await screen.findByLabelText("Batch *");
  });

  it("shows the slot editor once a batch is picked, and can add a slot", async () => {
    const user = userEvent.setup();
    renderDialog();

    await user.click(screen.getByRole("button", { name: "Weekly Timetable" }));
    // Pick the batch.
    const batchSelect = await screen.findByLabelText("Batch *");
    await user.selectOptions(batchSelect, "b1");

    // No slots yet, then add one.
    expect(screen.queryAllByTestId("timetable-slot")).toHaveLength(0);
    await user.click(screen.getByRole("button", { name: "+ Add slot" }));
    expect(screen.getAllByTestId("timetable-slot")).toHaveLength(1);
  });

  it("saves the timetable via PUT", async () => {
    const user = userEvent.setup();
    renderDialog();

    await user.click(screen.getByRole("button", { name: "Weekly Timetable" }));
    const batchSelect = await screen.findByLabelText("Batch *");
    await user.selectOptions(batchSelect, "b1");
    await user.click(screen.getByRole("button", { name: "+ Add slot" }));

    // Pick subject → the teacher dropdown loads only that subject's teachers.
    await user.selectOptions(screen.getByLabelText("Subject for slot 1"), "s1");
    // Wait for the subject-scoped teacher option to arrive before selecting.
    await screen.findByRole("option", { name: /Asha Kulkarni/ });
    await user.selectOptions(screen.getByLabelText("Teacher for slot 1"), "t1");

    await user.click(screen.getByRole("button", { name: "Save timetable" }));

    await waitFor(() => {
      expect(apiClient.put).toHaveBeenCalledWith(
        "/api/v1/lectures/timetable",
        { slots: expect.arrayContaining([expect.objectContaining({ subject_id: "s1", teacher_id: "t1" })]) },
        { params: { branch_id: "br1", batch_id: "b1" } }
      );
    });
  });

  it("disables the teacher dropdown until a subject is chosen (Subject→Teacher lock)", async () => {
    const user = userEvent.setup();
    renderDialog();
    await user.click(screen.getByRole("button", { name: "Weekly Timetable" }));
    await user.selectOptions(await screen.findByLabelText("Batch *"), "b1");
    await user.click(screen.getByRole("button", { name: "+ Add slot" }));

    // No subject yet → teacher dropdown is disabled, no teacher options.
    expect(screen.getByLabelText("Teacher for slot 1")).toBeDisabled();
    expect(
      screen.queryByRole("option", { name: /Asha Kulkarni/ })
    ).toBeNull();

    // Pick subject → teacher dropdown enables and lists the subject's teachers.
    await user.selectOptions(screen.getByLabelText("Subject for slot 1"), "s1");
    await screen.findByRole("option", { name: /Asha Kulkarni/ });
    expect(screen.getByLabelText("Teacher for slot 1")).not.toBeDisabled();
  });
});
