<script setup lang="ts">
import { BarChart } from "echarts/charts";
import { GridComponent, TooltipComponent } from "echarts/components";
import { init, use, type ECharts } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { NSpace, NText } from "naive-ui";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

import {
  POSITION_TIER_COLORS,
  segmentBlur,
  segmentEmphasis,
  segmentTooltip,
} from "@/lib/chart-colors";
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
    .map(
      (tier) =>
        `${tier.tier}，${tier.triggerType}，${tier.condition}，触发价 ${tier.price}，占计划买入 ${tier.allocation}%`,
    )
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
        ...segmentTooltip(),
        formatter: ({ seriesIndex }: { seriesIndex: number }) => {
          const tier = tiers.value[seriesIndex];
          return tier
            ? `${tier.tier}<br/>${tier.triggerType}<br/>${tier.condition}<br/>触发价 ${tier.price}<br/>占计划买入 ${tier.allocation}%`
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
          borderRadius:
            index === 0
              ? [8, 0, 0, 8]
              : index === tiers.value.length - 1
                ? [0, 8, 8, 0]
                : 0,
        },
        emphasis: segmentEmphasis(),
        blur: segmentBlur(),
        label: {
          show: true,
          position: "inside",
          align:
            tier.allocation < 12
              ? index === tiers.value.length - 1
                ? "right"
                : index === 0
                  ? "left"
                  : "center"
              : "center",
          color: "#07131f",
          fontSize: 12,
          fontWeight: 600,
          lineHeight: 16,
          formatter: tier.triggerType || `level${index + 1}`,
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
      <NText strong>四档买入计划</NText>
      <NText depth="3">按计划内比例分批执行</NText>
    </NSpace>
    <div ref="element" class="position-tier-canvas" />
  </div>
</template>
