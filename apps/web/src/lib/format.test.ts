import { describe, expect, it } from "vitest";

import { formatMoney, formatPercent, isStale } from "./format";

describe("format helpers", () => {
  it("formats percentages and missing values", () => {
    expect(formatPercent(12.34)).toBe("12.3%");
    expect(formatPercent(null)).toBe("—");
  });

  it("uses the business currency symbol", () => {
    expect(formatMoney(100.5, "CNY")).toBe("¥100.50");
    expect(formatMoney(100.5, "HKD")).toBe("HK$100.50");
  });

  it("marks reports older than the configured threshold", () => {
    expect(isStale(8, 7)).toBe(true);
    expect(isStale(7, 7)).toBe(false);
  });
});
