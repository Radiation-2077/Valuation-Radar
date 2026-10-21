export function formatNumber(
  value: number | null | undefined,
  digits = 1,
  suffix = "",
): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${value.toFixed(digits)}${suffix}`;
}

export function formatMoney(
  value: number | null | undefined,
  currency: string,
): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const symbol = currency === "HKD" ? "HK$" : currency === "USD" ? "$" : "¥";
  return `${symbol}${value.toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

export function formatPercent(value: number | null | undefined, digits = 1): string {
  return formatNumber(value, digits, "%");
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(`${value.slice(0, 10)}T00:00:00`);
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const hasZone = /(?:Z|[+-]\d{2}:\d{2})$/i.test(value);
  const date = new Date(hasZone ? value : `${value}Z`);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

export const pathLabels: Record<string, string> = {
  stable: "稳定增长",
  cyclical: "周期",
  financial: "金融",
  etf: "ETF",
};

export const marketLabels: Record<string, string> = {
  A: "A 股",
  H: "H 股",
  CN: "中国市场",
  US: "美股",
};

export function isStale(days: number, threshold: number): boolean {
  return days > threshold;
}
