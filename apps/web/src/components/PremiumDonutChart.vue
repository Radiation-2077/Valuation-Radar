<script setup lang="ts">
import { PieChart } from "echarts/charts";
import { LegendComponent, TooltipComponent } from "echarts/components";
import { init, use, type ECharts } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { NSpace, NText } from "naive-ui";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

import { formatPercent } from "@/lib/format";
import { parseConicGradient } from "@/lib/report-detail";

use([PieChart, TooltipComponent, LegendComponent, CanvasRenderer]);

const props = defineProps<{
  value: string;
  comparisonValue?: string;
  label: string;
  background: string;
  context?: string;
  labels?: string[];
}>();

const element = ref<HTMLDivElement>();
let chart: ECharts | undefined;
let observer: ResizeObserver | undefined;

const segments = computed(() => {
  const parsed = parseConicGradient(props.background);
  return parsed.length ? parsed : [{ color: "#435466", value: 100 }];
});
const segmentLabels = computed(() =>
  segments.value.map(
    (segment, index) => props.labels?.[index] || `${segment.value}%`,
  ),
);
const legendLabels = computed(() =>
  segments.value.map(
    (segment, index) =>
      `${segmentLabels.value[index]} ${formatPercent(segment.value)}`,
  ),
);

function render() {
  chart?.setOption(
    {
      animationDuration: 500,
      tooltip: {
        trigger: "item",
        formatter: (params: { name?: string }) => params.name ?? "",
      },
      legend: {
        bottom: 0,
        left: "center",
        width: "94%",
        icon: "circle",
        itemWidth: 9,
        itemHeight: 9,
        itemGap: 14,
        textStyle: {
          color: "#9fb1bf",
          fontSize: 12,
        },
        data: legendLabels.value,
      },
      series: [
        {
          type: "pie",
          radius: ["46%", "80%"],
          center: ["50%", "43%"],
          startAngle: 90,
          clockwise: true,
          label: { show: false },
          labelLine: { show: false },
          itemStyle: {
            borderColor: "#0b1c29",
            borderRadius: 6,
            borderWidth: 3,
          },
          emphasis: { scale: true, scaleSize: 5 },
          data: segments.value.map((segment, index) => ({
            value: segment.value,
            name: legendLabels.value[index],
            itemStyle: { color: segment.color },
          })),
        },
      ],
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

watch(() => [props.background, props.value, props.label, props.labels], render);

onBeforeUnmount(() => {
  observer?.disconnect();
  chart?.dispose();
});
</script>

<template>
  <div
    class="premium-donut-chart"
    role="img"
    :aria-label="`${context || label}：名义${value}${comparisonValue ? `，实际${comparisonValue}` : ''}；${legendLabels.join('、')}`"
  >
    <div ref="element" class="premium-donut-canvas" />
    <NSpace class="premium-donut-copy" vertical align="center" :size="2">
      <template v-if="comparisonValue">
        <NText depth="3">名义 vs 实际</NText>
        <NText strong class="premium-donut-value">
          {{ value }} vs {{ comparisonValue }}
        </NText>
      </template>
      <template v-else>
        <NText strong class="premium-donut-value">{{ value }}</NText>
        <NText depth="3">{{ label }}</NText>
      </template>
    </NSpace>
  </div>
</template>
