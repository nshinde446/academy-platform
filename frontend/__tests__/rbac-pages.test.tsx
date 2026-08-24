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

describe("RBAC admin pages", () => {
  it("Accounts module is scaffolded as a placeholder", () => {
    render(<AccountsPage />);
    expect(screen.getByText("Accounts module coming soon")).toBeInTheDocument();
  });

  it("WhatsApp delivery log shows a delivered row with its status", () => {
    render(<WhatsappLogPage />);
    expect(screen.getByText("Asha Patil")).toBeInTheDocument();
    expect(screen.getByText("PRN-1001")).toBeInTheDocument();
    expect(screen.getByText("SENT")).toBeInTheDocument();
    expect(screen.getByText("auto")).toBeInTheDocument();
  });
});
