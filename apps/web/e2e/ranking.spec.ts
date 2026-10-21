import { expect, test } from "@playwright/test";

test("switches risk profile and opens a valuation detail", async ({ page }) => {
  await page.goto("/");

  await expect(
    page.getByRole("heading", { name: "把估值结论，压缩成可执行的排序。" }),
  ).toBeVisible();
  await expect(page.locator(".top-card")).toHaveCount(3);
  await expect(page.getByRole("table").first()).toBeVisible();

  await page.locator(".n-radio-button").filter({ hasText: "进取" }).click();
  await expect(page).toHaveURL(/profile=aggressive/);
  await expect(
    page.locator(".n-radio-button").filter({ hasText: "进取" }).locator("input"),
  ).toBeChecked();

  const firstCard = page.locator(".top-card").first();
  await expect(firstCard).toContainText("宁德时代");
  await firstCard.click();

  await expect(page).toHaveURL(/profile=aggressive/);
  await expect(page.locator(".n-drawer")).toBeVisible();
  await expect(page.locator(".n-drawer .detail-panel h1")).toContainText("宁德时代");
  await expect(page.getByText("价格相对合理区间")).toBeVisible();
  await expect(page.getByText("评分拆解")).toBeVisible();
  await expect(page.getByText("预期年化来自哪里")).toBeVisible();
});

test("keeps the ranking usable on a narrow screen", async ({ page }) => {
  await page.goto("/?profile=balanced");

  await expect(
    page.locator(".n-radio-button").filter({ hasText: "均衡" }).locator("input"),
  ).toBeChecked();
  await expect(page.locator(".status-card")).toBeVisible();
  await expect(page.locator(".top-card").first()).toBeVisible();
  await expect(page.locator(".etf-table")).toBeVisible();
  await expect(page.locator(".excluded-table")).toBeVisible();

  await page.locator(".top-card").first().click();
  await expect(page.locator(".n-drawer")).toBeVisible();
  await expect(page.getByText("仓位与执行")).toBeVisible();
  await expect(page.getByText("关键风险与反证")).toBeVisible();
  await expect(page).toHaveURL(/profile=balanced/);
});

test("risk profile controls do not overlap the freshness bar", async ({ page }) => {
  await page.setViewportSize({ width: 960, height: 720 });
  await page.goto("/?profile=conservative");

  const profileBox = await page.locator(".n-radio-group").boundingBox();
  const freshnessBox = await page.locator(".status-card").boundingBox();
  expect(profileBox).not.toBeNull();
  expect(freshnessBox).not.toBeNull();
  expect(profileBox!.y + profileBox!.height).toBeLessThan(freshnessBox!.y);
});

test("dashboard and update cards keep consistent spacing and heights", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/");

  const chartBox = await page.locator(".chart-card").boundingBox();
  const filterBox = await page.locator(".filter-card").boundingBox();
  expect(chartBox).not.toBeNull();
  expect(filterBox).not.toBeNull();
  expect(Math.abs(chartBox!.height - filterBox!.height)).toBeLessThan(1);
  const tableShellStyle = await page.locator(".table-shell").first().evaluate((element) => {
    const style = getComputedStyle(element);
    return {
      borderStyle: style.borderStyle,
      borderWidth: Number.parseFloat(style.borderWidth),
      paddingLeft: Number.parseFloat(style.paddingLeft),
    };
  });
  expect(tableShellStyle.borderStyle).toBe("solid");
  expect(tableShellStyle.borderWidth).toBeGreaterThanOrEqual(1);
  expect(tableShellStyle.paddingLeft).toBeGreaterThanOrEqual(10);
  const tableBottomBorder = await page.locator(".ranking-table").first().evaluate(
    (element) => getComputedStyle(element).borderBottomWidth,
  );
  expect(tableBottomBorder).toBe("0px");

  await page.goto("/updates");
  const statusCards = page.locator(".ops-status-grid .n-card");
  await expect(statusCards).toHaveCount(4);
  const first = await statusCards.nth(0).boundingBox();
  const second = await statusCards.nth(1).boundingBox();
  const hero = await page.locator(".updates-hero").boundingBox();
  const statusGrid = await page.locator(".ops-status-grid").boundingBox();
  expect(first).not.toBeNull();
  expect(second).not.toBeNull();
  expect(hero).not.toBeNull();
  expect(statusGrid).not.toBeNull();
  const horizontalGap = second!.x - (first!.x + first!.width);
  const verticalGap = statusGrid!.y - (hero!.y + hero!.height);
  expect(horizontalGap).toBeGreaterThanOrEqual(24);
  expect(Math.abs(horizontalGap - verticalGap)).toBeLessThanOrEqual(2);
});
