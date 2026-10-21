import type { ReportDetailBlock, ReportDetailSection } from "@/api/types";

export function visibleReportSections(
  sections: ReportDetailSection[],
  market: string,
): ReportDetailSection[] {
  return sections
    .filter((section) => {
      if (section.title.includes("A 股估值") && market !== "A") return false;
      if (section.title.includes("H 股估值") && market !== "H") return false;
      return true;
    })
    .map((section) => ({
      ...section,
      blocks: filterMarketBlocks(section.title, section.blocks, market),
    }))
    .filter((section) => section.blocks.length > 0);
}

export function blockText(block: ReportDetailBlock, key = "text"): string {
  const value = block[key];
  return typeof value === "string" ? value : "";
}

export function blockNumber(block: ReportDetailBlock, key: string): number {
  const value = block[key];
  return typeof value === "number" ? value : 0;
}

export function blockObjects(block: ReportDetailBlock, key: string): Record<string, unknown>[] {
  const value = block[key];
  return Array.isArray(value)
    ? value.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
    : [];
}

export function blockColumns(block: ReportDetailBlock): ReportDetailBlock[][] {
  const value = block.columns;
  if (!Array.isArray(value)) return [];
  return value.map((column) =>
    Array.isArray(column)
      ? column.filter(
          (item): item is ReportDetailBlock =>
            Boolean(item) && typeof item === "object" && typeof (item as ReportDetailBlock).type === "string",
        )
      : [],
  );
}

export function blockNestedBlocks(block: ReportDetailBlock): ReportDetailBlock[] {
  const value = block.blocks;
  return Array.isArray(value)
    ? value.filter(
        (item): item is ReportDetailBlock =>
          Boolean(item) && typeof item === "object" && typeof (item as ReportDetailBlock).type === "string",
      )
    : [];
}

export function tableHeaders(block: ReportDetailBlock): string[] {
  const value = block.headers;
  return Array.isArray(value) ? value.map(String) : [];
}

export function tableRows(block: ReportDetailBlock): string[][] {
  const value = block.rows;
  return Array.isArray(value)
    ? value.map((row) => (Array.isArray(row) ? row.map(String) : []))
    : [];
}

export function objectText(item: Record<string, unknown>, key: string): string {
  const value = item[key];
  return typeof value === "string" ? value : "";
}

export function objectNumber(item: Record<string, unknown>, key: string): number {
  const value = item[key];
  return typeof value === "number" ? value : 0;
}

export function objectBoolean(item: Record<string, unknown>, key: string): boolean {
  return item[key] === true;
}

function filterMarketBlocks(
  sectionTitle: string,
  blocks: ReportDetailBlock[],
  market: string,
): ReportDetailBlock[] {
  if (sectionTitle.includes("跨市场校正")) return blocks;
  const hasMarketHeadings = blocks.some(
    (block) =>
      block.type === "heading" &&
      (/^A\s*股/.test(blockText(block)) || /^H\s*股/.test(blockText(block))),
  );
  if (
    !hasMarketHeadings &&
    !sectionTitle.includes("仓位") &&
    !sectionTitle.includes("预期收益率") &&
    !sectionTitle.includes("关键结论")
  ) {
    return blocks;
  }

  let activeMarket: string | null = null;
  const filtered: ReportDetailBlock[] = [];
  for (const block of blocks) {
    if (block.type === "heading") {
      const text = blockText(block);
      if (/^A\s*股/.test(text)) activeMarket = "A";
      else if (/^H\s*股/.test(text)) activeMarket = "H";
      else if (text.includes("组合")) activeMarket = null;
    }
    if (sectionTitle.includes("关键结论") && block.type === "paragraph") {
      const text = blockText(block);
      if (/^A\s*股/.test(text) && market !== "A") continue;
      if (/^H\s*股/.test(text) && market !== "H") continue;
    }
    if (activeMarket === null || activeMarket === market) filtered.push(block);
  }
  return filtered;
}
