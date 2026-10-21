export interface PositionTierSource {
  title: string;
  body: string;
  active?: boolean;
}

export interface PositionTier {
  tier: string;
  price: string;
  allocation: number;
  active: boolean;
}

export function parsePositionTiers(items: PositionTierSource[]): PositionTier[] {
  return items.map((item, index) => {
    const price = item.title.match(/(?:HK\$|¥|\$)\s?[\d,]+(?:\.\d+)?/i)?.[0] ?? "—";
    const allocation =
      Number.parseFloat(item.body.match(/(\d+(?:\.\d+)?)\s*%/)?.[1] ?? "0") || 0;
    return {
      tier: item.title.split("·")[0]?.trim() || `第 ${index + 1} 档`,
      price,
      allocation,
      active: item.active ?? false,
    };
  });
}
