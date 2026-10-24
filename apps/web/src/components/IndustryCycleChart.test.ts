// @vitest-environment jsdom

import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import IndustryCycleChart from "@/components/IndustryCycleChart.vue";

describe("IndustryCycleChart", () => {
  it("marks the current point on the cycle curve", () => {
    const wrapper = mount(IndustryCycleChart, {
      props: { position: 55, phase: "pullback", direction: "down" },
    });

    expect(wrapper.find(".cycle-current-point").attributes("cx")).toBe("550");
    expect(wrapper.find(".cycle-stop--peak").exists()).toBe(true);
    expect(wrapper.find(".cycle-stop--trough").exists()).toBe(true);
    expect(wrapper.findAll(".cycle-extreme").map((item) => item.text())).toEqual([
      "顶峰",
      "低谷",
    ]);
    expect(wrapper.find(".industry-cycle-chart").text()).not.toContain("回升");
    expect(wrapper.find(".industry-cycle-chart").text()).not.toContain("放缓");
    expect(wrapper.attributes("aria-label")).toContain("当前高位回落");
    expect(wrapper.attributes("aria-label")).toContain("方向下行");
    expect(wrapper.find(".cycle-current-callout").text()).toBe("当前：↓ 高位回落");
  });

  it("clamps positions to the supported range", () => {
    const wrapper = mount(IndustryCycleChart, {
      props: { position: 120, phase: "downswing", direction: "down" },
    });

    expect(wrapper.attributes("data-position")).toBe("100");
    expect(wrapper.attributes("data-phase")).toBe("downswing");
    expect(wrapper.find(".cycle-current-point").attributes("cx")).toBe("1000");
  });

  it("does not invent a cycle direction when the card omits it", () => {
    const wrapper = mount(IndustryCycleChart, {
      props: { position: 60 },
    });

    expect(wrapper.find(".cycle-current-callout").text()).toBe("当前：状态未判定");
    expect(wrapper.find(".cycle-chart-head strong").text()).toBe(
      "方向未判定 · 状态未判定",
    );
  });
});
