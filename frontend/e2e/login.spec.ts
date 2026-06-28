import { test, expect } from "@playwright/test";

test.describe("Login flow", () => {
  test("shows login form", async ({ page }) => {
    await page.goto("/login");

    await expect(page.getByText("Matrix Science Academy")).toBeVisible();
    await expect(page.getByText("Sign in to your account")).toBeVisible();
    await expect(page.getByLabel("Email")).toBeVisible();
    await expect(page.getByLabel("Password")).toBeVisible();
    await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
  });

  test("shows error on invalid credentials", async ({ page }) => {
    await page.goto("/login");

    await page.getByLabel("Email").fill("bad@example.com");
    await page.getByLabel("Password").fill("wrongpass");
    await page.getByRole("button", { name: "Sign in" }).click();

    await expect(
      page.getByText(/invalid|failed|unauthorized/i)
    ).toBeVisible({ timeout: 10000 });
  });
});

test.describe("Protected routes", () => {
  test("redirects unauthenticated user to login", async ({ page }) => {
    await page.goto("/home");

    await page.waitForURL("**/login", { timeout: 10000 });
    expect(page.url()).toContain("/login");
  });
});

test.describe("Logout", () => {
  test("login page is accessible", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
  });
});
