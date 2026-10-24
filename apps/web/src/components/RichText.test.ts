// @vitest-environment jsdom

import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import type { ReportDetailBlock } from "@/api/types";
import BulletList from "@/components/BulletList.vue";
import FormulaBlock from "@/components/FormulaBlock.vue";
import RichText from "@/components/RichText.vue";
import { parseInlineRichText } from "@/lib/report-rich-text";

const AH_FORMULA =
  "\\frac{D}{P_A}(1-t_A)+g=\\frac{D}{P_H}(1-t_H)+g";

describe("rich report text", () => {
  it("parses controlled inline formatting and formulas", () => {
    expect(
      parseInlineRichText(
        "**重点**：`DGS10` 满足 \\(\\frac{D}{P_A}(1-t_A)+g=\\frac{D}{P_H}(1-t_H)+g\\)",
      ),
    ).toEqual([
      { type: "strong", value: "重点" },
      { type: "text", value: "：" },
      { type: "code", value: "DGS10" },
      { type: "text", value: " 满足 " },
      { type: "inline_math", value: AH_FORMULA },
    ]);
  });

  it("does not treat currency amounts as formulas", () => {
    expect(parseInlineRichText("Brent 由 $104 回落至 $65")).toEqual([
      { type: "text", value: "Brent 由 $104 回落至 $65" },
    ]);
  });

  it("renders bold text, code and inline KaTeX", () => {
    const wrapper = mount(RichText, {
      props: {
        text: `**合理溢价** \\(${AH_FORMULA}\\) 来源 \`DGS10\``,
      },
    });

    expect(wrapper.find("strong").text()).toBe("合理溢价");
    expect(wrapper.find("code").text()).toBe("DGS10");
    expect(wrapper.find(".katex").exists()).toBe(true);
  });

  it("renders a display formula with caption", () => {
    const block: ReportDetailBlock = {
      type: "formula",
      latex: AH_FORMULA,
      substitution: "\\frac{1}{50}(1-0)+3\\%=\\frac{1}{40}(1-20\\%)+3\\%",
      caption: "同一现金流下，A/H 税后股息率应相等",
      explanation:
        "其中 \\(D\\) 指每股现金分红，\\(P_A\\) 指A股价格；分红取2025年度数据，价格取2026-10-23收盘价。",
    };
    const wrapper = mount(FormulaBlock, { props: { block } });

    expect(wrapper.find(".math-formula--display").exists()).toBe(true);
    expect(wrapper.text()).toContain("同一现金流下");
    expect(wrapper.text()).toContain("代入数据");
    expect(wrapper.text()).toContain("指每股现金分红");
    expect(wrapper.text()).toContain("指A股价格");
  });

  it("renders structured bullet content", () => {
    const block: ReportDetailBlock = {
      type: "bullets",
      items: [
        "**高股息**标的受税费差影响更大",
        "低股息、高成长标的受影响较小",
      ],
    };
    const wrapper = mount(BulletList, { props: { block } });

    expect(wrapper.findAll("li")).toHaveLength(2);
    expect(wrapper.find("strong").text()).toBe("高股息");
  });
});
