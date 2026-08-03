import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Switch } from "@/components/ui/switch";

describe("Switch", () => {
  it("renders a switch role reflecting the checked state", () => {
    render(<Switch checked aria-label="Toggle" onCheckedChange={() => {}} />);
    expect(screen.getByRole("switch")).toBeChecked();
  });

  it("fires onCheckedChange with the next value when clicked", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Switch checked={false} aria-label="Toggle" onCheckedChange={onChange} />);

    await user.click(screen.getByRole("switch"));

    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange.mock.calls[0][0]).toBe(true);
  });

  it("does not fire when disabled", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <Switch checked={false} disabled aria-label="Toggle" onCheckedChange={onChange} />,
    );

    await user.click(screen.getByRole("switch"));

    expect(onChange).not.toHaveBeenCalled();
  });
});
