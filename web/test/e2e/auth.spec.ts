import { expect, test } from "@playwright/test";

test.describe("auth flow", () => {
  test("redirects unauth user to /login", async ({ page }) => {
    // Act
    await page.goto("/library");

    // Assert
    await expect(page).toHaveURL(/\/login\?next=%2Flibrary/);
  });

  test("admin can sign in and reach /library", async ({ page }) => {
    // Arrange
    await page.goto("/login");

    // Act
    await page.getByLabel("Email").fill("admin@logscope.local");
    await page.getByLabel("密碼").fill("changeme");
    await page.getByRole("button", { name: "登入" }).click();

    // Assert
    await expect(page).toHaveURL(/\/library$/);
    await expect(page.getByRole("link", { name: "LogScope" })).toBeVisible();
  });

  test("rejects wrong password with inline error", async ({ page }) => {
    // Arrange
    await page.goto("/login");

    // Act
    await page.getByLabel("Email").fill("admin@logscope.local");
    await page.getByLabel("密碼").fill("definitely-wrong");
    await page.getByRole("button", { name: "登入" }).click();

    // Assert
    await expect(page.getByRole("alert").filter({ hasText: "帳號或密碼錯誤" })).toBeVisible();
  });

  test("logout clears session and bounces /library to /login", async ({ page }) => {
    // Arrange: log in
    await page.goto("/login");
    await page.getByLabel("Email").fill("admin@logscope.local");
    await page.getByLabel("密碼").fill("changeme");
    await page.getByRole("button", { name: "登入" }).click();
    await expect(page).toHaveURL(/\/library$/);

    // Act: open user menu and sign out
    await page.locator('[data-slot="dropdown-menu-trigger"]').click();
    await page.locator('[data-slot="dropdown-menu-item"]:has-text("Sign out")').click();

    // Assert
    await expect(page).toHaveURL(/\/login/);
  });
});
