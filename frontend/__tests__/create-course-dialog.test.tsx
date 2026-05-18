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
    render(<CreateCourseDialog onSubmit={mockOnSubmit} isPending={false} />);

    expect(
      screen.getByRole("button", { name: /create course/i })
    ).toBeInTheDocument();
  });

  it("shows form fields when dialog opens", async () => {
    render(<CreateCourseDialog onSubmit={mockOnSubmit} isPending={false} />);

    await user.click(screen.getByRole("button", { name: /create course/i }));

    await waitFor(() => {
      expect(screen.getByLabelText(/course name/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/course code/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/duration/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/description/i)).toBeInTheDocument();
    });
  });

  it("submits with duration_years", async () => {
    mockOnSubmit.mockResolvedValue(undefined);

    render(<CreateCourseDialog onSubmit={mockOnSubmit} isPending={false} />);

    await user.click(screen.getByRole("button", { name: /create course/i }));

    await waitFor(() => {
      expect(screen.getByLabelText(/course name/i)).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText(/course name/i), "NEET 2-Year");
    await user.type(screen.getByLabelText(/course code/i), "NEET-2Y");
    await user.clear(screen.getByLabelText(/duration/i));
    await user.type(screen.getByLabelText(/duration/i), "2");

    await user.click(screen.getByRole("button", { name: /^create$/i }));

    await waitFor(() => {
      expect(mockOnSubmit).toHaveBeenCalledWith({
        name: "NEET 2-Year",
        code: "NEET-2Y",
        description: null,
        duration_years: 2,
      });
    });
  });

  it("defaults duration to 1", async () => {
    mockOnSubmit.mockResolvedValue(undefined);

    render(<CreateCourseDialog onSubmit={mockOnSubmit} isPending={false} />);

    await user.click(screen.getByRole("button", { name: /create course/i }));

    await waitFor(() => {
      expect(screen.getByLabelText(/course name/i)).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText(/course name/i), "Class 9");
    await user.type(screen.getByLabelText(/course code/i), "C9");

    await user.click(screen.getByRole("button", { name: /^create$/i }));

    await waitFor(() => {
      expect(mockOnSubmit).toHaveBeenCalledWith(
        expect.objectContaining({ duration_years: 1 })
      );
    });
  });

  it("disables submit button when isPending", async () => {
    render(<CreateCourseDialog onSubmit={mockOnSubmit} isPending={true} />);

    await user.click(screen.getByRole("button", { name: /create course/i }));

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /creating/i })
      ).toBeDisabled();
    });
  });
});
