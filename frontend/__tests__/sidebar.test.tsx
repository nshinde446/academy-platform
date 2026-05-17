import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { Sidebar } from "@/components/layout/sidebar";

let currentPathname = "/home";

vi.mock("next/navigation", () => ({
  usePathname: () => currentPathname,
}));

vi.mock("next/link", () => ({
  default: ({ children, href, className }: any) => (
    <a href={href} className={className}>{children}</a>
  ),
}));

describe("Sidebar", () => {
  beforeEach(() => {
    currentPathname = "/home";
  });

  it("renders navigation title", () => {
    render(<Sidebar />);
    expect(screen.getByText("Navigation")).toBeInTheDocument();
  });

  it("renders Home nav item", () => {
    render(<Sidebar />);
    const homeLink = screen.getByRole("link", { name: "Home" });
    expect(homeLink).toBeInTheDocument();
    expect(homeLink).toHaveAttribute("href", "/home");
  });

  it("applies active style to current route", () => {
    currentPathname = "/home";
    render(<Sidebar />);
    const homeLink = screen.getByRole("link", { name: "Home" });
    expect(homeLink.className).toContain("bg-sidebar-accent");
    expect(homeLink.className).toContain("font-medium");
  });

  it("applies inactive style when not on route", () => {
    currentPathname = "/settings";
    render(<Sidebar />);
    const homeLink = screen.getByRole("link", { name: "Home" });
    expect(homeLink.className).not.toContain("font-medium");
    expect(homeLink.className).toContain("hover:bg-sidebar-accent/50");
  });
});
