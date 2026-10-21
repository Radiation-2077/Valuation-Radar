export type PricePosition = "low" | "fair" | "high";
export const SCENARIO_COLORS = ["#80c7ff", "#b8a1ff", "#e8b86d"] as const;

export function classifyPricePosition(
  currentPosition: number,
  rangeStart: number,
  rangeWidth: number,
): PricePosition {
  if (currentPosition < rangeStart) return "low";
  if (currentPosition > rangeStart + rangeWidth) return "high";
  return "fair";
}

export function pricePositionColor(position: PricePosition): string {
  if (position === "low") return "#57d6b1";
  if (position === "high") return "#ee8c78";
  return "#e8b86d";
}

export function scenarioMarkerColor(index: number): string {
  return SCENARIO_COLORS[index % SCENARIO_COLORS.length];
}
