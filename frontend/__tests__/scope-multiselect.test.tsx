import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  ScopeMultiSelect,
  type ScopeOption,
} from "@/app/(dashboard)/staff/_components/scope-multiselect";

const options: ScopeOption[] = [
  { id: "a", label: "MSA-Teachers" },
  { id: "b", label: "Security" },
  { id: "c", label: "Cleaning Unit" },
];

const onChange = vi.fn();

beforeEach(() => vi.clearAllMocks());

function renderScope(
  over: Partial<React.ComponentProps<typeof ScopeMultiSelect>> = {},
) {
  return render(
    <ScopeMultiSelect
      label="Departments"
      allLabel="All departments"
      options={options}
      selected={new Set()}
      onChange={onChange}
      {...over}
    />,
  );
}

describe("ScopeMultiSelect", () => {
  it("treats an empty selection as 'All' and summarises it", () => {
    renderScope();
    expect(screen.getByText("All departments")).toBeInTheDocument();
    // The "All" row checkbox is the only checked box.
    const boxes = screen.getAllByRole("checkbox") as HTMLInputElement[];
    expect(boxes[0].checked).toBe(true);
    expect(boxes.slice(1).every((b) => !b.checked)).toBe(true);
  });

  it("adds an id to the selection when a row is ticked", async () => {
    const user = userEvent.setup();
    renderScope();
    await user.click(screen.getByText("Security"));
    expect(onChange).toHaveBeenCalledTimes(1);
    expect([...onChange.mock.calls[0][0]]).toEqual(["b"]);
  });

  it("removes an id when a ticked row is clicked again", async () => {
    const user = userEvent.setup();
    renderScope({ selected: new Set(["b"]) });
    await user.click(screen.getByText("Security"));
    expect([...onChange.mock.calls[0][0]]).toEqual([]);
  });

  it("clears the selection back to 'All' when the All row is ticked", async () => {
    const user = userEvent.setup();
    renderScope({ selected: new Set(["a", "b"]) });
    expect(screen.getByText("2 selected")).toBeInTheDocument();
    await user.click(screen.getByText("All departments"));
    expect([...onChange.mock.calls[0][0]]).toEqual([]);
  });

  it("shows the disabled note instead of the list when disabled", () => {
    renderScope({ disabled: true, disabledNote: "Ignored while staff chosen." });
    expect(screen.getByText("Ignored while staff chosen.")).toBeInTheDocument();
    expect(screen.queryByText("MSA-Teachers")).not.toBeInTheDocument();
  });

  it("shows the empty note when there are no options", () => {
    renderScope({ options: [], emptyNote: "No departments yet." });
    expect(screen.getByText("No departments yet.")).toBeInTheDocument();
  });
});
