import { describe, it, expect, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { DeviceSync } from "@/app/(dashboard)/attendance/_components/device-sync";
import type {
  DeviceCommandRow,
  ProvisionDevicesResponse,
  ProvisionPlanResponse,
  ReconcileResponse,
} from "@/app/(dashboard)/attendance/_schemas/provisioning";

const devicesMock = vi.fn();
const reconcileMock = vi.fn();
const commandsMock = vi.fn();
const dryRunMutate = vi.fn();
const pushMutate = vi.fn();
const cancelMutate = vi.fn();

vi.mock("@/app/(dashboard)/attendance/_hooks/use-provisioning", () => ({
  useProvisionDevices: (...args: unknown[]) => devicesMock(...args),
  useReconcile: (...args: unknown[]) => reconcileMock(...args),
  useDeviceCommands: (...args: unknown[]) => commandsMock(...args),
  useProvisionDryRun: () => ({ mutateAsync: dryRunMutate, isPending: false }),
  useProvisionPush: () => ({ mutateAsync: pushMutate, isPending: false }),
  useCancelCommand: () => ({ mutateAsync: cancelMutate, isPending: false }),
}));

const toastSuccess = vi.fn();
const toastError = vi.fn();
vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: toastSuccess, error: toastError }),
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

function setCommands(rows: DeviceCommandRow[] | undefined, loading = false) {
  commandsMock.mockReturnValue({ data: rows, isLoading: loading });
}

const DEVICES: ProvisionDevicesResponse = {
  enabled: true,
  devices: [{ dev_id: "AMDB26013800122" }],
};

const RECONCILE: ReconcileResponse = {
  dev_id: "AMDB26013800122",
  on_platform_not_on_device: [
    { vendor_user_id: "1001", name: "Ravi Kumar", student_id: "s1" },
    { vendor_user_id: "1002", name: "Asha Patil", student_id: "s2" },
  ],
  on_device_not_on_platform: [
    { vendor_user_id: "9999", name: "Ghost User", student_id: null },
  ],
  drift: [],
};

function cmd(over: Partial<DeviceCommandRow>): DeviceCommandRow {
  return {
    id: "c1",
    dev_id: "AMDB26013800122",
    command: "SET_USER_INFO",
    vendor_user_id: "1001",
    student_id: "s1",
    command_status: "pending",
    attempts: 0,
    last_error: null,
    sent_at: null,
    confirmed_at: null,
    created_at: "2026-07-29T00:00:00Z",
    ...over,
  };
}

