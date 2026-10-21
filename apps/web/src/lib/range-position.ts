export type PricePosition = "low" | "fair" | "high";

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
