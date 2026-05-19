import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ConfirmDialog", () => {
  it("renders both Cancel and Confirm buttons by default", () => {
    render(
      <ConfirmDialog
        open
        onOpenChange={() => {}}
        title="Delete?"
        description="Are you sure?"
        confirmLabel="Delete"
        destructive
        onConfirm={vi.fn()}
      />
    );

    expect(screen.getByRole("button", { name: /cancel/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /delete/i })).toBeInTheDocument();
  });

  it("hides the Cancel button when hideCancel is true", () => {
    render(
      <ConfirmDialog
        open
        onOpenChange={() => {}}
        title="Action failed"
        description="Something went wrong."
        confirmLabel="OK"
        hideCancel
      />
    );

    expect(screen.queryByRole("button", { name: /cancel/i })).toBeNull();
    expect(screen.getByRole("button", { name: /ok/i })).toBeInTheDocument();
  });

  it("invokes onConfirm and closes when Confirm is clicked", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn().mockResolvedValue(undefined);
    const onOpenChange = vi.fn();

    render(
      <ConfirmDialog
        open
        onOpenChange={onOpenChange}
        title="Delete?"
        description="Are you sure?"
        confirmLabel="Delete"
        destructive
        onConfirm={onConfirm}
      />
    );

    await user.click(screen.getByRole("button", { name: /delete/i }));

    await waitFor(() => {
      expect(onConfirm).toHaveBeenCalledTimes(1);
    });
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("closes without crashing when onConfirm is omitted (info/alert mode)", async () => {
    const user = userEvent.setup();
    const onOpenChange = vi.fn();

    render(
      <ConfirmDialog
        open
        onOpenChange={onOpenChange}
        title="Heads up"
        description="Just letting you know."
        confirmLabel="OK"
        hideCancel
      />
    );

    await user.click(screen.getByRole("button", { name: /ok/i }));

    await waitFor(() => {
      expect(onOpenChange).toHaveBeenCalledWith(false);
    });
  });

  it("surfaces an error message when onConfirm rejects", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn().mockRejectedValue({
      response: { data: { detail: "Course has active batches" } },
    });

    render(
      <ConfirmDialog
        open
        onOpenChange={() => {}}
        title="Delete?"
        description="Are you sure?"
        confirmLabel="Delete"
        destructive
        onConfirm={onConfirm}
      />
    );

    await user.click(screen.getByRole("button", { name: /delete/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert").textContent).toMatch(
        /course has active batches/i
      );
    });
  });
});
