import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { Skeleton, TableSkeleton } from "@/components/ui/skeleton";

describe("Skeleton", () => {
  it("renders a pulsing placeholder and forwards className", () => {
    const { container } = render(<Skeleton className="h-4 w-10" />);
    const el = container.querySelector('[data-slot="skeleton"]');
    expect(el).toBeInTheDocument();
    expect(el).toHaveClass("animate-pulse", "h-4", "w-10");
  });
});

describe("TableSkeleton", () => {
  it("renders the requested number of placeholder rows", () => {
    const { container } = render(<TableSkeleton rows={5} />);
    // Each row is a flex line; assert via the busy region + placeholder count.
    const region = container.querySelector('[aria-busy="true"]');
    expect(region).toBeInTheDocument();
    const blocks = container.querySelectorAll('[data-slot="skeleton"]');
    // 3 header blocks + 4 blocks per row * 5 rows = 23.
    expect(blocks.length).toBe(3 + 4 * 5);
  });
});
