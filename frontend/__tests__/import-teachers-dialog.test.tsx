import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ImportTeachersDialog } from "@/app/(dashboard)/teachers/_components/import-teachers-dialog";

function renderDialog() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ImportTeachersDialog branchId="b1" />
    </QueryClientProvider>,
  );
}

describe("ImportTeachersDialog", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("offers a Download sample CSV button inside the dialog", async () => {
    const user = userEvent.setup();
    renderDialog();
    await user.click(screen.getByRole("button", { name: /import teachers/i }));
    expect(
      screen.getByRole("button", { name: /download sample csv/i }),
    ).toBeInTheDocument();
  });

  it("downloads a template with the per-row import columns only", async () => {
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
    await user.click(screen.getByRole("button", { name: /import teachers/i }));
    await user.click(
      screen.getByRole("button", { name: /download sample csv/i }),
    );

    expect(captured).toBeTruthy();
    const text = await (captured as unknown as Blob).text();
    expect(text).toContain("Name");
    expect(text).toContain("Email");
    expect(text).toContain("Qualification");
    expect(text).toContain("Subjects");
    // Two example rows with example.edu emails.
    expect(text).toContain("example.edu");
    // Subjects column supports comma-separated names — make sure that
    // sample row's quoting is correct (the cell contains a comma).
    expect(text).toMatch(/"Mathematics, Statistics"/);
  });
});
