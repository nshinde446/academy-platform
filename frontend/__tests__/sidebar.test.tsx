import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Sidebar } from "@/components/layout/sidebar";

let currentPathname = "/home";

vi.mock("next/navigation", () => ({
  usePathname: () => currentPathname,
}));

vi.mock("next/link", () => ({
  default: ({ children, href, className }: any) => (
    <a href={href} className={className}>
      {children}
    </a>
  ),
}));

describe("Sidebar", () => {
  beforeEach(() => {
    currentPathname = "/home";
  });

  it("renders the navigation header", () => {
    render(<Sidebar />);
    expect(screen.getByText("Navigation")).toBeInTheDocument();
  });

  it("renders top-level operational items", () => {
    render(<Sidebar />);
    expect(screen.getByRole("link", { name: "Home" })).toHaveAttribute(
      "href",
      "/home"
    );
    expect(screen.getByRole("link", { name: "Students" })).toHaveAttribute(
      "href",
      "/students"
    );
    expect(screen.getByRole("link", { name: "Lectures" })).toHaveAttribute(
      "href",
      "/lectures"
    );
  });

  it("highlights the current top-level route", () => {
    currentPathname = "/students";
    render(<Sidebar />);
    expect(screen.getByRole("link", { name: "Students" }).className).toContain(
      "font-medium"
    );
    expect(screen.getByRole("link", { name: "Home" }).className).not.toContain(
      "font-medium"
    );
  });

  it("renders Academics as a collapsible group, collapsed by default when no child active", () => {
    currentPathname = "/home";
    render(<Sidebar />);

    const trigger = screen.getByRole("button", { name: /academics/i });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    // Children are hidden when collapsed.
    expect(screen.queryByRole("link", { name: "Courses" })).toBeNull();
  });

  it("opens the Academics group on click and reveals all four children", async () => {
    const user = userEvent.setup();
    currentPathname = "/home";
    render(<Sidebar />);

    await user.click(screen.getByRole("button", { name: /academics/i }));

    expect(
      screen.getByRole("button", { name: /academics/i })
    ).toHaveAttribute("aria-expanded", "true");

    for (const label of ["Courses", "Batches", "Academic Years", "Syllabus"]) {
      expect(screen.getByRole("link", { name: label })).toBeInTheDocument();
    }
    expect(screen.getByRole("link", { name: "Courses" })).toHaveAttribute(
      "href",
      "/courses"
    );
  });

  it("auto-opens Academics when an academic child route is active", () => {
    currentPathname = "/syllabus";
    render(<Sidebar />);

    const trigger = screen.getByRole("button", { name: /academics/i });
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("link", { name: "Syllabus" })).toBeInTheDocument();
  });

  it("highlights the active academic child", () => {
    currentPathname = "/batches";
    render(<Sidebar />);

    expect(screen.getByRole("link", { name: "Batches" }).className).toContain(
      "font-medium"
    );
    expect(screen.getByRole("link", { name: "Courses" }).className).not.toContain(
      "font-medium"
    );
  });

  it("keeps the Academics parent highlighted when any child is active", () => {
    currentPathname = "/academic-years";
    render(<Sidebar />);

    const trigger = screen.getByRole("button", { name: /academics/i });
    expect(trigger.className).toContain("font-medium");
  });

  it("does NOT highlight Academics when no academic child is active", () => {
    currentPathname = "/students";
    render(<Sidebar />);

    const trigger = screen.getByRole("button", { name: /academics/i });
    expect(trigger.className).not.toContain("font-medium");
  });

  it("operational pages (Lectures, Students, Home) are NOT inside Academics", async () => {
    const user = userEvent.setup();
    currentPathname = "/home";
    render(<Sidebar />);

    await user.click(screen.getByRole("button", { name: /academics/i }));
    const academicsRegion = document.getElementById("sidebar-academics");
    expect(academicsRegion).not.toBeNull();

    // None of the operational items should be reachable inside the Academics region.
    for (const label of ["Home", "Students", "Lectures"]) {
      const within = academicsRegion!.querySelector(
        `a[href="/${label === "Home" ? "home" : label.toLowerCase()}"]`
      );
      expect(within).toBeNull();
    }
  });
});
