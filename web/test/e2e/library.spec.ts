import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill("admin@logscope.local");
  await page.getByLabel("密碼").fill("changeme");
  await page.getByRole("button", { name: "登入" }).click();
  await expect(page).toHaveURL(/\/library$/);
});

test.describe("Library list and detail", () => {
  test("can create vendor + product and navigate to detail", async ({ page }) => {
    // Arrange
    const slug = `e2e-${Date.now()}`;
    const productSlug = "p-e2e";

    // Act 1: create vendor via dialog（toolbar 按鈕排在第一）
    await page.getByRole("button", { name: "新增 Vendor" }).first().click();
    await page.getByLabel("名稱").fill(`E2E Vendor ${slug}`);
    await page.getByLabel("Slug（可選）").fill(slug);
    await page.getByRole("button", { name: /建立$/ }).click();

    // Assert 1
    await expect(page.getByText(`E2E Vendor ${slug}`)).toBeVisible();

    // Act 2: open + Product modal for that vendor
    await page
      .locator(`section:has-text("E2E Vendor ${slug}") button:has-text("+ Product")`)
      .click();
    await page.getByLabel("名稱").fill("E2E Product");
    await page.getByLabel("Slug（可選）").fill(productSlug);
    await page.getByRole("button", { name: /建立$/ }).click();

    // Assert 2
    await expect(page.getByText("E2E Product")).toBeVisible();

    // Act 3: click product card → detail page
    await page.getByText("E2E Product").click();

    // Assert 3
    await expect(page).toHaveURL(new RegExp(`/library/${slug}/${productSlug}$`));
    await expect(page.getByText(/還沒有 log type/)).toBeVisible();

    // Cleanup via API（用瀏覽器直接 fetch）
    await page.evaluate(
      async ({ vendorSlug, productSlug: pslug }) => {
        const res = await fetch(`/api/v1/library/vendors/${vendorSlug}/products/${pslug}`, {
          credentials: "include",
        });
        const product = (await res.json()).data;
        await fetch(`/api/v1/library/products/${product.id}`, {
          method: "DELETE",
          credentials: "include",
        });
        const vRes = await fetch(`/api/v1/library/vendors/${vendorSlug}`, {
          credentials: "include",
        });
        const vendor = (await vRes.json()).data;
        await fetch(`/api/v1/library/vendors/${vendor.id}`, {
          method: "DELETE",
          credentials: "include",
        });
      },
      { vendorSlug: slug, productSlug },
    );
  });

  test("Copilot panel opens with placeholder content", async ({ page }) => {
    // Act
    await page.getByRole("button", { name: /Open Copilot/ }).click();

    // Assert
    await expect(page.getByText(/即將於 spec D 開放/)).toBeVisible();
  });
});
