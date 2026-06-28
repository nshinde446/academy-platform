import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import LoginPage from "@/app/login/page";

const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

const mockPost = vi.fn();
vi.mock("@/services/api-client", () => ({
  default: { post: (...args: any[]) => mockPost(...args) },
}));

const mockSetAuthenticated = vi.fn();
vi.mock("@/store/auth-store", () => ({
  useAuthStore: (selector: any) => selector({ setAuthenticated: mockSetAuthenticated }),
}));

const mockFetchUser = vi.fn().mockResolvedValue(undefined);
vi.mock("@/store/user-store", () => ({
  useUserStore: (selector: any) => selector({ fetchUser: mockFetchUser }),
}));

describe("LoginPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders login form", () => {
    render(<LoginPage />);

    expect(screen.getByText("Matrix Science Academy")).toBeInTheDocument();
    expect(screen.getByText("Sign in to your account")).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign in" })).toBeInTheDocument();
  });

  it("updates input values on typing", async () => {
    const user = userEvent.setup();
    render(<LoginPage />);

    const emailInput = screen.getByLabelText("Email");
    const passwordInput = screen.getByLabelText("Password");

    await user.type(emailInput, "admin@test.com");
    await user.type(passwordInput, "secret123");

    expect(emailInput).toHaveValue("admin@test.com");
    expect(passwordInput).toHaveValue("secret123");
  });

  it("submits form and redirects on success", async () => {
    const user = userEvent.setup();
    mockPost.mockResolvedValueOnce({ data: {} });

    render(<LoginPage />);

    await user.type(screen.getByLabelText("Email"), "admin@test.com");
    await user.type(screen.getByLabelText("Password"), "secret123");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith("/api/v1/auth/login", {
        email: "admin@test.com",
        password: "secret123",
      });
      expect(mockSetAuthenticated).toHaveBeenCalledWith(true);
      expect(mockFetchUser).toHaveBeenCalled();
      expect(mockPush).toHaveBeenCalledWith("/home");
    });
  });

  it("shows error message on failed login", async () => {
    const user = userEvent.setup();
    mockPost.mockRejectedValueOnce({
      response: { data: { error: { message: "Invalid credentials" } } },
    });

    render(<LoginPage />);

    await user.type(screen.getByLabelText("Email"), "bad@test.com");
    await user.type(screen.getByLabelText("Password"), "wrong");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => {
      expect(screen.getByText("Invalid credentials")).toBeInTheDocument();
    });
  });

  it("shows generic error when no detail in response", async () => {
    const user = userEvent.setup();
    mockPost.mockRejectedValueOnce({ response: { data: {} } });

    render(<LoginPage />);

    await user.type(screen.getByLabelText("Email"), "bad@test.com");
    await user.type(screen.getByLabelText("Password"), "wrong");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => {
      expect(screen.getByText("Login failed")).toBeInTheDocument();
    });
  });

  it("shows loading state during submission", async () => {
    const user = userEvent.setup();
    let resolvePost: any;
    mockPost.mockImplementation(() => new Promise((r) => { resolvePost = r; }));

    render(<LoginPage />);

    await user.type(screen.getByLabelText("Email"), "admin@test.com");
    await user.type(screen.getByLabelText("Password"), "secret123");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => {
      expect(screen.getByText("Signing in...")).toBeInTheDocument();
    });

    resolvePost({ data: {} });

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Sign in" })).toBeInTheDocument();
    });
  });

  it("disables button while loading", async () => {
    const user = userEvent.setup();
    mockPost.mockImplementation(() => new Promise(() => {}));

    render(<LoginPage />);

    await user.type(screen.getByLabelText("Email"), "admin@test.com");
    await user.type(screen.getByLabelText("Password"), "secret123");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Signing in..." })).toBeDisabled();
    });
  });
});
