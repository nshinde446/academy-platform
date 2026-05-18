import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CreateBatchDialog } from "@/app/(dashboard)/batches/_components/create-batch-dialog";
import type {
  AcademicYearResponse,
  CourseResponse,
} from "@/app/(dashboard)/batches/_schemas/batch";

const MOCK_YEARS: AcademicYearResponse[] = [
  {
    id: "ay1",
    branch_id: "br1",
    name: "2025-2026",
    start_year: 2025,
    end_year: 2026,
    status: "active",
  },
];

const MOCK_COURSES: CourseResponse[] = [
  {
    id: "c1",
    branch_id: "br1",
    academic_year_id: "ay1",
    name: "Physics",
    code: "PHY",
    description: null,
    status: "active",
  },
  {
    id: "c2",
    branch_id: "br1",
    academic_year_id: "ay1",
    name: "Chemistry",
    code: "CHM",
    description: "Advanced Chemistry",
    status: "active",
  },
];

describe("CreateBatchDialog", () => {
  const mockOnSubmit = vi.fn();
  const user = userEvent.setup();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the trigger button", () => {
    render(
      <CreateBatchDialog
        academicYears={MOCK_YEARS}
        courses={MOCK_COURSES}
        onSubmit={mockOnSubmit}
        isPending={false}
      />
    );

    expect(
      screen.getByRole("button", { name: /create batch/i })
    ).toBeInTheDocument();
  });

  it("shows form fields when dialog opens", async () => {
    render(
      <CreateBatchDialog
        academicYears={MOCK_YEARS}
        courses={MOCK_COURSES}
        onSubmit={mockOnSubmit}
        isPending={false}
      />
    );

    await user.click(screen.getByRole("button", { name: /create batch/i }));

    await waitFor(() => {
      expect(screen.getByLabelText(/batch name/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/batch code/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/capacity/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/course/i)).toBeInTheDocument();
    });
  });

  it("calls onSubmit with form data", async () => {
    mockOnSubmit.mockResolvedValue(undefined);

    render(
      <CreateBatchDialog
        academicYears={MOCK_YEARS}
        courses={MOCK_COURSES}
        onSubmit={mockOnSubmit}
        isPending={false}
      />
    );

    await user.click(screen.getByRole("button", { name: /create batch/i }));

    await waitFor(() => {
      expect(screen.getByLabelText(/batch name/i)).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText(/batch name/i), "Physics Morning");
    await user.type(screen.getByLabelText(/batch code/i), "PHY-M");
    await user.clear(screen.getByLabelText(/capacity/i));
    await user.type(screen.getByLabelText(/capacity/i), "25");

    await user.click(screen.getByRole("button", { name: /^create$/i }));

    await waitFor(() => {
      expect(mockOnSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "Physics Morning",
          code: "PHY-M",
          capacity: 25,
          academic_year_id: "ay1",
          course_id: "c1",
        })
      );
    });
  });

  it("disables submit button when isPending", async () => {
    render(
      <CreateBatchDialog
        academicYears={MOCK_YEARS}
        courses={MOCK_COURSES}
        onSubmit={mockOnSubmit}
        isPending={true}
      />
    );

    await user.click(screen.getByRole("button", { name: /create batch/i }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /creating/i })).toBeDisabled();
    });
  });

  it("shows error when no courses available", async () => {
    render(
      <CreateBatchDialog
        academicYears={MOCK_YEARS}
        courses={[]}
        onSubmit={mockOnSubmit}
        isPending={false}
      />
    );

    await user.click(screen.getByRole("button", { name: /create batch/i }));

    await waitFor(() => {
      expect(screen.getByLabelText(/batch name/i)).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText(/batch name/i), "Test");
    await user.type(screen.getByLabelText(/batch code/i), "TST");

    await user.click(screen.getByRole("button", { name: /^create$/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/no course available/i)
      ).toBeInTheDocument();
    });
  });
});
