<script setup lang="ts">
import { GaugeChart } from "echarts/charts";
import { TooltipComponent } from "echarts/components";
import { init, use, type ECharts } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { onBeforeUnmount, onMounted, ref, watch } from "vue";

use([GaugeChart, TooltipComponent, CanvasRenderer]);

const props = defineProps<{
  label: string;
  value: number;
  displayValue: string;
  color?: string;
}>();

const element = ref<HTMLDivElement>();
let chart: ECharts | undefined;
let observer: ResizeObserver | undefined;

function render() {
  chart?.setOption({
    series: [
      {
        type: "gauge",
        startAngle: 210,
        endAngle: -30,
        min: 0,
        max: 100,
        radius: "88%",
        center: ["50%", "58%"],
        pointer: { show: false },
        progress: {
          show: true,
          width: 9,
          roundCap: true,
          itemStyle: { color: props.color ?? "#57d6b1" },
        },
        axisLine: {
          lineStyle: {
            width: 9,
            color: [[1, "rgba(158,190,210,.14)"]],
          },
        },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { show: false },
        detail: {
          valueAnimation: true,
          formatter: () => props.displayValue,
          offsetCenter: [0, "10%"],
          color: "#dce7ef",
          fontSize: 18,
          fontWeight: 600,
        },
        title: {
          offsetCenter: [0, "42%"],
          color: "#8296a5",
          fontSize: 11,
        },
        data: [{ value: props.value, name: props.label }],
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

watch(() => [props.value, props.displayValue, props.color], render);

onBeforeUnmount(() => {
  observer?.disconnect();
  chart?.dispose();
});
</script>

<template>
  <div
    ref="element"
    class="metric-gauge"
    role="img"
    :aria-label="`${label} ${displayValue}`"
    style="width: 100%; height: 150px"
  />
</template>
