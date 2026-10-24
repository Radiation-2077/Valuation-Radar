export interface PositionTierSource {
  title: string;
  body: string;
  active?: boolean;
  triggerType?: string;
  condition?: string;
}

export interface PositionTier {
  tier: string;
  price: string;
  allocation: number;
  active: boolean;
  triggerType: string;
  condition: string;
}

const TRIGGER_LABELS: Record<string, string> = {
  valuation: "估值触发",
  evidence: "证据确认",
  stabilization: "止跌确认",
  catalyst: "催化剂",
  reserve: "预留",
};

export function triggerTypeLabel(value: string): string {
  return TRIGGER_LABELS[value] ?? value;
}

export function parsePositionTiers(items: PositionTierSource[]): PositionTier[] {
  let allocated = 0;
  return items.map((item, index) => {
    const price = item.title.match(/(?:HK\$|¥|\$)\s?[\d,]+(?:\.\d+)?/i)?.[0] ?? "—";
    const explicit = item.body.match(/计划买入\s*(\d+(?:\.\d+)?)\s*%/)?.[1];
    const fallback = item.body.match(/(\d+(?:\.\d+)?)\s*%/)?.[1];
    const extracted = Number.parseFloat(explicit ?? fallback ?? "0") || 0;
    const allocation =
      item.body.includes("加至") && item.body.includes("完成建仓")
        ? Math.max(0, 100 - allocated)
        : extracted;
    allocated += allocation;
    return {
      tier: item.title.split("·")[0]?.trim() || `第 ${index + 1} 档`,
      price,
      allocation,
      active: item.active ?? false,
      triggerType: triggerTypeLabel(item.triggerType ?? ""),
      condition: item.condition ?? "",
    };
  });
}
