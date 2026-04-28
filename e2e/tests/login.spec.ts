import { test, expect } from "@playwright/test";

test("admin can sign in and reach dashboard", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill("admin@example.com");
  await page.getByLabel("Password").fill("password123");
  await page.getByRole("button", { name: /sign in/i }).click();
  // The login page navigates to "/" on success; the page itself owns the
  // <h1>Dashboard</h1>, which is rendered after the route change. The navbar's
  // authed state is non-reactive (see frontend bug), so asserting on the page
  // heading is more robust than asserting on the navbar link.
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
});
