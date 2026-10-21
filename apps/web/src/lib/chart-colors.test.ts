import { describe, expect, it } from "vitest";

import {
  CHART_COLORS,
  POSITION_TIER_COLORS,
  returnSourceColor,
} from "./chart-colors";

describe("chart color helpers", () => {
  it("uses the shared position-tier palette", () => {
    expect(POSITION_TIER_COLORS).toEqual([
      CHART_COLORS.green,
      CHART_COLORS.blue,
      CHART_COLORS.gold,
    ]);
  });

  it("maps return sources to the shared semantic colors", () => {
    expect(returnSourceColor("增长 8.0%", "#000000")).toBe(CHART_COLORS.blue);
    expect(returnSourceColor("股息 4.3%", "#000000")).toBe(CHART_COLORS.green);
    expect(returnSourceColor("估值修复 15.6%", "#000000")).toBe(CHART_COLORS.gold);
    expect(returnSourceColor("估值 −2.2%", "#000000")).toBe(CHART_COLORS.red);
  });
});
