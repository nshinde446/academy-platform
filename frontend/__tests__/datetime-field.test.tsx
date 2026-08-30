import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  DateTimeField,
  addMinutesToLocal,
} from "@/components/ui/datetime-field";

describe("addMinutesToLocal", () => {
  it("adds minutes and keeps the datetime-local shape", () => {
    expect(addMinutesToLocal("2026-05-20T10:00", 90)).toBe("2026-05-20T11:30");
    expect(addMinutesToLocal("2026-05-20T23:30", 60)).toBe("2026-05-21T00:30");
  });

  it("returns the input unchanged when it isn't a valid datetime", () => {
    expect(addMinutesToLocal("", 60)).toBe("");
  });
});

describe("DateTimeField", () => {
  it("renders a date input and a typeable time dropdown (no minute spinner)", () => {
    render(
      <DateTimeField value="2026-05-20T10:00" onChange={() => {}} ariaLabel="Start" />,
    );
    expect(screen.getByLabelText("Start date")).toHaveValue("2026-05-20");
    const time = screen.getByLabelText("Start time") as HTMLSelectElement;
    expect(time.tagName).toBe("SELECT");
    expect(time.value).toBe("10:00");
  });

  it("emits the recombined value when the time is changed", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <DateTimeField
        value="2026-05-20T10:00"
        onChange={onChange}
        ariaLabel="Start"
        step={15}
      />,
    );
    await user.selectOptions(screen.getByLabelText("Start time"), "10:30");
    expect(onChange).toHaveBeenCalledWith("2026-05-20T10:30");
  });

  it("emits the recombined value when the date is changed", () => {
    const onChange = vi.fn();
    render(
      <DateTimeField value="2026-05-20T10:00" onChange={onChange} ariaLabel="Start" />,
    );
    fireEvent.change(screen.getByLabelText("Start date"), {
      target: { value: "2026-05-21" },
    });
    expect(onChange).toHaveBeenCalledWith("2026-05-21T10:00");
  });

  it("preserves an off-grid time as a selectable option", () => {
    render(
      <DateTimeField
        value="2026-05-20T10:07"
        onChange={() => {}}
        ariaLabel="Actual start"
        step={15}
      />,
    );
    // 10:07 isn't on the 15-min grid but must still be shown/selected.
    expect(screen.getByLabelText("Actual start time")).toHaveValue("10:07");
  });
});
