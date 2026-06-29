import { describe, it, expect, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const pullMutate = vi.fn().mockResolvedValue({
  rows: 3, events: 5, inserted: 4, skipped_no_student: 0,
  skipped_duplicate: 1, days_rebuilt: 2, from_date: "2026-06-01", to_date: "2026-06-29",
});

let etoStatus: { enabled: boolean; configured: boolean } = {
  enabled: true,
  configured: true,
};

vi.mock("@/store/user-store", () => ({
  useUserStore: (sel: (s: unknown) => unknown) =>
    sel({ user: { branch_roles: [{ branch_id: "br1" }] } }),
}));

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn() }),
}));

vi.mock("@/app/(dashboard)/integrations/_hooks/use-integrations", () => ({
  useEtoStatus: () => ({ data: { ...etoStatus, base_url: "x", lookback_days: 2, default_branch_id: "br1" } }),
  useEtoPull: () => ({ mutateAsync: pullMutate, isPending: false }),
}));

import IntegrationsPage from "@/app/(dashboard)/integrations/page";

describe("IntegrationsPage", () => {
  it("shows both integration cards", () => {
    render(<IntegrationsPage />);
    expect(screen.getByText("eTimeOffice / TeamOffice")).toBeInTheDocument();
    expect(screen.getByText("BioMax SmartOffice")).toBeInTheDocument();
  });

  it("renders the BioMax device push URL", () => {
    render(<IntegrationsPage />);
    expect(screen.getByText(/\/iclock\/cdata$/)).toBeInTheDocument();
  });

  it("triggers an eTimeOffice pull and shows the result", async () => {
    const user = userEvent.setup();
    pullMutate.mockClear();
    render(<IntegrationsPage />);

    await user.click(screen.getByRole("button", { name: /pull now/i }));

    expect(pullMutate).toHaveBeenCalledTimes(1);
    // Result panel surfaces the inserted count.
    expect(await screen.findByText("Days updated")).toBeInTheDocument();
  });

  it("disables Pull now when the integration is off", () => {
    etoStatus = { enabled: false, configured: false };
    render(<IntegrationsPage />);
    const btn = screen.getByRole("button", { name: /pull now/i });
    expect(btn).toBeDisabled();
    expect(screen.getByText(/Disabled\./)).toBeInTheDocument();
    etoStatus = { enabled: true, configured: true }; // reset
  });
});
