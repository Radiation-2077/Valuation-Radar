export const CHART_COLORS = {
  green: "#57d6b1",
  blue: "#80c7ff",
  purple: "#b8a1ff",
  gold: "#e8b86d",
  red: "#ee8c78",
} as const;

export const POSITION_TIER_COLORS = [
  CHART_COLORS.green,
  CHART_COLORS.blue,
  CHART_COLORS.gold,
] as const;

export function segmentTooltip() {
  return {
    trigger: "item" as const,
    backgroundColor: "#0c1c2a",
    borderColor: "rgba(158,190,210,.25)",
    textStyle: { color: "#dce7ef" },
  };
}

export function segmentEmphasis() {
  return {
    focus: "series" as const,
    itemStyle: {
      borderColor: "#dce7ef",
      borderWidth: 2,
      shadowBlur: 14,
      shadowColor: "rgba(220, 231, 239, 0.42)",
    },
  };
}

export function segmentBlur() {
  return {
    itemStyle: { opacity: 0.45 },
  };
}

export function returnSourceColor(label: string, fallback: string): string {
  if (label.includes("股息")) return CHART_COLORS.green;
  if (label.includes("增长")) return CHART_COLORS.blue;
  if (label.includes("估值")) {
    return /[−-]/.test(label) ? CHART_COLORS.red : CHART_COLORS.gold;
  }
  return fallback;
}
