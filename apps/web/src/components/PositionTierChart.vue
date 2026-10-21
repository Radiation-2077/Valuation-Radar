<script setup lang="ts">
import { BarChart } from "echarts/charts";
import { GridComponent, TooltipComponent } from "echarts/components";
import { init, use, type ECharts } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { NSpace, NText } from "naive-ui";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

import { POSITION_TIER_COLORS } from "@/lib/chart-colors";
import {
  parsePositionTiers,
  type PositionTierSource,
} from "@/lib/position-tiers";

const props = defineProps<{
  items: PositionTierSource[];
}>();

use([BarChart, GridComponent, TooltipComponent, CanvasRenderer]);
const element = ref<HTMLDivElement>();
let chart: ECharts | undefined;
let observer: ResizeObserver | undefined;

const tiers = computed(() => parsePositionTiers(props.items));
const accessibleLabel = computed(() =>
  tiers.value
    .map((tier) => `${tier.tier}，买入价 ${tier.price}，占目标仓位 ${tier.allocation}%`)
    .join("；"),
);

function render() {
  chart?.setOption(
    {
      animationDuration: 500,
      grid: { left: 0, right: 0, top: 8, bottom: 8 },
      xAxis: { type: "value", min: 0, max: 100, show: false },
      yAxis: { type: "category", data: [""], show: false },
      tooltip: {
        trigger: "item",
        formatter: ({ dataIndex }: { dataIndex: number }) => {
          const tier = tiers.value[dataIndex];
          return tier
            ? `${tier.tier}<br/>买入价 ${tier.price}<br/>占目标仓位 ${tier.allocation}%`
            : "";
        },
      },
      series: tiers.value.map((tier, index) => ({
        type: "bar" as const,
        stack: "position",
        data: [tier.allocation],
        barWidth: 32,
        itemStyle: {
          color: POSITION_TIER_COLORS[index % POSITION_TIER_COLORS.length],
          borderColor: tier.active ? "#dce7ef" : "transparent",
          borderWidth: tier.active ? 2 : 0,
          borderRadius:
            index === 0
              ? [8, 0, 0, 8]
              : index === tiers.value.length - 1
                ? [0, 8, 8, 0]
                : 0,
        },
        label: {
          show: true,
          position: "inside",
          color: "#07131f",
          fontSize: 12,
          fontWeight: 600,
          lineHeight: 16,
          formatter: `level${index + 1}：${tier.price}`,
        },
      })),
    },
    true,
  );
}

onMounted(() => {
  if (!element.value) return;
  chart = init(element.value);
  observer = new ResizeObserver(() => chart?.resize());
  observer.observe(element.value);
  render();
});

watch(() => props.items, render, { deep: true });

onBeforeUnmount(() => {
  observer?.disconnect();
  chart?.dispose();
});
</script>

<template>
  <div
    class="position-tier-chart"
    role="img"
    :aria-label="accessibleLabel"
    :data-tier-count="tiers.length"
  >
    <NSpace class="position-tier-heading" align="center" justify="space-between" :size="8">
      <NText strong>三档买入计划</NText>
      <NText depth="3">占该标的的目标仓位</NText>
    </NSpace>
    <div ref="element" class="position-tier-canvas" />
  </div>
</template>
