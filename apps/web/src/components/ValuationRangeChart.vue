<script setup lang="ts">
import { BarChart } from "echarts/charts";
import { GridComponent, MarkLineComponent, TooltipComponent } from "echarts/components";
import { init, use, type ECharts } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { onBeforeUnmount, onMounted, ref, watch } from "vue";

import { formatMoney } from "@/lib/format";

use([BarChart, GridComponent, MarkLineComponent, TooltipComponent, CanvasRenderer]);

const props = defineProps<{
  low: number;
  mid: number;
  high: number;
  price: number;
  currency: string;
}>();

const element = ref<HTMLDivElement>();
let chart: ECharts | undefined;
let observer: ResizeObserver | undefined;

function render() {
  const axisMin = Math.min(props.low, props.price) * 0.9;
  const axisMax = Math.max(props.high, props.price) * 1.08;
  chart?.setOption({
    animationDuration: 450,
    grid: { left: 24, right: 24, top: 54, bottom: 32 },
    tooltip: { show: false },
    xAxis: {
      type: "value",
      min: axisMin,
      max: axisMax,
      axisLabel: {
        color: "#8296a5",
        formatter: (value: number) => formatMoney(value, props.currency),
      },
      splitLine: { lineStyle: { color: "rgba(158,190,210,.10)" } },
    },
    yAxis: { type: "category", data: [""], axisLabel: { show: false }, axisLine: { show: false } },
    series: [
      {
        type: "bar",
        stack: "range",
        silent: true,
        data: [props.low - axisMin],
        itemStyle: { color: "transparent" },
        barWidth: 16,
      },
      {
        type: "bar",
        stack: "range",
        silent: true,
        data: [props.high - props.low],
        itemStyle: { color: "rgba(87,214,177,.68)", borderRadius: 8 },
        label: {
          show: true,
          position: "top",
          color: "#8296a5",
          formatter: "合理区间",
        },
        markLine: {
          symbol: ["none", "pin"],
          symbolSize: 22,
          label: {
            show: true,
            formatter: `现价 ${formatMoney(props.price, props.currency)}`,
            color: "#e8b86d",
          },
          lineStyle: { color: "#e8b86d", width: 2 },
          data: [{ xAxis: props.price }],
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
watch(() => [props.low, props.mid, props.high, props.price, props.currency], render);
onBeforeUnmount(() => {
  observer?.disconnect();
  chart?.dispose();
});
</script>

<template>
  <div ref="element" style="width: 100%; height: 190px" />
</template>
