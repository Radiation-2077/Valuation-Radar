<script setup lang="ts">
import type { Freshness } from "@/api/types";
import { formatDate, formatDateTime } from "@/lib/format";

defineProps<{
  freshness: Freshness;
  counts: Record<string, number>;
}>();
</script>

<template>
  <section class="freshness-bar" aria-label="数据状态">
    <div class="freshness-primary">
      <span class="pulse" :class="`pulse--${freshness.status}`" aria-hidden="true"></span>
      <div>
        <small>排名计算</small>
        <strong>{{ formatDateTime(freshness.ranking_as_of) }}</strong>
      </div>
    </div>
    <div class="freshness-item">
      <small>最新估值</small>
      <strong>{{ formatDate(freshness.latest_analysis_date) }}</strong>
    </div>
    <div class="freshness-item">
      <small>最新行情</small>
      <strong>{{ formatDate(freshness.latest_price_date) }}</strong>
    </div>
    <div class="freshness-item">
      <small>排序单元</small>
      <strong>{{ counts.all ?? 0 }}</strong>
    </div>
    <div v-if="freshness.stale_units" class="freshness-warning">
      {{ freshness.stale_units }} 条估值超过 {{ freshness.stale_after_days }} 天
    </div>
  </section>
</template>
