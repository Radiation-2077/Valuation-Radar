import { describe, expect, it } from "vitest";

import {
  classifyPricePosition,
  pricePositionColor,
  scenarioMarkerColor,
} from "./range-position";

describe("range position helpers", () => {
  it("classifies prices relative to the fair range", () => {
    expect(classifyPricePosition(20, 50, 30)).toBe("low");
    expect(classifyPricePosition(60, 50, 30)).toBe("fair");
    expect(classifyPricePosition(90, 50, 30)).toBe("high");
  });

  it("uses green for undervaluation and red for overvaluation", () => {
    expect(pricePositionColor("low")).toBe("#57d6b1");
    expect(pricePositionColor("high")).toBe("#ee8c78");
  });

  it("assigns distinct colors to scenario markers", () => {
    expect(new Set([0, 1, 2].map(scenarioMarkerColor)).size).toBe(3);
  });
});
