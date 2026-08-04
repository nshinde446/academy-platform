import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ManageSubjectsDialog } from "@/app/(dashboard)/courses/_components/manage-subjects-dialog";
import type { CourseResponse } from "@/app/(dashboard)/courses/_schemas/course";
import apiClient from "@/services/api-client";

vi.mock("@/services/api-client", () => ({
  default: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}));

// useToast needs a Base UI Toast provider; stub it for these unit tests.
vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}));

const COURSE: CourseResponse = {
  id: "c-cet2",
  branch_id: "br1",
  name: "11TH CET-2",
  code: "CET2",
  description: null,
  duration_years: 1,
  status: "active",
};

function withQuery(ui: React.ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{ui}</QueryClientProvider>;
}

const get = apiClient.get as ReturnType<typeof vi.fn>;
const post = apiClient.post as ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.clearAllMocks();
  get.mockImplementation((url: string) => {
    if (url.includes("/subjects")) {
      return Promise.resolve({
        data: [
          {
            id: "s1",
            branch_id: "br1",
            academic_year_id: "ay1",
            course_id: "c-cet2",
            name: "Physics",
            code: "PHY",
            status: "active",
          },
        ],
      });
    }
    if (url.includes("/syllabi")) {
      return Promise.resolve({
        data: [
          { key: "MHT-CET", label: "MHT-CET (all four)", subjects: [] },
          { key: "JEE", label: "JEE (PCM)", subjects: [] },
        ],
      });
    }
    if (url.includes("/academic-years")) {
      return Promise.resolve({
        data: [
          { id: "ay1", branch_id: "br1", name: "2025-26", start_year: 2025, end_year: 2026, status: "active" },
        ],
      });
    }
    return Promise.resolve({ data: [] });
  });
  post.mockResolvedValue({ data: { created: 4, subjects: [] } });
});

describe("ManageSubjectsDialog", () => {
  it("lists the course's existing subjects", async () => {
    render(
      withQuery(
        <ManageSubjectsDialog
          course={COURSE}
          open
          onOpenChange={() => {}}
          branchId="br1"
        />
      )
    );
    expect(await screen.findByText("Physics")).toBeInTheDocument();
    expect(screen.getByText("PHY")).toBeInTheDocument();
  });

  it("seeds subjects from the chosen syllabus", async () => {
    const user = userEvent.setup();
    render(
      withQuery(
        <ManageSubjectsDialog
          course={COURSE}
          open
          onOpenChange={() => {}}
          branchId="br1"
        />
      )
    );

    await screen.findByText("Physics");
    await user.selectOptions(
      screen.getByLabelText("Seed from syllabus"),
      "MHT-CET"
    );
    await user.click(screen.getByRole("button", { name: /^seed$/i }));

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/api/v1/academic/subjects/seed", {
        branch_id: "br1",
        course_id: "c-cet2",
        syllabus_key: "MHT-CET",
      })
    );
  });

  it("adds a single subject with a derived code when none is given", async () => {
    const user = userEvent.setup();
    post.mockResolvedValue({ data: { id: "s2" } });
    render(
      withQuery(
        <ManageSubjectsDialog
          course={COURSE}
          open
          onOpenChange={() => {}}
          branchId="br1"
        />
      )
    );

    await screen.findByText("Physics");
    await user.type(screen.getByLabelText("Add a subject"), "Chemistry");
    await user.click(screen.getByRole("button", { name: /^add$/i }));

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/api/v1/academic/subjects", {
        branch_id: "br1",
        course_id: "c-cet2",
        academic_year_id: "ay1",
        name: "Chemistry",
        code: "CHE",
      })
    );
  });
});
