import { describe, expect, it } from "vitest";

import { parsePositionTiers } from "./position-tiers";

describe("position tier helpers", () => {
  it("extracts tier names, prices and allocation percentages", () => {
    expect(
      parsePositionTiers([
        { title: "第 1 档 · 现价 HK$51.55", body: "首笔 40%（≈2.4%）", active: true },
        { title: "第 2 档 · 回调至 HK$48", body: "加 30%（≈1.8%）" },
        { title: "第 3 档 · HK$46 以下", body: "加 30% 完成建仓" },
      ]),
    ).toEqual([
      { tier: "第 1 档", price: "HK$51.55", allocation: 40, active: true },
      { tier: "第 2 档", price: "HK$48", allocation: 30, active: false },
      { tier: "第 3 档", price: "HK$46", allocation: 30, active: false },
    ]);
  });

  it("treats a final cumulative position as the remaining tranche", () => {
    expect(
      parsePositionTiers([
        { title: "第 1 档 · 现价 ¥52.19", body: "建 40%（≈1.2% 仓位）", active: true },
        { title: "第 2 档 · 回调至 ¥46–47", body: "加 30%" },
        { title: "第 3 档 · 跌破 ¥42", body: "加至 3%，完成建仓" },
      ]).map((tier) => tier.allocation),
    ).toEqual([40, 30, 30]);
  });
});
