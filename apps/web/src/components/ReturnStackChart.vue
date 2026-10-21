<script setup lang="ts">
import { BarChart } from "echarts/charts";
import { GridComponent } from "echarts/components";
import { init, use, type ECharts } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { onBeforeUnmount, onMounted, ref, watch } from "vue";

const props = defineProps<{
  items: Array<{ label: string; width: number; color: string }>;
}>();

use([BarChart, GridComponent, CanvasRenderer]);
const element = ref<HTMLDivElement>();
let chart: ECharts | undefined;
let observer: ResizeObserver | undefined;

function render() {
  chart?.setOption({
    grid: { left: 0, right: 0, top: 0, bottom: 0 },
    xAxis: { type: "value", max: 100, show: false },
    yAxis: { type: "category", data: [""], show: false },
    series: props.items.map((item) => ({
      type: "bar",
      stack: "return",
      data: [item.width],
      barWidth: 38,
      itemStyle: { color: item.color, borderRadius: 4 },
      label: {
        show: item.width >= 12,
        color: "#fff",
        formatter: item.label,
      },
    })),
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
  <div ref="element" style="width: 100%; height: 46px" />
</template>
