import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  QBFilterRail,
  type QBFilters,
} from "@/app/(dashboard)/question-bank/_components/qb-filter-rail";

const DEFAULT: QBFilters = {
  review_status: "pending_review",
  difficulty: "",
  source_prefix: "",
};

const COUNTS = { pending: 87, approved: 1604, rejected: 12 };

describe("QBFilterRail", () => {
  it("renders the three section headings", () => {
    render(
      <QBFilterRail filters={DEFAULT} onChange={() => {}} counts={COUNTS} />,
    );
    expect(screen.getByText("Status")).toBeInTheDocument();
    expect(screen.getByText("Difficulty")).toBeInTheDocument();
    expect(screen.getByText("Source")).toBeInTheDocument();
  });

  it("renders status counts next to each option", () => {
    render(
      <QBFilterRail filters={DEFAULT} onChange={() => {}} counts={COUNTS} />,
    );
    expect(screen.getByText("87")).toBeInTheDocument();
    expect(screen.getByText("1604")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
  });

  it("marks the active status with aria-pressed", () => {
    render(
      <QBFilterRail filters={DEFAULT} onChange={() => {}} counts={COUNTS} />,
    );
    expect(
      screen.getByRole("button", { name: /pending review/i }),
    ).toHaveAttribute("aria-pressed", "true");
    expect(
      screen.getByRole("button", { name: /^approved/i }),
    ).toHaveAttribute("aria-pressed", "false");
  });

  it("emits the new filter on click", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <QBFilterRail filters={DEFAULT} onChange={onChange} counts={COUNTS} />,
    );

    await user.click(screen.getByRole("button", { name: /hard/i }));
    expect(onChange).toHaveBeenCalledWith({
      ...DEFAULT,
      difficulty: "HARD",
    });
  });

  it("toggles an active filter off on second click", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <QBFilterRail
        filters={{ ...DEFAULT, difficulty: "EASY" }}
        onChange={onChange}
        counts={COUNTS}
      />,
    );

    await user.click(screen.getByRole("button", { name: /easy/i }));
    expect(onChange).toHaveBeenCalledWith({
      ...DEFAULT,
      difficulty: "",
    });
  });
});
