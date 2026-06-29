import { describe, it, expect, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PageHeader } from "@/components/layout/page-header";

describe("PageHeader", () => {
  it("renders the title and actions inline", () => {
    render(
      <PageHeader
        title="Attendance"
        actions={<button type="button">Mark all present</button>}
      />,
    );
    expect(
      screen.getByRole("heading", { name: "Attendance" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Mark all present" }),
    ).toBeInTheDocument();
  });

  it("hides the description behind an info popover (progressive disclosure)", async () => {
    const user = userEvent.setup();
    render(<PageHeader title="Attendance" description="A long helper note." />);

    // Not shown until requested — reclaims the vertical space.
    expect(screen.queryByText("A long helper note.")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /what is this/i }));
    expect(screen.getByRole("tooltip")).toHaveTextContent("A long helper note.");
  });

  it("closes the popover on Escape", async () => {
    const user = userEvent.setup();
    render(<PageHeader title="X" description="hello" />);
    await user.click(screen.getByRole("button", { name: /what is this/i }));
    expect(screen.getByRole("tooltip")).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("renders a second-row child (e.g. a view toggle)", () => {
    render(
      <PageHeader title="Lectures">
        <div data-testid="toggle">Full · Calendar</div>
      </PageHeader>,
    );
    expect(screen.getByTestId("toggle")).toBeInTheDocument();
  });

  it("omits the info button when there is no description", () => {
    render(<PageHeader title="Papers" />);
    expect(
      screen.queryByRole("button", { name: /what is this/i }),
    ).not.toBeInTheDocument();
  });
});
