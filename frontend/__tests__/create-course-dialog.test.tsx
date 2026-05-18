import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CreateCourseDialog } from "@/app/(dashboard)/courses/_components/create-course-dialog";

describe("CreateCourseDialog", () => {
  const mockOnSubmit = vi.fn();
  const user = userEvent.setup();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the trigger button", () => {
    render(
      <CreateCourseDialog
        academicYearId="ay1"
        onSubmit={mockOnSubmit}
        isPending={false}
      />
    );

    expect(
      screen.getByRole("button", { name: /create course/i })
    ).toBeInTheDocument();
  });

  it("disables trigger when no academic year is selected", () => {
    render(
      <CreateCourseDialog
        academicYearId={undefined}
        onSubmit={mockOnSubmit}
        isPending={false}
      />
    );

    expect(
      screen.getByRole("button", { name: /create course/i })
    ).toBeDisabled();
  });

  it("shows form fields when dialog opens", async () => {
    render(
      <CreateCourseDialog
        academicYearId="ay1"
        onSubmit={mockOnSubmit}
        isPending={false}
      />
    );

    await user.click(screen.getByRole("button", { name: /create course/i }));

    await waitFor(() => {
      expect(screen.getByLabelText(/course name/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/course code/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/description/i)).toBeInTheDocument();
    });
  });

  it("calls onSubmit with form data", async () => {
    mockOnSubmit.mockResolvedValue(undefined);

    render(
      <CreateCourseDialog
        academicYearId="ay1"
        onSubmit={mockOnSubmit}
        isPending={false}
      />
    );

    await user.click(screen.getByRole("button", { name: /create course/i }));

    await waitFor(() => {
      expect(screen.getByLabelText(/course name/i)).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText(/course name/i), "Physics");
    await user.type(screen.getByLabelText(/course code/i), "PHY");
    await user.type(
      screen.getByLabelText(/description/i),
      "Mechanics & Waves"
    );

    await user.click(screen.getByRole("button", { name: /^create$/i }));

    await waitFor(() => {
      expect(mockOnSubmit).toHaveBeenCalledWith({
        academic_year_id: "ay1",
        name: "Physics",
        code: "PHY",
        description: "Mechanics & Waves",
      });
    });
  });

  it("sends null description when blank", async () => {
    mockOnSubmit.mockResolvedValue(undefined);

    render(
      <CreateCourseDialog
        academicYearId="ay1"
        onSubmit={mockOnSubmit}
        isPending={false}
      />
    );

    await user.click(screen.getByRole("button", { name: /create course/i }));

    await waitFor(() => {
      expect(screen.getByLabelText(/course name/i)).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText(/course name/i), "Math");
    await user.type(screen.getByLabelText(/course code/i), "MAT");

    await user.click(screen.getByRole("button", { name: /^create$/i }));

    await waitFor(() => {
      expect(mockOnSubmit).toHaveBeenCalledWith(
        expect.objectContaining({ description: null })
      );
    });
  });

  it("disables submit button when isPending", async () => {
    render(
      <CreateCourseDialog
        academicYearId="ay1"
        onSubmit={mockOnSubmit}
        isPending={true}
      />
    );

    await user.click(screen.getByRole("button", { name: /create course/i }));

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /creating/i })
      ).toBeDisabled();
    });
  });
});
