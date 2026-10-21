<script setup lang="ts">
import { BarChart } from "echarts/charts";
import { GridComponent, TooltipComponent } from "echarts/components";
import { init, use, type ECharts } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

const props = defineProps<{
  data: Record<string, number | null>;
}>();

use([BarChart, GridComponent, TooltipComponent, CanvasRenderer]);

const element = ref<HTMLDivElement>();
let chart: ECharts | undefined;
let observer: ResizeObserver | undefined;

const rows = computed(() => [
  { key: "dividend", label: "股息", value: props.data.dividend ?? 0 },
  { key: "growth", label: "盈利增长", value: props.data.growth ?? 0 },
  { key: "valuation", label: "估值修复", value: props.data.valuation ?? 0 },
  { key: "fx", label: "汇率", value: props.data.fx ?? 0 },
]);

function render() {
  const values = rows.value;
  const bound = Math.max(4, ...values.map((item) => Math.abs(item.value)));
  chart?.setOption({
    grid: { left: 76, right: 44, top: 16, bottom: 16 },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      valueFormatter: (value: number) => `${value.toFixed(1)}%`,
    },
    xAxis: {
      type: "value",
      min: -bound,
      max: bound,
      axisLabel: { color: "#8296a5", formatter: "{value}%" },
      splitLine: { lineStyle: { color: "rgba(158,190,210,.10)" } },
    },
    yAxis: {
      type: "category",
      data: values.map((item) => item.label),
      axisLabel: { color: "#a9bac6" },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    series: [
      {
        type: "bar",
        data: values.map((item) => ({
          value: item.value,
          itemStyle: { color: item.value < 0 ? "#ee8c78" : "#80c7ff", borderRadius: 4 },
        })),
        barWidth: 10,
        label: {
          show: true,
          position: "right",
          color: "#dce7ef",
          formatter: ({ value }: { value: number }) => `${value.toFixed(1)}%`,
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
watch(rows, render, { deep: true });
onBeforeUnmount(() => {
  observer?.disconnect();
  chart?.dispose();
});
</script>

<template>
  <div ref="element" style="width: 100%; height: 190px" />
</template>
