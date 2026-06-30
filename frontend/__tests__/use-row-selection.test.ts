import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useRowSelection } from "@/hooks/use-row-selection";

describe("useRowSelection", () => {
  it("starts empty", () => {
    const { result } = renderHook(() => useRowSelection());
    expect(result.current.count).toBe(0);
    expect(result.current.selected).toEqual([]);
  });

  it("toggles a single id on and off", () => {
    const { result } = renderHook(() => useRowSelection());
    act(() => result.current.toggle("a"));
    expect(result.current.isSelected("a")).toBe(true);
    expect(result.current.count).toBe(1);
    act(() => result.current.toggle("a"));
    expect(result.current.isSelected("a")).toBe(false);
    expect(result.current.count).toBe(0);
  });

  it("selects all page ids, then clears them when all already selected", () => {
    const { result } = renderHook(() => useRowSelection());
    act(() => result.current.toggleAll(["a", "b", "c"]));
    expect(result.current.count).toBe(3);
    // All on -> toggleAll clears them.
    act(() => result.current.toggleAll(["a", "b", "c"]));
    expect(result.current.count).toBe(0);
  });

  it("toggleAll adds missing ids when only some are selected", () => {
    const { result } = renderHook(() => useRowSelection());
    act(() => result.current.toggle("a"));
    act(() => result.current.toggleAll(["a", "b", "c"]));
    expect(result.current.selected.sort()).toEqual(["a", "b", "c"]);
  });

  it("clear() empties the selection", () => {
    const { result } = renderHook(() => useRowSelection());
    act(() => result.current.toggleAll(["a", "b"]));
    act(() => result.current.clear());
    expect(result.current.count).toBe(0);
  });

  it("toggleAll on an empty page is a no-op", () => {
    const { result } = renderHook(() => useRowSelection());
    act(() => result.current.toggleAll([]));
    expect(result.current.count).toBe(0);
  });
});
