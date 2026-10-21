<script setup lang="ts">
import { BarChart } from "echarts/charts";
import { GridComponent } from "echarts/components";
import { init, use, type ECharts } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { onBeforeUnmount, onMounted, ref, watch } from "vue";

const props = defineProps<{
  items: Array<{ label: string; height: number; highlight: boolean }>;
}>();

use([BarChart, GridComponent, CanvasRenderer]);
const element = ref<HTMLDivElement>();
let chart: ECharts | undefined;
let observer: ResizeObserver | undefined;

function render() {
  chart?.setOption({
    grid: { left: 24, right: 24, top: 30, bottom: 30 },
    xAxis: {
      type: "category",
      data: props.items.map((item) => item.label),
      axisLabel: { color: "#a9bac6" },
      axisLine: { lineStyle: { color: "rgba(158,190,210,.2)" } },
    },
    yAxis: { type: "value", max: 100, show: false },
    series: [
      {
        type: "bar",
        data: props.items.map((item) => ({
          value: item.height,
          itemStyle: {
            color: item.highlight ? "#80c7ff" : "rgba(128,199,255,.38)",
            borderRadius: [6, 6, 0, 0],
          },
        })),
        barWidth: "34%",
        label: {
          show: true,
          position: "top",
          color: "#dce7ef",
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
  render();
});
watch(() => props.items, render, { deep: true });
onBeforeUnmount(() => {
  observer?.disconnect();
  chart?.dispose();
});
</script>

<template>
  <div ref="element" style="width: 100%; height: 220px" />
</template>
