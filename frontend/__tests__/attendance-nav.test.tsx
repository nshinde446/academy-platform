import { describe, it, expect, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { AttendanceNav } from "@/app/(dashboard)/attendance/_components/attendance-nav";

describe("AttendanceNav", () => {
  it("renders every view with a name and a purpose", () => {
    render(<AttendanceNav view="overview" onChange={() => {}} defaultersCount={0} />);
    for (const name of [
      "Today at a glance",
      "Defaulters",
      "Batch month grid",
      "Day register",
      "Mark a lecture",
    ]) {
      expect(screen.getByText(name)).toBeInTheDocument();
    }
    expect(
      screen.getByText(/every batch's present % right now/i),
    ).toBeInTheDocument();
  });

  it("marks the current view as selected", () => {
    render(<AttendanceNav view="defaulters" onChange={() => {}} defaultersCount={0} />);
    expect(screen.getByRole("tab", { name: /Defaulters/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  it("shows the live defaulter badge only when there are defaulters", () => {
    const { rerender } = render(
      <AttendanceNav view="overview" onChange={() => {}} defaultersCount={0} />,
    );
    expect(screen.queryByText(/below 75%/)).not.toBeInTheDocument();
    rerender(
      <AttendanceNav view="overview" onChange={() => {}} defaultersCount={3} />,
    );
    expect(screen.getByText("3 below 75%")).toBeInTheDocument();
  });

  it("calls onChange with the picked view", () => {
    const onChange = vi.fn();
    render(<AttendanceNav view="overview" onChange={onChange} defaultersCount={0} />);
    fireEvent.click(screen.getByRole("tab", { name: /Batch month grid/ }));
    expect(onChange).toHaveBeenCalledWith("month");
  });
});
