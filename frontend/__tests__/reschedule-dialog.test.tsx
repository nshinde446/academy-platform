import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { RescheduleDialog } from "@/app/(dashboard)/lectures/_components/reschedule-dialog";
import type { LectureResponse } from "@/app/(dashboard)/lectures/_schemas/lecture";

// The dialog only reads scheduled_start/end + classroom_id; cast a partial.
const lecture = {
  id: "lec-1",
  scheduled_start: "2026-07-24T09:00:00.000Z",
  scheduled_end: "2026-07-24T10:00:00.000Z",
  classroom_id: null,
} as unknown as LectureResponse;

const classrooms = [{ id: "room-1", name: "Room 101" }];

function renderDialog(onSubmit = vi.fn()) {
  render(
    <RescheduleDialog
      lecture={lecture}
      classrooms={classrooms}
      open
      onOpenChange={() => {}}
      onSubmit={onSubmit}
      isPending={false}
    />,
  );
  return onSubmit;
}

describe("RescheduleDialog", () => {
  it("prefills the start and end from the lecture's current schedule", () => {
    renderDialog();
    const start = screen.getByLabelText("New start *") as HTMLInputElement;
    const end = screen.getByLabelText("New end *") as HTMLInputElement;
    // datetime-local strings (local wall-clock); non-empty and end after start.
    expect(start.value).not.toBe("");
    expect(end.value).not.toBe("");
    expect(end.value > start.value).toBe(true);
  });

  it("blocks submit when end is not after start", async () => {
    const onSubmit = renderDialog();
    const start = screen.getByLabelText("New start *") as HTMLInputElement;
    const end = screen.getByLabelText("New end *") as HTMLInputElement;
    // Set end before start.
    fireEvent.change(end, { target: { value: start.value } });
    fireEvent.click(screen.getByRole("button", { name: "Reschedule" }));
    expect(
      await screen.findByText("End time must be after the start time."),
    ).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("submits ISO times and the chosen room", async () => {
    const onSubmit = renderDialog();
    fireEvent.change(screen.getByLabelText("Room"), {
      target: { value: "room-1" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Reschedule" }));
    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    const payload = onSubmit.mock.calls[0][0];
    expect(payload.classroom_id).toBe("room-1");
    // ISO 8601 UTC strings round-tripped through the datetime-local inputs.
    expect(new Date(payload.scheduled_start).toISOString()).toBe(
      payload.scheduled_start,
    );
    expect(
      new Date(payload.scheduled_end).getTime() >
        new Date(payload.scheduled_start).getTime(),
    ).toBe(true);
  });
});
