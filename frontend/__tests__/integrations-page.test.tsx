import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const pullMutate = vi.fn().mockResolvedValue({
  rows: 3, events: 5, inserted: 4, skipped_no_student: 0,
  skipped_duplicate: 1, days_rebuilt: 2, from_date: "2026-06-01", to_date: "2026-06-29",
});

let soStatus: { enabled: boolean; configured: boolean } = {
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
  useSmartOfficeStatus: () => ({
    data: { ...soStatus, base_url: "x", lookback_days: 1, default_branch_id: "br1" },
  }),
  useSmartOfficePull: () => ({ mutateAsync: pullMutate, isPending: false }),
}));

import IntegrationsPage from "@/app/(dashboard)/integrations/page";

describe("IntegrationsPage", () => {
  it("shows only the BioMax SmartOffice integration (no eTimeOffice)", () => {
    render(<IntegrationsPage />);
    expect(screen.getByText("BioMax SmartOffice")).toBeInTheDocument();
    expect(screen.queryByText(/eTimeOffice/i)).not.toBeInTheDocument();
  });

  it("surfaces the agent ingest URL and the direct device push URL to configure", () => {
    render(<IntegrationsPage />);
    expect(
      screen.getByText(/\/api\/v1\/attendance\/smartoffice\/ingest$/),
    ).toBeInTheDocument();
    expect(screen.getByText(/\/iclock\/cdata$/)).toBeInTheDocument();
  });

  it("links to the device setup guide", () => {
    render(<IntegrationsPage />);
    const link = screen.getByRole("link", { name: /setup guide/i });
    expect(link).toHaveAttribute(
      "href",
      expect.stringContaining("biomax-direct-push-setup"),
    );
    expect(link).toHaveAttribute("target", "_blank");
  });

  it("triggers a cloud pull test and shows the result", async () => {
    const user = userEvent.setup();
    pullMutate.mockClear();
    render(<IntegrationsPage />);

    await user.click(screen.getByRole("button", { name: /pull now/i }));

    expect(pullMutate).toHaveBeenCalledTimes(1);
    expect(await screen.findByText("Days updated")).toBeInTheDocument();
  });

  it("disables Pull now when cloud pull is off", () => {
    soStatus = { enabled: false, configured: false };
    render(<IntegrationsPage />);
    const btn = screen.getByRole("button", { name: /pull now/i });
    expect(btn).toBeDisabled();
    expect(screen.getByText(/Cloud pull disabled\./)).toBeInTheDocument();
    soStatus = { enabled: true, configured: true }; // reset
  });
});
