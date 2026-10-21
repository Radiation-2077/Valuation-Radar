<script setup lang="ts">
import { NProgress } from "naive-ui";

import type { Score } from "@/api/types";
import { formatNumber } from "@/lib/format";

defineProps<{
  score: Score;
}>();

const dimensions = [
  { key: "margin", label: "安全边际" },
  { key: "base", label: "基础收益" },
  { key: "risk", label: "抗跌性" },
  { key: "stability", label: "稳定性" },
] as const;
</script>

<template>
  <div class="score-bars">
    <div v-for="dimension in dimensions" :key="dimension.key" class="score-row">
      <span>{{ dimension.label }}</span>
      <NProgress
        type="line"
        :percentage="Math.max(0, Math.min(100, score[dimension.key] ?? 0))"
        :height="6"
        :show-indicator="false"
        color="#57d6b1"
        rail-color="rgba(158, 190, 210, 0.10)"
      />
      <strong>{{ formatNumber(score[dimension.key], 1) }}</strong>
    </div>
  </div>
</template>
