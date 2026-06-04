import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ImportStudentsDialog } from "@/app/(dashboard)/students/_components/import-students-dialog";
import apiClient from "@/services/api-client";

vi.mock("@/services/api-client", () => ({
  default: { post: vi.fn() },
}));

function renderDialog() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ImportStudentsDialog branchId="b1" />
    </QueryClientProvider>,
  );
}

describe("ImportStudentsDialog", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("offers a Download sample CSV button inside the dialog", async () => {
    const user = userEvent.setup();
    renderDialog();
    await user.click(screen.getByRole("button", { name: /import students/i }));
    expect(
      screen.getByRole("button", { name: /download sample csv/i }),
    ).toBeInTheDocument();
  });

  it("downloads a template with per-row Class / Target / Batch columns", async () => {
    const user = userEvent.setup();
    let captured: Blob | null = null;
    URL.createObjectURL = ((b: Blob) => {
      captured = b;
      return "blob:mock";
    }) as typeof URL.createObjectURL;
    URL.revokeObjectURL = (() => {}) as typeof URL.revokeObjectURL;
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(
      () => {},
    );

    renderDialog();
    await user.click(screen.getByRole("button", { name: /import students/i }));
    await user.click(
      screen.getByRole("button", { name: /download sample csv/i }),
    );

    expect(captured).toBeTruthy();
    const text = await (captured as unknown as Blob).text();
    // Required + optional INPUT headers.
    expect(text).toContain("Name");
    expect(text).toContain("Class");
    expect(text).toContain("Target");
    expect(text).toContain("Batch");
    expect(text).toContain("Roll No");
    expect(text).toContain("Parent Mobile");
    expect(text).toContain("RFIDNumber");
    // Sample rows exercise common class / exam / batch values.
    expect(text).toMatch(/NEET/);
    expect(text).toMatch(/JEE-Main/);
    // Derived columns must not leak into the template.
    expect(text).not.toMatch(/\bRank\b/);
    expect(text).not.toMatch(/Avg score/i);
    expect(text).not.toMatch(/Attendance/);
    expect(text).not.toMatch(/\bDPP\b/);
    expect(text).not.toMatch(/Fees/);
  });

  it("sample template exercises every allowed Class and Target value", async () => {
    const user = userEvent.setup();
    let captured: Blob | null = null;
    URL.createObjectURL = ((b: Blob) => {
      captured = b;
      return "blob:mock";
    }) as typeof URL.createObjectURL;
    URL.revokeObjectURL = (() => {}) as typeof URL.revokeObjectURL;
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(
      () => {},
    );

    renderDialog();
    await user.click(screen.getByRole("button", { name: /import students/i }));
    await user.click(
      screen.getByRole("button", { name: /download sample csv/i }),
    );

    const text = await (captured as unknown as Blob).text();
    // Allowed Class values.
    for (const cls of ["9", "10", "11", "12", "Dropper"]) {
      expect(text).toContain(`,${cls},`);
    }
    // Allowed Target values.
    for (const t of [
      "NEET",
      "JEE-Main",
      "JEE-Advanced",
      "Both",
      "Foundation",
      "Other",
    ]) {
      expect(text).toContain(`,${t},`);
    }
  });

  it("shows partial-failure feedback when the server skips rows", async () => {
    const user = userEvent.setup();
    (apiClient.post as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      data: {
        imported: 0,
        skipped: 2,
        errors: [
          "Row 2: Invalid target_exam 'JEE'.",
          "Row 3: unknown batch code 'MHT-11-A'",
        ],
      },
    });

    renderDialog();
    await user.click(screen.getByRole("button", { name: /import students/i }));

    const fileInput = screen.getByLabelText(/file/i) as HTMLInputElement;
    const file = new File(["Name\nfoo"], "x.csv", { type: "text/csv" });
    await user.upload(fileInput, file);
    await user.click(screen.getByRole("button", { name: /upload/i }));

    await waitFor(() => {
      expect(screen.getByText(/no rows were saved/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/Invalid target_exam 'JEE'/)).toBeInTheDocument();
    expect(screen.getByText(/unknown batch code/i)).toBeInTheDocument();
    // Upload button is replaced by a Close / Upload another file pair.
    expect(screen.queryByRole("button", { name: /^upload$/i })).toBeNull();
  });
});
