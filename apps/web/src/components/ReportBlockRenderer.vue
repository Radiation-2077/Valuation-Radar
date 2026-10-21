<script setup lang="ts">
import {
  NAlert,
  NCard,
  NGrid,
  NGridItem,
  NH3,
  NProgress,
  NSpace,
  NTable,
  NTag,
  NText,
  NTbody,
  NTd,
  NTh,
  NThead,
  NTr,
} from "naive-ui";

import type { ReportDetailBlock } from "@/api/types";
import MetricGauge from "@/components/MetricGauge.vue";
import PositionTierChart from "@/components/PositionTierChart.vue";
import PremiumDonutChart from "@/components/PremiumDonutChart.vue";
import RangePositionChart from "@/components/RangePositionChart.vue";
import ReturnStackChart from "@/components/ReturnStackChart.vue";
import ScenarioBarChart from "@/components/ScenarioBarChart.vue";
import {
  blockColumns,
  blockNestedBlocks,
  blockNumber,
  blockObjects,
  blockText,
  cleanReportNarrative,
  objectBoolean,
  objectNumber,
  objectText,
  tableHeaders,
  tableRows,
} from "@/lib/report-detail";

defineOptions({ name: "ReportBlockRenderer" });
defineProps<{
  blocks: ReportDetailBlock[];
  alignScoresWithTable?: boolean;
  donutLabels?: string[];
}>();

function calloutType(tone: string): "success" | "warning" | "error" | "info" {
  if (tone === "pos") return "success";
  if (tone === "warn") return "warning";
  if (tone === "neg") return "error";
  return "info";
}

function riskType(level: string): "error" | "warning" | "success" | "info" {
  if (level === "h") return "error";
  if (level === "m") return "warning";
  if (level === "l") return "success";
  return "info";
}

function itemString(item: Record<string, unknown>, key: string): string {
  return objectText(item, key);
}

function itemNumber(item: Record<string, unknown>, key: string): number {
  return objectNumber(item, key);
}

function itemBoolean(item: Record<string, unknown>, key: string): boolean {
  return objectBoolean(item, key);
}

function gaugeValue(value: string): number {
  return Number.parseFloat(value.replace("%", "")) || 0;
}

function gaugeColor(tone: string): string {
  if (tone === "acc") return "#57d6b1";
  if (tone === "warn") return "#e8b86d";
  if (tone === "neg") return "#ee8c78";
  return "#80c7ff";
}

function gridPairsScoresWithTable(block: ReportDetailBlock): boolean {
  const columns = blockColumns(block);
  return (
    columns.some((column) => column.some((item) => item.type === "scores")) &&
    columns.some((column) => column.some((item) => item.type === "table"))
  );
}

function gridDonutLabels(block: ReportDetailBlock): string[] {
  for (const column of blockColumns(block)) {
    const table = column.find((item) => item.type === "table");
    if (!table) continue;
    const headers = tableHeaders(table);
    const percentageIndex = headers.findIndex(
      (header) => header.includes("%") || header.includes("占比"),
    );
    if (percentageIndex < 0) continue;
    const labelIndex = headers.findIndex((header) =>
      ["成因", "项目", "类别", "维度"].some((name) => header.includes(name)),
    );
    if (labelIndex < 0) continue;
    return tableRows(table)
      .map((row) => row[labelIndex] ?? "")
      .filter(Boolean);
  }
  return [];
}
</script>

