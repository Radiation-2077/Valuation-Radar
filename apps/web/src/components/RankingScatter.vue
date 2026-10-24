<script setup lang="ts">
import { ScatterChart } from "echarts/charts";
import { GridComponent, TooltipComponent } from "echarts/components";
import { init, use, type ECharts } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { onBeforeUnmount, onMounted, ref, watch } from "vue";

import type { RankingItem } from "@/api/types";
import { chartThemeColors, observeChartTheme } from "@/lib/chart-theme";

use([ScatterChart, GridComponent, TooltipComponent, CanvasRenderer]);

const props = defineProps<{
  items: RankingItem[];
}>();

const emit = defineEmits<{
  select: [id: number];
}>();

const chartElement = ref<HTMLDivElement>();
let chart: ECharts | undefined;
let resizeObserver: ResizeObserver | undefined;
let stopThemeObserver: (() => void) | undefined;

type ScatterDatum = [number, number, RankingItem];

function render() {
  if (!chart || !props.items.length) return;
  const theme = chartThemeColors();
  const bandColors: Record<string, string> = {
    S: theme.accent,
    A: theme.blue,
    B: theme.warm,
    C: theme.red,
    D: "#9a7880",
  };
  chart.setOption({
    animationDuration: 500,
    grid: { left: 54, right: 28, top: 28, bottom: 52 },
    tooltip: {
      trigger: "item",
      backgroundColor: theme.labelBackground,
      borderColor: theme.border,
      textStyle: { color: theme.labelText },
      formatter: (params: { data: ScatterDatum }) => {
        const item = params.data[2];
        return [
          `<strong>${item.name} ${item.market}</strong>`,
          `综合分 ${item.score.total?.toFixed(1) ?? "—"} · ${item.score.band} 档`,
          `回撤 ${Math.abs(item.max_drawdown_pct ?? 0).toFixed(1)}%`,
          `预期年化 ${item.expected_return.total?.toFixed(1) ?? "—"}%`,
        ].join("<br/>");
      },
    },
    xAxis: {
      name: "悲观情景回撤 →",
      nameLocation: "middle",
      nameGap: 32,
      min: 0,
      nameTextStyle: { color: theme.muted },
      splitLine: { lineStyle: { color: theme.border } },
      axisLabel: { color: theme.muted, formatter: "{value}%" },
      axisLine: { lineStyle: { color: theme.border } },
    },
    yAxis: {
      name: "预期年化",
      nameTextStyle: { color: theme.muted },
      splitLine: { lineStyle: { color: theme.border } },
      axisLabel: { color: theme.muted, formatter: "{value}%" },
    },
    series: [
      {
        type: "scatter",
        data: props.items.map(
          (item): ScatterDatum => [
            Math.abs(item.max_drawdown_pct ?? 0),
            item.expected_return.total ?? 0,
            item,
          ],
        ),
        symbolSize: (value: ScatterDatum) =>
          11 + Math.max(0, Math.min(9, (value[2].safety_margin_pct ?? 0) / 5)),
        itemStyle: {
          opacity: 0.88,
          borderColor: theme.labelBackground,
          borderWidth: 2,
          color: (params: { data: ScatterDatum }) =>
            bandColors[params.data[2].score.band] ?? "#80c7ff",
        },
        label: {
          show: true,
          position: "top",
          distance: 6,
          color: theme.text,
          fontSize: 11,
          formatter: (params: { data: ScatterDatum }) =>
            `${params.data[2].name}${params.data[2].market}`,
        },
        emphasis: { scaleSize: 5 },
      },
    ],
  });
}

onMounted(() => {
  if (!chartElement.value) return;
  chart = init(chartElement.value);
  chart.on("click", (params) => {
    const data = params.data as ScatterDatum | undefined;
    if (data?.[2]) emit("select", data[2].valuation_market_id);
  });
  resizeObserver = new ResizeObserver(() => chart?.resize());
  resizeObserver.observe(chartElement.value);
  stopThemeObserver = observeChartTheme(() => {
    render();
  });
  render();
});

watch(() => props.items, render, { deep: true });

onBeforeUnmount(() => {
  resizeObserver?.disconnect();
  stopThemeObserver?.();
  chart?.dispose();
});
</script>

<template>
  <div
    v-if="items.length"
    ref="chartElement"
    class="scatter-chart"
    role="img"
    aria-label="性价比象限图"
  ></div>
  <div v-else class="empty-panel">当前筛选下没有可绘制的标的。</div>
</template>
