import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill("admin@logscope.local");
  await page.getByLabel("密碼").fill("changeme");
  await page.getByRole("button", { name: "登入" }).click();
  await expect(page).toHaveURL(/\/library$/);
});

test.describe("Analyzer", () => {
  test("parse a trivial VRL with engine 0.32", async ({ page }) => {
    // Arrange
    await page.goto("/analyzer");

    // Act — type into CodeMirror + textarea. CodeMirror needs trailing
    // `.` so resolution returns the modified event dict, not the value.
    const editor = page.locator(".cm-content").first();
    await editor.click();
    await page.keyboard.type('.action = "allow"\n.');
    await page.locator('textarea[placeholder*="500 行"]').fill("anything");

    // Assert — wait for parse summary + grouped result
    await expect(page.getByText(/parse ok/)).toBeVisible({ timeout: 5000 });
    await expect(page.getByText("事件欄位")).toBeVisible();
    // Use exact match scoped to result area to avoid matching CodeMirror span
    await expect(page.getByText("action", { exact: true })).toBeVisible();
  });

  test("save buttons disabled without log_type_id context", async ({ page }) => {
    await page.goto("/analyzer");
    await expect(page.getByRole("button", { name: /存回 Library/ })).toBeDisabled();
    await expect(page.getByRole("button", { name: /存為 sample/ })).toBeDisabled();
  });

  test("Library detail link navigates with log_type_id", async ({ page }) => {
    // Arrange — create vendor + product + log_type via API
    const slug = `e2e-analyzer-${Date.now()}`;
    const created = await page.evaluate(async (slug) => {
      await fetch("/api/v1/library/vendors", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ name: `E2E ${slug}`, slug, status: "active" }),
      });
      const pRes = await fetch(`/api/v1/library/vendors/${slug}/products`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ name: "P", slug: "p", status: "active" }),
      });
      const product = (await pRes.json()).data;
      const ltRes = await fetch(`/api/v1/library/products/${product.id}/log_types`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          name: "Traffic",
          slug: "traffic",
          format: "csv",
        }),
      });
      const lt = (await ltRes.json()).data;
      return {
        slug,
        product_id: product.id,
        log_type_id: lt.id,
      };
    }, slug);

    // Act — go to product detail and click 載入 Analyzer
    await page.goto(`/library/${slug}/p`);
    await expect(page.getByText("Traffic")).toBeVisible();
    const loadLink = page.getByRole("link", { name: /載入 Analyzer/ });
    await expect(loadLink).toBeVisible();
    await loadLink.click();
    await expect(page).toHaveURL(/\/analyzer\?log_type_id=/);

    // Cleanup — delete log_type, product, then vendor (by id, which we
    // need to look up via the vendor-by-slug GET endpoint).
    await page.evaluate(async (c) => {
      await fetch(`/api/v1/library/log_types/${c.log_type_id}`, {
        method: "DELETE",
        credentials: "include",
      });
      await fetch(`/api/v1/library/products/${c.product_id}`, {
        method: "DELETE",
        credentials: "include",
      });
      const vRes = await fetch(`/api/v1/library/vendors/${c.slug}`, {
        credentials: "include",
      });
      const v = (await vRes.json()).data;
      await fetch(`/api/v1/library/vendors/${v.id}`, {
        method: "DELETE",
        credentials: "include",
      });
    }, created);
  });
});
