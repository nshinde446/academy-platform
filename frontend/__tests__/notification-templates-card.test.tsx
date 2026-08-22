import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { NotificationTemplate } from "@/app/(dashboard)/settings/_schemas/settings";

const TEMPLATES: NotificationTemplate[] = [
  {
    id: "t1",
    name: "Attendance — absent alert",
    event_type: "STUDENT_ABSENT",
    channel: "WHATSAPP",
    subject: null,
    body_template: "Dear Parent, {student_name} was absent on {attendance_date}.",
    is_active: true,
    branch_id: null,
    provider_template_name: "attendance_absent_alert",
    provider_language: "en",
  },
];

const updateMutate = vi.fn().mockResolvedValue({});

vi.mock("@/app/(dashboard)/settings/_hooks/use-notification-settings", () => ({
  useNotificationTemplates: () => ({
    data: TEMPLATES,
    isLoading: false,
    isError: false,
  }),
  useUpdateNotificationTemplate: () => ({
    mutateAsync: updateMutate,
    isPending: false,
  }),
}));

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}));

import { NotificationTemplatesCard } from "@/app/(dashboard)/settings/_components/notification-templates-card";

beforeEach(() => {
  updateMutate.mockClear();
});

describe("NotificationTemplatesCard", () => {
  it("renders each template with its message and channel", () => {
    render(<NotificationTemplatesCard branchId="br1" />);
    expect(screen.getByText("Attendance — absent alert")).toBeInTheDocument();
    expect(screen.getByText("WHATSAPP")).toBeInTheDocument();
    expect(
      screen.getByDisplayValue(/Dear Parent, \{student_name\}/),
    ).toBeInTheDocument();
  });

  it("saves an edited template via the update mutation", async () => {
    const user = userEvent.setup();
    render(<NotificationTemplatesCard branchId="br1" />);

    const textarea = screen.getByLabelText(/message for attendance/i);
    await user.clear(textarea);
    // Avoid "{" in typed text — userEvent treats it as a special-key sequence.
    await user.type(textarea, "New wording for parents");

    await user.click(screen.getByRole("button", { name: /^save$/i }));

    expect(updateMutate).toHaveBeenCalledTimes(1);
    expect(updateMutate.mock.calls[0][0]).toMatchObject({
      id: "t1",
      data: expect.objectContaining({
        body_template: "New wording for parents",
        provider_template_name: "attendance_absent_alert",
      }),
    });
  });

  it("keeps Save disabled until an edit is made", () => {
    render(<NotificationTemplatesCard branchId="br1" />);
    expect(screen.getByRole("button", { name: /^save$/i })).toBeDisabled();
  });
});
