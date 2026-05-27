import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { Header } from "@/components/layout/header";

let currentPathname = "/home";

vi.mock("next/navigation", () => ({
  usePathname: () => currentPathname,
}));

describe("Header (breadcrumb)", () => {
  beforeEach(() => {
    currentPathname = "/home";
  });

  it("renders a Home breadcrumb on the root dashboard route", () => {
    render(<Header />);
    expect(screen.getByText("Home")).toBeInTheDocument();
  });

  it("maps known slug to label", () => {
    currentPathname = "/question-bank";
    render(<Header />);
    expect(screen.getByText("Question Bank")).toBeInTheDocument();
  });

  it("builds a multi-segment breadcrumb for detail routes", () => {
    currentPathname = "/teachers/abc-123";
    render(<Header />);
    expect(screen.getByText("Teachers")).toBeInTheDocument();
    // The trailing slug is shown as-is so detail pages can override.
    expect(screen.getByText("abc-123")).toBeInTheDocument();
  });

  it("renders the ⌘K hint and today's date", () => {
    render(<Header />);
    expect(screen.getByText("⌘K")).toBeInTheDocument();
    // Today's date renders via toLocaleDateString — just check the
    // year is on the page somewhere (more stable than the full string).
    const year = new Date().getFullYear().toString();
    expect(screen.getByText(new RegExp(year))).toBeInTheDocument();
  });
});
