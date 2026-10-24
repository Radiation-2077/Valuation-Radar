<script setup lang="ts">
import {
  NAlert,
  NCard,
  NEllipsis,
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
import BulletList from "@/components/BulletList.vue";
import FormulaBlock from "@/components/FormulaBlock.vue";
import IndustryCycleChart from "@/components/IndustryCycleChart.vue";
import IndustryLifecycleChart from "@/components/IndustryLifecycleChart.vue";
import MetricGauge from "@/components/MetricGauge.vue";
import PositionTierChart from "@/components/PositionTierChart.vue";
import PremiumDonutChart from "@/components/PremiumDonutChart.vue";
import RangePositionChart from "@/components/RangePositionChart.vue";
import RichText from "@/components/RichText.vue";
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
  tableColumnRoles,
  tableHeaders,
  tableRows,
} from "@/lib/report-detail";
import { triggerTypeLabel } from "@/lib/position-tiers";
import { formatPercent } from "@/lib/format";

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

function scoreText(item: Record<string, unknown>): string {
  const value = item.score;
  return typeof value === "number" ? value.toFixed(1) : itemString(item, "score") || "—";
}

function scoreWidth(item: Record<string, unknown>): number {
  const width = itemNumber(item, "width");
  if (width > 0) return width;
  const score = Number(item.score);
  return Number.isFinite(score) ? Math.max(0, Math.min(100, score * 10)) : 0;
}

