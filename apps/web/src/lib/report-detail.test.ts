import { describe, expect, it } from "vitest";

import type { ReportDetailBlock } from "@/api/types";

import {
  cleanReportNarrative,
  flattenPositionLayout,
  mergeScenarioIntoRange,
  normalizeQualityScorecard,
  parseConicGradient,
  visibleReportSections,
} from "./report-detail";

describe("report detail helpers", () => {
  it("converts conic gradient ranges into donut segments", () => {
    const segments = parseConicGradient(
      "background:conic-gradient(#1d4ed8 0 21%,#3b82f6 21% 92%,#f59e0b 92% 99%,#dc2626 99% 100%)",
    );

    expect(segments).toEqual([
      { color: "#1d4ed8", value: 21 },
      { color: "#3b82f6", value: 71 },
      { color: "#f59e0b", value: 7 },
      { color: "#dc2626", value: 1 },
    ]);
  });

  it("returns no segments without a conic gradient", () => {
    expect(parseConicGradient("background:#57d6b1")).toEqual([]);
  });

  it("removes market scope prefixes from report narrative", () => {
    expect(cleanReportNarrative("只放 H 股数据，与上一章共用同一套假设。")).toBe(
      "与上一章共用同一套假设。",
    );
    expect(
      cleanReportNarrative("lv-h 高 / lv-m 中 / lv-l 低。共同风险在前，市场间风险在后。"),
    ).toBe("风险等级：高 / 中 / 低。共同风险在前，市场间风险在后。");
    expect(
      cleanReportNarrative(
        "最大回撤情景：A 股约 −31.3%（¥160）／ H 股约 −33.7%（HK$250）",
      ),
    ).toBe("最大回撤情景：A 股约 −31.3%（¥160）；H 股约 −33.7%（HK$250）");
  });

  it("merges scenario bars and their explanation into the range block", () => {
    const blocks: ReportDetailBlock[] = [
      { type: "heading", text: "估值情景对比（H 股）" },
      {
        type: "scenario_bars",
        items: [
          { label: "HK$50", height: 80 },
          { label: "HK$62", height: 90, highlight: true },
          { label: "HK$72", height: 100 },
        ],
      },
      { type: "paragraph", text: "只放 H 股数据，三档情景说明。" },
      {
        type: "range_bar",
        fill_left: 54.5,
        fill_width: 36.4,
        pin_left: 14.9,
        pin_label: "现价 HK$51.55",
        axis: ["HK$47", "HK$55", "HK$68", "HK$75"],
      },
      { type: "paragraph", text: "合理区间 HK$55–68，中枢 HK$62。" },
    ];

    const merged = mergeScenarioIntoRange(blocks);

    expect(merged).toHaveLength(1);
    expect(merged[0]).toMatchObject({
      type: "range_bar",
      scenario_explanation: "三档情景说明。\n合理区间 HK$55–68，中枢 HK$62。",
    });
    expect(merged[0].scenarios).toHaveLength(3);
  });

  it("flattens a position table and removes its donut column", () => {
    const blocks: ReportDetailBlock[] = [
      {
        type: "grid",
        columns: [
          [{ type: "table", headers: ["步骤"], rows: [["① 基础仓位"]] }],
          [
            { type: "donut", percentage: 7, value: "7%" },
            {
              type: "group",
              blocks: [{ type: "paragraph", text: "止盈与认错条件" }],
            },
          ],
        ],
      },
    ];

    const flattened = flattenPositionLayout(blocks, "六、操作建议与仓位管理");
    const columns = flattened[0].columns as ReportDetailBlock[][];

    expect(columns).toHaveLength(1);
    expect(columns[0].map((block) => block.type)).toEqual(["table", "group"]);
  });

  it("normalizes the legacy quality grid into the shared scorecard", () => {
    const blocks: ReportDetailBlock[] = [
      {
        type: "grid",
        columns: [
          [
            {
              type: "scores",
              items: [
                { label: "利润现金含量", score: "9.2", width: 92 },
                { label: "资产负债表", score: "6.8", width: 68 },
                { label: "ROE 水平", score: "8.6", width: 86 },
                { label: "护城河强度", score: "8.2", width: 82 },
                { label: "生存能力", score: "7.6", width: 76 },
              ],
            },
          ],
          [
            {
              type: "table",
              headers: ["维度", "结果", "评价"],
              rows: [
                ["经营现金流 / 净利润", "2.7 倍", "真实"],
                ["有息负债率", "13.4%", "安全"],
                ["ROE（近 3 年均值）", "21.9%", "优秀"],
                ["护城河", "成本优势", "强"],
                ["危机年份", "均盈利", "通过"],
              ],
            },
          ],
        ],
      },
    ];

    const normalized = normalizeQualityScorecard(blocks, "一、标的质地");
    expect(normalized[0]).toMatchObject({
      type: "quality_scorecard",
      scale_max: 10,
    });
    expect(
      (normalized[0].dimensions as Record<string, unknown>[]).map((item) => item.key),
    ).toEqual([
      "profit_cash_quality",
      "balance_sheet",
      "roe",
      "moat",
      "survival",
    ]);
  });

  it("hides market-specific sections from the other market", () => {
    const sections = [
      {
        id: "quality",
        title: "一、标的质地",
        market: "common",
        blocks: [{ type: "paragraph", text: "共用结论" }],
      },
      {
        id: "position-A",
        title: "六、A 股仓位",
        market: "A",
        blocks: [{ type: "paragraph", text: "仅 A 股" }],
      },
      {
        id: "position-H",
        title: "六、H 股仓位",
        market: "H",
        blocks: [{ type: "paragraph", text: "仅 H 股" }],
      },
    ];

    expect(visibleReportSections(sections, "A").map((section) => section.id)).toEqual([
      "quality",
      "position-A",
    ]);
    expect(visibleReportSections(sections, "H").map((section) => section.id)).toEqual([
      "quality",
      "position-H",
    ]);
  });
});