describe("DeviceSync", () => {
  beforeEach(() => {
    devicesMock.mockReset();
    reconcileMock.mockReset();
    commandsMock.mockReset();
    dryRunMutate.mockReset();
    pushMutate.mockReset();
    cancelMutate.mockReset();
    toastSuccess.mockReset();
    toastError.mockReset();
    setReconcile({ data: undefined });
    setCommands([]);
  });

  it("shows a dormant message and skips reconcile when provisioning is off", () => {
    setDevices({ data: { enabled: false, devices: [{ dev_id: "DEV-1" }] } });
    render(<DeviceSync branchId="br1" />);

    expect(screen.getByText("Provisioning off")).toBeInTheDocument();
    expect(screen.getByText(/turned off/i)).toBeInTheDocument();
    expect(reconcileMock).toHaveBeenLastCalledWith("br1", "DEV-1", false);
  });

  it("renders the three reconcile groups; device-only rows aren't pushable", () => {
    setDevices({ data: DEVICES });
    setReconcile({ data: RECONCILE });
    render(<DeviceSync branchId="br1" />);

    expect(screen.getByText("Provisioning on")).toBeInTheDocument();
    expect(
      screen.getByText("Need pushing (no identity on device yet)"),
    ).toBeInTheDocument();
    expect(screen.getByText("Ravi Kumar")).toBeInTheDocument();
    expect(screen.getByText("Ghost User")).toBeInTheDocument();

    // Platform rows link to the student; the device-only row does not.
    expect(screen.getByRole("link", { name: "Ravi Kumar" })).toHaveAttribute(
      "href",
      "/students/s1",
    );
    expect(
      screen.queryByRole("link", { name: "Ghost User" }),
    ).not.toBeInTheDocument();
  });

  it("defaults the selector to the first configured device", () => {
    setDevices({ data: DEVICES });
    setReconcile({ data: undefined, isLoading: true });
    render(<DeviceSync branchId="br1" />);
    expect(reconcileMock).toHaveBeenLastCalledWith("br1", "AMDB26013800122", true);
  });

  it("tells non-admins the feature is admin-only on a 403", () => {
    setDevices({ isError: true });
    render(<DeviceSync branchId="br1" />);
    expect(screen.getByText(/administrators only/i)).toBeInTheDocument();
  });

  it("selecting a student reveals the push bar and dry-runs on push", async () => {
    setDevices({ data: DEVICES });
    setReconcile({ data: RECONCILE });
    const plan: ProvisionPlanResponse = {
      dev_id: "AMDB26013800122",
      to_create: 1,
      to_update: 0,
      no_change: 0,
      skipped: 0,
      commands: [
        {
          student_id: "s1",
          vendor_user_id: "1001",
          name: "Ravi Kumar",
          action: "create",
          reason: null,
        },
      ],
    };
    dryRunMutate.mockResolvedValue(plan);
    pushMutate.mockResolvedValue({
      dev_id: "AMDB26013800122",
      enqueued: 1,
      skipped: 0,
      commands: [],
    });

    render(<DeviceSync branchId="br1" />);

    // No push bar until something is selected.
    expect(screen.queryByRole("button", { name: /Push to device/ })).toBeNull();

    fireEvent.click(screen.getByRole("checkbox", { name: "Select Ravi Kumar" }));
    expect(screen.getByText("1 student selected")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Push to device/ }));
    await waitFor(() => expect(dryRunMutate).toHaveBeenCalledWith(["s1"]));

    // Preview dialog opens with the plan.
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/queues/i)).toBeInTheDocument();

    // Confirm queues the commands.
    fireEvent.click(
      within(dialog).getByRole("button", { name: /Queue 1 command/ }),
    );
    await waitFor(() => expect(pushMutate).toHaveBeenCalledWith(["s1"]));
    expect(toastSuccess).toHaveBeenCalled();
  });

  it("shows awaiting-face rows as a non-pushable, informational group", () => {
    setDevices({ data: DEVICES });
    setReconcile({
      data: {
        ...RECONCILE,
        on_platform_not_on_device: [],
        awaiting_face_enrollment: [
          { vendor_user_id: "2001", name: "Meera Joshi", student_id: "s9" },
        ],
      },
    });
    render(<DeviceSync branchId="br1" />);

    expect(screen.getByText("Awaiting face enrollment")).toBeInTheDocument();
    expect(screen.getByText("Meera Joshi")).toBeInTheDocument();
    // Not selectable — no "Select all" checkbox for this group.
    expect(
      screen.queryByRole("checkbox", { name: /Select all in Awaiting face/ }),
    ).toBeNull();
  });

  it("select-all in a section selects every row in it", () => {
    setDevices({ data: DEVICES });
    setReconcile({ data: RECONCILE });
    render(<DeviceSync branchId="br1" />);

    fireEvent.click(
      screen.getByRole("checkbox", {
        name: /Select all in Need pushing/,
      }),
    );
    expect(screen.getByText("2 students selected")).toBeInTheDocument();
  });

  it("renders the command queue with statuses and cancels a pending command", async () => {
    setDevices({ data: DEVICES });
    setReconcile({ data: RECONCILE });
    setCommands([
      cmd({ id: "c1", vendor_user_id: "1001", command_status: "pending" }),
      cmd({ id: "c2", vendor_user_id: "1002", command_status: "confirmed" }),
    ]);
    cancelMutate.mockResolvedValue(cmd({ id: "c1", command_status: "cancelled" }));

    render(<DeviceSync branchId="br1" />);

    expect(screen.getByText("Command queue")).toBeInTheDocument();
    expect(screen.getByText("pending")).toBeInTheDocument();
    expect(screen.getByText("confirmed")).toBeInTheDocument();

    // Only the pending row exposes a Cancel action.
    const cancelButtons = screen.getAllByRole("button", { name: "Cancel" });
    expect(cancelButtons).toHaveLength(1);
    fireEvent.click(cancelButtons[0]);
    await waitFor(() => expect(cancelMutate).toHaveBeenCalledWith("c1"));
  });
});
