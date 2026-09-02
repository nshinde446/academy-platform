import { describe, it, expect, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { DeviceSync } from "@/app/(dashboard)/attendance/_components/device-sync";
import type {
  DeviceCommandRow,
  InstituteReconcileResponse,
  ProvisionDevicesResponse,
  ProvisionPlanResponse,
} from "@/app/(dashboard)/attendance/_schemas/provisioning";

const devicesMock = vi.fn();
const instituteMock = vi.fn();
const commandsMock = vi.fn();
const dryRunMutate = vi.fn();
const pushMutate = vi.fn();
const cancelMutate = vi.fn();

vi.mock("@/app/(dashboard)/attendance/_hooks/use-provisioning", () => ({
  useProvisionDevices: (...args: unknown[]) => devicesMock(...args),
  useInstituteReconcile: (...args: unknown[]) => instituteMock(...args),
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

function setInstitute(over: {
  data?: InstituteReconcileResponse;
  isLoading?: boolean;
  isError?: boolean;
}) {
  instituteMock.mockReturnValue({
    data: over.data,
    isLoading: over.isLoading ?? false,
    isError: over.isError ?? false,
  });
}

function setCommands(rows: DeviceCommandRow[] | undefined, loading = false) {
  commandsMock.mockReturnValue({ data: rows, isLoading: loading });
}

const DEV1 = "AMDB26013800122";
const DEV2 = "AMDB25083200131";

const DEVICES: ProvisionDevicesResponse = {
  enabled: true,
  devices: [{ dev_id: DEV1 }, { dev_id: DEV2 }],
};

// Two machines so the health strip + queue selector are exercised. DEV1 has
// reported live counts; DEV2 hasn't polled yet.
const INSTITUTE: InstituteReconcileResponse = {
  total_students: 5,
  face_enrolled: 2,
  awaiting_face: [],
  not_pushed: [
    { vendor_user_id: "1001", name: "Ravi Kumar", student_id: "s1" },
    { vendor_user_id: "1002", name: "Asha Patil", student_id: "s2" },
  ],
  name_drift: [],
  on_device_not_on_platform: [
    { vendor_user_id: "9999", name: "Ghost User", student_id: null },
  ],
  machines: [
    {
      dev_id: DEV1,
      last_seen_at: new Date().toISOString(),
      user_count: 116,
      face_count: 115,
      fp_count: 1,
      firmware: "K8D",
    },
    {
      dev_id: DEV2,
      last_seen_at: null,
      user_count: null,
      face_count: null,
      fp_count: null,
      firmware: null,
    },
  ],
};

function cmd(over: Partial<DeviceCommandRow>): DeviceCommandRow {
  return {
    id: "c1",
    dev_id: DEV1,
    command: "SET_USER_INFO",
    vendor_user_id: "1001",
    batch_user_count: null,
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

describe("DeviceSync (institute-wide)", () => {
  beforeEach(() => {
    devicesMock.mockReset();
    instituteMock.mockReset();
    commandsMock.mockReset();
    dryRunMutate.mockReset();
    pushMutate.mockReset();
    cancelMutate.mockReset();
    toastSuccess.mockReset();
    toastError.mockReset();
    setInstitute({ data: undefined });
    setCommands([]);
  });

  it("shows a dormant message and skips reconcile when provisioning is off", () => {
    setDevices({ data: { enabled: false, devices: [{ dev_id: DEV1 }] } });
    render(<DeviceSync branchId="br1" />);

    expect(screen.getByText("Provisioning off")).toBeInTheDocument();
    expect(screen.getByText(/turned off/i)).toBeInTheDocument();
    // Institute reconcile is gated on the enabled flag.
    expect(instituteMock).toHaveBeenLastCalledWith("br1", false);
  });

  it("renders the institute summary and actionable buckets, dedup across machines", () => {
    setDevices({ data: DEVICES });
    setInstitute({ data: INSTITUTE });
    render(<DeviceSync branchId="br1" />);

    expect(screen.getByText("Provisioning on")).toBeInTheDocument();
    // Summary tiles counted once across the institute.
    expect(screen.getByText("Students")).toBeInTheDocument();
    expect(screen.getByText("Face enrolled")).toBeInTheDocument();
    expect(
      screen.getByText("Not pushed (no identity on any machine)"),
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

  it("shows each machine's own live counts in the health strip", () => {
    setDevices({ data: DEVICES });
    setInstitute({ data: INSTITUTE });
    render(<DeviceSync branchId="br1" />);

    // The serial is shown (strip + queue selector both reference it).
    expect(screen.getAllByText(DEV1).length).toBeGreaterThan(0);
    // DEV1's reported live counts.
    expect(screen.getByText("116")).toBeInTheDocument();
    expect(screen.getByText("115")).toBeInTheDocument();
  });

  it("gates the institute reconcile on the enabled flag", () => {
    setDevices({ data: DEVICES });
    setInstitute({ data: undefined, isLoading: true });
    render(<DeviceSync branchId="br1" />);
    expect(instituteMock).toHaveBeenLastCalledWith("br1", true);
  });

  it("tells non-admins the feature is admin-only on a 403", () => {
    setDevices({ isError: true });
    render(<DeviceSync branchId="br1" />);
    expect(screen.getByText(/administrators only/i)).toBeInTheDocument();
  });

  it("selecting a student reveals the push bar and dry-runs on push", async () => {
    setDevices({ data: DEVICES });
    setInstitute({ data: INSTITUTE });
    const plan: ProvisionPlanResponse = {
      dev_id: DEV1,
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
      dev_id: DEV1,
      enqueued: 1,
      skipped: 0,
      commands: [],
    });

    render(<DeviceSync branchId="br1" />);

    // No push bar until something is selected.
    expect(screen.queryByRole("button", { name: /Push to machine/ })).toBeNull();

    fireEvent.click(screen.getByRole("checkbox", { name: "Select Ravi Kumar" }));
    expect(screen.getByText("1 student selected")).toBeInTheDocument();
    // A target-machine picker is offered in the push bar.
    expect(
      screen.getByRole("combobox", { name: /Target machine for push/ }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Push to machine/ }));
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
    setInstitute({
      data: {
        ...INSTITUTE,
        not_pushed: [],
        awaiting_face: [
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
    setInstitute({ data: INSTITUTE });
    render(<DeviceSync branchId="br1" />);

    fireEvent.click(
      screen.getByRole("checkbox", {
        name: /Select all in Not pushed/,
      }),
    );
    expect(screen.getByText("2 students selected")).toBeInTheDocument();
  });

  it("renders the command queue with statuses and cancels a pending command", async () => {
    setDevices({ data: DEVICES });
    setInstitute({ data: INSTITUTE });
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

  it("labels batch commands legibly instead of a bare dash", () => {
    setDevices({ data: DEVICES });
    setInstitute({ data: INSTITUTE });
    setCommands([
      cmd({
        id: "b1",
        command: "GET_USER_INFO",
        vendor_user_id: null,
        batch_user_count: 5,
        student_id: null,
        command_status: "pending",
      }),
    ]);

    render(<DeviceSync branchId="br1" />);

    // Friendly command name, not the raw wire code.
    expect(screen.getByText("Refresh face status")).toBeInTheDocument();
    expect(screen.queryByText("GET_USER_INFO")).not.toBeInTheDocument();
    // Batch target shows the user count rather than "—".
    expect(screen.getByText("batch · 5 users")).toBeInTheDocument();
  });
});
