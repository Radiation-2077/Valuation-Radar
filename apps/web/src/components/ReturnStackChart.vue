<script setup lang="ts">
import { BarChart } from "echarts/charts";
import { GridComponent, TooltipComponent } from "echarts/components";
import { init, use, type ECharts } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { NSpace, NText } from "naive-ui";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

import {
  returnSourceColor,
  segmentBlur,
  segmentEmphasis,
  segmentTooltip,
} from "@/lib/chart-colors";
import { formatPercent } from "@/lib/format";

const props = defineProps<{
  items: Array<{
    label: string;
    width: number;
    color: string;
    valuePct?: number;
  }>;
}>();

use([BarChart, GridComponent, TooltipComponent, CanvasRenderer]);
const element = ref<HTMLDivElement>();
let chart: ECharts | undefined;
let observer: ResizeObserver | undefined;
const segments = computed(() =>
  props.items.filter((item) => Number.isFinite(item.width) && item.width > 0),
);

function render() {
  chart?.setOption({
    grid: { left: 0, right: 0, top: 0, bottom: 0 },
    xAxis: { type: "value", max: 100, show: false },
    yAxis: { type: "category", data: [""], show: false },
    tooltip: {
      ...segmentTooltip(),
      formatter: (params: { dataIndex?: number }) => {
        const item = segments.value[params.dataIndex ?? 0];
        if (!item) return "";
        if (item.valuePct === undefined) {
          return `${item.label}<br/>图表占比 ${item.width.toFixed(1)}%`;
        }
        return `${item.label}<br/>年化贡献 ${item.valuePct >= 0 ? "+" : ""}${formatPercent(item.valuePct)}`;
      },
    },
    series: segments.value.map((item, index) => ({
      type: "bar",
      stack: "return",
      data: [item.width],
      barWidth: 32,
      itemStyle: {
        color: returnSourceColor(item.label, item.color),
        borderRadius:
          index === 0
            ? [8, 0, 0, 8]
            : index === segments.value.length - 1
              ? [0, 8, 8, 0]
              : 0,
      },
      emphasis: segmentEmphasis(),
      blur: segmentBlur(),
      label: {
        show: item.width >= 12,
        color: "#07131f",
        fontSize: 12,
        fontWeight: 600,
        lineHeight: 16,
        formatter: item.label,
      },
    })),
  }, true);
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
    class="return-stack-chart"
    role="img"
    :aria-label="segments.map((item) => item.label).join('、')"
    :data-segment-count="segments.length"
  >
    <NSpace class="return-stack-heading" align="center" justify="space-between" :size="8">
      <NText strong>收益拆解</NText>
      <NText depth="3">年化贡献</NText>
    </NSpace>
    <div ref="element" class="return-stack-canvas" />
  </div>
</template>
