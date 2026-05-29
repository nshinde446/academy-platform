import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RecentPapers } from "@/app/(dashboard)/papers/_components/recent-papers";
import type { TestResponse } from "@/app/(dashboard)/papers/_schemas/paper";

function paper(id: string, name: string): TestResponse {
  return {
    id,
    name,
    description: null,
    paper_type: "DPP",
    batch_id: "b1",
    subject_id: "s1",
    scheduled_at: null,
    duration_minutes: 60,
    total_marks: 10,
    test_status: "DRAFT",
    branch_id: "br1",
    academic_year_id: "ay1",
    status: "active",
  };
}

const NOOP = () => {};

describe("RecentPapers", () => {
  it("renders nothing when there are no papers", () => {
    const { container } = render(
      <RecentPapers
        papers={[]}
        onDownload={NOOP}
        onDelete={NOOP}
        busyKey={null}
        deletingId={null}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("lists papers with Paper + Key + Delete buttons", () => {
    render(
      <RecentPapers
        papers={[paper("1", "Mechanics DPP")]}
        onDownload={NOOP}
        onDelete={NOOP}
        busyKey={null}
        deletingId={null}
      />,
    );
    expect(screen.getByText("Mechanics DPP")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Paper" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Key" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /delete mechanics dpp/i }),
    ).toBeInTheDocument();
  });

  it("fires onDownload with the right kind per button", async () => {
    const user = userEvent.setup();
    const onDownload = vi.fn();
    const p = paper("1", "Mechanics DPP");
    render(
      <RecentPapers
        papers={[p]}
        onDownload={onDownload}
        onDelete={NOOP}
        busyKey={null}
        deletingId={null}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Paper" }));
    expect(onDownload).toHaveBeenCalledWith(p, "paper");

    await user.click(screen.getByRole("button", { name: "Key" }));
    expect(onDownload).toHaveBeenCalledWith(p, "answer-key");
  });

  it("fires onDelete with the paper when Delete is clicked", async () => {
    const user = userEvent.setup();
    const onDelete = vi.fn();
    const p = paper("1", "Mechanics DPP");
    render(
      <RecentPapers
        papers={[p]}
        onDownload={NOOP}
        onDelete={onDelete}
        busyKey={null}
        deletingId={null}
      />,
    );
    await user.click(screen.getByRole("button", { name: /delete mechanics dpp/i }));
    expect(onDelete).toHaveBeenCalledWith(p);
  });

  it("disables the busy download button", () => {
    render(
      <RecentPapers
        papers={[paper("1", "Mechanics DPP")]}
        onDownload={NOOP}
        onDelete={NOOP}
        busyKey={"1:paper"}
        deletingId={null}
      />,
    );
    expect(screen.getByRole("button", { name: "…" })).toBeDisabled();
  });

  it("disables the Delete button while that paper is being deleted", () => {
    render(
      <RecentPapers
        papers={[paper("1", "Mechanics DPP")]}
        onDownload={NOOP}
        onDelete={NOOP}
        busyKey={null}
        deletingId={"1"}
      />,
    );
    expect(
      screen.getByRole("button", { name: /delete mechanics dpp/i }),
    ).toBeDisabled();
  });
});
