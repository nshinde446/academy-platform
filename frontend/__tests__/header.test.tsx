import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { Header } from "@/components/layout/header";

const mockUseUserStore = vi.fn();

vi.mock("@/store/user-store", () => ({
  useUserStore: (selector: any) => mockUseUserStore(selector),
}));

describe("Header", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders platform title", () => {
    mockUseUserStore.mockImplementation((selector: any) =>
      selector({ user: null })
    );

    render(<Header />);
    expect(screen.getByText("Academy Platform")).toBeInTheDocument();
  });

  it("shows 'Not signed in' when no user", () => {
    mockUseUserStore.mockImplementation((selector: any) =>
      selector({ user: null })
    );

    render(<Header />);
    expect(screen.getByText("Not signed in")).toBeInTheDocument();
  });

  it("shows user name and roles when signed in", () => {
    const user = {
      id: "1",
      email: "admin@test.com",
      first_name: "Admin",
      last_name: "User",
      status: "active",
      roles: ["super_admin", "branch_admin"],
      permissions: [],
      branch_roles: [],
    };

    mockUseUserStore.mockImplementation((selector: any) =>
      selector({ user })
    );

    render(<Header />);
    expect(screen.getByText("Admin User (super_admin, branch_admin)")).toBeInTheDocument();
  });

  it("shows single role without comma", () => {
    const user = {
      id: "1",
      email: "teacher@test.com",
      first_name: "John",
      last_name: "Doe",
      status: "active",
      roles: ["teacher"],
      permissions: [],
      branch_roles: [],
    };

    mockUseUserStore.mockImplementation((selector: any) =>
      selector({ user })
    );

    render(<Header />);
    expect(screen.getByText("John Doe (teacher)")).toBeInTheDocument();
  });
});
