import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { UserTable } from "@/app/(dashboard)/users/_components/user-table";
import type { AdminUser } from "@/app/(dashboard)/users/_schemas/users";

const USERS: AdminUser[] = [
  {
    id: "u1", email: "admin@test.com", first_name: "Ada", last_name: "Admin",
    phone: null, status: "active", roles: ["super_admin"],
  },
  {
    id: "u2", email: "teach@test.com", first_name: "Tom", last_name: "Teach",
    phone: "123", status: "inactive", roles: ["teacher"],
  },
];

const ROLE_LABELS = { super_admin: "Super Admin", teacher: "Teacher" };
const noop = vi.fn();

beforeEach(() => vi.clearAllMocks());

function renderTable(currentUserId?: string) {
  return render(
    <UserTable
      users={USERS}
      roleLabels={ROLE_LABELS}
      currentUserId={currentUserId}
      onEdit={noop}
      onResetPassword={noop}
      onDelete={noop}
    />,
  );
}

describe("UserTable", () => {
  it("renders users with display-name roles and status", () => {
    renderTable();
    expect(screen.getByText("Ada Admin")).toBeInTheDocument();
    expect(screen.getByText("Tom Teach")).toBeInTheDocument();
    expect(screen.getByText("Super Admin")).toBeInTheDocument();
    expect(screen.getByText("Teacher")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
    expect(screen.getByText("Inactive")).toBeInTheDocument();
  });

  it("marks the current user as (you)", () => {
    renderTable("u1");
    expect(screen.getByText("(you)")).toBeInTheDocument();
  });

  it("renders a Manage action per row", () => {
    renderTable();
    expect(screen.getAllByRole("button", { name: /manage/i })).toHaveLength(2);
  });
});
