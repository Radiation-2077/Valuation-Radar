import { expect, test } from "@playwright/test";

test("follows the system theme until the user selects a mode", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await page.goto("/");

  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(page.getByLabel("服务已连接")).toBeVisible();
  await expect(page.locator(".header-status")).toHaveText("");
  await expect(page.getByText("CONNECTED", { exact: true })).toHaveCount(0);
  await page.locator(".header-status").hover();
  await expect(page.getByRole("tooltip")).toHaveText("服务已连接");

  await page.emulateMedia({ colorScheme: "light" });
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await expect(page.getByRole("button", { name: "切换到暗色模式" })).toBeVisible();

  await page.getByRole("button", { name: "切换到暗色模式" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect
    .poll(() => page.evaluate(() => localStorage.getItem("valuation-radar-theme")))
    .toBe("dark");
  await expect(page.getByRole("button", { name: "切换到亮色模式" })).toBeVisible();
});
