import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  PieChart,
  withOthers,
  type PieSlice,
} from "@/app/(dashboard)/teachers/productivity/_components/pie-chart";

describe("withOthers", () => {
  it("drops zero-value slices and sorts descending", () => {
    const out = withOthers(
      [
        { label: "A", value: 0 },
        { label: "B", value: 5 },
        { label: "C", value: 10 },
      ],
      9,
    );
    expect(out.map((s) => s.label)).toEqual(["C", "B"]);
  });

  it("folds the tail beyond topN into an Others slice", () => {
    const many: PieSlice[] = Array.from({ length: 12 }, (_, i) => ({
      label: `S${i}`,
      value: 12 - i,
    }));
    const out = withOthers(many, 9);
    expect(out).toHaveLength(10); // 9 + Others
    expect(out[9].label).toBe("Others");
    // Others = sum of the three smallest (3 + 2 + 1).
    expect(out[9].value).toBe(6);
  });
});

describe("PieChart", () => {
  it("renders a legend with count and percent per slice", () => {
    render(
      <PieChart
        title="Subject-wise Lectures"
        slices={[
          { label: "MATHS", value: 75 },
          { label: "PHY", value: 25 },
        ]}
      />,
    );
    expect(screen.getByText("Subject-wise Lectures")).toBeInTheDocument();
    expect(screen.getByText("MATHS")).toBeInTheDocument();
    expect(screen.getByText("75 · 75%")).toBeInTheDocument();
    expect(screen.getByText("25 · 25%")).toBeInTheDocument();
  });

  it("shows an explanatory note when there is no data", () => {
    render(<PieChart title="Teacher-wise Lectures" slices={[]} />);
    expect(screen.getByText("No lectures in this range.")).toBeInTheDocument();
  });
});
