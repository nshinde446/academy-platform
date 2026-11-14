import { describe, it, expect } from "vitest";
import { cellColor, columnBounds } from "@/app/(dashboard)/test-portal/_lib/color-scale";

describe("rank list colour scale", () => {
  it("maps highest→green, lowest→red, midpoint→white", () => {
    expect(cellColor(50, 10, 50)).toBe("rgb(87, 187, 138)"); // green
    expect(cellColor(10, 10, 50)).toBe("rgb(230, 124, 115)"); // red
    expect(cellColor(30, 10, 50)).toBe("rgb(255, 255, 255)"); // white (midpoint)
  });

  it("gives equal marks the same colour (ties)", () => {
    expect(cellColor(42, 10, 50)).toBe(cellColor(42, 10, 50));
  });

  it("returns undefined when there is no spread or no value", () => {
    expect(cellColor(20, 20, 20)).toBeUndefined();
    expect(cellColor(null, 10, 50)).toBeUndefined();
    expect(cellColor(undefined, 10, 50)).toBeUndefined();
  });

  it("columnBounds ignores absent (null) marks", () => {
    expect(columnBounds([90, null, 30, undefined])).toEqual({ min: 30, max: 90 });
    expect(columnBounds([null, undefined])).toBeUndefined();
  });
});
