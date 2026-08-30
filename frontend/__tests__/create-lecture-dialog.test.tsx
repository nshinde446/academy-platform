import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";
import { CreateLectureDialog } from "@/app/(dashboard)/lectures/_components/create-lecture-dialog";
import type {
  BatchSummary,
  TeacherSummary,
} from "@/app/(dashboard)/lectures/_schemas/lecture";
import apiClient from "@/services/api-client";

vi.mock("@/services/api-client", () => ({
  default: { get: vi.fn() },
}));

const BATCHES: BatchSummary[] = [
  { id: "b1", name: "NEET 2025-A", code: "NEET-A", course_id: "c1" },
];
const TEACHERS: TeacherSummary[] = [
  { id: "t1", first_name: "Asha", last_name: "Kulkarni" },
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
      if (url.includes("/subjects")) {
        return Promise.resolve({
          data: [
            { id: "s1", name: "Physics", code: "PHY", course_id: "c1" },
          ],
        });
      }
      if (url.includes("/topics")) {
        return Promise.resolve({
          data: [{ id: "tp1", name: "Newton's Laws", chapter_id: "ch1" }],
        });
      }
      // Subject→Teacher lock: teachers are loaded scoped to the picked subject.
      if (url.includes("/teachers/by-subject")) {
        return Promise.resolve({ data: TEACHERS });
      }
      return Promise.resolve({ data: [] });
    }
  );
});

describe("CreateLectureDialog", () => {
  it("renders the trigger button", () => {
    const onSubmit = vi.fn();
    render(
      withQuery(
        <CreateLectureDialog
          branchId="br1"
          batches={BATCHES}
          classrooms={[]}
          onSubmit={onSubmit}
          isPending={false}
        />
      )
    );
    expect(
      screen.getByRole("button", { name: /schedule lecture/i })
    ).toBeInTheDocument();
  });

  it("subject dropdown is disabled until a batch is picked", async () => {
    const user = userEvent.setup();
    render(
      withQuery(
        <CreateLectureDialog
          branchId="br1"
          batches={BATCHES}
          classrooms={[]}
          onSubmit={vi.fn()}
          isPending={false}
        />
      )
    );

    await user.click(
      screen.getByRole("button", { name: /schedule lecture/i })
    );
    const subjectSelect = screen.getByLabelText(/^subject \*/i);
    expect(subjectSelect).toBeDisabled();
  });

  it("loading subjects for the batch's course enables the subject dropdown", async () => {
    const user = userEvent.setup();
    render(
      withQuery(
        <CreateLectureDialog
          branchId="br1"
          batches={BATCHES}
          classrooms={[]}
          onSubmit={vi.fn()}
          isPending={false}
        />
      )
    );

    await user.click(
      screen.getByRole("button", { name: /schedule lecture/i })
    );

    const batchSelect = screen.getByLabelText(/^batch \*/i);
    await user.selectOptions(batchSelect, "b1");

    await waitFor(() => {
      expect(screen.getByLabelText(/^subject \*/i)).not.toBeDisabled();
    });

    // It also called the subjects endpoint with the batch's course_id.
    expect(apiClient.get).toHaveBeenCalledWith(
      "/api/v1/academic/subjects",
      expect.objectContaining({
        params: { branch_id: "br1", course_id: "c1" },
      })
    );
  });

  it("picking a subject enables the topic dropdown and calls topics endpoint with subject_id", async () => {
    const user = userEvent.setup();
    render(
      withQuery(
        <CreateLectureDialog
          branchId="br1"
          batches={BATCHES}
          classrooms={[]}
          onSubmit={vi.fn()}
          isPending={false}
        />
      )
    );

    await user.click(
      screen.getByRole("button", { name: /schedule lecture/i })
    );

    await user.selectOptions(screen.getByLabelText(/^batch \*/i), "b1");
    await waitFor(() => {
      expect(screen.getByLabelText(/^subject \*/i)).not.toBeDisabled();
    });

    await user.selectOptions(screen.getByLabelText(/^subject \*/i), "s1");
    await waitFor(() => {
      expect(screen.getByLabelText(/^topic$/i)).not.toBeDisabled();
    });

    expect(apiClient.get).toHaveBeenCalledWith(
      "/api/v1/academic/topics",
      expect.objectContaining({
        params: { branch_id: "br1", subject_id: "s1" },
      })
    );
  });

  it("submits a complete payload to onSubmit", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(
      withQuery(
        <CreateLectureDialog
          branchId="br1"
          batches={BATCHES}
          classrooms={[]}
          onSubmit={onSubmit}
          isPending={false}
        />
      )
    );

    await user.click(
      screen.getByRole("button", { name: /schedule lecture/i })
    );

    await user.selectOptions(screen.getByLabelText(/^batch \*/i), "b1");

    await waitFor(() => {
      expect(screen.getByLabelText(/^subject \*/i)).not.toBeDisabled();
    });
    await user.selectOptions(screen.getByLabelText(/^subject \*/i), "s1");

    // Teacher is subject-scoped — enabled only after the subject loads it.
    await waitFor(() => {
      expect(screen.getByLabelText(/^teacher \*/i)).not.toBeDisabled();
    });
    await user.selectOptions(screen.getByLabelText(/^teacher \*/i), "t1");

    // Start is a split date + typeable time select now (no minute spinner).
    fireEvent.change(screen.getByLabelText("Scheduled start date"), {
      target: { value: "2026-05-20" },
    });
    await user.selectOptions(
      screen.getByLabelText("Scheduled start time"),
      "10:00"
    );
    // End set in one tap via a duration preset (start + 1h).
    await user.click(screen.getByRole("button", { name: "1h" }));

    await user.click(screen.getByRole("button", { name: /^schedule$/i }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledTimes(1);
    });
    const payload = onSubmit.mock.calls[0][0];
    expect(payload).toMatchObject({
      batch_id: "b1",
      teacher_id: "t1",
      subject_id: "s1",
      delivery_mode: "online",
    });
    expect(payload.scheduled_start).toMatch(/^\d{4}-\d{2}-\d{2}T/);
    expect(payload.scheduled_end).toMatch(/^\d{4}-\d{2}-\d{2}T/);
  });
});