<template>
  <NSpace class="report-block-stack" vertical :size="20">
    <template v-for="(block, index) in blocks" :key="`${block.type}-${index}`">
    <NH3 v-if="block.type === 'heading'">{{ blockText(block) }}</NH3>

    <NText
      v-else-if="block.type === 'paragraph'"
      :depth="block.note ? 3 : 2"
      style="white-space: pre-line; line-height: 1.8"
    >
      {{ cleanReportNarrative(blockText(block)) }}
    </NText>

    <NAlert
      v-else-if="block.type === 'callout'"
      :type="calloutType(blockText(block, 'tone'))"
      :title="cleanReportNarrative(blockText(block, 'title'))"
      :bordered="false"
    >
      <span style="white-space: pre-line">
        {{ cleanReportNarrative(blockText(block, "body")) }}
      </span>
    </NAlert>

    <div v-else-if="block.type === 'table'" class="table-shell">
      <NTable size="small" :bordered="false" :single-line="false">
        <NThead v-if="tableHeaders(block).length && !alignScoresWithTable">
          <NTr>
            <NTh v-for="header in tableHeaders(block)" :key="header">{{ header }}</NTh>
          </NTr>
        </NThead>
        <NTbody>
          <NTr v-for="(row, rowIndex) in tableRows(block)" :key="rowIndex">
            <NTd v-for="(cell, cellIndex) in row" :key="cellIndex">{{ cell }}</NTd>
          </NTr>
        </NTbody>
      </NTable>
    </div>

    <NSpace
      v-else-if="block.type === 'scores'"
      :class="['score-list', { 'score-list--table-aligned': alignScoresWithTable }]"
      vertical
      :size="12"
    >
      <div
        v-for="item in blockObjects(block, 'items')"
        :key="itemString(item, 'label')"
        class="score-row"
      >
        <span>{{ itemString(item, "label") }}</span>
        <NProgress
          type="line"
          :percentage="itemNumber(item, 'width')"
          :height="7"
          :show-indicator="false"
          :color="itemString(item, 'tone') === 'negative' ? '#e8b86d' : '#57d6b1'"
        />
        <strong>{{ itemString(item, "score") }}</strong>
      </div>
    </NSpace>

    <NGrid
      v-else-if="block.type === 'gauges'"
      responsive="screen"
      cols="2 m:4"
      :x-gap="12"
      :y-gap="12"
    >
      <NGridItem v-for="item in blockObjects(block, 'items')" :key="itemString(item, 'label')">
        <MetricGauge
          :label="itemString(item, 'label')"
          :value="gaugeValue(itemString(item, 'value'))"
          :display-value="itemString(item, 'value')"
          :color="gaugeColor(itemString(item, 'tone'))"
        />
      </NGridItem>
    </NGrid>

    <NGrid
      v-else-if="block.type === 'metric_cards'"
      responsive="screen"
      cols="1 s:2 m:4"
      :x-gap="12"
      :y-gap="12"
    >
      <NGridItem v-for="item in blockObjects(block, 'items')" :key="itemString(item, 'label')">
        <NCard size="small">
          <NSpace vertical :size="6">
            <NText depth="3">{{ itemString(item, "label") }}</NText>
            <NText strong style="font-size: 18px">{{ itemString(item, "value") }}</NText>
            <NText depth="3">{{ itemString(item, "detail") }}</NText>
          </NSpace>
        </NCard>
      </NGridItem>
    </NGrid>

    <NGrid
      v-else-if="block.type === 'grid'"
      responsive="screen"
      :cols="blockColumns(block).length"
      :x-gap="20"
      :y-gap="16"
    >
      <NGridItem v-for="(column, columnIndex) in blockColumns(block)" :key="columnIndex">
        <ReportBlockRenderer
          :blocks="column"
          :align-scores-with-table="gridPairsScoresWithTable(block)"
          :donut-labels="gridDonutLabels(block)"
        />
      </NGridItem>
    </NGrid>

    <NSpace v-else-if="block.type === 'scale'" vertical :size="12">
      <NProgress
        type="line"
        :percentage="blockNumber(block, 'position')"
        :height="10"
        :show-indicator="false"
      />
      <NSpace justify="space-between" :wrap="true">
        <NTag
          v-for="stop in blockObjects(block, 'stops')"
          :key="itemString(stop, 'label')"
          :type="itemBoolean(stop, 'active') ? 'info' : 'default'"
          :bordered="false"
        >
          {{ itemString(stop, "label") }}
        </NTag>
      </NSpace>
    </NSpace>

    <ScenarioBarChart
      v-else-if="block.type === 'scenario_bars'"
      :items="
        blockObjects(block, 'items').map((item) => ({
          label: itemString(item, 'label'),
          height: itemNumber(item, 'height'),
          highlight: itemBoolean(item, 'highlight'),
        }))
      "
    />

    <RangePositionChart
      v-else-if="block.type === 'range_bar'"
      :fill-left="blockNumber(block, 'fill_left')"
      :fill-width="blockNumber(block, 'fill_width')"
      :pin-left="blockNumber(block, 'pin_left')"
      :pin-label="blockText(block, 'pin_label')"
      :axis="(block.axis as string[] | undefined) ?? []"
      :scenarios="
        blockObjects(block, 'scenarios').map((item) => ({
          label: itemString(item, 'label'),
          highlight: itemBoolean(item, 'highlight'),
        }))
      "
      :explanation="blockText(block, 'scenario_explanation')"
    />

    <ReturnStackChart
      v-else-if="block.type === 'return_stack'"
      :items="
        blockObjects(block, 'items').map((item) => ({
          label: itemString(item, 'label'),
          width: itemNumber(item, 'width'),
          color: itemString(item, 'color') || '#80c7ff',
        }))
      "
    />

    <NGrid
      v-else-if="block.type === 'risk_cards'"
      responsive="screen"
      cols="1 m:2"
      :x-gap="16"
      :y-gap="16"
    >
      <NGridItem v-for="risk in blockObjects(block, 'items')" :key="itemString(risk, 'title')">
        <NCard size="small">
          <NSpace vertical :size="10">
            <NSpace align="center" justify="space-between">
              <NText strong>{{ itemString(risk, "title") }}</NText>
              <NTag :type="riskType(itemString(risk, 'level'))" size="small" :bordered="false">
                {{ itemString(risk, "probability") }}
              </NTag>
            </NSpace>
            <NText depth="2">{{ itemString(risk, "body") }}</NText>
            <NAlert v-if="itemString(risk, 'mitigation')" type="success" :bordered="false">
              {{ itemString(risk, "mitigation") }}
            </NAlert>
          </NSpace>
        </NCard>
      </NGridItem>
    </NGrid>

    <PositionTierChart
      v-else-if="block.type === 'steps'"
      :items="
        blockObjects(block, 'items').map((item) => ({
          title: itemString(item, 'title'),
          body: itemString(item, 'body'),
          active: itemBoolean(item, 'active'),
        }))
      "
    />

    <PremiumDonutChart
      v-else-if="block.type === 'donut'"
      :value="blockText(block, 'center_value') || blockText(block, 'value')"
      :label="blockText(block, 'center_label') || blockText(block, 'label')"
      :background="blockText(block, 'background')"
      :context="blockText(block, 'context')"
      :labels="donutLabels"
    />

    <NGrid
      v-else-if="block.type === 'position_block'"
      responsive="screen"
      cols="1 m:2"
      :x-gap="20"
      :y-gap="16"
    >
      <NGridItem>
        <NProgress
          type="circle"
          :percentage="blockNumber(block, 'percentage')"
          :stroke-width="10"
        >
          <NText strong>{{ blockText(block, "center_value") || blockText(block, "value") }}</NText>
          <br />
          <NText depth="3">{{ blockText(block, "center_label") || blockText(block, "label") }}</NText>
        </NProgress>
      </NGridItem>
      <NGridItem>
        <NSpace vertical :size="10">
          <NTag v-if="blockText(block, 'action')" type="info" :bordered="false">
            {{ blockText(block, "action") }}
          </NTag>
          <NText
            v-for="note in (block.notes as string[] | undefined) ?? []"
            :key="note"
            depth="2"
            style="white-space: pre-line; line-height: 1.75"
          >
            {{ note }}
          </NText>
        </NSpace>
      </NGridItem>
    </NGrid>

    <ReportBlockRenderer v-else-if="block.type === 'group'" :blocks="blockNestedBlocks(block)" />
    </template>
  </NSpace>
</template>
