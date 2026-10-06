import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SecondarySubjects } from "@/app/(dashboard)/teachers/_components/secondary-subjects";

const catalogMock = vi.fn();
const rowsMock = vi.fn();
const assignMock = vi.fn();
const removeMock = vi.fn();
const batchesMock = vi.fn();

vi.mock("@/app/(dashboard)/teachers/_hooks/use-secondary-subjects", () => ({
  useSubjectCatalog: () => catalogMock(),
  useSecondaryForTeacher: () => rowsMock(),
  useAssignSecondarySubjects: () => ({ mutateAsync: assignMock, isPending: false }),
  useRemoveSecondarySubject: () => ({ mutate: removeMock, isPending: false }),
}));

vi.mock("@/app/(dashboard)/batches/_hooks/use-batches", () => ({
  useBatches: () => batchesMock(),
}));

beforeEach(() => {
  vi.clearAllMocks();
  catalogMock.mockReturnValue({
    data: ["Physics", "IT", "Marathi", "English"],
  });
  batchesMock.mockReturnValue({
    data: [
      { id: "bD", name: "Batch D", code: "BD" },
      { id: "bE", name: "Batch E", code: "BE" },
      { id: "bA", name: "Batch A", code: "BA" },
    ],
  });
  rowsMock.mockReturnValue({ data: [] });
  assignMock.mockResolvedValue([]);
});

function renderIt() {
  return render(<SecondarySubjects branchId="br1" teacherId="t1" />);
}

describe("SecondarySubjects", () => {
  it("shows the empty state when the teacher has no secondary subjects", () => {
    renderIt();
    expect(
      screen.getByText(/teaches their core subject only/i),
    ).toBeInTheDocument();
  });

  it("lists existing assignments grouped by subject with removable batch chips", () => {
    rowsMock.mockReturnValue({
      data: [
        { id: "m1", teacher_id: "t1", teacher_name: "Mr Patil", subject_id: "s_it", subject_name: "IT", batch_id: "bD", batch_name: "Batch D" },
        { id: "m2", teacher_id: "t1", teacher_name: "Mr Patil", subject_id: "s_it", subject_name: "IT", batch_id: "bE", batch_name: "Batch E" },
      ],
    });
    renderIt();
    // "IT" also appears as a dropdown option and the batch names also appear in
    // the add-form checkbox list, so assert presence (>=1) rather than unique.
    expect(screen.getAllByText("IT").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Batch D").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Batch E").length).toBeGreaterThan(0);
    // The remove control for an assignment chip is present.
    expect(
      screen.getByLabelText("Remove IT for Batch D"),
    ).toBeInTheDocument();
  });

  it("assigns a subject to the picked batches", async () => {
    const user = userEvent.setup();
    renderIt();
    await user.selectOptions(screen.getByLabelText("Subject"), "IT");
    await user.click(screen.getByRole("checkbox", { name: /Batch D/i }));
    await user.click(screen.getByRole("checkbox", { name: /Batch E/i }));
    await user.click(screen.getByRole("button", { name: /Add secondary subject/i }));
    expect(assignMock).toHaveBeenCalledWith({
      teacherId: "t1",
      subjectName: "IT",
      batchIds: ["bD", "bE"],
    });
  });

  it("validates that a subject and at least one batch are chosen", async () => {
    const user = userEvent.setup();
    renderIt();
    await user.click(screen.getByRole("button", { name: /Add secondary subject/i }));
    expect(screen.getByText(/Pick a subject/i)).toBeInTheDocument();
    expect(assignMock).not.toHaveBeenCalled();
  });
});
