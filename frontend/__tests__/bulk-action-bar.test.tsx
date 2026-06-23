import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BulkActionBar } from "@/app/(dashboard)/students/_components/bulk-action-bar";

const handlers = {
  onSetFees: vi.fn(),
  onSetClass: vi.fn(),
  onSetStream: vi.fn(),
  onAssignBatch: vi.fn(),
  onExport: vi.fn(),
  onDelete: vi.fn(),
  onClear: vi.fn(),
};

beforeEach(() => vi.clearAllMocks());

function renderBar(over: Partial<React.ComponentProps<typeof BulkActionBar>> = {}) {
  return render(
    <BulkActionBar
      count={3}
      batches={[{ id: "b1", code: "NEET-11-A" }]}
      pending={false}
      {...handlers}
      {...over}
    />,
  );
}

describe("BulkActionBar", () => {
  it("shows the selected count", () => {
    renderBar();
    expect(screen.getByText("3 selected")).toBeInTheDocument();
  });

  it("fires onSetFees when a fees value is picked", async () => {
    const user = userEvent.setup();
    renderBar();
    await user.selectOptions(
      screen.getByRole("combobox", { name: /set fees/i }),
      "paid",
    );
    expect(handlers.onSetFees).toHaveBeenCalledWith("paid");
  });

  it("fires onAssignBatch with the batch id", async () => {
    const user = userEvent.setup();
    renderBar();
    await user.selectOptions(
      screen.getByRole("combobox", { name: /assign batch/i }),
      "b1",
    );
    expect(handlers.onAssignBatch).toHaveBeenCalledWith("b1");
  });

  it("disables Assign batch when there are no batches", () => {
    renderBar({ batches: [] });
    expect(
      screen.getByRole("combobox", { name: /assign batch/i }),
    ).toBeDisabled();
  });

  it("fires delete, export, and clear", async () => {
    const user = userEvent.setup();
    renderBar();
    await user.click(screen.getByRole("button", { name: /^delete$/i }));
    await user.click(screen.getByRole("button", { name: /export selected/i }));
    await user.click(screen.getByRole("button", { name: /^clear$/i }));
    expect(handlers.onDelete).toHaveBeenCalled();
    expect(handlers.onExport).toHaveBeenCalled();
    expect(handlers.onClear).toHaveBeenCalled();
  });

  it("disables actions while a bulk op is pending", () => {
    renderBar({ pending: true });
    expect(screen.getByRole("combobox", { name: /set class/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /^delete$/i })).toBeDisabled();
  });
});
