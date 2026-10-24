// @vitest-environment jsdom

import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import IndustryLifecycleChart from "@/components/IndustryLifecycleChart.vue";

describe("IndustryLifecycleChart", () => {
  it("highlights the current industry lifecycle stage", () => {
    const wrapper = mount(IndustryLifecycleChart, {
      props: { stage: "成熟期" },
    });

    expect(wrapper.findAll(".lifecycle-label")).toHaveLength(4);
    expect(wrapper.find(".lifecycle-label--active").attributes("data-label")).toBe("成熟");
    expect(wrapper.find(".lifecycle-callout").text()).toBe("当前：成熟期");
    expect(wrapper.find(".lifecycle-label--active .lifecycle-marker").exists()).toBe(true);
  });

  it("keeps all four stages visible", () => {
    const wrapper = mount(IndustryLifecycleChart, {
      props: { stage: "导入/爆发期" },
    });

    expect(
      wrapper.findAll(".lifecycle-label").map((item) => item.attributes("data-label")),
    ).toEqual(["导入/爆发", "平台增长", "成熟", "衰退"]);
  });
});
