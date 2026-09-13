import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mutateAsync = vi.fn().mockResolvedValue([]);
const toast = { success: vi.fn(), error: vi.fn() };

let batchesData: {
  batch_id: string;
  name: string;
  code: string;
  student_count: number;
  enabled: boolean;
}[];

vi.mock("@/components/ui/toast", () => ({
  useToast: () => toast,
}));

vi.mock(
  "@/app/(dashboard)/settings/_hooks/use-notification-settings",
  () => ({
    useWhatsappBatches: () => ({
      data: batchesData,
      isLoading: false,
      isError: false,
    }),
    useUpdateWhatsappBatches: () => ({
      mutateAsync,
      isPending: false,
    }),
  }),
);

import { WhatsappBatchesCard } from "@/app/(dashboard)/settings/_components/whatsapp-batches-card";

beforeEach(() => {
  vi.clearAllMocks();
  batchesData = [
    { batch_id: "a", name: "12th CJ", code: "CJ", student_count: 44, enabled: false },
    { batch_id: "b", name: "12th JEE", code: "JEE", student_count: 34, enabled: true },
  ];
});

describe("WhatsappBatchesCard", () => {
  it("lists batches with their reach", () => {
    render(<WhatsappBatchesCard branchId="br1" />);
    expect(screen.getByText("12th CJ")).toBeInTheDocument();
    expect(screen.getByText(/CJ · 44 students/)).toBeInTheDocument();
    // one of two enabled by default
    expect(screen.getByText(/1 of 2/)).toBeInTheDocument();
  });

  it("enabling a batch makes Save active and PUTs the new set", async () => {
    const user = userEvent.setup();
    render(<WhatsappBatchesCard branchId="br1" />);

    // Save is disabled until a change is made.
    expect(screen.getByRole("button", { name: /^save$/i })).toBeDisabled();

    await user.click(
      screen.getByRole("switch", { name: /notifications for 12th CJ/i }),
    );
    const save = screen.getByRole("button", { name: /^save$/i });
    expect(save).toBeEnabled();

    await user.click(save);
    // Started with {b} enabled; adding {a} => both.
    expect(mutateAsync).toHaveBeenCalledTimes(1);
    expect([...mutateAsync.mock.calls[0][0]].sort()).toEqual(["a", "b"]);
  });

  it("Clear empties the selection and saves an empty set", async () => {
    const user = userEvent.setup();
    render(<WhatsappBatchesCard branchId="br1" />);

    await user.click(screen.getByRole("button", { name: /^clear$/i }));
    await user.click(screen.getByRole("button", { name: /^save$/i }));
    expect(mutateAsync).toHaveBeenCalledWith([]);
  });

  it("Select all enables every batch", async () => {
    const user = userEvent.setup();
    render(<WhatsappBatchesCard branchId="br1" />);

    await user.click(screen.getByRole("button", { name: /select all/i }));
    await user.click(screen.getByRole("button", { name: /^save$/i }));
    expect([...mutateAsync.mock.calls[0][0]].sort()).toEqual(["a", "b"]);
  });
});
