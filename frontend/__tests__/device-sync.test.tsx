import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { DeviceSync } from "@/app/(dashboard)/attendance/_components/device-sync";
import type {
  ProvisionDevicesResponse,
  ReconcileResponse,
} from "@/app/(dashboard)/attendance/_schemas/provisioning";

const devicesMock = vi.fn();
const reconcileMock = vi.fn();

vi.mock("@/app/(dashboard)/attendance/_hooks/use-provisioning", () => ({
  useProvisionDevices: (...args: unknown[]) => devicesMock(...args),
  useReconcile: (...args: unknown[]) => reconcileMock(...args),
}));

function setDevices(over: {
  data?: ProvisionDevicesResponse;
  isLoading?: boolean;
  isError?: boolean;
}) {
  devicesMock.mockReturnValue({
    data: over.data,
    isLoading: over.isLoading ?? false,
    isError: over.isError ?? false,
  });
}

function setReconcile(over: {
  data?: ReconcileResponse;
  isLoading?: boolean;
  isError?: boolean;
}) {
  reconcileMock.mockReturnValue({
    data: over.data,
    isLoading: over.isLoading ?? false,
    isError: over.isError ?? false,
  });
}

const DEVICES: ProvisionDevicesResponse = {
  enabled: true,
  devices: [{ dev_id: "AMDB26013800122" }],
};

describe("DeviceSync", () => {
  beforeEach(() => {
    devicesMock.mockReset();
    reconcileMock.mockReset();
    setReconcile({ data: undefined });
  });

  it("shows a dormant message and skips reconcile when provisioning is off", () => {
    setDevices({ data: { enabled: false, devices: [{ dev_id: "DEV-1" }] } });
    render(<DeviceSync branchId="br1" />);

    expect(screen.getByText("Provisioning off")).toBeInTheDocument();
    expect(screen.getByText(/turned off/i)).toBeInTheDocument();
    // Reconcile is called but with enabled=false so the hook stays idle.
    expect(reconcileMock).toHaveBeenLastCalledWith("br1", "DEV-1", false);
  });

  it("renders the three reconcile groups with counts", () => {
    setDevices({ data: DEVICES });
    setReconcile({
      data: {
        dev_id: "AMDB26013800122",
        on_platform_not_on_device: [
          { vendor_user_id: "1001", name: "Ravi Kumar", student_id: "s1" },
          { vendor_user_id: "1002", name: "Asha Patil", student_id: "s2" },
        ],
        on_device_not_on_platform: [
          { vendor_user_id: "9999", name: "Ghost User", student_id: null },
        ],
        drift: [],
      },
    });
    render(<DeviceSync branchId="br1" />);

    expect(screen.getByText("Provisioning on")).toBeInTheDocument();
    expect(
      screen.getByText("On the platform, not on the device"),
    ).toBeInTheDocument();
    expect(screen.getByText("Ravi Kumar")).toBeInTheDocument();
    expect(screen.getByText("Ghost User")).toBeInTheDocument();

    // A platform-side row links to the student; a device-only row does not.
    expect(screen.getByRole("link", { name: "Ravi Kumar" })).toHaveAttribute(
      "href",
      "/students/s1",
    );
    expect(
      screen.queryByRole("link", { name: "Ghost User" }),
    ).not.toBeInTheDocument();

    // The "need pushing" tile reflects the 2 platform-only rows.
    const tile = screen.getByText("Need pushing").parentElement as HTMLElement;
    expect(within(tile).getByText("2")).toBeInTheDocument();
  });

  it("defaults the selector to the first configured device", () => {
    setDevices({ data: DEVICES });
    setReconcile({ data: undefined, isLoading: true });
    render(<DeviceSync branchId="br1" />);
    // Reconcile is keyed on the auto-selected device without any interaction.
    expect(reconcileMock).toHaveBeenLastCalledWith(
      "br1",
      "AMDB26013800122",
      true,
    );
  });

  it("tells non-admins the feature is admin-only on a 403", () => {
    setDevices({ isError: true });
    render(<DeviceSync branchId="br1" />);
    expect(screen.getByText(/administrators only/i)).toBeInTheDocument();
  });
});
