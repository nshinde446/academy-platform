import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ValidationGridStep } from "@/app/(dashboard)/students/_components/validation-grid-step";
import apiClient from "@/services/api-client";

vi.mock("@/services/api-client", () => ({ default: { post: vi.fn() } }));

const post = apiClient.post as ReturnType<typeof vi.fn>;

const PARSE = {
  data: {
    fields: ["name", "class", "target", "batch"],
    import_fields: [
      { key: "name", label: "Name", required: "1" },
      { key: "class", label: "Class" },
      { key: "target", label: "Target exam" },
      { key: "batch", label: "Batch" },
    ],
    rows: [
      {
        index: 0,
        row_number: 2,
        values: { name: "Aman", class: "11", target: "NEET", batch: "BATCH-A" },
      },
      {
        index: 1,
        row_number: 3,
        values: { name: "", class: "11", target: "NEET", batch: "BATCH-A" },
      },
    ],
    validation: [
      { index: 0, errors: [], warnings: [] },
      { index: 1, errors: ["Name is required"], warnings: [] },
    ],
  },
};

beforeEach(() => {
  post.mockReset();
  post.mockImplementation((url: string) => {
    if (url.includes("/import/parse")) return Promise.resolve(PARSE);
    if (url.includes("/import/validate")) {
      // After editing, pretend everything validates clean.
      return Promise.resolve({
        data: {
          validation: [
            { index: 0, errors: [], warnings: [] },
            { index: 1, errors: [], warnings: [] },
          ],
        },
      });
    }
    return Promise.resolve({ data: {} });
  });
});

function renderGrid(onImport = vi.fn()) {
  return render(
    <ValidationGridStep
      branchId="b1"
      file={new File(["x"], "roster.csv", { type: "text/csv" })}
      columnMap={null}
      onImport={onImport}
      onBack={vi.fn()}
    />,
  );
}

describe("ValidationGridStep", () => {
  it("shows ready/needs-fixing counts and the row error", async () => {
    renderGrid();
    expect(await screen.findByText("1 ready")).toBeInTheDocument();
    expect(screen.getByText("1 need fixing")).toBeInTheDocument();
    expect(screen.getByText("Name is required")).toBeInTheDocument();
  });

  it("imports a CSV built from the ready rows", async () => {
    const onImport = vi.fn();
    renderGrid(onImport);
    const btn = await screen.findByRole("button", {
      name: /import 1 ready row/i,
    });
    await userEvent.click(btn);
    expect(onImport).toHaveBeenCalledTimes(1);
    const [csvFile, createMissing] = onImport.mock.calls[0];
    expect(csvFile).toBeInstanceOf(File);
    expect(createMissing).toBe(false);
  });

  it("re-validates after editing a cell", async () => {
    renderGrid();
    // Fix the blank name (row 3 input).
    const input = (await screen.findByLabelText(
      /name row 3/i,
    )) as HTMLInputElement;
    await userEvent.type(input, "Bina");
    // Debounced revalidate hits the validate endpoint and clears the error.
    await waitFor(
      () =>
        expect(
          post.mock.calls.some((c) => String(c[0]).includes("/import/validate")),
        ).toBe(true),
      { timeout: 2000 },
    );
    await waitFor(() => expect(screen.getByText("2 ready")).toBeInTheDocument());
  });
});
