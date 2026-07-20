import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ErrorState } from "@/components/ui/error-state";
import DashboardError from "@/app/(dashboard)/error";
import RootError from "@/app/error";

afterEach(() => vi.restoreAllMocks());

describe("ErrorState", () => {
  it("exposes itself to assistive tech as an alert", () => {
    render(<ErrorState />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("shows the digest so a production error can be quoted in a report", () => {
    render(<ErrorState digest="abc123" />);
    expect(screen.getByText(/abc123/)).toBeInTheDocument();
  });

  it("hides the retry button when there is nothing to retry", () => {
    render(<ErrorState />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("calls onRetry when the retry button is pressed", async () => {
    const onRetry = vi.fn();
    render(<ErrorState onRetry={onRetry} />);
    await userEvent.click(screen.getByRole("button", { name: /try again/i }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});

describe("route error boundaries", () => {
  it("dashboard boundary resets the segment rather than reloading", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const reset = vi.fn();
    render(<DashboardError error={new Error("boom")} reset={reset} />);

    await userEvent.click(screen.getByRole("button", { name: /try again/i }));
    expect(reset).toHaveBeenCalledTimes(1);
  });

  it("root boundary logs the error under a greppable prefix", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    const error = new Error("boom");
    render(<RootError error={error} reset={vi.fn()} />);

    expect(spy).toHaveBeenCalledWith("[boundary:root]", error);
  });
});
