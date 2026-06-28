import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
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

// Sidebar reads from these stores; stub them to keep tests focused.
vi.mock("@/store/user-store", () => ({
  useUserStore: (selector: any) =>
    selector({ user: null, fetchUser: vi.fn() }),
}));
vi.mock("@/store/auth-store", () => ({
  useAuthStore: (selector: any) => selector({ logout: vi.fn() }),
}));

describe("Sidebar (MSA_Design section layout)", () => {
  beforeEach(() => {
    currentPathname = "/home";
  });

  it("renders the brand mark + product name", () => {
    render(<Sidebar />);
    // MSA wordmark + the gold exam-stream tagline beneath it.
    expect(screen.getByText("Matrix Science Academy")).toBeInTheDocument();
    expect(screen.getByText("JEE · NEET · MHT-CET")).toBeInTheDocument();
  });

  it("renders the user footer placeholder when not signed in", () => {
    render(<Sidebar />);
    expect(screen.getByText("Not signed in")).toBeInTheDocument();
  });

  it("renders the top (unlabeled) primary surfaces", () => {
    render(<Sidebar />);
    for (const label of [
      "Home",
      "Today",
      "Students",
      "Teachers",
      "Lectures",
      "Attendance",
      "Insights",
    ]) {
      expect(screen.getByRole("link", { name: label })).toBeInTheDocument();
    }
  });

  it("renders Content section with Materials + Question Bank + Papers", () => {
    render(<Sidebar />);
    expect(screen.getByText("Content")).toBeInTheDocument();

    // Papers is the newest addition (M4) — flagged NEW.
    const papers = screen.getByRole("link", { name: /papers/i });
    expect(papers).toHaveAttribute("href", "/papers");
    expect(papers.textContent).toMatch(/NEW/);

    // Materials stays in Content but no longer carries the NEW chip.
    const materials = screen.getByRole("link", { name: /materials/i });
    expect(materials).toHaveAttribute("href", "/materials");
    expect(materials.textContent).not.toMatch(/NEW/);

    // Question Bank stays in Content, no NEW chip.
    const qb = screen.getByRole("link", { name: /question bank/i });
    expect(qb).toHaveAttribute("href", "/question-bank");
    expect(qb.textContent).not.toMatch(/NEW/);
  });

  it("renders Academics section with every config surface", () => {
    render(<Sidebar />);
    expect(screen.getByText("Academics")).toBeInTheDocument();
    for (const [label, href] of [
      ["Courses", "/courses"],
      ["Batches", "/batches"],
      ["Classrooms", "/classrooms"],
      ["Academic Years", "/academic-years"],
      ["Syllabus", "/syllabus"],
    ] as const) {
      expect(screen.getByRole("link", { name: label })).toHaveAttribute(
        "href",
        href,
      );
    }
  });

  it("highlights the active route", () => {
    currentPathname = "/students";
    render(<Sidebar />);
    expect(screen.getByRole("link", { name: "Students" }).className).toContain(
      "font-medium",
    );
    expect(screen.getByRole("link", { name: "Home" }).className).not.toContain(
      "font-medium",
    );
  });

  it("treats child paths as active for the parent route", () => {
    currentPathname = "/students/abc-123";
    render(<Sidebar />);
    expect(screen.getByRole("link", { name: "Students" }).className).toContain(
      "font-medium",
    );
  });
});
