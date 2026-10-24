<script setup lang="ts">
import { BarChart } from "echarts/charts";
import { GridComponent } from "echarts/components";
import { init, use, type ECharts } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { onBeforeUnmount, onMounted, ref, watch } from "vue";

import { chartThemeColors, observeChartTheme } from "@/lib/chart-theme";

const props = defineProps<{
  items: Array<{ label: string; height: number; highlight: boolean }>;
}>();

use([BarChart, GridComponent, CanvasRenderer]);
const element = ref<HTMLDivElement>();
let chart: ECharts | undefined;
let observer: ResizeObserver | undefined;
let stopThemeObserver: (() => void) | undefined;

function render() {
  const theme = chartThemeColors();
  chart?.setOption({
    grid: { left: 24, right: 24, top: 30, bottom: 30 },
    xAxis: {
      type: "category",
      data: props.items.map((item) => item.label),
      axisLabel: { color: theme.muted },
      axisLine: { lineStyle: { color: theme.border } },
    },
    yAxis: { type: "value", max: 100, show: false },
    series: [
      {
        type: "bar",
        data: props.items.map((item) => ({
          value: item.height,
          itemStyle: {
            color: theme.blue,
            opacity: item.highlight ? 1 : 0.38,
            borderRadius: [6, 6, 0, 0],
          },
        })),
        barWidth: "34%",
        label: {
          show: true,
          position: "top",
          color: theme.text,
          formatter: ({ dataIndex }: { dataIndex: number }) => props.items[dataIndex]?.label ?? "",
        },
      },
    ],
  });
}

onMounted(() => {
  if (!element.value) return;
  chart = init(element.value);
  observer = new ResizeObserver(() => chart?.resize());
  observer.observe(element.value);
  stopThemeObserver = observeChartTheme(render);
  render();
});
watch(() => props.items, render, { deep: true });
onBeforeUnmount(() => {
  observer?.disconnect();
  stopThemeObserver?.();
  chart?.dispose();
});
</script>

<template>
  <div ref="element" style="width: 100%; height: 220px" />
</template>
