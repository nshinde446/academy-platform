import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ImportScheduleDialog } from "@/app/(dashboard)/lectures/_components/import-schedule-dialog";

function renderDialog() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ImportScheduleDialog branchId="b1" />
    </QueryClientProvider>,
  );
}

describe("ImportScheduleDialog", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("opens the dialog from its trigger", async () => {
    const user = userEvent.setup();
    renderDialog();
    await user.click(screen.getByRole("button", { name: /import schedule/i }));
    expect(
      screen.getByRole("heading", { name: /import lecture schedule/i }),
    ).toBeInTheDocument();
  });

  it("downloads a sample CSV when Download sample CSV is clicked", async () => {
    const user = userEvent.setup();

    // jsdom doesn't implement URL.createObjectURL / revokeObjectURL — and
    // capture the blob the dialog hands us so we can assert its contents.
    let capturedBlob: Blob | null = null;
    const createObjectURL = vi.fn((b: Blob) => {
      capturedBlob = b;
      return "blob:mock";
    });
    const revokeObjectURL = vi.fn();
    URL.createObjectURL = createObjectURL as typeof URL.createObjectURL;
    URL.revokeObjectURL = revokeObjectURL as typeof URL.revokeObjectURL;

    // Stub anchor.click so the test doesn't actually navigate.
    const clickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => {});

    renderDialog();
    await user.click(screen.getByRole("button", { name: /import schedule/i }));
    await user.click(
      screen.getByRole("button", { name: /download sample csv/i }),
    );

    expect(clickSpy).toHaveBeenCalled();
    expect(createObjectURL).toHaveBeenCalled();
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:mock");

    // Verify the CSV contains the required headers and at least one
    // realistic example row.
    expect(capturedBlob).toBeTruthy();
    const text = await (capturedBlob as unknown as Blob).text();
    expect(text).toContain("date,start_time,end_time,teacher_email,batch_code,subject_code");
    expect(text).toContain("classroom_code");
    expect(text).toContain("delivery_mode");
    expect(text).toContain("notes");
    expect(text).toContain("2026-06-01");
    expect(text).toContain("offline");
  });
});
