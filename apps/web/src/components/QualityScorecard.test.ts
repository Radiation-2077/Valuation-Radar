// @vitest-environment jsdom

import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import type { ReportDetailBlock } from "@/api/types";
import QualityScorecard from "@/components/QualityScorecard.vue";

describe("QualityScorecard", () => {
  it("renders the five paired quality dimensions", () => {
    const block: ReportDetailBlock = {
      type: "quality_scorecard",
      scale_max: 10,
      dimensions: [
        dimension("profit_cash_quality", "利润现金含量", "1.2 倍", "真实"),
        dimension("balance_sheet", "资产负债表", "20%", "稳健"),
        dimension("roe", "ROE 水平", "12%", "中上"),
        dimension("moat", "护城河强度", "规模与成本", "强"),
        dimension("survival", "生存能力", "保持盈利", "通过"),
      ],
    };

    const wrapper = mount(QualityScorecard, { props: { block } });
    const text = wrapper.text();
    for (const label of [
      "利润现金含量",
      "资产负债表",
      "ROE 水平",
      "护城河强度",
      "生存能力",
    ]) {
      expect(text).toContain(label);
    }
    expect(text).toContain("8 / 10");
    expect(text).toContain("保持盈利");
  });
});

function dimension(
  key: string,
  label: string,
  value: string,
  assessment: string,
): Record<string, unknown> {
  return {
    key,
    label,
    score: 8,
    indicator: `${label}指标`,
    value,
    assessment,
  };
}
