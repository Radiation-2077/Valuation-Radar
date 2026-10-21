<script setup lang="ts">
import { BarChart } from "echarts/charts";
import { GridComponent, MarkLineComponent } from "echarts/components";
import { init, use, type ECharts } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { NSpace, NTag, NText } from "naive-ui";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

import {
  classifyPricePosition,
  pricePositionColor,
  type PricePosition,
} from "@/lib/range-position";

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

const position = computed<PricePosition>(() =>
  classifyPricePosition(props.pinLeft, props.fillLeft, props.fillWidth),
);
const positionColor = computed(() => pricePositionColor(position.value));
const statusLabel = computed(() => {
  if (position.value === "low") return "低估";
  if (position.value === "high") return "高估";
  return "合理";
});
const statusType = computed<"success" | "warning" | "error">(() => {
  if (position.value === "low") return "success";
  if (position.value === "high") return "error";
  return "warning";
});
const axisBounds = computed(() => {
  const values = props.axis
    .map((label) => Number.parseFloat(label.replace(/[^\d.-]/g, "")))
    .filter(Number.isFinite);
  const min = values[0] ?? 0;
  const max = values.at(-1) ?? 100;
  const span = max - min || 1;
  return {
    min,
    max,
    low: values[1] ?? min + span * (props.fillLeft / 100),
    high: values[2] ?? min + span * ((props.fillLeft + props.fillWidth) / 100),
    current: min + span * (props.pinLeft / 100),
  };
});
const axisDecimals = computed(() =>
  Math.max(
    0,
    ...props.axis.map(
      (label) => label.split(".")[1]?.replace(/\D/g, "").length ?? 0,
    ),
  ),
);
const axisSymbol = computed(
  () => props.axis[0]?.replace(/[\d.,\s-]/g, "") ?? "",
);
const formatPrice = (value: number) =>
  `${axisSymbol.value}${new Intl.NumberFormat("zh-CN", {
    maximumFractionDigits: axisDecimals.value,
  }).format(value)}`;
const rangeLabel = computed(
  () => `${formatPrice(axisBounds.value.low)}–${formatPrice(axisBounds.value.high).replace(axisSymbol.value, "")}`,
);

function render() {
  chart?.setOption({
    grid: { left: 24, right: 24, top: 46, bottom: 36 },
    xAxis: {
      type: "value",
      min: axisBounds.value.min,
      max: axisBounds.value.max,
      axisLabel: {
        color: "#a9bac6",
        formatter: (value: number) => formatPrice(value),
      },
      axisTick: { show: false },
      splitLine: { show: false },
      axisLine: { lineStyle: { color: "rgba(158,190,210,.22)" } },
    },
    yAxis: { type: "category", data: [""], show: false },
    series: [
      {
        type: "bar",
        stack: "track",
        silent: true,
        data: [axisBounds.value.min],
        itemStyle: { color: "transparent" },
        barWidth: 18,
      },
      {
        type: "bar",
        stack: "track",
        silent: true,
        data: [axisBounds.value.max - axisBounds.value.min],
        itemStyle: {
          color: "rgba(158,190,210,.14)",
          borderRadius: 9,
        },
        barWidth: 18,
      },
      {
        type: "bar",
        stack: "range",
        silent: true,
        data: [axisBounds.value.low],
        itemStyle: { color: "transparent" },
        barWidth: 14,
        barGap: "-100%",
      },
      {
        type: "bar",
        stack: "range",
        silent: true,
        data: [axisBounds.value.high - axisBounds.value.low],
        itemStyle: {
          color: positionColor.value,
          borderRadius: 7,
        },
        markLine: {
          symbol: ["none", "circle"],
          symbolSize: 10,
          label: {
            show: true,
            formatter: props.pinLabel,
            color: positionColor.value,
            backgroundColor: "rgba(7,19,31,.92)",
            borderColor: positionColor.value,
            borderWidth: 1,
            borderRadius: 4,
            padding: [4, 7],
          },
          lineStyle: {
            color: positionColor.value,
            width: 2,
            type: "dashed",
          },
          data: [{ xAxis: axisBounds.value.current }],
        },
        barWidth: 14,
      },
    ],
  }, true);
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
  <div class="range-position-chart" :data-position="position">
    <NSpace class="range-position-meta" align="center" justify="space-between" :size="8">
      <NSpace align="center" :size="6">
        <NText depth="3">合理区间</NText>
        <NText strong>{{ rangeLabel }}</NText>
      </NSpace>
      <NTag
        class="range-position-status"
        :type="statusType"
        :bordered="false"
        :data-status="position"
      >
        {{ pinLabel }} · {{ statusLabel }}
      </NTag>
    </NSpace>
    <div ref="element" class="range-position-canvas" />
  </div>
</template>
