import { describe, it, expect, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ReportsHub } from "@/app/(dashboard)/attendance/_components/reports-hub";

const downloadMutate = vi.fn();
vi.mock("@/app/(dashboard)/attendance/_hooks/use-attendance", () => ({
  useDownloadAttendanceReport: () => ({ mutateAsync: downloadMutate }),
}));

const toastError = vi.fn();
vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ error: toastError, success: vi.fn() }),
}));

const BATCHES = [
  { id: "b1", name: "11TH CET-1" },
  { id: "b2", name: "12th CJ" },
];

describe("ReportsHub", () => {
  beforeEach(() => {
    downloadMutate.mockReset();
    downloadMutate.mockResolvedValue(undefined);
    toastError.mockReset();
  });

  it("lists the biometric summaries and the existing reports", () => {
    render(<ReportsHub branchId="br1" batches={BATCHES} />);
    expect(screen.getByText("Daywise · Batchwise (biometric)")).toBeInTheDocument();
    expect(screen.getByText("Batchwise · Datewise (biometric)")).toBeInTheDocument();
    expect(screen.getByText("Daily ledger (all students)")).toBeInTheDocument();
    expect(screen.getByText("All-batches summary")).toBeInTheDocument();
    expect(screen.getByText("Single-batch register")).toBeInTheDocument();
    expect(screen.getByText("Single-day snapshot")).toBeInTheDocument();
  });

  it("downloads the daywise-batchwise report as Excel with the date range", async () => {
    render(<ReportsHub branchId="br1" batches={BATCHES} />);
    // First "Excel" button belongs to the daywise-batchwise card (first in the list).
    fireEvent.click(screen.getAllByRole("button", { name: "Excel" })[0]);
    await waitFor(() =>
      expect(downloadMutate).toHaveBeenCalledWith(
        expect.objectContaining({
          scope: "daywise-batchwise",
          fmt: "xlsx",
          id: undefined,
          start: expect.any(String),
          end: expect.any(String),
        }),
      ),
    );
  });

  it("blocks batch reports until a batch is picked, then passes the batch id", async () => {
    render(<ReportsHub branchId="br1" batches={BATCHES} />);
    // The batchwise-datewise card is the 2nd Excel button; disabled with no batch.
    const batchwiseExcel = () =>
      screen.getAllByRole("button", { name: "Excel" })[1];
    expect(batchwiseExcel()).toBeDisabled();

    fireEvent.change(
      screen.getByRole("combobox", { name: /Batch for batch-scoped reports/ }),
      { target: { value: "b2" } },
    );
    expect(batchwiseExcel()).not.toBeDisabled();

    fireEvent.click(batchwiseExcel());
    await waitFor(() =>
      expect(downloadMutate).toHaveBeenCalledWith(
        expect.objectContaining({
          scope: "batchwise-datewise",
          fmt: "xlsx",
          id: "b2",
        }),
      ),
    );
  });

  it("single-day snapshot sends a day, not a range", async () => {
    render(<ReportsHub branchId="br1" batches={BATCHES} />);
    fireEvent.change(
      screen.getByRole("combobox", { name: /Batch for batch-scoped reports/ }),
      { target: { value: "b1" } },
    );
    // Day card is last; its PDF button is the last "PDF" in the list.
    const pdfButtons = screen.getAllByRole("button", { name: "PDF" });
    fireEvent.click(pdfButtons[pdfButtons.length - 1]);
    await waitFor(() =>
      expect(downloadMutate).toHaveBeenCalledWith(
        expect.objectContaining({
          scope: "day",
          fmt: "pdf",
          id: "b1",
          day: expect.any(String),
        }),
      ),
    );
    // A single-day report must not carry start/end.
    const call = downloadMutate.mock.calls.at(-1)![0];
    expect(call.start).toBeUndefined();
    expect(call.end).toBeUndefined();
  });
});
