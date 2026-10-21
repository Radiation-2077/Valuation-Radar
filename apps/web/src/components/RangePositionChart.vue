<script setup lang="ts">
import { BarChart } from "echarts/charts";
import { GridComponent, MarkLineComponent } from "echarts/components";
import { init, use, type ECharts } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { onBeforeUnmount, onMounted, ref, watch } from "vue";

const props = defineProps<{
  fillLeft: number;
  fillWidth: number;
  pinLeft: number;
  pinLabel: string;
  axis: string[];
}>();

use([BarChart, GridComponent, MarkLineComponent, CanvasRenderer]);
const element = ref<HTMLDivElement>();
let chart: ECharts | undefined;
let observer: ResizeObserver | undefined;

function render() {
  chart?.setOption({
    grid: { left: 20, right: 20, top: 46, bottom: 34 },
    xAxis: { type: "value", min: 0, max: 100, show: false },
    yAxis: { type: "category", data: [""], show: false },
    series: [
      {
        type: "bar",
        stack: "range",
        silent: true,
        data: [props.fillLeft],
        itemStyle: { color: "transparent" },
        barWidth: 12,
      },
      {
        type: "bar",
        stack: "range",
        silent: true,
        data: [props.fillWidth],
        itemStyle: { color: "rgba(128,199,255,.7)", borderRadius: 6 },
        markLine: {
          symbol: ["none", "pin"],
          symbolSize: 20,
          label: { color: "#dce7ef", formatter: props.pinLabel },
          lineStyle: { color: "#e8b86d", width: 2 },
          data: [{ xAxis: props.pinLeft }],
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
watch(() => props, render, { deep: true });
onBeforeUnmount(() => {
  observer?.disconnect();
  chart?.dispose();
});
</script>

<template>
  <div>
    <div ref="element" style="width: 100%; height: 120px" />
    <div style="display: flex; justify-content: space-between; gap: 12px">
      <span v-for="label in axis" :key="label">{{ label }}</span>
    </div>
  </div>
</template>
