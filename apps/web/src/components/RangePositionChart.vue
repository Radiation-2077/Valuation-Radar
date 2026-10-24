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
  scenarioMarkerColor,
  type PricePosition,
} from "@/lib/range-position";
import { chartThemeColors, observeChartTheme } from "@/lib/chart-theme";

const props = defineProps<{
  fillLeft: number;
  fillWidth: number;
  pinLeft: number;
  pinLabel: string;
  axis: string[];
  scenarios?: Array<{ label: string; highlight?: boolean }>;
  explanation?: string;
}>();

use([BarChart, GridComponent, MarkLineComponent, CanvasRenderer]);
const element = ref<HTMLDivElement>();
let chart: ECharts | undefined;
let observer: ResizeObserver | undefined;
let stopThemeObserver: (() => void) | undefined;
const theme = ref(chartThemeColors());

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
const scenarioLabels = ["保守", "中性", "乐观"];
const scenarioMarkers = computed(() =>
  (props.scenarios ?? [])
    .map((scenario, index) => {
      const value = Number.parseFloat(scenario.label.replace(/[^\d.-]/g, ""));
      if (!Number.isFinite(value)) return null;
      const color = scenarioMarkerColor(index);
      const name =
        scenario.label
          .replace(/\s*(?:HK\$|¥|\$)?\s*-?\d[\d,]*(?:\.\d+)?\s*$/, "")
          .trim() || scenarioLabels[index] || `情景${index + 1}`;
      return {
        xAxis: value,
        symbol: ["none", "none"],
        label: {
          show: true,
          position: "end",
          rotate: 0,
          formatter: `${name} ${formatPrice(value)}`,
          color: theme.value.labelText,
          fontWeight: scenario.highlight ? 600 : 400,
          backgroundColor: theme.value.labelBackground,
          borderColor: color,
          borderWidth: 1,
          borderRadius: 4,
          padding: [3, 6],
        },
        lineStyle: {
          color,
          width: 1,
          type: "dashed",
        },
      };
    })
    .filter((marker): marker is NonNullable<typeof marker> => marker !== null),
);

function render() {
  chart?.setOption({
    grid: { left: 24, right: 24, top: 46, bottom: 36 },
    xAxis: {
      type: "value",
      min: axisBounds.value.min,
      max: axisBounds.value.max,
      axisLabel: {
        color: theme.value.muted,
        formatter: (value: number) => formatPrice(value),
      },
      axisTick: { show: false },
      splitLine: { show: false },
      axisLine: { lineStyle: { color: theme.value.border } },
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
          color: theme.value.track,
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
        barWidth: 18,
        barGap: "-100%",
      },
      {
        type: "bar",
        stack: "range",
        silent: true,
        data: [axisBounds.value.high - axisBounds.value.low],
        itemStyle: {
          color: positionColor.value,
          borderRadius: 9,
        },
        markLine: {
          symbol: ["none", "circle"],
          symbolSize: 10,
          label: {
            show: true,
            position: "end",
            rotate: 0,
            formatter: props.pinLabel,
            color: theme.value.labelText,
            backgroundColor: theme.value.labelBackground,
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
          data: [
            ...scenarioMarkers.value,
            { xAxis: axisBounds.value.current },
          ],
        },
        barWidth: 18,
      },
    ],
  }, true);
}

onMounted(() => {
  if (!element.value) return;
  chart = init(element.value);
  observer = new ResizeObserver(() => chart?.resize());
  observer.observe(element.value);
  stopThemeObserver = observeChartTheme(() => {
    theme.value = chartThemeColors();
    render();
  });
  render();
});
watch(() => props, render, { deep: true });
onBeforeUnmount(() => {
  observer?.disconnect();
  stopThemeObserver?.();
  chart?.dispose();
});
</script>

<template>
  <div
    class="range-position-chart"
    :data-position="position"
    :data-scenarios="scenarios?.map((scenario) => scenario.label).join('|')"
  >
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
    <NText v-if="explanation" class="range-position-explanation" depth="2">
      {{ explanation }}
    </NText>
  </div>
</template>
