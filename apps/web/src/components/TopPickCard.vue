<script setup lang="ts">
import type { RankingItem } from "@/api/types";
import { formatPercent } from "@/lib/format";

defineProps<{
  item: RankingItem;
}>();

const emit = defineEmits<{
  select: [id: number];
}>();
</script>

<template>
  <button class="top-card" type="button" @click="emit('select', item.valuation_market_id)">
    <span class="top-rank">0{{ item.rank }}</span>
    <span class="band" :class="`band--${item.score.band.toLowerCase()}`">
      {{ item.score.band }}
    </span>
    <div class="top-card-heading">
      <div>
        <h3>{{ item.name }}</h3>
        <p>{{ item.market }} · {{ item.code }}</p>
      </div>
      <strong class="top-score">{{ formatPercent(item.score.total, 1).replace("%", "") }}</strong>
    </div>
    <div class="top-metrics">
      <div>
        <small>安全边际</small>
        <strong>{{ formatPercent(item.safety_margin_pct) }}</strong>
      </div>
      <div>
        <small>预期年化</small>
        <strong>{{ formatPercent(item.expected_return.total) }}</strong>
      </div>
      <div>
        <small>最大回撤</small>
        <strong>{{ formatPercent(item.max_drawdown_pct) }}</strong>
      </div>
    </div>
    <p class="top-thesis">{{ item.thesis }}</p>
    <span class="top-verdict">{{ item.verdict }}</span>
  </button>
</template>
