import { describe, it, expect, beforeEach } from "vitest";
import {
  EMPTY_FILTERS,
  hasActiveFilters,
  loadSavedViews,
  upsertSavedView,
  deleteSavedView,
  type RosterFilters,
} from "@/app/(dashboard)/students/_lib/saved-views";

const BR = "branch-1";

beforeEach(() => localStorage.clear());

describe("saved-views", () => {
  it("detects active filters", () => {
    expect(hasActiveFilters(EMPTY_FILTERS)).toBe(false);
    expect(hasActiveFilters({ ...EMPTY_FILTERS, feesStatus: "due" })).toBe(true);
  });

  it("round-trips a saved view per branch", () => {
    const filters: RosterFilters = {
      standard: "12",
      targetExam: "NEET",
      feesStatus: "due",
      batchId: "",
    };
    upsertSavedView(BR, { name: "12 NEET due", filters });
    const views = loadSavedViews(BR);
    expect(views).toHaveLength(1);
    expect(views[0].filters).toEqual(filters);
    // A different branch has its own list.
    expect(loadSavedViews("branch-2")).toEqual([]);
  });

  it("replaces a view with the same name instead of duplicating", () => {
    upsertSavedView(BR, { name: "x", filters: { ...EMPTY_FILTERS, standard: "11" } });
    upsertSavedView(BR, { name: "x", filters: { ...EMPTY_FILTERS, standard: "12" } });
    const views = loadSavedViews(BR);
    expect(views).toHaveLength(1);
    expect(views[0].filters.standard).toBe("12");
  });

  it("deletes a view by name", () => {
    upsertSavedView(BR, { name: "a", filters: EMPTY_FILTERS });
    upsertSavedView(BR, { name: "b", filters: EMPTY_FILTERS });
    const after = deleteSavedView(BR, "a");
    expect(after.map((v) => v.name)).toEqual(["b"]);
  });

  it("returns [] on malformed storage", () => {
    localStorage.setItem(`students:saved-views:${BR}`, "{not json");
    expect(loadSavedViews(BR)).toEqual([]);
  });
});
