import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SelectionBar } from "@/components/ui/selection-bar";

const handlers = {
  onDelete: vi.fn(),
  onClear: vi.fn(),
};

beforeEach(() => vi.clearAllMocks());

describe("SelectionBar", () => {
  it("renders nothing when nothing is selected", () => {
    const { container } = render(
      <SelectionBar count={0} noun="course" {...handlers} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("pluralizes the noun by count", () => {
    const { rerender } = render(
      <SelectionBar count={1} noun="course" {...handlers} />,
    );
    expect(screen.getByText("1 course selected")).toBeInTheDocument();
    rerender(<SelectionBar count={3} noun="course" {...handlers} />);
    expect(screen.getByText("3 courses selected")).toBeInTheDocument();
  });

  it("fires onDelete and onClear", async () => {
    const user = userEvent.setup();
    render(<SelectionBar count={2} noun="batch" {...handlers} />);
    await user.click(screen.getByRole("button", { name: /delete selected/i }));
    await user.click(screen.getByRole("button", { name: /^clear$/i }));
    expect(handlers.onDelete).toHaveBeenCalled();
    expect(handlers.onClear).toHaveBeenCalled();
  });

  it("disables the delete button while pending", () => {
    render(<SelectionBar count={2} noun="batch" pending {...handlers} />);
    expect(
      screen.getByRole("button", { name: /delete selected/i }),
    ).toBeDisabled();
  });
});
