import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import AccountsPage from "@/app/(dashboard)/accounts/page";
import WhatsappLogPage from "@/app/(dashboard)/whatsapp-log/page";
import type { DeliveryLogRow } from "@/app/(dashboard)/whatsapp-log/_hooks/use-delivery-log";

const deliveryRows: DeliveryLogRow[] = [
  {
    id: "d1",
    student_name: "Asha Patil",
    prn: "PRN-1001",
    parent_contact: "+919999999999",
    date: "2026-08-20",
    delivery_status: "SENT",
    sent_by: "auto",
    sent_at: "2026-08-20T10:00:00Z",
    error_message: null,
    created_at: "2026-08-20T10:00:00Z",
  },
];

vi.mock("@/app/(dashboard)/whatsapp-log/_hooks/use-delivery-log", () => ({
  useDeliveryLog: () => ({ data: deliveryRows, isLoading: false, isError: false }),
}));

// The filters bar populates its Batch dropdown from useBatches; stub it so the
// page renders without a QueryClient in the test.
vi.mock("@/app/(dashboard)/batches/_hooks/use-batches", () => ({
  useBatches: () => ({ data: [], isLoading: false, isError: false }),
}));

// The Accounts page drives the fees module via react-query hooks + toast; stub
// them so it renders without a QueryClient / Toast.Provider in the test.
vi.mock("@/app/(dashboard)/accounts/_hooks/use-fees", () => {
  const empty = () => ({ data: undefined, isLoading: false, isError: false });
  return {
    useFollowUp: empty,
    useRecordPayment: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useAddRemark: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useCourseFees: () => ({ data: [], isLoading: false, isError: false }),
    useCreateFeeProfile: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useStudentsInBatch: () => ({ data: [], isLoading: false, isError: false }),
    useFeeProfile: empty,
  };
});
vi.mock("@/app/(dashboard)/lectures/_hooks/use-lectures", () => ({
  useBatchesForLectures: () => ({ data: [], isLoading: false, isError: false }),
}));
vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}));

describe("RBAC admin pages", () => {
  it("Accounts page renders the fees module (follow-up tab)", () => {
    render(<AccountsPage />);
    expect(screen.getByRole("heading", { name: "Accounts" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /daily follow-up/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /new fee profile/i })).toBeInTheDocument();
  });

  it("WhatsApp delivery log shows a delivered row with its status", () => {
    render(<WhatsappLogPage />);
    expect(screen.getByText("Asha Patil")).toBeInTheDocument();
    expect(screen.getByText("PRN-1001")).toBeInTheDocument();
    expect(screen.getByText("SENT")).toBeInTheDocument();
    expect(screen.getByText("auto")).toBeInTheDocument();
  });
});
