import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CreateStudentDialog } from "@/app/(dashboard)/students/_components/create-student-dialog";
import type { AcademicYearResponse } from "@/app/(dashboard)/students/_schemas/student";

const MOCK_YEARS: AcademicYearResponse[] = [
  {
    id: "ay1",
    branch_id: "b1",
    name: "2025-2026",
    start_year: 2025,
    end_year: 2026,
    status: "active",
  },
];

describe("CreateStudentDialog", () => {
  const mockOnCreate = vi.fn();
  const user = userEvent.setup();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the dialog trigger button", () => {
    render(
      <CreateStudentDialog
        academicYears={MOCK_YEARS}
        onSubmit={mockOnCreate}
        isPending={false}
      />
    );

    expect(screen.getByRole("button", { name: /create student/i })).toBeInTheDocument();
  });

  it("shows form fields when dialog is open", async () => {
    render(
      <CreateStudentDialog
        academicYears={MOCK_YEARS}
        onSubmit={mockOnCreate}
        isPending={false}
      />
    );

    await user.click(screen.getByRole("button", { name: /create student/i }));

    await waitFor(() => {
      expect(screen.getByLabelText(/first name/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/last name/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/^phone$/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/roll no/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/parent mobile/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/rfid number/i)).toBeInTheDocument();
    });
  });

  it("submits parent_mobile and rfid_number", async () => {
    mockOnCreate.mockResolvedValue(undefined);

    render(
      <CreateStudentDialog
        academicYears={MOCK_YEARS}
        onSubmit={mockOnCreate}
        isPending={false}
      />
    );

    await user.click(screen.getByRole("button", { name: /create student/i }));

    await waitFor(() => {
      expect(screen.getByLabelText(/first name/i)).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText(/first name/i), "Asha");
    await user.type(screen.getByLabelText(/last name/i), "Kumar");
    await user.type(screen.getByLabelText(/parent mobile/i), "9988776655");
    await user.type(screen.getByLabelText(/rfid number/i), "RFID-XYZ-9");
    // standard + target_exam are required at enrolment.
    await user.selectOptions(screen.getByLabelText(/standard/i), "11");
    await user.selectOptions(screen.getByLabelText(/target exam/i), "NEET");

    await user.click(screen.getByRole("button", { name: /^create$/i }));

    await waitFor(() => {
      expect(mockOnCreate).toHaveBeenCalledWith(
        expect.objectContaining({
          first_name: "Asha",
          last_name: "Kumar",
          parent_mobile: "9988776655",
          rfid_number: "RFID-XYZ-9",
          standard: "11",
          target_exam: "NEET",
        })
      );
    });
  });

  it("calls onSubmit with form data", async () => {
    mockOnCreate.mockResolvedValue(undefined);

    render(
      <CreateStudentDialog
        academicYears={MOCK_YEARS}
        onSubmit={mockOnCreate}
        isPending={false}
      />
    );

    await user.click(screen.getByRole("button", { name: /create student/i }));

    await waitFor(() => {
      expect(screen.getByLabelText(/first name/i)).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText(/first name/i), "Test");
    await user.type(screen.getByLabelText(/last name/i), "Student");
    await user.type(screen.getByLabelText(/email/i), "test@example.com");
    await user.selectOptions(screen.getByLabelText(/standard/i), "12");
    await user.selectOptions(screen.getByLabelText(/target exam/i), "JEE-Main");

    await user.click(screen.getByRole("button", { name: /^create$/i }));

    await waitFor(() => {
      expect(mockOnCreate).toHaveBeenCalledWith(
        expect.objectContaining({
          first_name: "Test",
          last_name: "Student",
          email: "test@example.com",
          academic_year_id: "ay1",
          standard: "12",
          target_exam: "JEE-Main",
        })
      );
    });
  });

  it("disables submit button when isPending is true", async () => {
    render(
      <CreateStudentDialog
        academicYears={MOCK_YEARS}
        onSubmit={mockOnCreate}
        isPending={true}
      />
    );

    await user.click(screen.getByRole("button", { name: /create student/i }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /creating/i })).toBeDisabled();
    });
  });
});
