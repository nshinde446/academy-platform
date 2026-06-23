import { describe, it, expect, beforeEach } from "vitest";
import {
  loadMappingProfile,
  saveMappingProfile,
  clearMappingProfile,
} from "@/app/(dashboard)/students/_lib/mapping-profile";

beforeEach(() => localStorage.clear());

describe("mapping-profile", () => {
  it("returns null when nothing is saved", () => {
    expect(loadMappingProfile("b1")).toBeNull();
  });

  it("round-trips a map per branch", () => {
    saveMappingProfile("b1", { "Student Name": "name", Std: "class" });
    expect(loadMappingProfile("b1")).toEqual({
      "Student Name": "name",
      Std: "class",
    });
    expect(loadMappingProfile("b2")).toBeNull();
  });

  it("clears a saved profile", () => {
    saveMappingProfile("b1", { X: "name" });
    clearMappingProfile("b1");
    expect(loadMappingProfile("b1")).toBeNull();
  });

  it("returns null on malformed storage", () => {
    localStorage.setItem("students:column-map:b1", "nope{");
    expect(loadMappingProfile("b1")).toBeNull();
  });
});
