import { describe, expect, it } from "vitest";

import type { ReportDetailBlock } from "@/api/types";

import {
  cleanReportNarrative,
  flattenPositionLayout,
  mergeScenarioAcrossSections,
  normalizeDashboardSections,
  parseConicGradient,
  tableColumnRoles,
  tableHeaders,
  tableRows,
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

  it("merges scenario bars from another section into the range block", () => {
    const sections = [
      {
        id: "valuation",
        title: "三、估值分析",
        market: "common",
        blocks: [
          { type: "paragraph", text: "正常化利润结论。" },
          { type: "heading", text: "估值情景对比" },
          {
            type: "scenario_bars",
            items: [
              { label: "HK$50", height: 80 },
              { label: "HK$62", height: 90, highlight: true },
              { label: "HK$72", height: 100 },
            ],
          },
          { type: "paragraph", text: "只放 H 股数据，三档情景说明。" },
        ],
      },
      {
        id: "range",
        title: "四、合理估值区间",
        market: "common",
        blocks: [
          {
            type: "range_bar",
            fill_left: 54.5,
            fill_width: 36.4,
            pin_left: 14.9,
            pin_label: "现价 HK$51.55",
            axis: ["HK$47", "HK$55", "HK$68", "HK$75"],
          },
          { type: "paragraph", text: "合理区间 HK$55–68，中枢 HK$62。" },
        ],
      },
    ];

    const merged = mergeScenarioAcrossSections(sections, "H");

    expect(merged[0].blocks).toEqual([
      { type: "paragraph", text: "正常化利润结论。" },
    ]);
    expect(merged[1].blocks[0]).toMatchObject({
      type: "range_bar",
      scenario_explanation: "三档情景说明。\n合理区间 HK$55–68，中枢 HK$62。",
    });
    expect(merged[1].blocks[0].scenarios).toHaveLength(3);
  });

  it("flattens a position table and removes its donut column", () => {
    const blocks: ReportDetailBlock[] = [
      {
        type: "grid",
        columns: [
          [{ type: "table", headers: ["步骤"], rows: [["① 计划买入"]] }],
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

  it("renders v1.2 object rows through semantic table columns", () => {
    const block: ReportDetailBlock = {
      type: "table",
      variant: "comparison",
      columns: [
        { key: "metric", label: "维度", role: "label" },
        { key: "value", label: "结果", role: "value" },
        { key: "note", label: "说明", role: "note" },
      ],
      rows: [
        {
          metric: "ROE",
          value: 13.4,
          note: "长期均值为正",
        },
      ],
    };

    expect(tableHeaders(block)).toEqual(["维度", "结果", "说明"]);
    expect(tableRows(block)).toEqual([["ROE", "13.4", "长期均值为正"]]);
    expect(tableColumnRoles(block)).toEqual(["label", "value", "note"]);
  });

  it("limits displayed percentages to one decimal place", () => {
    const block: ReportDetailBlock = {
      type: "table",
      headers: ["说明"],
      rows: [["贴现率差 12.399999999999999%，股息税差 34.44%"]],
    };

    expect(tableRows(block)).toEqual([["贴现率差 12.4%，股息税差 34.4%"]]);
  });

  it("preserves scenario names and prices when merging valuation charts", () => {
    const sections = [
      {
        id: "valuation",
        title: "估值",
        market: "A",
        blocks: [
          {
            type: "valuation_scenarios",
            market: "A",
            items: [
              { key: "conservative", label: "保守", price: 45.2 },
              { key: "base", label: "中性", price: 47.2 },
            ],
          },
          {
            type: "range_position",
            market: "A",
            min: 37,
            fair_low: 45.2,
            fair_high: 51,
            max: 55,
          },
        ],
      },
    ];

    const merged = mergeScenarioAcrossSections(sections, "A");
    expect(merged[0].blocks[0]).toMatchObject({
      type: "range_position",
      scenarios: [
        { label: "保守", price: 45.2, highlight: false },
        { label: "中性", price: 47.2, highlight: true },
      ],
    });
  });

  it("hides a legacy quality dimension column beside the score bars", () => {
    const block: ReportDetailBlock = {
      type: "table",
      variant: "comparison",
      columns: [
        { key: "metric", label: "维度", role: "label" },
        { key: "value", label: "结果", role: "value" },
        { key: "assessment", label: "评价", role: "assessment" },
      ],
      rows: [
        {
          metric: "经营现金流 / 净利润",
          value: "长期高于 1",
          assessment: "利润含金量可接受",
        },
      ],
    };

    expect(tableHeaders(block, true)).toEqual(["结果", "评价"]);
    expect(tableRows(block, true)).toEqual([["长期高于 1", "利润含金量可接受"]]);
    expect(tableColumnRoles(block, true)).toEqual(["value", "assessment"]);
  });

  it("keeps only gauges in a v1.2 dashboard section", () => {
    const sections = [
      {
        id: "dashboard-a",
        role: "dashboard",
        title: "决策仪表盘",
        market: "A",
        blocks: [
          { type: "paragraph", text: "不应展示的说明" },
          {
            type: "gauges",
            items: [
              {
                key: "safety_margin",
                label: "安全边际",
                value: 10,
                display_value: "10%",
                kind: "safety_margin_pct",
                tone: "pos",
              },
            ],
          },
          { type: "callout", title: "不应展示的小结", body: "不应展示" },
        ],
      },
    ];

    expect(visibleReportSections(sections, "A")[0].blocks.map((block) => block.type)).toEqual([
      "gauges",
    ]);
  });

  it("splits a legacy common dashboard by market", () => {
    const sections = [
      {
        id: "dashboard",
        title: "结论仪表盘",
        market: "common",
        blocks: [
          { type: "heading", text: "结论仪表盘" },
          { type: "table", headers: ["市场"], rows: [["A"], ["H"]] },
          { type: "gauges", market: "A", items: [] },
          { type: "gauges", market: "H", items: [] },
          { type: "callout", title: "A/H 混合结论", body: "混合内容" },
        ],
      },
    ];

    const [aSection] = normalizeDashboardSections(sections, "A");
    const [hSection] = normalizeDashboardSections(sections, "H");
    expect(aSection.blocks.map((block) => block.type)).toEqual(["gauges"]);
    expect(aSection.blocks.find((block) => block.type === "gauges")?.market).toBe("A");
    expect(hSection.blocks.map((block) => block.type)).toEqual(["gauges"]);
    expect(hSection.blocks.find((block) => block.type === "gauges")?.market).toBe("H");
  });
});
