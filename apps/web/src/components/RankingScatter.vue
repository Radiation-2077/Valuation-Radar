<script setup lang="ts">
import { ScatterChart } from "echarts/charts";
import { GridComponent, TooltipComponent } from "echarts/components";
import { init, use, type ECharts } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { onBeforeUnmount, onMounted, ref, watch } from "vue";

import type { RankingItem } from "@/api/types";

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

const bandColors: Record<string, string> = {
  S: "#57d6b1",
  A: "#80c7ff",
  B: "#e8b86d",
  C: "#ee8c78",
  D: "#9a7880",
};

type ScatterDatum = [number, number, RankingItem];

function render() {
  if (!chart || !props.items.length) return;
  chart.setOption({
    animationDuration: 500,
    grid: { left: 54, right: 28, top: 28, bottom: 52 },
    tooltip: {
      trigger: "item",
      backgroundColor: "#0c1c2a",
      borderColor: "rgba(158,190,210,.25)",
      textStyle: { color: "#dce7ef" },
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
      splitLine: { lineStyle: { color: "rgba(158,190,210,.10)" } },
      axisLabel: { color: "#718797", formatter: "{value}%" },
      axisLine: { lineStyle: { color: "rgba(158,190,210,.22)" } },
    },
    yAxis: {
      name: "预期年化",
      nameTextStyle: { color: "#718797" },
      splitLine: { lineStyle: { color: "rgba(158,190,210,.10)" } },
      axisLabel: { color: "#718797", formatter: "{value}%" },
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
          borderColor: "#07131f",
          borderWidth: 2,
          color: (params: { data: ScatterDatum }) =>
            bandColors[params.data[2].score.band] ?? "#80c7ff",
        },
        label: {
          show: true,
          position: "top",
          distance: 6,
          color: "#b6c7d3",
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
  render();
});

watch(() => props.items, render, { deep: true });

onBeforeUnmount(() => {
  resizeObserver?.disconnect();
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
