import type { ReportDetailBlock, ReportDetailSection } from "@/api/types";

export interface ConicGradientSegment {
  color: string;
  value: number;
}

export function parseConicGradient(background: string): ConicGradientSegment[] {
  const match = background.match(/conic-gradient\((.*)\)/i);
  if (!match) return [];

  const segments: ConicGradientSegment[] = [];
  const stopPattern =
    /(#[0-9a-f]{3,8}|rgba?\([^)]*\))\s+([\d.]+)%?\s+([\d.]+)%/gi;
  for (const stop of match[1].matchAll(stopPattern)) {
    const value = Number.parseFloat(stop[3]) - Number.parseFloat(stop[2]);
    if (value > 0) segments.push({ color: stop[1], value });
  }
  return segments;
}

export function cleanReportNarrative(text: string): string {
  return text
    .replace(/^只放\s*[AH]\s*股数据[，,。]\s*/, "")
    .replace(/^lv-h\s*高\s*\/\s*lv-m\s*中\s*\/\s*lv-l\s*低。/, "风险等级：高 / 中 / 低。")
    .replace(/\s*[／/]\s*(?=[AH]\s*股)/g, "；");
}

export function mergeScenarioAcrossSections(
  sections: ReportDetailSection[],
  market: string,
): ReportDetailSection[] {
  const working = sections.map((section) => ({
    ...section,
    blocks: [...section.blocks],
  }));
  let scenarioLocation: { section: number; block: number } | null = null;
  let scenarioBlock: ReportDetailBlock | null = null;
  for (const [sectionIndex, section] of working.entries()) {
    const blockIndex = section.blocks.findIndex(
      (block) =>
        ["scenario_bars", "valuation_scenarios"].includes(block.type) &&
        (!block.market || block.market === market),
    );
    if (blockIndex >= 0) {
      scenarioLocation = { section: sectionIndex, block: blockIndex };
      scenarioBlock = section.blocks[blockIndex];
      break;
    }
  }
  if (!scenarioLocation || !scenarioBlock) return working;

  let rangeLocation: { section: number; block: number } | null = null;
  let rangeBlock: ReportDetailBlock | null = null;
  for (const [sectionIndex, section] of working.entries()) {
    const blockIndex = section.blocks.findIndex(
      (block) =>
        ["range_bar", "range_position"].includes(block.type) &&
        (!block.market || block.market === market),
    );
    if (blockIndex >= 0) {
      rangeLocation = { section: sectionIndex, block: blockIndex };
      rangeBlock = section.blocks[blockIndex];
      break;
    }
  }
  if (!rangeLocation || !rangeBlock) return working;

  const scenarioSection = working[scenarioLocation.section];
  const rangeSection = working[rangeLocation.section];
  const explanationIndex =
    scenarioSection.blocks[scenarioLocation.block + 1]?.type === "paragraph"
      ? scenarioLocation.block + 1
      : -1;
  const rangeExplanationIndex =
    rangeSection.blocks[rangeLocation.block + 1]?.type === "paragraph" &&
    !(rangeLocation.section === scenarioLocation.section &&
      rangeLocation.block + 1 === explanationIndex)
      ? rangeLocation.block + 1
      : -1;
  const headingIndex =
    scenarioSection.blocks[scenarioLocation.block - 1]?.type === "heading" &&
    blockText(scenarioSection.blocks[scenarioLocation.block - 1]).includes("情景")
      ? scenarioLocation.block - 1
      : -1;
  const removed = new Set([
    scenarioLocation.block,
    explanationIndex,
    headingIndex,
  ]);
  const scenarioExplanation = [explanationIndex, rangeExplanationIndex]
    .filter((index) => index >= 0)
    .map((index) =>
      cleanReportNarrative(
        blockText(
          index === rangeExplanationIndex
            ? rangeSection.blocks[index]
            : scenarioSection.blocks[index],
        ),
      ),
    )
    .filter(Boolean)
    .join("\n");
  const scenarios = blockObjects(scenarioBlock, "items").map((item) => {
    if (item.name !== undefined || item.price !== undefined) {
      return {
        label:
          objectText(item, "label") ||
          objectText(item, "name") ||
          String(item.price ?? ""),
        price: item.price,
        highlight:
          item.key === "base" ||
          item.name === "中性" ||
          objectBoolean(item, "highlight"),
      };
    }
    return {
      label: objectText(item, "label"),
      price: item.price,
      highlight: objectBoolean(item, "highlight"),
    };
  });

  const mergedRangeBlock = {
    ...rangeBlock,
    scenarios,
    scenario_explanation: scenarioExplanation,
  };
  return working.map((section, sectionIndex) => ({
    ...section,
    blocks: section.blocks.flatMap((block, blockIndex) => {
      if (
        sectionIndex === rangeLocation.section &&
        blockIndex === rangeLocation.block
      ) {
        return [mergedRangeBlock];
      }
      if (
        sectionIndex === scenarioLocation.section &&
        removed.has(blockIndex)
      ) {
        return [];
      }
      if (
        sectionIndex === rangeLocation.section &&
        blockIndex === rangeExplanationIndex
      ) {
        return [];
      }
      return [block];
    }),
  }));
}

export function flattenPositionLayout(
  blocks: ReportDetailBlock[],
  sectionTitle: string,
): ReportDetailBlock[] {
  if (!sectionTitle.includes("仓位")) return blocks;
  return blocks.map((block) => {
    if (block.type !== "grid") return block;
    const columns = blockColumns(block);
    const hasTable = columns.some((column) =>
      column.some((item) => item.type === "table"),
    );
    const hasDonut = columns.some((column) =>
      column.some((item) => item.type === "donut"),
    );
    if (!hasTable || !hasDonut) return block;
    return {
      ...block,
      columns: [
        columns.flatMap((column) =>
          column.filter((item) => item.type !== "donut"),
        ),
      ],
    };
  });
}

export function visibleReportSections(
  sections: ReportDetailSection[],
  market: string,
): ReportDetailSection[] {
  const filteredSections = normalizeDashboardSections(sections, market)
    .filter((section) => {
      if (section.market && section.market !== "common" && section.market !== market) {
        return false;
      }
      if (section.title.includes("A 股估值") && market !== "A") return false;
      if (section.title.includes("H 股估值") && market !== "H") return false;
      return true;
    });
  return mergeScenarioAcrossSections(filteredSections, market)
    .map((section) => {
      const visibleBlocks = filterMarketBlocks(section.title, section.blocks, market);
      const layoutBlocks = flattenPositionLayout(visibleBlocks, section.title);
      const isDashboard =
        section.role === "dashboard" || section.title.includes("决策仪表盘");
      return {
        ...section,
        blocks: isDashboard
          ? layoutBlocks.filter((block) => block.type === "gauges")
          : layoutBlocks,
      };
    })
    .filter((section) => section.blocks.length > 0);
}

export function normalizeDashboardSections(
  sections: ReportDetailSection[],
  market: string,
): ReportDetailSection[] {
  return sections.flatMap((section) => {
    if (
      section.market !== "common" ||
      (section.id !== "dashboard" && !section.title.includes("结论仪表盘"))
    ) {
      return [section];
    }
    const gaugeMarkets = new Set(
      section.blocks
        .filter((block) => block.type === "gauges" && typeof block.market === "string")
        .map((block) => String(block.market)),
    );
    if (!gaugeMarkets.has("A") || !gaugeMarkets.has("H")) return [section];
    return [
      {
        ...section,
        id: `dashboard-${market}`,
        market,
        title: `${market === "A" ? "A 股" : "H 股"}结论仪表盘`,
        blocks: section.blocks.filter((block) => block.market === market),
      },
    ];
  });
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

export function tableHeaders(
  block: ReportDetailBlock,
  pairedQualityTable = false,
): string[] {
  const value = block.headers;
  const headers = Array.isArray(value)
    ? value.map(String)
    : blockObjects(block, "columns").map((column) => objectText(column, "label"));
  return pairedQualityTable && headers.length > 2 ? headers.slice(-2) : headers;
}

export function tableRows(
  block: ReportDetailBlock,
  pairedQualityTable = false,
): string[][] {
  const value = block.rows;
  if (!Array.isArray(value)) return [];
  const columns = blockObjects(block, "columns");
  const rows = !columns.length
    ? value.map((row) => (Array.isArray(row) ? row.map(tableCellText) : []))
    : value.map((row) => {
        if (!row || typeof row !== "object" || Array.isArray(row)) return [];
        return columns.map((column) =>
          tableCellText(
            (row as Record<string, unknown>)[objectText(column, "key")],
          ),
        );
      });
  const sourceColumnCount = columns.length || tableHeaders(block).length;
  return pairedQualityTable && sourceColumnCount > 2
    ? rows.map((row) => row.slice(-2))
    : rows;
}

export function tableColumnRoles(
  block: ReportDetailBlock,
  pairedQualityTable = false,
): string[] {
  const columns = blockObjects(block, "columns");
  const roles = columns.map(
    (column) => objectText(column, "role") || "note",
  );
  if (pairedQualityTable && !roles.length && Array.isArray(block.headers)) {
    return block.headers.slice(-2).map((header) =>
      String(header).includes("结果")
        ? "value"
        : /评价|说明/.test(String(header))
          ? "assessment"
          : "note",
    );
  }
  return pairedQualityTable && roles.length > 2 ? roles.slice(-2) : roles;
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

function tableCellText(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") return String(value);
  if (typeof value !== "string") return "";
  return value.replace(/(-?\d+(?:\.\d+)?)\s*%/g, (_, raw: string) => {
    const number = Number(raw);
    return Number.isFinite(number) ? `${number.toFixed(1)}%` : `${raw}%`;
  });
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
