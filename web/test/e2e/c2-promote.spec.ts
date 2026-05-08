import { expect, test } from "@playwright/test";

test.describe("C2 Promote flow", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email").fill("admin@logscope.local");
    await page.getByLabel("密碼").fill("changeme");
    await page.getByRole("button", { name: "登入" }).click();
    await expect(page).toHaveURL(/\/library$/);
  });

  test("Promote v2 archives v1 and updates current rule via Versions tab", async ({ page }) => {
    // Seed: vendor + product + log_type + 2 drafts via API
    const u = Math.random().toString(36).slice(2, 8);

    const created = await page.evaluate(async (slug: string) => {
      // 1. Create vendor
      const vRes = await fetch("/api/v1/library/vendors", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ name: `V ${slug}`, slug: `v-${slug}` }),
      });
      const vendor = (await vRes.json()).data as { id: string };

      // 2. Create product
      const pRes = await fetch(`/api/v1/library/vendors/v-${slug}/products`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ name: "P", slug: "p" }),
      });
      const product = (await pRes.json()).data as { id: string };

      // 3. Create log_type
      const ltRes = await fetch(`/api/v1/library/products/${product.id}/log_types`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ name: "LT", slug: "lt", format: "csv" }),
      });
      const logType = (await ltRes.json()).data as { id: string };

      // 4. First draft -> promote (becomes published v1)
      const r1Res = await fetch(`/api/v1/library/log_types/${logType.id}/parse_rules`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ vrl_code: ".x = 1", engine_version: "0.32" }),
      });
      const draft1 = (await r1Res.json()).data as { id: string };

      await fetch(`/api/v1/library/parse_rules/${draft1.id}/promote`, {
        method: "POST",
        credentials: "include",
      });

      // 5. Second draft (v2) — keep as draft for UI to promote
      await fetch(`/api/v1/library/log_types/${logType.id}/parse_rules`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ vrl_code: ".x = 2", engine_version: "0.32" }),
      });

      return {
        vendorId: vendor.id,
        productId: product.id,
        logTypeId: logType.id,
        slug,
      };
    }, u);

    // Navigate to product detail page
    await page.goto(`/library/v-${u}/p`);

    // Switch to Versions sub-tab
    await page.getByRole("button", { name: "Versions" }).click();

    // Both versions visible
    await expect(page.getByText("v1")).toBeVisible();
    await expect(page.getByText("v2")).toBeVisible();

    // Click Promote button (only the draft v2 has one)
    await page.getByRole("button", { name: "Promote" }).click();

    // Confirm dialog
    await page.getByRole("button", { name: "確定" }).click();

    // Wait for refetch: v2 becomes published, v1 becomes archived
    await expect(page.locator('tr:has-text("v2")').getByText("published")).toBeVisible({
      timeout: 5000,
    });
    await expect(page.locator('tr:has-text("v1")').getByText("archived")).toBeVisible({
      timeout: 5000,
    });

    // Cleanup via API
    await page.evaluate(async (c: { vendorId: string; productId: string; logTypeId: string }) => {
      await fetch(`/api/v1/library/log_types/${c.logTypeId}`, {
        method: "DELETE",
        credentials: "include",
      });
      await fetch(`/api/v1/library/products/${c.productId}`, {
        method: "DELETE",
        credentials: "include",
      });
      await fetch(`/api/v1/library/vendors/${c.vendorId}`, {
        method: "DELETE",
        credentials: "include",
      });
    }, created);
  });
});
