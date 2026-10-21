<script setup lang="ts">
import {
  NProgress,
  NSpace,
  NTable,
  NTbody,
  NTd,
  NText,
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
  <div class="table-shell">
    <NTable size="small" :bordered="false" :single-line="false">
      <NTbody>
        <NTr v-for="dimension in dimensions" :key="objectText(dimension, 'key')">
          <NTd>
            <NText strong>{{ objectText(dimension, "label") }}</NText>
          </NTd>
          <NTd>
            <NSpace vertical :size="4">
              <NProgress
                type="line"
                :percentage="scorePercent(dimension)"
                :height="8"
                :show-indicator="false"
              />
              <NText depth="3">{{ scoreLabel(dimension) }}</NText>
            </NSpace>
          </NTd>
          <NTd>{{ objectText(dimension, "indicator") }}</NTd>
          <NTd>{{ objectText(dimension, "value") }}</NTd>
          <NTd>{{ objectText(dimension, "assessment") }}</NTd>
        </NTr>
      </NTbody>
    </NTable>
  </div>
</template>