function gaugeValue(item: Record<string, unknown>): number | null {
  const value = item.value;
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number.parseFloat(value.replace("%", ""));
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function gaugeDisplay(item: Record<string, unknown>): string {
  const display = itemString(item, "display_value");
  if (display.endsWith("%")) {
    const parsed = Number.parseFloat(display.replace("%", ""));
    if (Number.isFinite(parsed)) return formatPercent(parsed);
  }
  if (display) return display;
  const value = gaugeValue(item);
  return value === null ? "暂无数据" : formatPercent(value);
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

function numberValue(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function currencySymbol(currency: unknown): string {
  if (currency === "HKD") return "HK$";
  if (currency === "USD") return "$";
  return "¥";
}

function priceText(value: unknown, currency: unknown): string {
  const number = numberValue(value);
  if (number === null) return "—";
  return `${currencySymbol(currency)}${number.toLocaleString("zh-CN", {
    maximumFractionDigits: 2,
  })}`;
}

function rangeChartProps(block: ReportDetailBlock): {
  fillLeft: number;
  fillWidth: number;
  pinLeft: number;
  pinLabel: string;
  axis: string[];
  scenarios: Array<{ label: string; highlight: boolean }>;
  explanation: string;
} {
  const min = blockNumber(block, "min");
  const max = blockNumber(block, "max");
  const low = blockNumber(block, "fair_low");
  const high = blockNumber(block, "fair_high");
  const current = blockNumber(block, "current_price");
  const span = max - min || 1;
  const percentage = (value: number) =>
    Math.max(0, Math.min(100, ((value - min) / span) * 100));
  const currency = block.currency;
  return {
    fillLeft: percentage(low),
    fillWidth: percentage(high) - percentage(low),
    pinLeft: percentage(current),
    pinLabel: `现价 ${priceText(current, currency)}`,
    axis: [min, low, high, max].map((value) => priceText(value, currency)),
    scenarios: blockObjects(block, "scenarios").map((item) => ({
      label: `${itemString(item, "label")} ${priceText(item.price, currency)}`,
      highlight: itemString(item, "key") === "base",
    })),
    explanation: blockText(block, "scenario_explanation"),
  };
}

function scenarioBarProps(block: ReportDetailBlock): Array<{
  label: string;
  height: number;
  highlight: boolean;
}> {
  const items = blockObjects(block, "items");
  if ("height" in (items[0] ?? {})) {
    return items.map((item) => ({
      label: itemString(item, "label"),
      height: itemNumber(item, "height"),
      highlight: itemBoolean(item, "highlight"),
    }));
  }
  return items.map((item, index) => ({
    label: `${itemString(item, "label")} ${priceText(item.price, block.currency)}`,
    height: 55 + index * 22,
    highlight: itemString(item, "key") === "base",
  }));
}

function positionTierProps(block: ReportDetailBlock): Array<{
  title: string;
  body: string;
  active: boolean;
  triggerType?: string;
  condition?: string;
}> {
  return blockObjects(block, "items").map((item, index) => {
    const legacyTitle = itemString(item, "title");
    if (legacyTitle) {
      return {
        title: legacyTitle,
        body: itemString(item, "body"),
        active: itemBoolean(item, "active"),
      };
    }
    return {
      title: `第 ${itemNumber(item, "level") || index + 1} 档 · ${triggerTypeLabel(itemString(item, "trigger_type"))} · ${priceText(item.price, block.currency)}`,
      body: `${itemString(item, "condition")} · 计划买入 ${formatPercent(itemNumber(item, "allocation_pct"))}${itemBoolean(item, "active") ? " · 当前执行" : ""}`,
      active: itemBoolean(item, "active"),
      triggerType: itemString(item, "trigger_type"),
      condition: itemString(item, "condition"),
    };
  });
}

function returnStackProps(block: ReportDetailBlock): Array<{
  label: string;
  width: number;
  color: string;
  valuePct?: number;
}> {
  const items = blockObjects(block, "items");
  const legacy = items.some((item) => numberValue(item.width) !== null);
  if (legacy) {
    return items.map((item) => ({
      label: itemString(item, "label"),
      width: itemNumber(item, "width"),
      color: itemString(item, "color") || "#80c7ff",
    }));
  }
  const absoluteTotal = items.reduce(
    (sum, item) => sum + Math.abs(numberValue(item.value_pct) ?? 0),
    0,
  ) || 1;
  const colors: Record<string, string> = {
    dividend: "#57d6b1",
    growth: "#80c7ff",
    valuation: "#e8b86d",
    fx: "#b8a1ff",
  };
  return items.map((item) => {
    const value = numberValue(item.value_pct) ?? 0;
    return {
      label: `${itemString(item, "label")} ${value >= 0 ? "+" : ""}${formatPercent(value)}`,
      width: (Math.abs(value) / absoluteTotal) * 100,
      color: colors[itemString(item, "source")] ?? "#80c7ff",
      valuePct: value,
    };
  });
}

function premiumDonutProps(block: ReportDetailBlock): {
  value: string;
  comparisonValue?: string;
  label: string;
  background: string;
  context: string;
  labels: string[];
} {
  const items = blockObjects(block, "items");
  const colors: Record<string, string> = {
    blue: "#80c7ff",
    gold: "#e8b86d",
    green: "#57d6b1",
    red: "#ee8c78",
  };
  let start = 0;
  const stops = items.map((item) => {
    const share = numberValue(item.share_pct) ?? 0;
    const end = Math.min(100, start + share);
    const stop = `${colors[itemString(item, "tone")] ?? "#80c7ff"} ${start}% ${end}%`;
    start = end;
    return stop;
  });
  const pair = Array.isArray(block.market_pair) ? block.market_pair.join("/") : "A/H";
  const total = numberValue(block.total_premium_pct);
  const actual = items.find((item) => itemString(item, "label").includes("残余"));
  const actualValue = actual ? numberValue(actual.contribution_pct) : null;
  return {
    value: total === null ? "—" : `${total > 0 ? "+" : ""}${formatPercent(total)}`,
    comparisonValue:
      actualValue === null
        ? undefined
        : `${actualValue > 0 ? "+" : ""}${formatPercent(actualValue)}`,
    label: `${pair} 名义溢价`,
    background: `conic-gradient(${stops.join(",")})`,
    context: items.map((item) => itemString(item, "label")).join(" / "),
    labels: items.map((item) => itemString(item, "label")),
  };
}

function riskLevel(risk: Record<string, unknown>): string {
  const severity = itemString(risk, "severity");
  if (severity === "high") return "h";
  if (severity === "medium") return "m";
  if (severity === "low") return "l";
  return itemString(risk, "level");
}

function riskLabel(risk: Record<string, unknown>): string {
  const severity = itemString(risk, "severity");
  if (severity === "high") return "高";
  if (severity === "medium") return "中";
  if (severity === "low") return "低";
  return itemString(risk, "probability");
}
</script>

<template>
  <NSpace class="report-block-stack" vertical :size="20">
    <template v-for="(block, index) in blocks" :key="`${block.type}-${index}`">
    <NH3 v-if="block.type === 'heading'">
      <RichText :text="blockText(block)" />
    </NH3>

    <NText
      v-else-if="block.type === 'paragraph'"
      :depth="block.note ? 3 : 2"
      style="white-space: pre-line; line-height: 1.8"
    >
      <RichText :text="cleanReportNarrative(blockText(block))" />
    </NText>

    <NAlert
      v-else-if="block.type === 'callout'"
      :type="calloutType(blockText(block, 'tone'))"
      :bordered="false"
    >
      <template #header>
        <RichText :text="cleanReportNarrative(blockText(block, 'title'))" />
      </template>
      <span style="white-space: pre-line">
        <RichText :text="cleanReportNarrative(blockText(block, 'body'))" />
      </span>
    </NAlert>

    <FormulaBlock
      v-else-if="block.type === 'formula'"
      :block="block"
    />

    <BulletList
      v-else-if="block.type === 'bullets'"
      :block="block"
    />

    <div
      v-else-if="block.type === 'table'"
      :class="['table-shell', { 'table-shell--quality': alignScoresWithTable }]"
    >
      <NTable size="small" :bordered="false" :single-line="false">
        <NThead
          v-if="
            tableHeaders(block, Boolean(alignScoresWithTable)).length &&
            !alignScoresWithTable
          "
        >
          <NTr>
            <NTh
              v-for="(header, headerIndex) in tableHeaders(
                block,
                Boolean(alignScoresWithTable),
              )"
              :key="header"
              :class="`table-cell--${tableColumnRoles(block, Boolean(alignScoresWithTable))[headerIndex] || 'note'}`"
            >
              {{ header }}
            </NTh>
          </NTr>
        </NThead>
        <NTbody>
          <NTr
            v-for="(row, rowIndex) in tableRows(
              block,
              Boolean(alignScoresWithTable),
            )"
            :key="rowIndex"
          >
            <NTd
              v-for="(cell, cellIndex) in row"
              :key="cellIndex"
              :class="`table-cell--${tableColumnRoles(block, Boolean(alignScoresWithTable))[cellIndex] || 'note'}`"
            >
              <NEllipsis v-if="alignScoresWithTable" :line-clamp="1" tooltip>
                <RichText :text="cell" />
              </NEllipsis>
              <RichText v-else :text="cell" />
            </NTd>
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
          :percentage="scoreWidth(item)"
          :height="7"
          :show-indicator="false"
          :color="itemString(item, 'tone') === 'negative' ? '#e8b86d' : '#57d6b1'"
        />
        <strong>{{ scoreText(item) }}</strong>
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
          :value="gaugeValue(item)"
          :display-value="gaugeDisplay(item)"
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
            <NText strong style="font-size: 18px">
              {{ itemString(item, "value") || "暂无数据" }}
            </NText>
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

    <IndustryLifecycleChart
      v-else-if="block.type === 'industry_lifecycle'"
      :stage="blockText(block, 'stage')"
    />

    <IndustryCycleChart
      v-else-if="block.type === 'industry_cycle'"
      :position="blockNumber(block, 'position')"
      :phase="blockText(block, 'phase')"
      :direction="blockText(block, 'direction')"
    />

    <ScenarioBarChart
      v-else-if="['scenario_bars', 'valuation_scenarios'].includes(block.type)"
      :items="scenarioBarProps(block)"
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

    <RangePositionChart
      v-else-if="block.type === 'range_position'"
      v-bind="rangeChartProps(block)"
    />

    <ReturnStackChart
      v-else-if="block.type === 'return_stack'"
      :items="returnStackProps(block)"
    />

    <NGrid
      v-else-if="block.type === 'risk_cards'"
      class="risk-card-grid"
      responsive="screen"
      cols="1 m:2"
      :x-gap="16"
      :y-gap="16"
    >
      <NGridItem v-for="risk in blockObjects(block, 'items')" :key="itemString(risk, 'title')">
        <NCard class="risk-card" size="small">
          <NSpace class="risk-card-content" vertical :size="10">
            <NSpace align="center" justify="space-between">
              <NText strong>{{ itemString(risk, "title") }}</NText>
              <NTag :type="riskType(riskLevel(risk))" size="small" :bordered="false">
                {{ riskLabel(risk) }}
              </NTag>
            </NSpace>
            <NText depth="2">{{ itemString(risk, "body") }}</NText>
            <NAlert
              v-if="itemString(risk, 'mitigation')"
              class="risk-mitigation"
              type="success"
              :bordered="false"
            >
              {{ itemString(risk, "mitigation") }}
            </NAlert>
          </NSpace>
        </NCard>
      </NGridItem>
    </NGrid>

    <PositionTierChart
      v-else-if="['steps', 'position_tiers'].includes(block.type)"
      :items="positionTierProps(block)"
    />

    <PremiumDonutChart
      v-else-if="block.type === 'donut'"
      :value="blockText(block, 'center_value') || blockText(block, 'value')"
      :label="blockText(block, 'center_label') || blockText(block, 'label')"
      :background="blockText(block, 'background')"
      :context="blockText(block, 'context')"
      :labels="donutLabels"
    />

    <PremiumDonutChart
      v-else-if="block.type === 'premium_donut'"
      v-bind="premiumDonutProps(block)"
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
