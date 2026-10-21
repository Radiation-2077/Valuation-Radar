<script setup lang="ts">
import {
  NGrid,
  NGridItem,
  NH3,
  NProgress,
  NSpace,
  NTable,
  NTbody,
  NTd,
  NTh,
  NThead,
  NTr,
} from "naive-ui";
import { computed } from "vue";

import type { ReportDetailBlock } from "@/api/types";
import {
  blockNumber,
  blockObjects,
  objectNumber,
  objectText,
} from "@/lib/report-detail";

const props = defineProps<{
  block: ReportDetailBlock;
}>();

const dimensions = computed(() => blockObjects(props.block, "dimensions"));
const scaleMax = computed(() => blockNumber(props.block, "scale_max") || 10);
const tableRows = computed(() =>
  dimensions.value.map((dimension) => [
    objectText(dimension, "indicator"),
    objectText(dimension, "value"),
    objectText(dimension, "assessment"),
  ]),
);

function scorePercent(dimension: Record<string, unknown>): number {
  const score = objectNumber(dimension, "score");
  return Math.max(0, Math.min(100, (score / scaleMax.value) * 100));
}

function scoreLabel(dimension: Record<string, unknown>): string {
  const score = objectNumber(dimension, "score");
  const formatted = Number.isInteger(score) ? String(score) : score.toFixed(1);
  return `${formatted} / ${scaleMax.value}`;
}
</script>

<template>
  <NGrid responsive="screen" cols="1 l:2" :x-gap="32" :y-gap="20">
    <NGridItem>
      <NSpace vertical :size="16">
        <NH3>质量分项（0–{{ scaleMax }}）</NH3>
        <div
          v-for="dimension in dimensions"
          :key="objectText(dimension, 'key')"
          class="score-row"
        >
          <span>{{ objectText(dimension, "label") }}</span>
          <NProgress
            type="line"
            :percentage="scorePercent(dimension)"
            :height="7"
            :show-indicator="false"
          />
          <strong>{{ scoreLabel(dimension) }}</strong>
        </div>
      </NSpace>
    </NGridItem>
    <NGridItem>
      <NSpace vertical :size="16">
        <NH3>关键指标</NH3>
        <div class="table-shell">
          <NTable size="small" :bordered="false" :single-line="false">
            <NThead>
              <NTr>
                <NTh>维度</NTh>
                <NTh>结果</NTh>
                <NTh>评价</NTh>
              </NTr>
            </NThead>
            <NTbody>
              <NTr v-for="(row, index) in tableRows" :key="index">
                <NTd>{{ row[0] }}</NTd>
                <NTd>{{ row[1] }}</NTd>
                <NTd>{{ row[2] }}</NTd>
              </NTr>
            </NTbody>
          </NTable>
        </div>
      </NSpace>
    </NGridItem>
  </NGrid>
</template>
