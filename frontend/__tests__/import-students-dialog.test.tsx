import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ImportStudentsDialog } from "@/app/(dashboard)/students/_components/import-students-dialog";

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
});
