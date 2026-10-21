import { CHART_COLORS } from "./chart-colors";

export type PricePosition = "low" | "fair" | "high";
export const SCENARIO_COLORS = [
  CHART_COLORS.blue,
  CHART_COLORS.purple,
  CHART_COLORS.gold,
] as const;

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
  if (position === "low") return CHART_COLORS.green;
  if (position === "high") return CHART_COLORS.red;
  return CHART_COLORS.gold;
}

export function scenarioMarkerColor(index: number): string {
  return SCENARIO_COLORS[index % SCENARIO_COLORS.length];
}
