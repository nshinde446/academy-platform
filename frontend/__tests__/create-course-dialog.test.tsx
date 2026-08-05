import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CreateCourseDialog } from "@/app/(dashboard)/courses/_components/create-course-dialog";
import apiClient from "@/services/api-client";

vi.mock("@/services/api-client", () => ({
  default: { get: vi.fn() },
}));

function withQuery(ui: React.ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{ui}</QueryClientProvider>;
}

describe("CreateCourseDialog", () => {
  const mockOnSubmit = vi.fn();
  const user = userEvent.setup();

  beforeEach(() => {
    vi.clearAllMocks();
    (apiClient.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: [
        { key: "JEE", label: "JEE — PCM (Physics, Chemistry, Maths)", subjects: [] },
        { key: "NEET", label: "NEET — PCB (Physics, Chemistry, Biology)", subjects: [] },
      ],
    });
  });

  it("renders the trigger button", () => {
    render(withQuery(<CreateCourseDialog onSubmit={mockOnSubmit} isPending={false} />));

    expect(
      screen.getByRole("button", { name: /create course/i })
    ).toBeInTheDocument();
  });

  it("shows form fields when dialog opens", async () => {
    render(withQuery(<CreateCourseDialog onSubmit={mockOnSubmit} isPending={false} />));

    await user.click(screen.getByRole("button", { name: /create course/i }));

    await waitFor(() => {
      expect(screen.getByLabelText(/course name/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/course code/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/duration/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/description/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/exam target/i)).toBeInTheDocument();
    });
  });

  it("submits with duration_years and no syllabus by default", async () => {
    mockOnSubmit.mockResolvedValue(undefined);

    render(withQuery(<CreateCourseDialog onSubmit={mockOnSubmit} isPending={false} />));

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
        syllabus_key: null,
      });
    });
  });

  it("passes the chosen exam target as syllabus_key", async () => {
    mockOnSubmit.mockResolvedValue(undefined);

    render(withQuery(<CreateCourseDialog onSubmit={mockOnSubmit} isPending={false} />));

    await user.click(screen.getByRole("button", { name: /create course/i }));

    await waitFor(() => {
      expect(screen.getByLabelText(/exam target/i)).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText(/course name/i), "NEET");
    await user.type(screen.getByLabelText(/course code/i), "NEET-01");
    await user.selectOptions(screen.getByLabelText(/exam target/i), "NEET");

    await user.click(screen.getByRole("button", { name: /^create$/i }));

    await waitFor(() => {
      expect(mockOnSubmit).toHaveBeenCalledWith(
        expect.objectContaining({ syllabus_key: "NEET" })
      );
    });
  });

  it("disables submit button when isPending", async () => {
    render(withQuery(<CreateCourseDialog onSubmit={mockOnSubmit} isPending={true} />));

    await user.click(screen.getByRole("button", { name: /create course/i }));

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /creating/i })
      ).toBeDisabled();
    });
  });
});
