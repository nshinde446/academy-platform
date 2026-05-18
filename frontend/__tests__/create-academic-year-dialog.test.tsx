import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CreateAcademicYearDialog } from "@/app/(dashboard)/academic-years/_components/create-academic-year-dialog";

describe("CreateAcademicYearDialog", () => {
  const mockOnSubmit = vi.fn();
  const user = userEvent.setup();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the trigger button", () => {
    render(
      <CreateAcademicYearDialog onSubmit={mockOnSubmit} isPending={false} />
    );

    expect(
      screen.getByRole("button", { name: /create academic year/i })
    ).toBeInTheDocument();
  });

  it("derives name from start year as user types", async () => {
    render(
      <CreateAcademicYearDialog onSubmit={mockOnSubmit} isPending={false} />
    );

    await user.click(
      screen.getByRole("button", { name: /create academic year/i })
    );

    await waitFor(() => {
      expect(screen.getByLabelText(/start year/i)).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText(/start year/i), "2028");

    const nameInput = screen.getByLabelText(/^name$/i) as HTMLInputElement;
    await waitFor(() => {
      expect(nameInput.value).toBe("2028-2029");
    });
  });

  it("submits with derived end_year and name", async () => {
    mockOnSubmit.mockResolvedValue(undefined);

    render(
      <CreateAcademicYearDialog onSubmit={mockOnSubmit} isPending={false} />
    );

    await user.click(
      screen.getByRole("button", { name: /create academic year/i })
    );

    await waitFor(() => {
      expect(screen.getByLabelText(/start year/i)).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText(/start year/i), "2030");
    await user.click(screen.getByRole("button", { name: /^create$/i }));

    await waitFor(() => {
      expect(mockOnSubmit).toHaveBeenCalledWith({
        name: "2030-2031",
        start_year: 2030,
        end_year: 2031,
      });
    });
  });

  it("disables submit when start year is missing", async () => {
    render(
      <CreateAcademicYearDialog onSubmit={mockOnSubmit} isPending={false} />
    );

    await user.click(
      screen.getByRole("button", { name: /create academic year/i })
    );

    await waitFor(() => {
      expect(screen.getByLabelText(/start year/i)).toBeInTheDocument();
    });

    expect(screen.getByRole("button", { name: /^create$/i })).toBeDisabled();
  });
});
